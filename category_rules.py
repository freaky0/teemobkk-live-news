"""Category taxonomy and multi-label matching, kept out of the collector core.

A story can belong to more than one axis - a tariff bill is both US policy and Trump - so the
matcher returns every match in priority order instead of stopping at the first one. The first
entry keeps behaving like the old single value: it is what gets stored in `category` and what
decides the importance bonus, so splitting a category does not move scores.

Order is the priority, and a term belongs to the narrowest axis that owns it:

  * `금리` absorbed the whole liquidity vocabulary. A separate `유동성` axis measured 6 rows in a
    24-hour window (0.7%), too thin for a filter chip that mostly returns two or three articles.
  * `달러·국채` was measured as a candidate and dropped for the same reason: with readable terms
    it captured 2 rows. The FX terms that used to sit in the combined category stay in `금리`.
  * Terms that are money *units* are not terms. `달러` matched "2 million 달러" in Korean
    summaries and dragged whale-liquidations into a rates axis; `treasury` alone matched
    "BTC Treasury" (a company's holdings). Both are why this table is narrow.
"""

# Terms that must match a whole word, chosen from measurement rather than taste.
#
# Substring matching stays the default: Korean and Thai have no reliable word breaks, so
# a compound like 규제법 legitimately contains 규제 and a Thai run contains its words
# joined. Latin terms are different — an unbounded hit usually means the term fired
# inside an unrelated word. Counting the enclosing words over one day showed which:
#
#   war  212 substring vs 21 whole-word: warsh(136), toward(30), warns(25), payward(16)
#   ban   92 vs  5: bank(67), banks(27), bitbank(18), banking(13)
#   sec  128 vs 44: security(27), secretary(20), second(18), sector(7)
#   repo  46 vs  4: reports(36), report(22)
#   eth  130 vs 28: whether(15), ethiopia(6), method(4)   (ethereum/ether are separate terms)
#   bill 121 vs 75: billion(66), billionaire(14)
#   gold  55 vs 39: goldman(19), golden(5)
#   rain  17 vs  8: train(7), bahrain(6), training(3), ukraine(2), brain(2)
#   fire   9 vs  4: gas-fired(4), ceasefire(4)
#   dust   7 vs  0: industry(13)          ppi 20 vs 10: shipping(5), dropping(4)
#   hospital 6 vs 1: hospitality(10)      qe   5 vs  0: base64-like feed artefacts
#
# The worst of these was not cosmetic: "warsh" was putting Fed-governor coverage into
# 지정학 instead of the rates categories.
#
# Deliberately NOT listed, because their unbounded hits are the intent:
#   fed→federal(71), institution→institutional(65), iran→iranian(26), russia→russian(15),
#   regulator→regulatory(19), law→lawsuit/lawmaker, market→polymarket, etf→etfflows
BOUNDARY_TERMS = {
    "war", "ban", "sec", "repo", "bill", "gold", "rain", "fire", "travel",
    "dust", "ppi", "qe", "defi", "hospital", "eth", "ether",
}

GLOBAL_RULES: list[tuple[str, list[str]]] = [
    # The vocabulary is exactly the list the combined category carried, so the split on its own
    # moves no score: a story that used to land in the combined rule still lands first in 금리.
    # Candidates that would widen it (`rate cut`, `rate hike`, `fed funds`, `역레포`, `기준금리`)
    # were measured and left out: they pull rate stories out of 거시경제 and 규제·정책, which earn
    # the impact bonus, so 111 rows would drop from 4 stars to 3. That is a separate change with
    # its own measurement, not a side effect of splitting a name.
    ("금리", ["liquidity", "repo", "reverse repo", "qt", "qe", "treasury cash", "bank reserves",
              "real yield", "interest rate", "central bank", "pboc", "ecb", "yuan", "midpoint",
              "interbank", "금리", "유동성", "국채"]),
    ("미국 정책", ["white house", "tariff", "executive order", "strategic reserve",
                   "백악관", "관세"]),
    ("트럼프", ["trump", "미국 대통령", "트럼프"]),
    ("ETF·수급", ["etf", "fund flow", "inflow", "outflow", "blackrock", "fidelity", "institutional buying"]),
    ("규제·정책", ["sec", "cftc", "regulation", "regulator", "law", "bill", "congress", "ban", "sanction", "법안", "규제", "과세", "세금", "당국"]),
    ("지정학", ["war", "iran", "israel", "ukraine", "russia", "china", "taiwan", "middle east", "geopolit", "전쟁", "중동", "지정학", "공습", "미사일", "제재"]),
    ("파생상품·청산", ["liquidation", "funding", "open interest", "options", "futures", "basis", "청산", "펀딩", "미결제약정", "선물"]),
    ("온체인·기관", ["whale", "wallet", "on-chain", "onchain", "exchange reserve", "exchange flow", "institution", "고래", "온체인", "거래소 유입", "거래소"]),
    ("스테이블코인", ["stablecoin", "usdt", "usdc", "depeg", "디페깅", "스테이블코인"]),
    ("X 발언", ["elon musk", "michael saylor", "jack dorsey", "x post", "twitter post", "x.com"]),
    ("주식·원자재", ["s&p 500", "nasdaq", "vix", "oil", "crude", "gold", "copper", "stocks", "원유", "금값", "증시", "급락", "급등"]),
    ("채굴", ["miner", "mining", "hashrate", "difficulty", "채굴", "해시레이트"]),
    ("거시경제", ["fed", "federal reserve", "inflation", "cpi", "ppi", "jobs", "yield", "dollar", "실업", "연준", "물가", "고용", "소비자"]),
    ("시장·가격", ["price", "rally", "crash", "market", "가격", "상승", "하락", "신고가", "신저가", "시가총액"]),
    ("이더리움·알트", ["ethereum", "ether", "solana", "xrp", "altcoin", "defi", "layer 2", "eth"]),
]

# Ordered by how directly it touches a resident's life.
THAI_RULES: list[tuple[str, list[str]]] = [
    ("비자·이민", ["visa", "immigration", "work permit", "residence permit", "permanent residence", "residence visa", "extension of stay", "90-day", "overstay", "visa run", "land border", "entry requirement", "비자", "이민", "체류", "워크퍼밋", "วีซ่า", "ตรวจคนเข้าเมือง", "ต่ออายุ"]),
    ("사고·재난", ["flood", "fire", "wildfire", "crash", "collision", "accident", "explosion", "earthquake", "storm", "drown", "collapse", "killed", "injured", "outbreak", "홍수", "화재", "사고", "폭발", "지진", "태풍", "붕", "사망", "부상", "น้ำท่วม", "ไฟไหม้", "อุบัติเหตุ", "แผ่นดินไหว", "พายุ", "ระเบิด"]),
    ("태국 생활", ["bts", "mrt", "skytrain", "subway", "tollway", "expressway", "traffic", "water outage", "power outage", "blackout", "electricity", "water supply", "dust", "pm2.5", "air quality", "weather", "rain", "heat", "교통", "단수", "정전", "지하철", "미세먼지", "날씨", "폭우", "고속도로", "น้ำไม่ไหล", "ไฟฟ้าดับ", "ฝุ่น", "จราจร", "อากาศ"]),
    ("태국 경제", ["baht", "thai economy", "gdp", "inflation", "set index", "bank of thailand", "bot ", "investment", "tax", "export", "tourism revenue", "minimum wage", "경제", "밧", "물가", "투자", "세금", "관세", "최저임금", "수출", "เศรษฐกิจ", "บาท", "ภาษี", "ลงทุน", "เงินเฟ้อ", "ค่าแรง"]),
    ("태국 정치·사회", ["government", "prime minister", "parliament", "senate", "election", "protest", "constitution", "court", "police", "corruption", "party", "cabinet", "정치", "정부", "총리", "의회", "선거", "시위", "경찰", "부패", "탄핵", "รัฐบาล", "นายกรัฐมนตรี", "สภา", "เลือกตั้ง", "ตำรวจ", "ทุจริต"]),
    ("태국 관광", ["tourist", "tourism", "hotel", "resort", "travel", "flight", "airport", "songkran", "full moon", "관광", "여행", "호텔", "공항", "항공", "축제", "ท่องเที่ยว", "นักท่องเที่ยว", "โรงแรม", "สนามบิน"]),
    ("태국 보건", ["hospital", "health", "dengue", "influenza", "vaccine", "disease", "clinic", "insurance", "medical", "보건", "병원", "의료", "질병", "독감", "백신", "보험", "โรงพยาบาล", "สุขภาพ", "ไข้เลือดออก", "วัคซีน", "ประกัน"]),
]

GENERIC_CATEGORY = "일반"


def term_hits(text: str, term: str) -> bool:
    """Match a category keyword: whole-word for the ambiguous ones, substring otherwise."""
    import re
    term = term.strip()
    if not term:
        return False
    if term in BOUNDARY_TERMS:
        return re.search(r"\b" + re.escape(term) + r"s?\b", text) is not None
    return term in text


def is_latin_term(term: str) -> bool:
    """True when every character is Latin/punctuation/digit - i.e. the term has word breaks.

    Korean and Thai runs have no reliable word breaks, so a boundary rule cannot be applied to
    them; a mixed term is treated as one of those, because it contains one.
    """
    return all(ord(char) < 0x2E80 for char in term)


def text_matches(text: str, needle: str) -> bool:
    """The one rule for a term the reader typed, shared by the server and the page script.

    A Latin term matches as a whole word (with the optional plural s the taxonomy already uses), so
    "AI" stops matching "said" and "Thailand". Measured: 'ai' as a plain substring matched 3,720
    rows in one window where the whole word matched 599. A Korean or Thai term stays a substring:
    their writing has no spaces between words, so a boundary test would drop real matches.

    A multi-word phrase is matched as a phrase, with boundaries only at its ends - the trend strip
    only offers a phrase when it appears joined in the title, because a clicked term that is not
    literally there returns nothing.
    """
    import re
    text = str(text or "").lower()
    needle = str(needle or "").strip().lower()
    if not needle:
        return False
    if not is_latin_term(needle):
        return needle in text
    body = re.escape(needle)
    tail = "s?" if " " not in needle else ""
    return re.search(r"(?<![a-z0-9])" + body + tail + r"(?![a-z0-9])", text) is not None


def match_all(text: str, rules: list[tuple[str, list[str]]]) -> list[str]:
    """Every matching category, in the table's priority order. Empty when nothing matches."""
    return [name for name, terms in rules if any(term_hits(text, term) for term in terms)]


def rules_for(region: str, thai_region: str) -> list[tuple[str, list[str]]]:
    return THAI_RULES if region == thai_region else GLOBAL_RULES


def valid_names() -> set[str]:
    return ({GENERIC_CATEGORY}
            | {name for name, _ in GLOBAL_RULES}
            | {name for name, _ in THAI_RULES})


def retire(name: str) -> str:
    """Map a name the table no longer offers onto the axis that replaced it.

    Renaming a combined category (유동성·금리 -> 금리, 미국 정책·트럼프 -> 미국 정책 + 트럼프) leaves
    that name behind in every row stored before the change, in a published file merged forward, and
    in any cache. A renamed name is recognised by its parts: a combined name whose words include a
    current axis belongs to that axis. Nothing is hard-coded, so the next rename is covered too, and
    an unrecognised name is left alone rather than guessed at.
    """
    name = str(name or "").strip()
    if not name or name in valid_names():
        return name
    for part in name.split("·"):
        part = part.strip()
        if part in valid_names():
            return part
    return name


def join_categories(names: list[str]) -> str:
    """Store the list in one column with commas.

    No stored category value contains a comma (checked in tests/test_categories.py), so a
    comma-joined string can be matched with a delimiter-safe LIKE instead of a substring one.
    """
    return ",".join(names)


def split_categories(stored: str | list | None, fallback: str | None = None) -> list[str]:
    """Read the column back into a list, tolerating rows written before the column existed.

    Accepts the stored comma-joined string *or* a list that has already been split. The DB layer
    hands callers a list, while a row read straight out of the table is a string, and a helper that
    accepted only the string turned the list into its own repr (a card whose chip read "['일반']"
    instead of 일반).

    Each name is passed through retire(), so a name from before a rename is normalised wherever it
    is read: a stored row, a published file merged forward, or a browser cache.
    """
    if isinstance(stored, (list, tuple)):
        names = [str(name) for name in stored if name]
    else:
        names = [part for part in str(stored or "").split(",") if part]
    if not names:
        names = [str(fallback)] if fallback else [GENERIC_CATEGORY]
    out: list[str] = []
    for name in names:
        current = retire(name)
        if current and current not in out:
            out.append(current)
    return out or [GENERIC_CATEGORY]
