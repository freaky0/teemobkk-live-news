"""숨긴 기사에서 '등록 전에 걸 규칙' 후보를 뽑는다.

운영자가 손으로 숨긴 기사는 남은 판단 신호 중 가장 정직한 것이다. 그 신호에서 되풀이되는 문구를
찾아 규칙 후보로 올린다. 후보는 꺼진 상태로 들어가고, 운영자가 무엇을 잡는지 보고 켠다.

토큰은 쓰지 않는다. 전부 문자열 계산이다 - 무료 티어도 필요 없다.

무엇을 뽑고 무엇을 뽑지 않는지 (실측으로 정한 선):
  * 되풀이되는 제목 앞머리  -> 뽑는다. 실측: "bloomberg news now" 는 숨김 5건을 전부 덮고 남은
    기사에는 같은 다이제스트 9건이 걸린다(오탐이 아니라 아직 안 숨긴 같은 기사다).
  * 숨김에만 잘 나오는 낱말 -> 뽑되 보수적으로. 숨김 2건 이상 + 그 낱말이 나온 기사의 절반 이상이
    숨김이어야 한다.
  * 주제가 다른 기사(실측 72%) -> 뽑지 않는다. 스포츠·요리·문화는 낱말 목록이 끝이 없고, 반대로
    '시장 낱말이 있어야 통과'를 걸면 실측 80%가 잘못 걸린다. 그쪽은 기사별 관련도 채점의 몫이다.
"""
from __future__ import annotations

import collections
import re

TOKEN = re.compile(r"[0-9A-Za-z']{3,}|[가-힣]{2,}")
# 구절은 낱말 단위로 자른다. 'is' 'a' 같은 짧은 말을 빼면 구절이 중첩되지 않아 한 정형 기사가
# 변형 여덟 개로 늘어난다(실측). 낱말 하나짜리 후보에만 길이 조건을 건다.
PHRASE_TOKEN = re.compile(r"[0-9A-Za-z']+|[가-힣]{2,}")

PHRASE_MIN = 3        # 구절로 인정할 최소 낱말 수 ('bloomberg news now' 처럼 꼬리표로 쓸 수 있게)
PHRASE_MAX = 8        # 최대
HIDDEN_MIN = 2        # 같은 문구가 숨김에 두 번은 나와야 '되풀이'다
LEAD = 12             # 제목 앞머리만 본다: 정형 기사의 표식이 거기 있다
WORD_HIDDEN_MIN = 3   # 낱말 후보의 최소 숨김 건수 (두 건은 한 기사가 두 경로로 들어온 것일 수 있다)
WORD_RATE = 0.5       # 그 낱말이 나온 기사의 절반 이상이 숨김이어야 한다
LIMIT = 8             # 한 번에 올릴 후보 수

# 문구에 섞여도 뜻이 없는 말. 이 말로 시작하는 구절은 꼬리표가 될 수 없다.
STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "by", "as", "is", "are", "was",
    "were", "be", "been", "for", "with", "that", "this", "these", "those", "from", "have", "has",
    "had", "will", "would", "can", "could", "should", "may", "might", "must", "you", "your",
    "they", "their", "them", "but", "not", "no", "its", "it", "his", "her", "our", "we", "how",
    "why", "what", "when", "who", "which", "while", "where", "there", "here", "new", "now", "out",
    "into", "over", "after", "before", "about", "against", "between", "during", "without",
    "within", "under", "above", "than", "then", "also", "more", "most", "one", "two", "very",
    "just", "only", "even", "still", "back", "down", "off", "all", "any", "so", "up", "do",
    "그리고", "그러나", "하지만", "이번", "오늘", "지난", "대한", "위해", "통해", "관련", "것으로",
}


def tokens(text: str) -> list[str]:
    return TOKEN.findall((text or "").lower())


def _phrase_tokens(text: str) -> list[str]:
    """구절용 낱말. 낱말에 붙은 어깨표는 떼어 낸다."""
    return [w for w in (t.strip("'") for t in PHRASE_TOKEN.findall((text or "").lower())) if w]


def _phrases(text: str) -> dict[str, int]:
    """제목 앞머리에서 만들 수 있는 낱말 묶음 -> 그 묶음이 시작한 자리(0 = 제목 맨 앞).

    시작 자리를 함께 들고 다니는 이유: 같은 숨김 묶음을 덮는 후보가 여럿일 때 제목 맨 앞에서
    시작하는 쪽이 정형 기사의 꼬리표다. 중간에서 잘린 토막("top stories hear")은 우연히 같이
    나온 말일 뿐이라 정형 기사의 뒤쪽이 조금만 달라져도 어긋난다.
    """
    words = _phrase_tokens(text)
    out: dict[str, int] = {}
    for n in range(PHRASE_MAX, PHRASE_MIN - 1, -1):
        for i in range(0, max(0, min(len(words) - n + 1, LEAD))):
            if words[i] in STOP:
                continue
            phrase = " ".join(words[i:i + n])
            if phrase not in out or i < out[phrase]:
                out[phrase] = i
    return out


def _meaningful(phrase: str) -> bool:
    """뜻 없는 말로만 이루어진 구절은 버린다."""
    return any(w not in STOP for w in phrase.split())


def derive(hidden_titles: list[str], kept_texts: list[str],
           exclude: set[str] | None = None, limit: int = LIMIT) -> list[dict]:
    """숨김과 남은 기사에서 규칙 후보를 뽑는다.

    `hidden_titles` 는 운영자가 숨긴 제목, `kept_texts` 는 아직 남아 있는 기사의 제목+요약이다.
    `exclude` 는 이미 있는 규칙(같은 문구를 두 번 올리지 않는다).
    """
    exclude = {e.strip().lower() for e in (exclude or set())}
    hidden_titles = [t for t in hidden_titles if t]
    kept_blob = "\n".join((t or "").lower() for t in kept_texts)

    # ── 되풀이되는 구절 ────────────────────────────────────────────────
    cands: dict[str, dict] = {}
    for idx, title in enumerate(hidden_titles):
        for phrase, start in _phrases(title).items():
            if not _meaningful(phrase):
                continue
            rec = cands.setdefault(phrase, {"pattern": phrase, "kind": "phrase", "hidden_hits": 0,
                                            "kept_hits": 0, "start": start, "titles": set()})
            rec["hidden_hits"] += 1
            rec["titles"].add(idx)
            rec["start"] = min(rec["start"], start)

    hits: list[dict] = []
    for rec in cands.values():
        if rec["hidden_hits"] < HIDDEN_MIN or rec["pattern"] in exclude:
            continue
        kept_n = kept_blob.count(rec["pattern"])
        # 남은 기사에 걸리는 것이 곧바로 오탐은 아니다: 되풀이되는 다이제스트가 아직 등록된 채
        # 남아 있을 수 있다(실측 9건). 흔한 말과 구별하는 것은 비율이 아니라 규모다 - 남은 기사에
        # 수십 건씩 걸리면 그건 문구가 아니라 낱말이다.
        if kept_n > max(5, rec["hidden_hits"] * 3):
            continue
        rec["kept_hits"] = kept_n
        hits.append(rec)

    # 제목 맨 앞에서 시작하고 짧은 것을 먼저 고른다. 같은 숨김 묶음을 덮는 후보는 하나만 남긴다 -
    # 안 그러면 한 정형 기사가 변형 여덟 개로 올라온다(실측).
    hits.sort(key=lambda r: (-r["hidden_hits"], r["start"], len(r["pattern"])))
    chosen: list[dict] = []
    covered: list[set[int]] = []
    for rec in hits:
        if any(rec["titles"] <= seen for seen in covered):
            continue
        chosen.append({"pattern": rec["pattern"], "kind": "phrase",
                       "hidden_hits": rec["hidden_hits"], "kept_hits": rec["kept_hits"]})
        covered.append(rec["titles"])
        if len(chosen) >= limit:
            break

    # ── 숨김에만 잘 나오는 낱말 ────────────────────────────────────────
    hid_count: collections.Counter[str] = collections.Counter()
    for title in hidden_titles:
        hid_count.update(set(tokens(title)))
    kept_count: collections.Counter[str] = collections.Counter()
    for text in kept_texts:
        kept_count.update(set(tokens(text)))

    words = []
    for word, hn in hid_count.items():
        if hn < WORD_HIDDEN_MIN or word in exclude or word in STOP or len(word) < 4:
            continue
        kn = kept_count.get(word, 0)
        if hn / float(hn + kn) < WORD_RATE:
            continue
        if any(word in c["pattern"] for c in chosen):
            continue
        words.append({"pattern": word, "kind": "word", "hidden_hits": hn, "kept_hits": kn})
    words.sort(key=lambda r: (-r["hidden_hits"], -len(r["pattern"])))

    return (chosen + words)[:limit]


def explain(cands: list[dict]) -> str:
    if not cands:
        return "아직 되풀이되는 문구가 없다 - 숨긴 기사가 쌓이면 후보가 나온다"
    return ", ".join("%s(숨김 %d)" % (c["pattern"][:28], c["hidden_hits"]) for c in cands[:4])
