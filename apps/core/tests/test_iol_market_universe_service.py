from datetime import date
from unittest.mock import Mock

import pytest
from django.utils import timezone

from apps.core.models import IOLMarketUniverseSnapshot
from apps.core.services.iol_market_universe_service import IOLMarketUniverseService


@pytest.mark.django_db
class TestIOLMarketUniverseService:
    def test_sync_universe_persists_instruments_and_panels(self):
        client = Mock()
        client.get_quote_instruments.return_value = [
            {"instrumento": "Acciones", "pais": "argentina"},
            {"instrumento": "Bonos", "pais": "argentina"},
        ]
        client.get_quote_panels.side_effect = [
            [{"panel": "Lideres"}, {"panel": "Cedears"}],
            [],
        ]

        result = IOLMarketUniverseService(client=client).sync_universe(
            paises=["argentina"],
            captured_at=timezone.make_aware(timezone.datetime(2026, 3, 26, 15, 0, 0)),
        )

        assert result["success"] is True
        assert result["rows_received"] == 3
        assert IOLMarketUniverseSnapshot.objects.count() == 3

        acciones = IOLMarketUniverseSnapshot.objects.filter(instrumento="Acciones").order_by("panel")
        assert list(acciones.values_list("panel", flat=True)) == ["Cedears", "Lideres"]

        bonos = IOLMarketUniverseSnapshot.objects.get(instrumento="Bonos")
        assert bonos.panel == ""
        assert bonos.metadata["panel_discovery_status"] == "empty"

    def test_list_latest_universe_groups_panels_from_latest_snapshot_only(self):
        captured_at = timezone.make_aware(timezone.datetime(2026, 3, 26, 15, 0, 0))
        previous_at = timezone.make_aware(timezone.datetime(2026, 3, 25, 15, 0, 0))

        IOLMarketUniverseSnapshot.objects.create(
            pais="argentina",
            pais_key="argentina",
            instrumento="Acciones",
            instrumento_key="acciones",
            panel="General",
            panel_key="general",
            source="iol",
            captured_at=previous_at,
            captured_date=date(2026, 3, 25),
            metadata={"panel_discovery_status": "available"},
        )
        IOLMarketUniverseSnapshot.objects.create(
            pais="argentina",
            pais_key="argentina",
            instrumento="Acciones",
            instrumento_key="acciones",
            panel="Cedears",
            panel_key="cedears",
            source="iol",
            captured_at=captured_at,
            captured_date=date(2026, 3, 26),
            metadata={"panel_discovery_status": "available"},
        )
        IOLMarketUniverseSnapshot.objects.create(
            pais="argentina",
            pais_key="argentina",
            instrumento="Bonos",
            instrumento_key="bonos",
            panel="",
            panel_key="",
            source="iol",
            captured_at=captured_at,
            captured_date=date(2026, 3, 26),
            metadata={"panel_discovery_status": "empty"},
        )

        payload = IOLMarketUniverseService().list_latest_universe(pais="argentina")

        assert payload["captured_date"] == "2026-03-26"
        assert payload["count"] == 2
        assert payload["panel_count"] == 1
        assert len(payload["countries"]) == 1
        assert payload["countries"][0]["pais"] == "argentina"
        assert payload["countries"][0]["instrumentos"][0]["paneles"] == [
            {"panel": "Cedears", "panel_key": "cedears"}
        ]
        assert payload["countries"][0]["instrumentos"][1]["metadata"]["panel_discovery_status"] == "empty"
