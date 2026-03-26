from unittest.mock import patch

import pytest
from django.core.management import call_command


@pytest.mark.django_db
class TestSyncIOLMarketCoverageCommand:
    @patch("apps.core.management.commands.sync_iol_market_coverage.IOLMarketCoverageService.sync_coverage")
    def test_command_runs_successfully(self, mock_sync):
        mock_sync.return_value = {
            "success": True,
            "countries_processed": 1,
            "instruments_processed": 2,
            "rows_received": 150,
            "created": 2,
            "updated": 0,
        }

        call_command("sync_iol_market_coverage")

        mock_sync.assert_called_once_with(paises=None, instrumentos=None)

    @patch("apps.core.management.commands.sync_iol_market_coverage.IOLMarketCoverageService.sync_coverage")
    def test_command_forwards_filters(self, mock_sync):
        mock_sync.return_value = {
            "success": True,
            "countries_processed": 1,
            "instruments_processed": 1,
            "rows_received": 10,
            "created": 1,
            "updated": 0,
        }

        call_command("sync_iol_market_coverage", "--pais=argentina", "--instrumento=Bonos")

        mock_sync.assert_called_once_with(paises=["argentina"], instrumentos=["Bonos"])
