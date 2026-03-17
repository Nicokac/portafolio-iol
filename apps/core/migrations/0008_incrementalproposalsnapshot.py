from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_macroseriessnapshot"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="IncrementalProposalSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_key", models.CharField(max_length=64)),
                ("source_label", models.CharField(max_length=120)),
                ("proposal_key", models.CharField(max_length=64)),
                ("proposal_label", models.CharField(max_length=160)),
                ("selected_context", models.CharField(blank=True, default="", max_length=160)),
                ("capital_amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("comparison_score", models.DecimalField(blank=True, decimal_places=4, max_digits=10, null=True)),
                ("purchase_plan", models.JSONField(blank=True, default=list)),
                ("simulation_delta", models.JSONField(blank=True, default=dict)),
                ("simulation_interpretation", models.TextField(blank=True, default="")),
                ("explanation", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="incremental_proposal_snapshots",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Incremental proposal snapshot",
                "verbose_name_plural": "Incremental proposal snapshots",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="incrementalproposalsnapshot",
            index=models.Index(fields=["user", "created_at"], name="core_increm_user_id_72d20f_idx"),
        ),
        migrations.AddIndex(
            model_name="incrementalproposalsnapshot",
            index=models.Index(fields=["source_key", "created_at"], name="core_increm_source__bf4270_idx"),
        ),
    ]
