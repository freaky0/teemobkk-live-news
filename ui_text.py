"""Interface strings for the dashboard, one table per language.

The pages are generated per language instead of swapping text in the browser, so the script
never has to know which language it is running in: it receives one flat dictionary and reads
keys from it. That also keeps each page single-language, which matters because a browser
decides what a page's language is from the text present when the page loads, and mixed text
leaves that judgement ambiguous.

Category names are data, not interface: they are the values stored in the database and the
value sent to /api/news. Only their display label is translated, so CATS maps the stored value
to a label and filtering keeps working in every language.
"""

from __future__ import annotations

# The two languages the pages are built in, in the order the switcher lists them.
LANGS = ("en", "ko")
LANG_LABEL = {"en": "English", "ko": "한국어"}

# Interface strings. Keys are shared; every language must define the same set (checked in
# check_tables() below, so a missing translation is a loud error rather than a blank label).
UI_EN = {
    # document
    "title": "TeemoBKK Live News",
    "titleThai": "TeemoBKK Live News · Thailand",
    "h1": "Live news dashboard",
    "metaDesc": ("Bitcoin, macro and Thailand news collected every few minutes, "
                 "with the economic calendar."),
    "ogDesc": "Bitcoin, macro and Thailand news in real time, with the indicator calendar.",
    # tabs
    "tabGlobal": "Markets",
    "tabCal": "Indicators",
    "tabThai": "Thailand",
    # header
    "connecting": "Connecting",
    "updated": "Updated",
    "themeDark": "Dark mode",
    "themeLight": "Light mode",
    "interval": "Refresh",
    "intervalAria": "Refresh interval",
    "sec10": "10s", "sec30": "30s", "min1": "1 min", "min2": "2 min", "min5": "5 min",
    # calendar
    "calHeading": "Indicators · speeches · earnings · presidential schedule",
    "calLoading": "Loading…",
    "calRetry": "Try again",
    "calFail": "Could not load the indicator data.",
    "calEmpty": "No events to show.",
    "calNone": "No major indicators",
    "calWindow": "Next 3 days",
    "calTop": "at ★4 or above",
    "calSources": "Sources: Nasdaq calendar · Federal Reserve · White House · Factba.se",
    "calTimeBasis": "Times are KST (UTC+9) · Bangkok is 2 hours behind",
    "calRoster": "Fed roster as of",
    "slotReleased": "released",
    "slotExpected": "expected",
    "actualValue": "actual",
    "slotPrevious": "previous",
    "slotEarnings": "Earnings",
    "slotPotus": "Presidential schedule",
    # toolbar
    "searchPlaceholder": "Search title, summary or source ( / )",
    "searchAria": "Search news",
    "hoursAria": "Period",
    "hours1": "Last hour", "hours6": "Last 6 hours",
    "hours12": "Last 12 hours", "hours24": "Last 24 hours",
    "hoursWeek": "Last 7 days", "hoursAll": "All Period",
    "condAdd": "+ Add condition",
    "condAddTitle": "Pin what is typed as a condition",
    "newLabel": "Show {n} new",
    "intervalFail": "Could not change the refresh interval",
    "rosterAsOf": "Fed roster as of {n}",
    "more": "More",
    "totop": "Back to top",
    # feed
    "all": "All",
    "countArchive": "archived",
    "counts": "Total <b>{n}</b>",
    "countShown": "Total <b>{n}</b>, <b>{m}</b> shown",
    "liveCount": "Showing <b>{n}</b>",
    "clearTerms": " selected ✕",
    "emptyTitle": "No stories match these filters",
    "emptyHint": "Clear the search or widen the period.",
    "loadFailTitle": "Could not load the data",
    "loadFailHint": "Refresh in a moment.",
    "stale": "Collection is behind — no new data since the time shown",
    "retrying": "Retrying",
    "connFail": "Connection failed",
    "openOriginal": "Open original",
    "expand": "Show more",
    "collapse": "Show less",
    "speakerChip": "speaker",
    "verifOfficial": "Official",
    "verifOfficialTitle": "Published by an official body",
    "verifSns": "Social",
    "verifSnsTitle": "Social or channel post — not press reporting, verify against the source",
    # time
    "timeUnknown": "time unknown",
    "secAgo": "s ago", "minAgo": "m ago", "hourAgo": "h ago",
    "bucketPrev": "Earlier",
    "bucket1h": "Last hour",
    "today": "Today", "yesterday": "Yesterday",
    # sources panel and guide
    "sideSources": "Collection",
    "sideWaiting": "Waiting",
    "srcOk": "ok", "srcFail": "failed",
    "guideGlobalH2": "What this watches",
    "guideGlobalP1": ("Rates and liquidity, the dollar and Treasuries, US policy, geopolitics, "
                      "ETF and institutional flows, derivatives, on-chain, stablecoins and "
                      "speaker remarks are collected first."),
    "guideGlobalP2": ("Facts and market interpretation are kept apart. Social posts and "
                      "breaking lines are not treated as confirmed until an official release "
                      "or the original text is checked."),
    "guideThaiH2": "Thailand",
    "guideThaiP1": ("Bangkok Post, Khaosod, Thai Enquirer and Prachatai in English; Thairath "
                    "and Matichon in Thai; Google News searches for Thailand, Bangkok and "
                    "Korean residents."),
    "guideThaiP2": ("Visa and immigration, accidents and disasters come first, and unconfirmed "
                    "lines are not stated as fact before the source is checked."),
    "trendLabel": "Trending now",
    "condLabel": "Selected conditions",
    "condNarrow": "Narrowest condition",
    "condWide": "Search a longer period",
    "condRelease": "Release this condition",
    "emptyAll": "No story matches every selected condition",
    "emptyAllHint": "Release the narrowest condition above, or search a longer period.",
    "footer1": ("Each story belongs to the outlet that published it. Only the headline, the "
                "summary and a link are shown; check the original through the link."),
    "footer2": ("Collected automatically, so wording or timing may be off. Do not use this as "
                "the basis for an investment decision."),
}

UI_KO = {
    # document
    "title": "TeemoBKK Live News",
    "titleThai": "TeemoBKK Live News · 태국 소식",
    "h1": "실시간 뉴스 대시보드",
    "metaDesc": ("비트코인·매크로·태국 뉴스를 몇 분마다 모아 보여주는 실시간 대시보드. "
                 "경제지표와 주요 일정 포함."),
    "ogDesc": "비트코인·매크로·태국 뉴스 실시간 대시보드. 경제지표·연설·실적 일정 포함.",
    # tabs
    "tabGlobal": "경제 소식",
    "tabCal": "경제 지표",
    "tabThai": "태국 소식",
    # header
    "connecting": "연결 중",
    "updated": "업데이트",
    "themeDark": "다크 모드",
    "themeLight": "일반 모드",
    "interval": "갱신",
    "intervalAria": "갱신 간격",
    "sec10": "10초", "sec30": "30초", "min1": "1분", "min2": "2분", "min5": "5분",
    # calendar
    "calHeading": "경제지표 · 연설 · 실적 · 대통령 일정",
    "calLoading": "불러오는 중…",
    "calRetry": "다시 시도",
    "calFail": "경제지표 데이터를 불러오지 못했습니다.",
    "calEmpty": "표시할 일정이 없습니다.",
    "calNone": "주요 지표 없음",
    "calWindow": "앞으로 3일 일정",
    "calTop": "중요도 ★4 이상",
    "calSources": "출처 나스닥 캘린더 · 연준 · 백악관 · Factba.se",
    "calTimeBasis": "시각 기준 KST(UTC+9) · 방콕은 여기서 2시간 뒤",
    "calRoster": "연준 인물 명단",
    "slotReleased": "발표",
    "slotExpected": "예상",
    "actualValue": "실제",
    "slotPrevious": "이전",
    "slotEarnings": "실적 발표",
    "slotPotus": "대통령 일정",
    # toolbar
    "searchPlaceholder": "제목·요약·출처 검색 ( / )",
    "searchAria": "뉴스 검색",
    "hoursAria": "기간",
    "hours1": "최근 1시간", "hours6": "최근 6시간",
    "hours12": "최근 12시간", "hours24": "최근 24시간",
    "hoursWeek": "최근 7일", "hoursAll": "전체 기간",
    "condAdd": "+ 조건 추가",
    "condAddTitle": "검색어를 조건으로 고정합니다",
    "newLabel": "새 글 {n}건 보기",
    "intervalFail": "갱신 간격 변경 실패",
    "rosterAsOf": "연준 인사 기준일 {n}",
    "more": "더 보기",
    "totop": "맨 위로",
    # feed
    "all": "전체",
    "countArchive": "보관",
    "counts": "총 <b>{n}</b>건",
    "countShown": "총 <b>{n}</b>건, <b>{m}</b>건 표시",
    "liveCount": "<b>{n}</b>건 표시 중",
    "clearTerms": "개 해제 ✕",
    "emptyTitle": "조건에 맞는 뉴스가 없습니다",
    "emptyHint": "검색어를 지우거나 기간을 넓혀 보세요.",
    "loadFailTitle": "데이터를 불러오지 못했습니다",
    "loadFailHint": "잠시 후 새로고침해 주세요.",
    "stale": "수집이 지연되고 있습니다 — 표시된 시각 이후 새 데이터가 없습니다",
    "retrying": "재시도 중",
    "connFail": "연결 실패",
    "openOriginal": "원문 열기",
    "expand": "펼쳐보기",
    "collapse": "접기",
    "speakerChip": "인물 발언",
    "verifOfficial": "공식",
    "verifOfficialTitle": "공식 기관이 직접 발표한 문서",
    "verifSns": "SNS",
    "verifSnsTitle": "소셜·채널 게시물 — 언론 보도가 아니며 원문 확인이 필요함",
    # time
    "timeUnknown": "시각 미상",
    "secAgo": "초 전", "minAgo": "분 전", "hourAgo": "시간 전",
    "bucketPrev": "그 이전",
    "bucket1h": "최근 1시간",
    "today": "오늘", "yesterday": "어제",
    # sources panel and guide
    "sideSources": "수집 상태",
    "sideWaiting": "대기 중",
    "srcOk": "정상", "srcFail": "실패",
    "guideGlobalH2": "관찰 기준",
    "guideGlobalP1": ("금리·유동성, 미국 정책·트럼프, 지정학, ETF·기관 수급, 파생상품, "
                      "온체인, 스테이블코인, X 발언을 우선 수집합니다."),
    "guideGlobalP2": ("뉴스 사실과 시장 해석을 분리합니다. X 게시물과 속보는 공식 발표나 "
                      "원문 확인 전까지 확정 사실로 취급하지 않습니다."),
    "guideThaiH2": "태국 소식",
    "guideThaiP1": ("방콕포스트·카오솟·타이인콰이어러·프라차타이(영문), 타이랏·마티촌(태국어), "
                    "구글뉴스 태국·방콕·교민 검색을 모읍니다."),
    "guideThaiP2": ("비자·이민과 사고·재난을 우선 표시하며, 확정되지 않은 속보는 원문 확인 "
                    "전까지 단정하지 않습니다."),
    "trendLabel": "지금 뜨는 키워드",
    "condLabel": "선택한 조건",
    "condNarrow": "가장 좁은 조건",
    "condWide": "더 긴 기간에서 찾기",
    "condRelease": "이 조건을 풉니다",
    "emptyAll": "선택한 조건을 모두 만족하는 뉴스가 없습니다",
    "emptyAllHint": "위 조건 줄에서 가장 좁은 조건을 풀거나 기간을 넓혀 보세요.",
    "footer1": ("각 기사의 저작권은 원 매체에 있습니다. 제목과 요약, 그리고 원문 링크만 "
                "표시하며 원문 확인은 링크를 통해 해 주세요."),
    "footer2": ("자동 수집 결과이므로 표기 오류나 지연이 있을 수 있습니다. 투자 판단의 "
                "근거로 사용하지 마세요."),
}

UI = {"en": UI_EN, "ko": UI_KO}

# Stored category value -> display label. The value is what the database holds and what the
# API filters on, so it is identical in every language; only the label changes.
CATS = {
    "global": [
        ("일반", "General"),
        ("금리", "Rates & liquidity"),
        ("미국 정책", "US policy"),
        ("트럼프", "Trump"),
        ("지정학", "Geopolitics"),
        ("ETF·수급", "ETF & flows"),
        ("파생상품·청산", "Derivatives & liquidations"),
        ("온체인·기관", "On-chain & institutions"),
        ("스테이블코인", "Stablecoins"),
        ("X 발언", "X posts"),
        ("주식·원자재", "Equities & commodities"),
        ("채굴", "Mining"),
        ("규제·정책", "Regulation & policy"),
        ("거시경제", "Macro"),
        ("시장·가격", "Market & price"),
        ("이더리움·알트", "Ethereum & alts"),
    ],
    "thai": [
        ("일반", "General"),
        ("비자·이민", "Visa & immigration"),
        ("사고·재난", "Accidents & disasters"),
        ("태국 생활", "Living, traffic & weather"),
        ("태국 경제", "Thai economy"),
        ("태국 정치·사회", "Thai politics & society"),
        ("태국 관광", "Tourism"),
        ("태국 보건", "Health"),
    ],
}

# Korean labels for the same values. The Thai categories show a shorter label than the stored
# value, which is why labels cannot simply be the value.
CAT_LABEL_KO = {
    "태국 생활": "생활·교통·날씨",
    "태국 정치·사회": "정치·사회",
    "태국 관광": "관광",
    "태국 보건": "보건",
}


def cat_labels(lang: str) -> dict[str, str]:
    """Stored category value -> label in `lang`."""
    table = {}
    for group in CATS.values():
        for value, label_en in group:
            table[value] = label_en if lang == "en" else CAT_LABEL_KO.get(value, value)
    return table


def cats(lang: str) -> dict[str, list[tuple[str, str]]]:
    """Category pills per tab, as (stored value, label) pairs."""
    table = cat_labels(lang)
    return {group: [(value, table[value]) for value, _ in values]
            for group, values in CATS.items()}


# Words dropped by the trend counter. These describe the headline text, not the interface, so
# they are the union of both languages rather than one table per language.
STOPWORDS = {
    "ko": ("그리고 그러나 또한 이번 지난 오늘 어제 내일 관련 발표 예정 가능 필요 대해 통해 "
           "위해 때문 이라 라고 이라고 있다 없다 했다 한다 된다 등등 경우 상황 내용"),
    "en": ("the and for with from that this will has have are was were its his her their "
           "says said after before about into over more than new amid as at by in of on to "
           "up out off not but you your we our they them it is be been being"),
}

# Subject words the dashboard is about, dropped from the trend strip in every language.
TOPIC_WORDS = ("bitcoin btc crypto cryptocurrency 비트코인 암호화폐 코인 thai thailand "
               "bangkok 태국 방콕 태국인 교민")

# Names that count as a "speaker" line. Matched against headline text, so the list covers both
# spellings instead of being translated.
SPEAKERS = ("트럼프", "Trump", "TRUMP", "머스크", "Musk", "MUSK", "파월", "Powell", "워시",
            "Warsh", "베센트", "Bessent", "라가르드", "Lagarde", "푸틴", "Putin", "시진핑",
            "Xi Jinping", "네타냐후", "Netanyahu", "우에다", "Ueda")


def check_tables() -> None:
    """Every language must define the same keys, or a label silently renders blank."""
    base = set(UI[LANGS[0]])
    for lang in LANGS[1:]:
        missing = base - set(UI[lang])
        extra = set(UI[lang]) - base
        if missing or extra:
            raise ValueError("ui_text: %s missing=%s extra=%s"
                             % (lang, sorted(missing), sorted(extra)))


check_tables()