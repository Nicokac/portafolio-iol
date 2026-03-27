from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.operaciones_iol.models import OperacionIOL


@pytest.mark.django_db(transaction=True)
class TestOperacionIOLConstraints:
    def test_database_rejects_negative_amount_fields(self):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                OperacionIOL.objects.create(
                    numero="op-negativa",
                    pais_consulta="argentina",
                    fecha_orden=timezone.now(),
                    tipo="compra",
                    estado="pendiente",
                    estado_actual="pendiente",
                    mercado="bcba",
                    simbolo="AAPL",
                    moneda="ARS",
                    cantidad=Decimal("-1"),
                    monto=Decimal("1000"),
                    modalidad="normal",
                )
