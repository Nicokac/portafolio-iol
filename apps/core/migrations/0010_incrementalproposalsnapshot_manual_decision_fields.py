from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0009_incrementalproposalsnapshot_is_tracking_baseline"),
    ]

    operations = [
        migrations.AddField(
            model_name="incrementalproposalsnapshot",
            name="manual_decided_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="incrementalproposalsnapshot",
            name="manual_decision_note",
            field=models.CharField(blank=True, default="", max_length=240),
        ),
        migrations.AddField(
            model_name="incrementalproposalsnapshot",
            name="manual_decision_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("accepted", "Accepted"),
                    ("deferred", "Deferred"),
                    ("rejected", "Rejected"),
                ],
                default="pending",
                max_length=16,
            ),
        ),
    ]
