from django.db import migrations, models


def migrate_feature_articles(apps, schema_editor):
    SyncedArticle = apps.get_model("briefings", "SyncedArticle")
    featured_articles = list(
        SyncedArticle.objects.filter(editorial_decision="feature").order_by("editorial_feature_rank", "id")
    )
    if not featured_articles:
        return

    highlighted_id = featured_articles[0].id
    for article in featured_articles:
        article.editorial_decision = "include"
        article.editorial_is_highlighted = article.id == highlighted_id
        article.save(update_fields=["editorial_decision", "editorial_is_highlighted"])


class Migration(migrations.Migration):

    dependencies = [
        ('briefings', '0004_pageviewevent'),
    ]

    operations = [
        migrations.AddField(
            model_name='syncedarticle',
            name='clean_labels',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='syncedarticle',
            name='clean_score',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='syncedarticle',
            name='editorial_is_highlighted',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='syncedarticle',
            name='is_manual_entry',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(migrate_feature_articles, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='syncedarticle',
            name='editorial_feature_rank',
        ),
        migrations.AlterField(
            model_name='syncedarticle',
            name='editorial_decision',
            field=models.CharField(choices=[('default', '기본'), ('include', '포함'), ('exclude', '배제')], default='default', max_length=16),
        ),
    ]
