from unittest.mock import patch

from django.core.management import call_command


@patch("apps.core.management.commands.sync_iol_fci_catalog.IOLFCICatalogService")
def test_sync_iol_fci_catalog_command_runs_service(MockService):
    MockService.return_value.sync_catalog.return_value = {
        "success": True,
        "created": 2,
        "updated": 1,
        "rows_received": 3,
        "captured_date": "2026-03-26",
    }

    call_command("sync_iol_fci_catalog")

    MockService.return_value.sync_catalog.assert_called_once_with()


@patch("apps.core.management.commands.sync_iol_fci_catalog.IOLFCICatalogService")
def test_sync_iol_fci_catalog_command_reports_failures(MockService):
    MockService.return_value.sync_catalog.return_value = {
        "success": False,
        "created": 0,
        "updated": 0,
        "rows_received": 0,
        "error": "forbidden",
    }

    call_command("sync_iol_fci_catalog")

    MockService.return_value.sync_catalog.assert_called_once_with()
