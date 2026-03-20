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
            moneda='peso_Argentino',
            disponible=1000.00,
            comprometido=0.00,
            saldo=1000.00,
            titulos_valorizados=0.00,
            total=1000.00,
            total_en_pesos=1000.00,
            saldos_detalle=[{"liquidacion": "inmediato", "disponibleOperar": 1000.00}],
            estado='activa',
        )
        expected = f"{resumen.numero_cuenta} - {resumen.fecha_extraccion}"
        assert str(resumen) == expected
        assert resumen.moneda == 'peso_Argentino'
        assert resumen.total_en_pesos == 1000.00
        assert resumen.saldos_detalle[0]["disponibleOperar"] == 1000.00
