from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_portfolioparameters_constraints'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='alert',
            index=models.Index(
                fields=['is_active', 'severidad', 'created_at'],
                name='alert_active_sev_created_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='incrementalproposalsnapshot',
            index=models.Index(
                fields=['user', 'manual_decision_status', 'created_at'],
                name='inc_user_status_created_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='incrementalproposalsnapshot',
            index=models.Index(
                fields=['user', 'is_backlog_front', 'manual_decision_status', 'created_at'],
                name='inc_user_front_status_created',
            ),
        ),
        migrations.AddIndex(
            model_name='incrementalproposalsnapshot',
            index=models.Index(
                fields=['user', 'is_tracking_baseline', 'created_at'],
                name='inc_user_base_created_idx',
            ),
        ),
    ]
