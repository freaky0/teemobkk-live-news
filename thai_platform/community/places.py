from urllib.parse import parse_qs, unquote, urlencode, urlsplit

from django.core.exceptions import ValidationError


GOOGLE_MAPS_SEARCH_URL = "https://www.google.com/maps/search/"
GOOGLE_MAPS_EMBED_URL = "https://www.google.com/maps/embed/v1/place"
GOOGLE_MAPS_HOSTS = {"google.com", "www.google.com", "maps.google.com", "maps.google.co.th", "www.google.co.th", "maps.app.goo.gl", "goo.gl"}


def build_google_maps_search_url(place_name: str, region: str) -> str:
    query = " ".join(value.strip() for value in (place_name, region) if value and value.strip())
    return f"{GOOGLE_MAPS_SEARCH_URL}?{urlencode({'api': '1', 'query': query})}"


def is_google_maps_url(value: str) -> bool:
    try:
        parsed = urlsplit(value or "")
        host = (parsed.hostname or "").lower()
    except ValueError:
        return False
    return host in GOOGLE_MAPS_HOSTS or host.endswith(".google.com")


def _google_maps_query(value: str) -> str:
    try:
        parsed = urlsplit(value or "")
    except ValueError:
        return ""
    if not is_google_maps_url(value):
        return ""
    query = parse_qs(parsed.query)
    for key in ("query", "q"):
        if query.get(key) and query[key][0].strip():
            return query[key][0].strip()
    parts = parsed.path.split("/")
    if "place" in parts:
        index = parts.index("place")
        if index + 1 < len(parts):
            return unquote(parts[index + 1].replace("+", " ")).strip()
    if "search" in parts:
        index = parts.index("search")
        if index + 1 < len(parts) and parts[index + 1]:
            return unquote(parts[index + 1].replace("+", " ")).strip()
    return ""


def build_google_maps_embed_url(place_name: str, region: str, place_url: str, api_key: str) -> str:
    """Return a trusted Google Maps Embed URL, or a pasted Google embed URL."""
    try:
        parsed = urlsplit(place_url or "")
    except ValueError:
        parsed = None
    if parsed and is_google_maps_url(place_url):
        params = parse_qs(parsed.query)
        if (parsed.scheme == "https" and not parsed.username and not parsed.password
                and parsed.path.rstrip("/") == "/maps/embed"
                and (params.get("pb") or params.get("output") == ["embed"])):
            return place_url
    if not api_key:
        return ""
    query = _google_maps_query(place_url) or " ".join(value.strip() for value in (place_name, region) if value and value.strip())
    if not query:
        return ""
    return f"{GOOGLE_MAPS_EMBED_URL}?{urlencode({'key': api_key, 'q': query})}"


def validate_external_place_url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme.lower() in {"http", "https"}
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValidationError("외부 장소 링크는 http 또는 https 주소만 입력할 수 있습니다.")
    return value
