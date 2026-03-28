from io import StringIO

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_sync_finviz_signal_overlays_command_forwards_scope_and_symbols(monkeypatch):
    captured = {}

    class DummyService:
        def sync_signals(self, **kwargs):
            captured.update(kwargs)
            return {
                "mapped_assets": 2,
                "created": 1,
                "updated": 1,
                "ok": 2,
                "errors": 0,
                "captured_date": "2026-03-27",
            }

    monkeypatch.setattr(
        "apps.core.management.commands.sync_finviz_signal_overlays.FinvizSignalOverlayService",
        lambda: DummyService(),
    )
    stdout = StringIO()

    call_command(
        "sync_finviz_signal_overlays",
        "--scope=portfolio",
        "--symbols=MSFT,AAPL",
        stdout=stdout,
    )

    assert captured["scope"] == "portfolio"
    assert captured["symbols"] == ["MSFT", "AAPL"]
    assert "mapped=2" in stdout.getvalue()
