from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.portafolio_iol.models import PortfolioSnapshot, PositionSnapshot


@pytest.mark.django_db(transaction=True)
class TestPortfolioSnapshotConstraints:
    def test_database_rejects_negative_snapshot_amounts(self):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                PortfolioSnapshot.objects.create(
                    fecha="2026-03-27",
                    total_iol=Decimal("-1.00"),
                    liquidez_operativa=Decimal("100.00"),
                    cash_management=Decimal("50.00"),
                    portafolio_invertido=Decimal("200.00"),
                    rendimiento_total=1.5,
                    exposicion_usa=40,
                    exposicion_argentina=60,
                )

    def test_database_rejects_exposure_outside_valid_range(self):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                PortfolioSnapshot.objects.create(
                    fecha="2026-03-27",
                    total_iol=Decimal("300.00"),
                    liquidez_operativa=Decimal("100.00"),
                    cash_management=Decimal("50.00"),
                    portafolio_invertido=Decimal("200.00"),
                    rendimiento_total=1.5,
                    exposicion_usa=120,
                    exposicion_argentina=60,
                )


@pytest.mark.django_db(transaction=True)
class TestPositionSnapshotConstraints:
    def test_database_rejects_weight_above_100(self):
        snapshot = PortfolioSnapshot.objects.create(
            fecha="2026-03-27",
            total_iol=Decimal("300.00"),
            liquidez_operativa=Decimal("100.00"),
            cash_management=Decimal("50.00"),
            portafolio_invertido=Decimal("200.00"),
            rendimiento_total=1.5,
            exposicion_usa=40,
            exposicion_argentina=60,
        )

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                PositionSnapshot.objects.create(
                    snapshot=snapshot,
                    simbolo="AAPL",
                    descripcion="Apple",
                    valorizado=Decimal("100.00"),
                    peso=120,
                    sector="Tecnologia",
                    pais="USA",
                    tipo="cedear",
                    bloque_estrategico="usa",
                )
