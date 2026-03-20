from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portafolio_iol", "0002_portfoliosnapshot_positionsnapshot"),
    ]

    operations = [
        migrations.AddField(
            model_name="portfoliosnapshot",
            name="cash_disponible_broker",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Cash broker explícito persistido para snapshots nuevos",
                max_digits=15,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="portfoliosnapshot",
            name="caucion_colocada",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Caución colocada persistida para snapshots nuevos",
                max_digits=15,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="portfoliosnapshot",
            name="total_patrimonio_modelado",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Total patrimonial modelado con capas explícitas",
                max_digits=15,
                null=True,
            ),
        ),
    ]
