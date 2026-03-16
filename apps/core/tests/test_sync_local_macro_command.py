from unittest.mock import patch

from django.core.management import call_command
from io import StringIO


@patch("apps.core.management.commands.sync_local_macro.LocalMacroSeriesService")
def test_sync_local_macro_command_runs_service(MockService):
    MockService.return_value.sync_all.return_value = {
        "usdars_oficial": {
            "created": 2,
            "updated": 0,
            "rows_received": 2,
        },
        "usdars_mep": {
            "created": 0,
            "updated": 0,
            "rows_received": 0,
            "skipped": True,
            "reason": "USDARS_MEP_API_URL is required",
        },
        "badlar_privada": {
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

    out = StringIO()
    call_command("sync_local_macro", stdout=out)

    MockService.return_value.sync_all.assert_called_once_with()
    output = out.getvalue()
    assert "usdars_mep: skipped (USDARS_MEP_API_URL is required)" in output
