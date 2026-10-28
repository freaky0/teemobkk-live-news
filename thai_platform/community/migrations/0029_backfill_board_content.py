from django.db import migrations


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


class Migration(migrations.Migration):
    dependencies = [('community', '0028_freepost_jobspost_livingpost_marketpost_noticepost')]
    operations = [migrations.RunPython(backfill_board_content, migrations.RunPython.noop)]
