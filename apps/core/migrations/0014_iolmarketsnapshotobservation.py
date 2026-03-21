from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0013_iolhistoricalpricesnapshot"),
    ]

    operations = [
        migrations.CreateModel(
            name="IOLMarketSnapshotObservation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("simbolo", models.CharField(max_length=20)),
                ("mercado", models.CharField(max_length=20)),
                ("source_key", models.CharField(default="cotizacion_detalle", max_length=32)),
                ("snapshot_status", models.CharField(default="available", max_length=16)),
                ("captured_at", models.DateTimeField()),
                ("captured_date", models.DateField()),
                ("descripcion", models.CharField(blank=True, default="", max_length=200)),
                ("tipo", models.CharField(blank=True, default="", max_length=50)),
                ("plazo", models.CharField(blank=True, default="", max_length=16)),
                ("ultimo_precio", models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True)),
                ("variacion", models.DecimalField(blank=True, decimal_places=6, max_digits=12, null=True)),
                ("cantidad_operaciones", models.IntegerField(default=0)),
                ("puntas_count", models.PositiveIntegerField(default=0)),
                ("spread_abs", models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True)),
                ("spread_pct", models.DecimalField(blank=True, decimal_places=6, max_digits=12, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-captured_at", "simbolo"],
                "indexes": [
                    models.Index(fields=["simbolo", "mercado", "captured_at"], name="core_iolmar_simbolo_2380ad_idx"),
                    models.Index(fields=["captured_date", "mercado"], name="core_iolmar_capture_9d3d4d_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("simbolo", "mercado", "captured_at"),
                        name="unique_iol_market_snapshot_observation",
                    )
                ],
            },
        ),
    ]
