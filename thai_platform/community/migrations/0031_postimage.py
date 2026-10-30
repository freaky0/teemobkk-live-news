from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('community', '0030_alter_post_job_region_alter_post_market_region_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='PostImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image_data', models.BinaryField(blank=True, editable=False, null=True)),
                ('content_type', models.CharField(blank=True, default='', max_length=30)),
                ('image_url', models.URLField(blank=True, default='', max_length=2048)),
                ('position', models.PositiveSmallIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('post', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='community.post')),
            ],
            options={
                'ordering': ['position', 'pk'],
                'constraints': [models.CheckConstraint(condition=models.Q(models.Q(('image_data__isnull', False), ('image_url', '')), models.Q(('image_data__isnull', True), ('image_url__gt', '')), _connector='OR'), name='community_post_image_has_source')],
            },
        ),
        migrations.AlterField(
            model_name='post',
            name='place_url',
            field=models.CharField(blank=True, db_default='', default='', max_length=2048),
        ),
    ]
