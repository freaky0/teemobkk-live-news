from django.shortcuts import render
from django.utils.html import strip_tags
from django.utils.text import Truncator


INDEX_ROBOTS = "index, follow"
NOINDEX_ROBOTS = "noindex, follow"


def seo_text(value, limit):
    plain = " ".join(strip_tags(str(value or "")).split())
    return Truncator(plain).chars(limit)


def render_seo(request, template_name, context=None, *, title, description, status=200, allow_from=False):
    allowed_query_keys = {"from"} if allow_from else set()
    indexable = (
        request.method == "GET"
        and status == 200
        and set(request.GET.keys()).issubset(allowed_query_keys)
    )
    robots = INDEX_ROBOTS if indexable else NOINDEX_ROBOTS
    page_context = dict(context or {})
    page_context.update({
        "seo_title": seo_text(title, 75),
        "seo_description": seo_text(description, 160),
        "seo_robots": robots,
    })
    response = render(request, template_name, page_context, status=status)
    response["X-Robots-Tag"] = robots
    return response
