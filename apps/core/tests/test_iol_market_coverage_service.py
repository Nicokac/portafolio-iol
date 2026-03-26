from datetime import date
from unittest.mock import Mock

import pytest
from django.utils import timezone

from apps.core.models import IOLMarketCoverageSnapshot
from apps.core.services.iol_market_coverage_service import IOLMarketCoverageService


@pytest.mark.django_db
class TestIOLMarketCoverageService:
    def test_sync_coverage_persists_summary_per_instrument(self):
        client = Mock()
        client.get_bulk_quotes.return_value = {
            "titulos": [
                {
                    "simbolo": "AL30",
                    "ultimoPrecio": 10.0,
                    "volumen": 15,
                    "cantidadOperaciones": 3,
                    "fecha": "2026-03-26T14:55:00",
                    "puntas": {"precioCompra": 9.9, "precioVenta": 10.1},
                },
                {
                    "simbolo": "GD30",
                    "ultimoPrecio": 0.0,
                    "volumen": 0,
                    "cantidadOperaciones": 0,
                    "fecha": "2026-03-26T12:00:00",
                    "puntas": None,
                },
            ]
        }
        universe_service = Mock()
        universe_service.list_latest_coverage = Mock()

        result = IOLMarketCoverageService(client=client, universe_service=universe_service).sync_coverage(
            paises=["argentina"],
            instrumentos=["Bonos"],
            captured_at=timezone.make_aware(timezone.datetime(2026, 3, 26, 15, 0, 0)),
        )

        assert result["success"] is True
        assert result["instruments_processed"] == 1
        assert result["rows_received"] == 2

        snapshot = IOLMarketCoverageSnapshot.objects.get(instrumento="Bonos")
        assert snapshot.total_titles == 2
        assert snapshot.priced_titles == 1
        assert snapshot.order_book_titles == 1
        assert snapshot.active_titles == 1
        assert snapshot.recent_titles == 1
        assert snapshot.stale_titles == 1
        assert float(snapshot.coverage_pct) == 50.0
        assert float(snapshot.order_book_coverage_pct) == 50.0
        assert snapshot.freshness_status == "mixed"
        assert snapshot.metadata["stale_sample_symbols"] == ["GD30"]

    def test_list_latest_coverage_groups_latest_snapshot_only(self):
        captured_at = timezone.make_aware(timezone.datetime(2026, 3, 26, 15, 0, 0))
        previous_at = timezone.make_aware(timezone.datetime(2026, 3, 25, 15, 0, 0))

        IOLMarketCoverageSnapshot.objects.create(
            pais="argentina",
            pais_key="argentina",
            instrumento="Bonos",
            instrumento_key="bonos",
            source="iol_bulk_quotes",
            captured_at=previous_at,
            captured_date=date(2026, 3, 25),
            total_titles=10,
            priced_titles=8,
            order_book_titles=6,
            active_titles=2,
            recent_titles=0,
            stale_titles=3,
            zero_price_titles=2,
            coverage_pct=80,
            order_book_coverage_pct=60,
            activity_pct=20,
            freshness_status="stale",
        )
        IOLMarketCoverageSnapshot.objects.create(
            pais="argentina",
            pais_key="argentina",
            instrumento="Bonos",
            instrumento_key="bonos",
            source="iol_bulk_quotes",
            captured_at=captured_at,
            captured_date=date(2026, 3, 26),
            total_titles=12,
            priced_titles=9,
            order_book_titles=5,
            active_titles=4,
            recent_titles=8,
            stale_titles=1,
            zero_price_titles=3,
            coverage_pct=75,
            order_book_coverage_pct=41.67,
            activity_pct=33.33,
            freshness_status="mixed",
        )

        payload = IOLMarketCoverageService().list_latest_coverage(pais="argentina")

        assert payload["captured_date"] == "2026-03-26"
        assert payload["count"] == 1
        assert payload["countries"][0]["pais"] == "argentina"
        assert payload["countries"][0]["instrumentos"][0]["instrumento"] == "Bonos"
        assert payload["countries"][0]["instrumentos"][0]["freshness_status"] == "mixed"
        assert payload["totals"]["total_titles"] == 12
        assert payload["totals"]["priced_titles"] == 9
