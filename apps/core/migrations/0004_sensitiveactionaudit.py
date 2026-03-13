from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_alert"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SensitiveActionAudit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(max_length=64)),
                ("status", models.CharField(choices=[("success", "Success"), ("failed", "Failed"), ("denied", "Denied")], max_length=16)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("details", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sensitive_action_audits", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Sensitive action audit",
                "verbose_name_plural": "Sensitive action audits",
                "ordering": ["-created_at"],
            },
        ),
    ]
