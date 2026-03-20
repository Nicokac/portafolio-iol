from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command


@patch("apps.core.management.commands.sync_iol_historical_prices.IOLHistoricalPriceService")
def test_sync_iol_historical_prices_command_syncs_current_portfolio_symbols(MockService):
    stdout = StringIO()
    MockService.return_value.sync_current_portfolio_symbols.return_value = {
        "success": True,
        "symbols_count": 2,
        "processed": 2,
        "results": {
            "BCBA:GGAL": {"success": True, "created": 3, "updated": 1, "rows_received": 4},
            "NASDAQ:AAPL": {"success": False, "rows_received": 0, "error": "missing"},
        },
    }

    call_command("sync_iol_historical_prices", stdout=stdout)

    MockService.return_value.sync_current_portfolio_symbols.assert_called_once_with()
    output = stdout.getvalue()
    assert "BCBA:GGAL: created=3 updated=1 rows=4" in output
    assert "NASDAQ:AAPL: error=missing rows=0" in output
    assert "Sincronizacion de historicos IOL completada con fallos parciales" in output


@patch("apps.core.management.commands.sync_iol_historical_prices.IOLHistoricalPriceService")
def test_sync_iol_historical_prices_command_syncs_single_symbol(MockService):
    stdout = StringIO()
    MockService.return_value.sync_symbol_history.return_value = {
        "success": True,
        "created": 5,
        "updated": 2,
        "rows_received": 7,
    }

    call_command(
        "sync_iol_historical_prices",
        "--mercado=BCBA",
        "--simbolo=GGAL",
        stdout=stdout,
    )

    MockService.return_value.sync_symbol_history.assert_called_once_with(mercado="BCBA", simbolo="GGAL")
    output = stdout.getvalue()
    assert "BCBA:GGAL: created=5 updated=2 rows=7" in output
    assert "Sincronizacion de historicos IOL completada" in output


@patch("apps.core.management.commands.sync_iol_historical_prices.IOLHistoricalPriceService")
def test_sync_iol_historical_prices_command_requires_both_symbol_and_market(MockService):
    with pytest.raises(SystemExit):
        call_command("sync_iol_historical_prices", "--simbolo=GGAL")

    MockService.return_value.sync_current_portfolio_symbols.assert_not_called()
    MockService.return_value.sync_symbol_history.assert_not_called()
