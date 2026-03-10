import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch
from apps.core.services.portfolio_simulator import PortfolioSimulator


@pytest.mark.django_db
class TestPortfolioSimulator:

    @pytest.fixture
    def simulator(self):
        return PortfolioSimulator()

    @pytest.fixture
    def portfolio(self):
        return {'total_iol': 10000}

    @pytest.fixture
    def mock_activo(self):
        activo = MagicMock()
        activo.simbolo = 'AAPL'
        activo.ultimo_precio = Decimal('100')
        activo.tipo = 'CEDEARS'
        activo.pais_titulo = 'USA'
        return activo

    @patch('apps.core.services.portfolio_simulator.Activo.objects')
    def test_simulate_purchase_success(self, mock_objects, simulator, portfolio, mock_activo):
        mock_objects.filter.return_value.first.return_value = mock_activo
        result = simulator.simulate_purchase('AAPL', Decimal('1000'), portfolio)
        assert result['accion'] == 'compra'
        assert result['activo'] == 'AAPL'
        assert result['capital_invertido'] == 1000.0

    @patch('apps.core.services.portfolio_simulator.Activo.objects')
    def test_simulate_purchase_activo_not_found(self, mock_objects, simulator, portfolio):
        mock_objects.filter.return_value.first.return_value = None
        result = simulator.simulate_purchase('UNKNOWN', Decimal('1000'), portfolio)
        assert 'error' in result

    @patch('apps.core.services.portfolio_simulator.Activo.objects')
    def test_simulate_sale_success(self, mock_objects, simulator, portfolio, mock_activo):
        mock_objects.filter.return_value.first.return_value = mock_activo
        result = simulator.simulate_sale('AAPL', Decimal('5'), portfolio)
        assert result['accion'] == 'venta'
        assert result['cantidad_vendida'] == 5.0
        assert result['impacto_liquidez'] == 'aumenta'

    @patch('apps.core.services.portfolio_simulator.Activo.objects')
    def test_simulate_sale_activo_not_found(self, mock_objects, simulator, portfolio):
        mock_objects.filter.return_value.first.return_value = None
        result = simulator.simulate_sale('UNKNOWN', Decimal('5'), portfolio)
        assert 'error' in result

    def test_simulate_rebalance_success(self, simulator, portfolio):
        target = {'AAPL': 50.0, 'GGAL': 30.0, 'AL30': 20.0}
        result = simulator.simulate_rebalance(target, portfolio)
        assert result['tipo'] == 'rebalanceo_completo'
        assert len(result['operaciones']) == 3
        assert result['total_portafolio'] == 10000.0

    def test_simulate_rebalance_empty_weights(self, simulator, portfolio):
        result = simulator.simulate_rebalance({}, portfolio)
        assert result['operaciones'] == []

    @patch('apps.core.services.portfolio_simulator.Activo.objects')
    def test_calcular_riesgo_argentina(self, mock_objects, simulator, portfolio, mock_activo):
        mock_activo.pais_titulo = 'Argentina'
        mock_objects.filter.return_value.first.return_value = mock_activo
        result = simulator.simulate_purchase('GGAL', Decimal('1000'), portfolio)
        assert result['riesgo_estimado'] == 'alto'

    @patch('apps.core.services.portfolio_simulator.Activo.objects')
    def test_calcular_riesgo_liquidez(self, mock_objects, simulator, portfolio, mock_activo):
        mock_activo.tipo = 'liquidez'
        mock_activo.pais_titulo = 'USA'
        mock_objects.filter.return_value.first.return_value = mock_activo
        result = simulator.simulate_purchase('CASH', Decimal('1000'), portfolio)
        assert result['riesgo_estimado'] == 'bajo'

    @patch('apps.core.services.portfolio_simulator.Activo.objects')
    def test_evaluar_diversificacion_venta(self, mock_objects, simulator, portfolio, mock_activo):
        mock_objects.filter.return_value.first.return_value = mock_activo
        result = simulator.simulate_sale('AAPL', Decimal('5'), portfolio)
        assert result['diversificacion'] == 'mejora'

    @patch('apps.core.services.portfolio_simulator.Activo.objects')
    def test_simulate_purchase_exception(self, mock_objects, simulator, portfolio):
        mock_objects.filter.side_effect = Exception('DB error')
        result = simulator.simulate_purchase('AAPL', Decimal('1000'), portfolio)
        assert 'error' in result

    @patch('apps.core.services.portfolio_simulator.Activo.objects')
    def test_simulate_sale_exception(self, mock_objects, simulator, portfolio):
        mock_objects.filter.side_effect = Exception('DB error')
        result = simulator.simulate_sale('AAPL', Decimal('5'), portfolio)
        assert 'error' in result

    def test_simulate_rebalance_exception(self, simulator):
        result = simulator.simulate_rebalance({'AAPL': 'invalid'}, {'total_iol': 'not_a_number'})
        assert 'error' in result