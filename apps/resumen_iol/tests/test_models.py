import pytest
from django.utils import timezone

from apps.resumen_iol.models import ResumenCuentaSnapshot


@pytest.mark.django_db
class TestResumenCuentaSnapshot:
    def test_str_representation(self):
        resumen = ResumenCuentaSnapshot.objects.create(
            fecha_extraccion=timezone.now(),
            numero_cuenta='12345',
            tipo_cuenta='CA',
            moneda='ARS',
            disponible=1000.00,
            comprometido=0.00,
            saldo=1000.00,
            titulos_valorizados=0.00,
            total=1000.00,
            estado='activa',
        )
        expected = f"{resumen.numero_cuenta} - {resumen.fecha_extraccion}"
        assert str(resumen) == expected