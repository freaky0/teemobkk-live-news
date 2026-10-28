from urllib.parse import urlencode, urlsplit

from django.core.exceptions import ValidationError


GOOGLE_MAPS_SEARCH_URL = "https://www.google.com/maps/search/"


def build_google_maps_search_url(place_name: str, region: str) -> str:
    query = " ".join(value.strip() for value in (place_name, region) if value and value.strip())
    return f"{GOOGLE_MAPS_SEARCH_URL}?{urlencode({'api': '1', 'query': query})}"


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
