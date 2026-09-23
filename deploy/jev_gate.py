"""Bounded JEV advisory and duplicate gate for the Telegram pusher.

JEV never verifies truth. The deterministic pusher remains authoritative for links, source
visibility, published age, pacing, and the final message shape. In live mode this module makes one
request per tick for at most three already-eligible candidates. Importance and freshness are stored
for audit only; a high-confidence same-event result can block a priority-4 rewrite.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

BASE_URL = (os.environ.get("JEV_BASE_URL") or "https://api.typesafe.ai").rstrip("/")
MODEL = os.environ.get("JEV_MODEL") or "jev-latest"
MODE = (os.environ.get("JEV_MODE") or "off").strip().lower()
TIMEOUT_SECONDS = int(os.environ.get("JEV_TIMEOUT_SECONDS") or 18)
DUPLICATE_THRESHOLD = float(os.environ.get("JEV_DUPLICATE_THRESHOLD") or 0.85)
BATCH_SIZE = 3

# Filter routine low-impact altcoin news before JEV duplicate review.
# Keep operator picks, priority-5 items, major assets, broad incidents, regulation, and security news.
ALT_NOTICE_FILTER = (os.environ.get("TG_ALT_NOTICE_FILTER") or "1").strip().lower() not in {
    "0", "false", "no", "off"
}
ALT_NOTICE_RE = re.compile(
    r"거래\s*(유의|주의|지원\s*종료|종료|정지|중단)|투자\s*(유의|주의)|"
    r"상장\s*(폐지|종료|유의)|입출금\s*(중단|정지|재개)|거래지원\s*(종료|중단)|"
    r"trading\s*(caution|warning|suspension|halt)|delist(?:ing)?|delisted|"
    r"listing\s*(warning|suspension)|deposit(?:s)?\s*(and\s*)?withdrawal(?:s)?\s*(suspend|halt)",
    re.I,
)
MAJOR_ASSET_RE = re.compile(r"\b(bitcoin|btc|ethereum|eth|ether)\b|비트코인|이더리움", re.I)
ALT_ASSET_RE = re.compile(
    r"\b(solana|sol|xrp|ripple|dogecoin|doge|cardano|ada|zcash|zec|sei|pepe|toncoin|"
    r"avalanche|avax|shiba|bonk|chainlink|polygon|matic|arbitrum|aptos|sui|"
    r"litecoin|ltc|tron|trx|stellar|xlm|injective|polkadot|dot|cosmos|atom|"
    r"filecoin|uniswap|aave|lido|jupiter|worldcoin|ondo|hyperliquid|bittensor|celestia|"
    r"kaspa|render|fetch(?:\.ai)?|stargate|ethena|pendle|aerodrome|jto|pyth|sophon|soph|remittix)\b",
    re.I,
)
# These names also occur as ordinary English words. Match them only as explicit tickers or
# structured asset values, never as arbitrary substrings of titles and summaries.
EXPLICIT_ALT_TICKER_RE = re.compile(r"\$(?:NEAR|OP)\b", re.I)
EXPLICIT_ALT_ASSET_RE = re.compile(r"^(?:NEAR|OP)$", re.I)
BROAD_NOTICE_RE = re.compile(
    r"거래소\s*(전체|전반)|(?:전|전체)\s*종목|시장\s*전체|전체\s*(자산|마켓|시장)|해킹|보안\s*사고|금융\s*당국|규제|법원|"
    r"exchange[- ]wide|all\s+(assets|markets)|hack|security\s+incident|regulator|court",
    re.I,
)


class JEVError(RuntimeError):
    """The batch could not produce a complete, trusted decision set."""


@dataclass(frozen=True)
class Decision:
    link: str
    importance: str
    duplicate_confidence: float
    freshness: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class Batch:
    run_id: str
    decisions: dict[str, Decision]
    raw: dict[str, Any]
    fallback: bool = False
    error: str = ""


def enabled() -> bool:
    return MODE in {"live", "shadow"} and bool(os.environ.get("JEV_API_KEY"))


def is_single_alt_notice(item: dict[str, Any]) -> bool:
    """Return true for routine news about low-impact altcoins."""
    if not ALT_NOTICE_FILTER:
        return False
    if bool(item.get("channel_pick")) or int(item.get("priority") or 0) >= 5:
        return False
    text = " ".join(str(item.get(key) or "") for key in ("title", "summary", "asset"))
    if BROAD_NOTICE_RE.search(text):
        return False
    asset = str(item.get("asset") or "").strip()
    # A major-market mention must win over a secondary ticker elsewhere in a mixed headline.
    if MAJOR_ASSET_RE.search(asset) or MAJOR_ASSET_RE.search(text):
        return False
    if EXPLICIT_ALT_ASSET_RE.fullmatch(asset) or EXPLICIT_ALT_TICKER_RE.search(text):
        return True
    if ALT_ASSET_RE.search(text):
        return True
    if ALT_NOTICE_RE.search(text):
        return True
    category = str(item.get("category") or "")
    categories = " ".join(str(value) for value in (item.get("categories") or []))
    is_alt_category = bool(re.search(r"이더리움\s*[·/]\s*알트|altcoin|alt", category + " " + categories, re.I))
    return is_alt_category and bool(asset or re.search(r"코인|토큰|coin|token", text, re.I))


def filter_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop routine single-altcoin notices before sending them to JEV."""
    return [item for item in items if not is_single_alt_notice(item)]


def _question_id(index: int, field: str) -> str:
    return "item_%d_%s" % (index, field)


def build_payload(items: list[dict[str, Any]], recent_titles: list[str], now: datetime) -> dict[str, Any]:
    questions: dict[str, dict[str, Any]] = {}
    lines = [
        "Current UTC time: %s" % now.isoformat(),
        "Return typed decisions only. Do not judge truth or invent facts.",
        "Recent channel headlines used only for same-event comparison:",
    ]
    for index, title in enumerate(recent_titles[:20], start=1):
        lines.append("R%d: %s" % (index, title))
    lines.append("Candidate headlines:")
    for index, item in enumerate(items, start=1):
        age = item.get("_age_minutes")
        lines.append(
            "C%d link=%s source=%s published=%s age_minutes=%s title=%s summary=%s"
            % (
                index,
                item.get("link", ""),
                item.get("source", ""),
                item.get("published_at", ""),
                "%.1f" % age if isinstance(age, (float, int)) else "unknown",
                item.get("title", ""),
                str(item.get("summary", ""))[:500],
            )
        )
        questions[_question_id(index, "importance")] = {
            "type": "choice",
            "instructions": "Rate importance for a Korean macro and bitcoin channel.",
            "criteria": {
                "low": "noise, SEO, routine or weakly relevant coverage",
                "medium": "useful ordinary coverage of the channel topics",
                "high": "market-moving, policy-changing or materially actionable news",
            },
        }
        questions[_question_id(index, "duplicate")] = {
            "type": "noul",
            "instructions": "Return the likelihood from 0 to 1 that this candidate is the same event as any recent channel headline R1-R20.",
        }
        questions[_question_id(index, "freshness")] = {
            "type": "choice",
            "instructions": "Classify freshness from the supplied published time and current time.",
            "criteria": {
                "fresh": "published within 30 minutes",
                "aging": "published within 90 minutes",
                "stale": "older than 90 minutes",
            },
        }
    return {
        "model": MODEL,
        "state": "\n".join(lines),
        "questions": questions,
    }


def _call(payload: dict[str, Any]) -> dict[str, Any]:
    key = os.environ.get("JEV_API_KEY", "").strip()
    if not key:
        raise JEVError("JEV_API_KEY is not set")
    request = urllib.request.Request(
        BASE_URL + "/v1/systemone",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise JEVError("HTTP %s" % exc.code) from exc
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        raise JEVError(str(exc)[:160]) from exc


def _parse(raw: dict[str, Any], items: list[dict[str, Any]], run_id: str) -> dict[str, Decision]:
    answers = raw.get("answers")
    if not isinstance(answers, dict):
        raise JEVError("missing answers")
    decisions: dict[str, Decision] = {}
    for index, item in enumerate(items, start=1):
        importance = answers.get(_question_id(index, "importance"), {})
        duplicate = answers.get(_question_id(index, "duplicate"), {})
        freshness = answers.get(_question_id(index, "freshness"), {})
        if not isinstance(importance, dict) or not isinstance(duplicate, dict) or not isinstance(freshness, dict):
            raise JEVError("malformed answer for item %d" % index)
        importance_choice = importance.get("choice")
        freshness_choice = freshness.get("choice")
        confidence_raw = duplicate.get("noul")
        if importance_choice not in {"low", "medium", "high"}:
            raise JEVError("invalid importance for item %d" % index)
        if freshness_choice not in {"fresh", "aging", "stale"}:
            raise JEVError("invalid freshness for item %d" % index)
        if confidence_raw is None:
            raise JEVError("missing duplicate confidence for item %d" % index)
        try:
            confidence = float(str(confidence_raw))
        except (TypeError, ValueError) as exc:
            raise JEVError("invalid duplicate confidence for item %d" % index) from exc
        if not 0.0 <= confidence <= 1.0:
            raise JEVError("duplicate confidence out of range for item %d" % index)
        link = str(item.get("link") or "")
        decisions[link] = Decision(
            link=link,
            importance=importance_choice,
            duplicate_confidence=confidence,
            freshness=freshness_choice,
            raw={
                "run_id": run_id,
                "importance": importance,
                "duplicate": duplicate,
                "freshness": freshness,
            },
        )
    return decisions


def evaluate(items: list[dict[str, Any]], recent_titles: list[str], now: datetime) -> Batch:
    """Evaluate a bounded batch; return deterministic fallback on every JEV failure."""
    run_id = uuid.uuid4().hex
    if not items:
        return Batch(run_id=run_id, decisions={}, raw={})
    items = filter_items(items)
    if not items:
        return Batch(run_id=run_id, decisions={}, raw={}, fallback=False, error="all candidates filtered")
    if MODE == "off":
        return Batch(run_id=run_id, decisions={}, raw={}, fallback=True, error="disabled")
    if not os.environ.get("JEV_API_KEY"):
        return Batch(run_id=run_id, decisions={}, raw={}, fallback=True, error="missing key")
    try:
        payload = build_payload(items[:BATCH_SIZE], recent_titles, now)
        raw = _call(payload)
        return Batch(run_id=run_id, decisions=_parse(raw, items[:BATCH_SIZE], run_id), raw=raw)
    except JEVError as exc:
        return Batch(run_id=run_id, decisions={}, raw={}, fallback=True, error=str(exc))


def should_block_duplicate(decision: Decision, priority: int, picked: bool) -> bool:
    """Only high-confidence JEV duplicate results can block ordinary priority-4 posts."""
    if picked or priority >= 5:
        return False
    return decision.duplicate_confidence >= DUPLICATE_THRESHOLD
