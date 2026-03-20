from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0012_incrementalproposalsnapshot_decision_engine_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="IOLHistoricalPriceSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("simbolo", models.CharField(max_length=20)),
                ("mercado", models.CharField(max_length=20)),
                ("source", models.CharField(default="iol", max_length=32)),
                ("fecha", models.DateField()),
                ("open", models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True)),
                ("high", models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True)),
                ("low", models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True)),
                ("close", models.DecimalField(decimal_places=6, max_digits=18)),
                ("volume", models.BigIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-fecha", "simbolo"],
                "constraints": [models.UniqueConstraint(fields=("simbolo", "mercado", "source", "fecha"), name="unique_iol_historical_price_per_day")],
                "indexes": [models.Index(fields=["simbolo", "mercado", "fecha"], name="core_iolhis_simbolo_de456a_idx"), models.Index(fields=["mercado", "fecha"], name="core_iolhis_mercado_4e3f36_idx")],
            },
        ),
    ]
