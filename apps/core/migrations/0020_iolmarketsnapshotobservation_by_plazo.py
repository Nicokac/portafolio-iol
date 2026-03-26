from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0019_iolmarketcoveragesnapshot"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="iolmarketsnapshotobservation",
            name="unique_iol_market_snapshot_observation",
        ),
        migrations.AddIndex(
            model_name="iolmarketsnapshotobservation",
            index=models.Index(
                fields=["captured_date", "mercado", "plazo"],
                name="core_iolmar_captured_1c97c8_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="iolmarketsnapshotobservation",
            constraint=models.UniqueConstraint(
                fields=("simbolo", "mercado", "captured_at", "plazo"),
                name="unique_iol_market_snapshot_observation_by_plazo",
            ),
        ),
    ]
