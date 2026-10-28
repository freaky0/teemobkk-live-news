import json
from django.utils.crypto import salted_hmac


def board_data_version(post):
    """Opaque snapshot of the exact stored post version approved for removal."""
    fields = ('market_kind', 'market_price', 'market_region', 'market_status', 'job_kind', 'job_region', 'job_compensation', 'job_status', 'place_name', 'place_region', 'place_note', 'place_url')
    value = json.dumps([post.pk, post.category, post.updated_at.isoformat(), *[str(getattr(post, name)) for name in fields]], ensure_ascii=False)
    return salted_hmac('community.board-data-version', value, algorithm='sha256').hexdigest()
