from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0016_operational_indexes"),
    ]

    operations = [
        migrations.CreateModel(
            name="IOLFCICatalogSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("simbolo", models.CharField(max_length=24)),
                ("descripcion", models.CharField(blank=True, default="", max_length=200)),
                ("source", models.CharField(default="iol", max_length=32)),
                ("captured_at", models.DateTimeField()),
                ("captured_date", models.DateField()),
                ("administradora", models.CharField(blank=True, default="", max_length=64)),
                ("administradora_key", models.CharField(blank=True, default="", max_length=64)),
                ("tipo_fondo", models.CharField(blank=True, default="", max_length=64)),
                ("horizonte_inversion", models.CharField(blank=True, default="", max_length=64)),
                ("rescate", models.CharField(blank=True, default="", max_length=16)),
                ("perfil_inversor", models.CharField(blank=True, default="", max_length=64)),
                ("perfil_inversor_key", models.CharField(blank=True, default="", max_length=64)),
                ("moneda", models.CharField(blank=True, default="", max_length=64)),
                ("pais", models.CharField(blank=True, default="", max_length=64)),
                ("mercado", models.CharField(blank=True, default="", max_length=32)),
                ("ultimo_operado", models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True)),
                ("variacion", models.DecimalField(blank=True, decimal_places=6, max_digits=12, null=True)),
                ("variacion_mensual", models.DecimalField(blank=True, decimal_places=6, max_digits=12, null=True)),
                ("variacion_anual", models.DecimalField(blank=True, decimal_places=6, max_digits=12, null=True)),
                ("monto_minimo", models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True)),
                ("fecha_corte", models.DateTimeField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-captured_date", "simbolo"],
            },
        ),
        migrations.AddIndex(
            model_name="iolfcicatalogsnapshot",
            index=models.Index(fields=["captured_date", "tipo_fondo"], name="core_iolfci_captured_477b2d_idx"),
        ),
        migrations.AddIndex(
            model_name="iolfcicatalogsnapshot",
            index=models.Index(fields=["captured_date", "moneda"], name="core_iolfci_captured_e6f14e_idx"),
        ),
        migrations.AddIndex(
            model_name="iolfcicatalogsnapshot",
            index=models.Index(fields=["captured_date", "rescate"], name="core_iolfci_captured_80ce52_idx"),
        ),
        migrations.AddIndex(
            model_name="iolfcicatalogsnapshot",
            index=models.Index(fields=["captured_date", "perfil_inversor_key"], name="core_iolfci_captured_59e57e_idx"),
        ),
        migrations.AddIndex(
            model_name="iolfcicatalogsnapshot",
            index=models.Index(fields=["captured_date", "administradora_key"], name="core_iolfci_captured_b24d42_idx"),
        ),
        migrations.AddConstraint(
            model_name="iolfcicatalogsnapshot",
            constraint=models.UniqueConstraint(fields=("simbolo", "source", "captured_date"), name="unique_iol_fci_catalog_snapshot_per_day"),
        ),
    ]
