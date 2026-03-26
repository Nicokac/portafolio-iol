from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0018_iolmarketuniversesnapshot"),
    ]

    operations = [
        migrations.CreateModel(
            name="IOLMarketCoverageSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("pais", models.CharField(max_length=64)),
                ("pais_key", models.CharField(blank=True, default="", max_length=64)),
                ("instrumento", models.CharField(max_length=64)),
                ("instrumento_key", models.CharField(blank=True, default="", max_length=64)),
                ("source", models.CharField(default="iol_bulk_quotes", max_length=32)),
                ("captured_at", models.DateTimeField()),
                ("captured_date", models.DateField()),
                ("total_titles", models.PositiveIntegerField(default=0)),
                ("priced_titles", models.PositiveIntegerField(default=0)),
                ("order_book_titles", models.PositiveIntegerField(default=0)),
                ("volume_titles", models.PositiveIntegerField(default=0)),
                ("active_titles", models.PositiveIntegerField(default=0)),
                ("recent_titles", models.PositiveIntegerField(default=0)),
                ("stale_titles", models.PositiveIntegerField(default=0)),
                ("zero_price_titles", models.PositiveIntegerField(default=0)),
                ("latest_quote_at", models.DateTimeField(blank=True, null=True)),
                ("oldest_quote_at", models.DateTimeField(blank=True, null=True)),
                ("latest_quote_age_minutes", models.PositiveIntegerField(blank=True, null=True)),
                ("oldest_quote_age_minutes", models.PositiveIntegerField(blank=True, null=True)),
                ("coverage_pct", models.DecimalField(decimal_places=2, default=0, max_digits=7)),
                ("order_book_coverage_pct", models.DecimalField(decimal_places=2, default=0, max_digits=7)),
                ("activity_pct", models.DecimalField(decimal_places=2, default=0, max_digits=7)),
                ("freshness_status", models.CharField(blank=True, default="unknown", max_length=16)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-captured_date", "pais", "instrumento"],
            },
        ),
        migrations.AddIndex(
            model_name="iolmarketcoveragesnapshot",
            index=models.Index(fields=["captured_date", "pais_key"], name="core_iolmar_captured_601c01_idx"),
        ),
        migrations.AddIndex(
            model_name="iolmarketcoveragesnapshot",
            index=models.Index(fields=["captured_date", "instrumento_key"], name="core_iolmar_captured_03e594_idx"),
        ),
        migrations.AddIndex(
            model_name="iolmarketcoveragesnapshot",
            index=models.Index(fields=["captured_date", "freshness_status"], name="core_iolmar_captured_39c5b8_idx"),
        ),
        migrations.AddConstraint(
            model_name="iolmarketcoveragesnapshot",
            constraint=models.UniqueConstraint(
                fields=("pais", "instrumento", "source", "captured_date"),
                name="unique_iol_market_coverage_snapshot_per_day",
            ),
        ),
    ]
