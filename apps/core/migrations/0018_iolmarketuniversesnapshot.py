from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_iolfcicatalogsnapshot"),
    ]

    operations = [
        migrations.CreateModel(
            name="IOLMarketUniverseSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("pais", models.CharField(max_length=64)),
                ("pais_key", models.CharField(blank=True, default="", max_length=64)),
                ("instrumento", models.CharField(max_length=64)),
                ("instrumento_key", models.CharField(blank=True, default="", max_length=64)),
                ("panel", models.CharField(blank=True, default="", max_length=64)),
                ("panel_key", models.CharField(blank=True, default="", max_length=64)),
                ("source", models.CharField(default="iol", max_length=32)),
                ("captured_at", models.DateTimeField()),
                ("captured_date", models.DateField()),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-captured_date", "pais", "instrumento", "panel"],
            },
        ),
        migrations.AddIndex(
            model_name="iolmarketuniversesnapshot",
            index=models.Index(fields=["captured_date", "pais_key"], name="core_iolmar_capture_4dcff1_idx"),
        ),
        migrations.AddIndex(
            model_name="iolmarketuniversesnapshot",
            index=models.Index(fields=["captured_date", "instrumento_key"], name="core_iolmar_capture_fae12a_idx"),
        ),
        migrations.AddIndex(
            model_name="iolmarketuniversesnapshot",
            index=models.Index(fields=["captured_date", "pais_key", "instrumento_key"], name="core_iolmar_capture_8e3324_idx"),
        ),
        migrations.AddConstraint(
            model_name="iolmarketuniversesnapshot",
            constraint=models.UniqueConstraint(
                fields=("pais", "instrumento", "panel", "source", "captured_date"),
                name="unique_iol_market_universe_snapshot_per_day",
            ),
        ),
    ]
