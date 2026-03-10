import pytest
from apps.parametros.models import ParametroActivo, ConfiguracionDashboard
from apps.core.constants import PAISES_PORTAFOLIO, ESTADOS_OPERACION, TIPOS_CUENTA, MONEDAS


@pytest.mark.django_db
class TestParametroActivoModel:

    def test_str_representation(self):
        pa = ParametroActivo.objects.create(
            simbolo='AAPL',
            sector='Tecnología',
            bloque_estrategico='Growth',
            pais_exposicion='USA',
            tipo_patrimonial='Growth',
        )
        assert str(pa) == 'AAPL - Tecnología'


@pytest.mark.django_db
class TestConfiguracionDashboardModel:

    def test_str_representation(self):
        config = ConfiguracionDashboard.objects.create(
            clave='test_clave',
            valor='test_valor',
        )
        assert str(config) == 'test_clave: test_valor'


class TestConstants:

    def test_paises_portafolio(self):
        assert 'argentina' in PAISES_PORTAFOLIO

    def test_estados_operacion(self):
        assert 'pendiente' in ESTADOS_OPERACION
        assert len(ESTADOS_OPERACION) == 4

    def test_tipos_cuenta(self):
        assert 'margen' in TIPOS_CUENTA

    def test_monedas(self):
        assert 'ARS' in MONEDAS
        assert 'USD' in MONEDAS