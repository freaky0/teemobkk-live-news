"""Conservative, bilingual event identity for short-window news display deduplication.

Only identify a semantic duplicate when an actor, an action and its target agree.
Unknown actors/actions fall back to existing headline/link deduplication rather than
merging unrelated stories merely because they share a topic.
"""
import re
import json
from datetime import datetime, timezone

WINDOW_SECONDS = 6 * 60 * 60

# Aliases are deliberately explicit: translating every word or matching just a topic
# makes distinct announcements about the same actor disappear.
ACTORS = {
    "trump": (r"\btrump\b", "트럼프"),
    "fed": (r"\bfed(?:eral reserve)?\b", "연준", "미 연방준비제도", "연방준비제도"),
    "samsung": (r"\bsamsung\b", "삼성"),
    "bitcoin": (r"\bbitcoin\b", r"\bbtc\b", "비트코인"),
    "ethereum": (r"\bethereum\b", r"\beth\b", "이더리움"),
    "china": (r"\bchina\b", "중국"),
    "korea": (r"\b(?:south )?korea\b", "한국", "대한민국"),
    "thailand": (r"\bthailand\b", "태국"),
    "us": (r"\bu\.?s\.?\b", r"\bunited states\b", "미국"),
}
ACTIONS = {
    "impose_tariff": (r"\b(?:impos\w*|lev\w*)\b.{0,30}\btariffs?\b", r"관세.{0,12}부과"),
    "delay_tariff": (r"\b(?:delay\w*|postpon\w*)\b.{0,30}\btariffs?\b", r"관세.{0,12}연기"),
    "raise_rate": (r"\b(?:rais\w*|hik\w*)\b.{0,30}\b(?:rates?|interest)\b", "금리 인상", "기준금리 인상"),
    "cut_rate": (r"\b(?:cut\w*|lower\w*)\b.{0,30}\b(?:rates?|interest)\b", "금리 인하", "기준금리 인하"),
    "hold_rate": (r"\b(?:hold\w*|keep\w*)\b.{0,30}\b(?:rates?|interest)\b", "금리 동결", "기준금리 동결"),
    "earnings": (r"\b(?:earnings|quarterly results)\b", "실적 발표", "분기 실적"),
    "launch": (r"\blaunch(?:es|ed)?\b", "발사", "출시"),
}
TARGETS = {
    "china": ACTORS["china"], "korea": ACTORS["korea"],
    "thailand": ACTORS["thailand"], "us": ACTORS["us"],
    "bitcoin": ACTORS["bitcoin"], "ethereum": ACTORS["ethereum"],
    "chips": (r"\bchips?\b", "반도체"),
    "steel": (r"\bsteel\b", "철강"),
    "cars": (r"\b(?:cars?|autos?|vehicles?)\b", "자동차"),
}


def _matches(text: str, aliases: tuple[str, ...]) -> bool:
    return any(re.search(alias, text) for alias in aliases)


def signature(title: str) -> tuple[tuple[str, ...], str, tuple[str, ...], tuple[str, ...]] | None:
    text = str(title or "").casefold()
    actors = tuple(key for key, aliases in ACTORS.items() if _matches(text, aliases))
    actions = tuple(key for key, aliases in ACTIONS.items() if _matches(text, aliases))
    if not actors or len(actions) != 1:
        return None
    targets = tuple(key for key, aliases in TARGETS.items() if _matches(text, aliases))
    # Material amounts (but not years) distinguish successive economic releases.
    amounts = tuple(sorted(set(re.findall(r"\b\d+(?:[.,]\d+)?\s*[%％]|\b\d+(?:[.,]\d+)?\s*(?:억|조|billion|million)\b", text))))
    return actors, actions[0], targets, amounts


def same_event(first: dict, second: dict) -> bool:
    try:
        a = datetime.fromisoformat(str(first.get("published_at") or "").replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(second.get("published_at") or "").replace("Z", "+00:00"))
        if a.tzinfo is None or b.tzinfo is None or abs((a.astimezone(timezone.utc) - b.astimezone(timezone.utc)).total_seconds()) > WINDOW_SECONDS:
            return False
    except ValueError:
        return False
    one, two = signature(first.get("title", "")), signature(second.get("title", ""))
    if not one or not two or one[1] != two[1]:
        return False
    # An actor named in one title but merely a target in the other is not enough.
    if not set(one[0]).intersection(two[0]):
        return False
    if one[2] != two[2]:
        return False
    return not (one[3] and two[3] and one[3] != two[3])


def browser_source() -> str:
    """Generate the browser's event predicate from the server's alias tables.

    Keep the conservative actor/action/target/amount and six-hour rules in one place.
    The aliases use only regex syntax shared by Python and JavaScript.
    """
    rules = json.dumps({"actors": ACTORS, "actions": ACTIONS, "targets": TARGETS,
                        "window": WINDOW_SECONDS * 1000}, ensure_ascii=False)
    return """const EVENT_RULES=__RULES__;
function eventSignature(title){
  const text=String(title||'').toLowerCase();
  const matching=table=>Object.keys(table).filter(key=>
    table[key].some(alias=>new RegExp(alias).test(text)));
  const actors=matching(EVENT_RULES.actors),actions=matching(EVENT_RULES.actions);
  if(!actors.length||actions.length!==1)return null;
  const targets=matching(EVENT_RULES.targets);
  const amounts=[...new Set(text.match(/\\b\\d+(?:[.,]\\d+)?\\s*[%％]|\\b\\d+(?:[.,]\\d+)?\\s*(?:억|조|billion|million)\\b/g)||[])].sort();
  return {actors,action:actions[0],targets,amounts};
}
function sameBriefingEvent(a,b){
  if(![a,b].every(item=>/^(?:\\d{4}-\\d{2}-\\d{2})T.*(?:Z|[+-]\\d{2}:?\\d{2})$/.test(String(item.published_at||''))))return false;
  const ta=Date.parse(a.published_at),tb=Date.parse(b.published_at);
  if(!Number.isFinite(ta)||!Number.isFinite(tb)||Math.abs(ta-tb)>EVENT_RULES.window)return false;
  const one=eventSignature(a.title),two=eventSignature(b.title);
  if(!one||!two||one.action!==two.action||!one.actors.some(x=>two.actors.includes(x)))return false;
  if(JSON.stringify(one.targets)!==JSON.stringify(two.targets))return false;
  return !(one.amounts.length&&two.amounts.length&&
    JSON.stringify(one.amounts)!==JSON.stringify(two.amounts));
}
""".replace("__RULES__", rules)
