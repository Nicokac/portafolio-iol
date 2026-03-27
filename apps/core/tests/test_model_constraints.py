from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.core.models import PortfolioParameters


@pytest.mark.django_db(transaction=True)
class TestPortfolioParametersConstraints:
    def test_model_meta_exposes_database_constraints(self):
        constraint_names = {constraint.name for constraint in PortfolioParameters._meta.constraints}

        assert "portfolio_params_target_range_valid" in constraint_names
        assert "portfolio_params_risk_range_valid" in constraint_names
        assert "portfolio_params_target_allocation_100" in constraint_names

    def test_database_rejects_invalid_total_target_allocation(self):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                PortfolioParameters.objects.create(
                    name="Asignacion invalida",
                    liquidez_target=Decimal("10.00"),
                    usa_target=Decimal("40.00"),
                    argentina_target=Decimal("30.00"),
                    emerging_target=Decimal("10.00"),
                )

    def test_database_rejects_invalid_risk_range(self):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                PortfolioParameters.objects.create(
                    name="Riesgo invalido",
                    max_single_position=Decimal("120.00"),
                )
