from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, IntervalSchedule, PeriodicTask


class Command(BaseCommand):
    help = "Crea o actualiza las tareas periodicas base para sync, snapshots y metricas."

    def handle(self, *args, **options):
        interval_30m, _ = IntervalSchedule.objects.get_or_create(
            every=30,
            period=IntervalSchedule.MINUTES,
        )
        interval_1h, _ = IntervalSchedule.objects.get_or_create(
            every=1,
            period=IntervalSchedule.HOURS,
        )
        interval_4h, _ = IntervalSchedule.objects.get_or_create(
            every=4,
            period=IntervalSchedule.HOURS,
        )
        daily_6am, _ = CrontabSchedule.objects.get_or_create(
            minute="0",
            hour="6",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            timezone="America/Argentina/Buenos_Aires",
        )
        daily_630pm, _ = CrontabSchedule.objects.get_or_create(
            minute="30",
            hour="18",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            timezone="America/Argentina/Buenos_Aires",
        )

        tasks = [
            {
                "name": "core.sync_portfolio_data",
                "task": "apps.core.tasks.portfolio_tasks.sync_portfolio_data",
                "interval": interval_30m,
            },
            {
                "name": "core.generate_alerts",
                "task": "apps.core.tasks.portfolio_tasks.generate_alerts",
                "interval": interval_1h,
            },
            {
                "name": "core.calculate_temporal_metrics",
                "task": "apps.core.tasks.portfolio_tasks.calculate_temporal_metrics",
                "interval": interval_4h,
            },
            {
                "name": "core.generate_daily_snapshot",
                "task": "apps.core.tasks.portfolio_tasks.generate_daily_snapshot",
                "crontab": daily_6am,
            },
            {
                "name": "core.sync_local_macro_series",
                "task": "apps.core.tasks.portfolio_tasks.sync_local_macro_series",
                "crontab": daily_630pm,
            },
        ]

        for payload in tasks:
            defaults = {
                "task": payload["task"],
                "enabled": True,
            }
            if "interval" in payload:
                defaults["interval"] = payload["interval"]
                defaults["crontab"] = None
            if "crontab" in payload:
                defaults["crontab"] = payload["crontab"]
                defaults["interval"] = None

            PeriodicTask.objects.update_or_create(
                name=payload["name"],
                defaults=defaults,
            )

        self.stdout.write(self.style.SUCCESS(f"Periodic tasks configured: {len(tasks)}"))
