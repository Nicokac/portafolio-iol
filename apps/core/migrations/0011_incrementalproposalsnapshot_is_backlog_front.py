from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_incrementalproposalsnapshot_manual_decision_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="incrementalproposalsnapshot",
            name="is_backlog_front",
            field=models.BooleanField(default=False),
        ),
    ]
