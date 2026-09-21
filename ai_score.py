"""Score article importance with a language model, on top of the rule score.

Not wired into the pipeline yet: the plan is to validate the model's judgement against a
hand-labelled sample first, and the account key is not registered. Run `--dry` to see the
batches and the token estimate without calling anything.

Design constraints, from the measurement that preceded it:

* The rule score stays authoritative in `priority`; the model's opinion lands in a
  separate `ai_priority` column so it can be compared, ignored, or reverted without
  touching the rules. Nothing reads it until the display is changed, deliberately.
* The input is the **title only**. Summaries would multiply input tokens by ~2.8x, and
  about a tenth of articles have none.
* The output is one number per article. A reason string would double output tokens and
  nothing in the UI reads it.
* A failed call changes nothing: the rule score is the fallback, so a rate limit must not
  blank a card's stars.

Environment (all optional; without the first two the module is a no-op):

    AI_SCORE_BASE_URL   OpenAI-compatible base, e.g. https://api.example.com/v1
    AI_SCORE_API_KEY    key for that endpoint
    AI_SCORE_MODEL      model id

Usage:
    python ai_score.py --dry              show batches and token estimate
    python ai_score.py --limit 30         score 30 pending articles
    python ai_score.py --dry --stock 30   build a dry run over N articles for labelling
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE / "news.db"
BATCH = 100
WINDOW_HOURS = 24

# Fixed so the prefix can be cached by the provider: the cached part is billed at a
# fraction of the normal input rate, and it is the only part that repeats every call.
RUBRIC = (
    "You score news headlines for one reader: a Korean resident of Bangkok who trades "
    "bitcoin and follows US rates, dollar and macro. Reply with one line per item, "
    "\"<id>:<score>\", score 1-5 where 5 is something that moves markets or changes what "
    "the reader must do today, 3 is ordinary coverage of the topics they follow, and 1 is "
    "noise, listicles, SEO filler and press-release boilerplate. Judge importance and "
    "relevance to that reader only. Do not judge whether the claim is true. No prose, no "
    "explanations, no blank lines."
)


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB, timeout=15)
    connection.row_factory = sqlite3.Row
    return connection


def ensure_column(connection: sqlite3.Connection) -> None:
    """Add the overlay column once. The rule score in `priority` is never overwritten."""
    columns = {row[1] for row in connection.execute("PRAGMA table_info(articles)")}
    if "ai_priority" not in columns:
        connection.execute("ALTER TABLE articles ADD COLUMN ai_priority INTEGER")
        connection.commit()
        print("added column ai_priority")


def pending(connection: sqlite3.Connection, limit: int | None) -> list[sqlite3.Row]:
    """Articles in the window that no model run has scored yet, newest first.

    A story an operator rule caught is left out: it is already off every page, so scoring it would
    spend tokens on something no reader will see. The rule is joined in rather than trusted, so a
    rule that was switched off cannot keep costing anything.
    """
    rows = connection.execute(
        "SELECT link, title, source, priority FROM articles "
        "WHERE ai_priority IS NULL AND published_at >= datetime('now', ?) "
        "AND link NOT IN (SELECT h.link FROM filter_hits h JOIN filter_rules r ON r.id = h.rule_id "
        "                 WHERE r.enabled = 1 AND h.link NOT IN (SELECT link FROM filter_keeps)) "
        "ORDER BY published_at DESC",
        ("-%d hours" % WINDOW_HOURS,),
    ).fetchall()
    return rows[:limit] if limit else rows


URL = re.compile(r"https?://\S+|\b[\w-]+\.(?:com|net|org|co|io|kr|uk|rs|me|ly|gov|ai|news)\S*", re.I)
TAIL = re.compile(r"\s+-\s+[^-]{2,40}$")


def clean_title(title: str, source: str) -> str:
    """Drop the publisher tail and embedded links before the title is sent.

    Same cleaning the keyword strip uses, and for the same reason: search-feed titles
    carry a " - Publisher" tail and social posts embed short links, so leaving them in
    spends tokens on a publisher name and gives the model noise to react to.
    """
    text = (title or "").strip()
    if (source or "").startswith("Google News"):
        text = TAIL.sub("", text)
    return URL.sub(" ", text).strip()


def build_batch(rows: list[sqlite3.Row]) -> tuple[str, dict[str, str]]:
    """Number the titles and keep the mapping back to the link."""
    index: dict[str, str] = {}
    lines = []
    for position, row in enumerate(rows, start=1):
        index[str(position)] = row["link"]
        lines.append("%d. %s" % (position, clean_title(row["title"], row["source"])))
    return "\n".join(lines), index


def estimate(rows: list[sqlite3.Row]) -> dict[str, float]:
    """Rough token math, so the cost of a run is known before it happens."""
    def tokens(text: str) -> float:
        korean = sum(1 for ch in text if "\uac00" <= ch <= "\ud7a3")
        return korean / 1.6 + (len(text) - korean) / 4.0

    titles = sum(tokens(row["title"] or "") for row in rows)
    calls = (len(rows) + BATCH - 1) // BATCH if rows else 0
    return {
        "articles": len(rows),
        "input_tokens": titles,
        "output_tokens": len(rows) * 5.0,
        "calls": calls,
        "rubric_tokens": tokens(RUBRIC) * calls,
    }


def ask(payload: str) -> str | None:
    """One completion request. Returns None on any failure so the caller keeps rule scores."""
    base = os.environ.get("AI_SCORE_BASE_URL")
    key = os.environ.get("AI_SCORE_API_KEY")
    model = os.environ.get("AI_SCORE_MODEL")
    if not (base and key and model):
        print("  AI_SCORE_BASE_URL / AI_SCORE_API_KEY / AI_SCORE_MODEL not set - nothing to do")
        return None
    body = json.dumps({
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": RUBRIC},
            {"role": "user", "content": payload},
        ],
    }).encode("utf-8")
    request = urllib.request.Request(
        base.rstrip("/") + "/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
        return data["choices"][0]["message"]["content"]
    except (urllib.error.URLError, KeyError, ValueError, TimeoutError) as exc:
        # Rate limits and outages are expected on a free tier; the rule score stands.
        print("  call failed, keeping rule scores (%s)" % str(exc)[:120])
        return None


def parse(text: str, index: dict[str, str]) -> dict[str, int]:
    """Read "<id>:<score>" lines, ignoring anything malformed."""
    out: dict[str, int] = {}
    for line in (text or "").splitlines():
        if ":" not in line:
            continue
        ident, _, value = line.partition(":")
        link = index.get(ident.strip())
        try:
            score = int(value.strip())
        except ValueError:
            continue
        if link and 1 <= score <= 5:
            out[link] = score
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM importance scoring (overlay on the rule score)")
    parser.add_argument("--dry", action="store_true", help="build batches and estimate only")
    parser.add_argument("--limit", type=int, default=0, help="score at most N articles")
    args = parser.parse_args()

    connection = connect()
    ensure_column(connection)
    rows = pending(connection, args.limit or None)
    print("pending: %d articles in the last %dh" % (len(rows), WINDOW_HOURS))
    if not rows:
        print("nothing to score")
        return

    stats = estimate(rows)
    print("  batches %d - input %d tok + rubric %d tok, output %d tok"
          % (stats["calls"], stats["input_tokens"], stats["rubric_tokens"], stats["output_tokens"]))
    print("  first batch preview:")
    payload, index = build_batch(rows[:BATCH])
    for line in payload.splitlines()[:3]:
        print("     " + line[:96])

    if args.dry:
        print("dry run - no request sent, no row written")
        return

    scored: dict[str, int] = {}
    for offset in range(0, len(rows), BATCH):
        chunk = rows[offset:offset + BATCH]
        payload, index = build_batch(chunk)
        answer = ask(payload)
        if answer is None:
            continue
        scored.update(parse(answer, index))

    if not scored:
        print("no scores returned - rule scores unchanged")
        return
    connection.executemany(
        "UPDATE articles SET ai_priority = ? WHERE link = ?",
        [(score, link) for link, score in scored.items()],
    )
    connection.commit()
    print("wrote ai_priority for %d articles (priority untouched)" % len(scored))


if __name__ == "__main__":
    sys.exit(main())