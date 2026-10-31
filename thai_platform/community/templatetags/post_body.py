import html
import re
from urllib.parse import urlsplit

from django import template
from django.utils.html import format_html, format_html_join

register = template.Library()

_INLINE = re.compile(
    r"!\[([^\]]*)\]\((https?://[^\s)]+)\)"
    r"|\[([^\]]+)\]\((https?://[^\s)]+)\)"
    r"|\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`"
    r"|(https?://[^\s<>]+)"
)


def _safe_url(value):
    value = value.rstrip(".,!?;:")
    try:
        parts = urlsplit(value)
        if parts.scheme in {"http", "https"} and parts.netloc and not parts.username and not parts.password:
            return value
    except ValueError:
        pass
    return ""


def _inline(value):
    rendered = []
    cursor = 0
    for match in _INLINE.finditer(value):
        if match.start() > cursor:
            rendered.append(format_html("{}", value[cursor:match.start()]))
        image_alt, image_url, link_label, link_url, bold, italic, code, bare_url = match.groups()
        if image_url:
            url = _safe_url(image_url)
            item = format_html(
                '<img src="{}" alt="{}" loading="lazy" decoding="async" referrerpolicy="no-referrer">',
                url,
                image_alt,
            ) if url else format_html("{}", match.group(0))
        elif link_url:
            url = _safe_url(link_url)
            item = format_html(
                '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>', url, link_label
            ) if url else format_html("{}", match.group(0))
        elif bold:
            item = format_html("<strong>{}</strong>", bold)
        elif italic:
            item = format_html("<em>{}</em>", italic)
        elif code:
            item = format_html("<code>{}</code>", code)
        else:
            url = _safe_url(bare_url)
            path = urlsplit(url).path.lower() if url else ""
            if url and path.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif")):
                item = format_html(
                    '<img src="{}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">', url
                )
            else:
                item = format_html(
                    '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>',
                    url,
                    bare_url.rstrip(".,!?;:"),
                ) if url else format_html("{}", bare_url)
        rendered.append(item)
        cursor = match.end()
    if cursor < len(value):
        rendered.append(format_html("{}", value[cursor:]))
    return format_html_join("", "{}", ((item,) for item in rendered))


@register.filter
def community_body(value):
    """Render a safe, intentionally small Markdown subset for community posts."""
    source = html.unescape(str(value or "")).replace("\r\n", "\n").replace("\r", "\n")
    source = re.sub(r"\\\s*\n", "\n", source)
    source = re.sub(r"(?<!\\)\\\s*$", "", source, flags=re.MULTILINE)
    source = re.sub(r"\\([()[\]:])", r"\1", source)
    blocks = []
    paragraph = []
    items = []
    list_kind = None

    def flush_paragraph():
        if paragraph:
            lines = format_html_join("<br>", "{}", ((_inline(line),) for line in paragraph))
            blocks.append(format_html("<p>{}</p>", lines))
            paragraph.clear()

    def flush_list():
        nonlocal list_kind
        if items:
            rendered_items = format_html_join("", "<li>{}</li>", ((_inline(item),) for item in items))
            blocks.append(format_html("<{}>{}</{}>", list_kind, rendered_items, list_kind))
            items.clear()
        list_kind = None

    for line in source.split("\n"):
        if not line.strip():
            flush_paragraph()
            flush_list()
            continue
        bullet = re.match(r"^\s*[-*]\s+(.+)$", line)
        numbered = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
        if bullet or numbered:
            flush_paragraph()
            kind = "ul" if bullet else "ol"
            if list_kind != kind:
                flush_list()
                list_kind = kind
            items.append((bullet or numbered).group(1))
            continue
        flush_list()
        quote = re.match(r"^\s*>\s?(.*)$", line)
        heading = re.match(r"^\s*(#{1,3})\s+(.+)$", line)
        section = re.match(r"^\s*\[([^\]]{2,100})\]\s*$", line)
        if quote or heading or section:
            flush_paragraph()
            if quote:
                blocks.append(format_html("<blockquote>{}</blockquote>", _inline(quote.group(1))))
            else:
                level = len(heading.group(1)) + 1 if heading else 3
                title = heading.group(2) if heading else section.group(1)
                blocks.append(format_html("<h{}>{}</h{}>", level, _inline(title), level))
            continue
        paragraph.append(line)

    flush_paragraph()
    flush_list()
    return format_html_join("", "{}", ((block,) for block in blocks))
