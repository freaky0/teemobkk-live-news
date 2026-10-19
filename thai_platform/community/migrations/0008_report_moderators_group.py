from django.db import migrations


def create_report_moderators_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.using(schema_editor.connection.alias).get_or_create(name='Report moderators')


class Migration(migrations.Migration):
    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('community', '0007_report_target_type'),
    ]

    operations = [
        migrations.RunPython(create_report_moderators_group, migrations.RunPython.noop),
    ]
