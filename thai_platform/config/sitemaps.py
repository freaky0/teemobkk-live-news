from datetime import date, datetime
from xml.etree import ElementTree as ET

from django.http import HttpResponse
from django.views.decorators.http import require_GET

from community import news, services
from .context import PUBLIC_ORIGIN, PUBLIC_PREFIX


SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
MAX_URLS_PER_SITEMAP = 20000
# Retain the old name for code that imports this limit.
MAX_DYNAMIC_URLS_PER_SECTION = MAX_URLS_PER_SITEMAP


def _iso_date(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return value[:10]
    return ""


def _sitemap_location(path):
    return f"{PUBLIC_ORIGIN}{PUBLIC_PREFIX}/{path}"


def _xml_response(root):
    body = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    response = HttpResponse(body, content_type="application/xml; charset=utf-8")
    response["Cache-Control"] = "public, max-age=3600"
    return response


def _urlset(entries):
    ET.register_namespace("", SITEMAP_NS)
    root = ET.Element(f"{{{SITEMAP_NS}}}urlset")
    for path, lastmod in entries:
        node = ET.SubElement(root, f"{{{SITEMAP_NS}}}url")
        ET.SubElement(node, f"{{{SITEMAP_NS}}}loc").text = (
            f"{PUBLIC_ORIGIN}{PUBLIC_PREFIX}{path}"
        )
        value = _iso_date(lastmod)
        if value:
            ET.SubElement(node, f"{{{SITEMAP_NS}}}lastmod").text = value
    return root


def _page_count(total):
    return (total + MAX_URLS_PER_SITEMAP - 1) // MAX_URLS_PER_SITEMAP


@require_GET
def sitemap_xml(request):
    """List every sitemap chunk so large feeds are not silently truncated."""
    ET.register_namespace("", SITEMAP_NS)
    root = ET.Element(f"{{{SITEMAP_NS}}}sitemapindex")
    locations = ["sitemap-static.xml"]

    try:
        news_total = news.sitemap_article_count()
    except news.NewsUnavailable:
        # Keep the public pages discoverable if the read-only news DB is offline.
        news_total = 0
    locations.extend(
        f"sitemap-news-{part}.xml"
        for part in range(1, _page_count(news_total) + 1)
    )

    community_total = services.public_posts().count()
    locations.extend(
        f"sitemap-community-{part}.xml"
        for part in range(1, _page_count(community_total) + 1)
    )

    for path in locations:
        node = ET.SubElement(root, f"{{{SITEMAP_NS}}}sitemap")
        ET.SubElement(node, f"{{{SITEMAP_NS}}}loc").text = _sitemap_location(path)

    return _xml_response(root)


@require_GET
def sitemap_static_xml(request):
    return _xml_response(_urlset([
        ("/", None),
        ("/newsroom/", None),
        ("/community/", None),
    ]))


@require_GET
def sitemap_news_xml(request, part):
    if part < 1:
        return HttpResponse(status=404)
    try:
        total = news.sitemap_article_count()
        if part > _page_count(total):
            return HttpResponse(status=404)
        offset = (part - 1) * MAX_URLS_PER_SITEMAP
        articles = news.sitemap_articles(limit=MAX_URLS_PER_SITEMAP, offset=offset)
    except news.NewsUnavailable:
        return HttpResponse(status=503)

    entries = [
        (f"/newsroom/{item['id']}/", item["published_at"])
        for item in articles
    ]
    return _xml_response(_urlset(entries))


@require_GET
def sitemap_community_xml(request, part):
    if part < 1:
        return HttpResponse(status=404)
    posts = services.public_posts()
    total = posts.count()
    if part > _page_count(total):
        return HttpResponse(status=404)
    offset = (part - 1) * MAX_URLS_PER_SITEMAP
    entries = [
        (f"/community/{pk}/", updated_at)
        for pk, updated_at in posts.values_list("pk", "updated_at")[
            offset:offset + MAX_URLS_PER_SITEMAP
        ]
    ]
    return _xml_response(_urlset(entries))
