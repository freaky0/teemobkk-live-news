from datetime import date, datetime
from xml.etree import ElementTree as ET

from django.http import HttpResponse
from django.views.decorators.http import require_GET

from community import news, services
from .context import PUBLIC_ORIGIN, PUBLIC_PREFIX


SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
MAX_DYNAMIC_URLS_PER_SECTION = 20000


def _iso_date(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return value[:10]
    return ""


@require_GET
def sitemap_xml(request):
    ET.register_namespace("", SITEMAP_NS)
    root = ET.Element(f"{{{SITEMAP_NS}}}urlset")
    entries = [
        ("/", None),
        ("/newsroom/", None),
        ("/community/", None),
    ]

    try:
        entries.extend(
            (f"/newsroom/{item['id']}/", item["published_at"])
            for item in news.sitemap_articles(limit=MAX_DYNAMIC_URLS_PER_SECTION)
        )
    except news.NewsUnavailable:
        # Keep the sitemap useful for the rest of the site while news is offline.
        pass

    entries.extend(
        (f"/community/{pk}/", updated_at)
        for pk, updated_at in services.public_posts().values_list("pk", "updated_at")[:MAX_DYNAMIC_URLS_PER_SECTION]
    )

    for path, lastmod in entries:
        node = ET.SubElement(root, f"{{{SITEMAP_NS}}}url")
        ET.SubElement(node, f"{{{SITEMAP_NS}}}loc").text = (
            f"{PUBLIC_ORIGIN}{PUBLIC_PREFIX}{path}"
        )
        value = _iso_date(lastmod)
        if value:
            ET.SubElement(node, f"{{{SITEMAP_NS}}}lastmod").text = value

    body = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    response = HttpResponse(body, content_type="application/xml; charset=utf-8")
    response["Cache-Control"] = "public, max-age=3600"
    return response
