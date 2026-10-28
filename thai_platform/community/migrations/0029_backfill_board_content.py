from django.db import migrations
from django.apps import apps as current_apps


def backfill_board_content(apps, schema_editor):
    """Copy legacy content without overwriting existing independent slice rows."""
    alias = schema_editor.connection.alias
    Post = apps.get_model('community', 'Post')
    categories = {
        'NoticePost': ('notice',),
        'FreePost': ('free',),
        'MarketPost': ('market',),
        'JobsPost': ('jobs',),
        'LivingPost': ('living', 'housing', 'banking'),
    }
    for model_name, values in categories.items():
        Model = apps.get_model('community', model_name)
        posts = Post.objects.using(alias).filter(category__in=values).order_by('pk')
        for post in posts.iterator(chunk_size=500):
            Model.objects.using(alias).get_or_create(
                post_id=post.pk, defaults={'title': post.title, 'body': post.body},
            )


def restore_board_content(apps, schema_editor):
    """Copy every board row back onto Post before 0028 drops those tables.

    Runs on the live app registry: reversing 0029 precedes 0028, so the board
    tables still exist, but the historical project state no longer has them.
    """
    alias = schema_editor.connection.alias
    Post = current_apps.get_model('community', 'Post')
    for model_name in ('NoticePost', 'FreePost', 'MarketPost', 'JobsPost', 'LivingPost'):
        Model = current_apps.get_model('community', model_name)
        for content in Model.objects.using(alias).order_by('post_id').iterator(chunk_size=500):
            Post.objects.using(alias).filter(pk=content.post_id).update(
                title=content.title, body=content.body,
            )


class Migration(migrations.Migration):
    dependencies = [('community', '0028_freepost_jobspost_livingpost_marketpost_noticepost')]
    # Reversing runs before 0028 drops the board tables, so the authoritative
    # rows are copied back onto Post instead of being silently lost.
    operations = [migrations.RunPython(backfill_board_content, restore_board_content)]
