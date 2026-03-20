from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.services.data_quality.snapshot_integrity import SnapshotIntegrityService
from apps.portafolio_iol.models import PortfolioSnapshot


@pytest.mark.django_db
class TestSnapshotIntegrityService:
    def test_no_snapshots_returns_warning(self):
        result = SnapshotIntegrityService().run_checks(days=30)
        assert result["warning"] == "no_snapshots"
        assert result["duplicate_dates"] == []

    def test_detects_extreme_changes_and_valuation_inconsistencies(self):
        today = timezone.now().date()
        PortfolioSnapshot.objects.create(
            fecha=today - timedelta(days=2),
            total_iol=1000,
            liquidez_operativa=100,
            cash_management=50,
            portafolio_invertido=850,
            rendimiento_total=0,
            exposicion_usa=50,
            exposicion_argentina=50,
        )
        PortfolioSnapshot.objects.create(
            fecha=today - timedelta(days=1),
            total_iol=2000,  # salto extremo +100%
            liquidez_operativa=100,
            cash_management=50,
            portafolio_invertido=850,  # inconsistente vs total
            rendimiento_total=0,
            exposicion_usa=50,
            exposicion_argentina=50,
        )
        PortfolioSnapshot.objects.create(
            fecha=today,
            total_iol=2100,
            liquidez_operativa=200,
            cash_management=100,
            portafolio_invertido=1800,
            rendimiento_total=0,
            exposicion_usa=50,
            exposicion_argentina=50,
        )

        result = SnapshotIntegrityService().run_checks(days=30)
        assert result["issues_count"] > 0
        assert len(result["extreme_changes"]) >= 1
        assert len(result["valuation_inconsistencies"]) >= 1

    def test_uses_explicit_liquidity_layers_when_available(self):
        today = timezone.now().date()
        PortfolioSnapshot.objects.create(
            fecha=today - timedelta(days=1),
            total_iol=2100,
            liquidez_operativa=200,
            cash_management=100,
            portafolio_invertido=1500,
            total_patrimonio_modelado=2100,
            cash_disponible_broker=200,
            caucion_colocada=300,
            rendimiento_total=0,
            exposicion_usa=50,
            exposicion_argentina=50,
        )
        PortfolioSnapshot.objects.create(
            fecha=today,
            total_iol=2200,
            liquidez_operativa=250,
            cash_management=100,
            portafolio_invertido=1600,
            total_patrimonio_modelado=2100,
            cash_disponible_broker=250,
            caucion_colocada=300,
            rendimiento_total=0,
            exposicion_usa=50,
            exposicion_argentina=50,
        )

        result = SnapshotIntegrityService().run_checks(days=30)

        assert any(
            issue["reference_field"] == "total_patrimonio_modelado"
            for issue in result["valuation_inconsistencies"]
        )
