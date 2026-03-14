from unittest.mock import patch

from django.core.management import call_command


@patch("apps.core.management.commands.sync_local_macro.LocalMacroSeriesService")
def test_sync_local_macro_command_runs_service(MockService):
    MockService.return_value.sync_all.return_value = {
        "usdars_oficial": {
            "created": 2,
            "updated": 0,
            "rows_received": 2,
        },
        "ipc_nacional": {
            "created": 2,
            "updated": 0,
            "rows_received": 2,
        },
    }

    call_command("sync_local_macro")

    MockService.return_value.sync_all.assert_called_once_with()
