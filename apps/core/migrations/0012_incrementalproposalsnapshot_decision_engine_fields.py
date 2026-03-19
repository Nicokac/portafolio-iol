from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0011_incrementalproposalsnapshot_is_backlog_front"),
    ]

    operations = [
        migrations.AddField(
            model_name="incrementalproposalsnapshot",
            name="decision_confidence",
            field=models.CharField(blank=True, max_length=16, null=True),
        ),
        migrations.AddField(
            model_name="incrementalproposalsnapshot",
            name="decision_explanation",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="incrementalproposalsnapshot",
            name="decision_score",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="incrementalproposalsnapshot",
            name="macro_state",
            field=models.CharField(blank=True, max_length=24, null=True),
        ),
        migrations.AddField(
            model_name="incrementalproposalsnapshot",
            name="portfolio_state",
            field=models.CharField(blank=True, max_length=24, null=True),
        ),
    ]
