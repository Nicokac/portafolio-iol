from io import StringIO

import pytest
from django.core.management import call_command
from django_celery_beat.models import PeriodicTask


@pytest.mark.django_db
def test_setup_periodic_tasks_creates_expected_schedule():
    stdout = StringIO()

    call_command("setup_periodic_tasks", stdout=stdout)

    tasks = {task.name: task for task in PeriodicTask.objects.all()}

    assert "core.sync_portfolio_data" in tasks
    assert "core.generate_alerts" in tasks
    assert "core.calculate_temporal_metrics" in tasks
    assert "core.generate_daily_snapshot" in tasks
    assert all(task.enabled for task in tasks.values())
    assert "Periodic tasks configured: 4" in stdout.getvalue()


@pytest.mark.django_db
def test_setup_periodic_tasks_is_idempotent():
    call_command("setup_periodic_tasks")
    call_command("setup_periodic_tasks")

    assert PeriodicTask.objects.count() == 4
