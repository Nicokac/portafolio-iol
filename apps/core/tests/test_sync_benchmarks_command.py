from unittest.mock import patch

from django.core.management import call_command


@patch("apps.core.management.commands.sync_benchmarks.BenchmarkSeriesService")
def test_sync_benchmarks_command_runs_service(MockService):
    MockService.return_value.sync_all.return_value = {
        "cedear_usa": {
            "created": 10,
            "updated": 0,
            "rows_received": 10,
        }
    }

    call_command("sync_benchmarks")

    MockService.return_value.sync_all.assert_called_once_with(outputsize="compact")
