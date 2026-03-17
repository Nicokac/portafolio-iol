from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_incrementalproposalsnapshot"),
    ]

    operations = [
        migrations.AddField(
            model_name="incrementalproposalsnapshot",
            name="is_tracking_baseline",
            field=models.BooleanField(default=False),
        ),
    ]
