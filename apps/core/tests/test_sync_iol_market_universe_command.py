from unittest.mock import patch

from django.core.management import call_command


@patch("apps.core.management.commands.sync_iol_market_universe.IOLMarketUniverseService")
def test_sync_iol_market_universe_command_runs_service(MockService):
    MockService.return_value.sync_universe.return_value = {
        "success": True,
        "created": 3,
        "updated": 1,
        "rows_received": 4,
        "countries_processed": 1,
        "captured_date": "2026-03-26",
    }

    call_command("sync_iol_market_universe")

    MockService.return_value.sync_universe.assert_called_once_with(paises=None)


@patch("apps.core.management.commands.sync_iol_market_universe.IOLMarketUniverseService")
def test_sync_iol_market_universe_command_accepts_country_filter(MockService):
    MockService.return_value.sync_universe.return_value = {
        "success": True,
        "created": 1,
        "updated": 0,
        "rows_received": 1,
        "countries_processed": 1,
        "captured_date": "2026-03-26",
    }

    call_command("sync_iol_market_universe", "--pais", "argentina")

    MockService.return_value.sync_universe.assert_called_once_with(paises=["argentina"])
