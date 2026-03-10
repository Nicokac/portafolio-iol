import pytest
from apps.core.services.rebalance_engine import (
    RebalanceEngine,
    ConcentrationRebalance,
    LiquidityRebalance,
    CountryDiversificationRebalance,
    SectorDiversificationRebalance,
)


class TestRebalanceRules:

    def test_concentration_rebalance_with_signals(self):
        rule = ConcentrationRebalance(max_concentration=15.0)
        data = {'senales_rebalanceo': [
            {'tipo': 'concentracion', 'activo': 'AAPL', 'porcentaje': 25.0}
        ]}
        result = rule.analyze(data)
        assert result['regla'] == 'concentracion_maxima'
        assert len(result['sugerencias']) == 1
        assert result['sugerencias'][0]['accion'] == 'reducir'

    def test_concentration_rebalance_no_signals(self):
        rule = ConcentrationRebalance()
        result = rule.analyze({'senales_rebalanceo': []})
        assert result['sugerencias'] == []

    def test_liquidity_rebalance_too_low(self):
        rule = LiquidityRebalance(min_liquidity=10.0, max_liquidity=30.0)
        result = rule.analyze({'pct_liquidez_operativa': 5.0})
        assert len(result['sugerencias']) == 1
        assert result['sugerencias'][0]['accion'] == 'incrementar_liquidez'

    def test_liquidity_rebalance_too_high(self):
        rule = LiquidityRebalance(min_liquidity=10.0, max_liquidity=30.0)
        result = rule.analyze({'pct_liquidez_operativa': 45.0})
        assert len(result['sugerencias']) == 1
        assert result['sugerencias'][0]['accion'] == 'invertir_liquidez'

    def test_liquidity_rebalance_optimal(self):
        rule = LiquidityRebalance(min_liquidity=10.0, max_liquidity=30.0)
        result = rule.analyze({'pct_liquidez_operativa': 20.0})
        assert result['sugerencias'] == []

    def test_country_diversification_triggered(self):
        rule = CountryDiversificationRebalance(max_country_exposure=50.0)
        result = rule.analyze({'concentracion_pais': {'USA': 70.0, 'Argentina': 30.0}})
        assert len(result['sugerencias']) == 1
        assert result['sugerencias'][0]['pais'] == 'USA'

    def test_country_diversification_not_triggered(self):
        rule = CountryDiversificationRebalance(max_country_exposure=50.0)
        result = rule.analyze({'concentracion_pais': {'USA': 40.0, 'Argentina': 60.0}})
        assert len(result['sugerencias']) == 1
        assert result['sugerencias'][0]['pais'] == 'Argentina'

    def test_country_diversification_empty(self):
        rule = CountryDiversificationRebalance()
        result = rule.analyze({'concentracion_pais': {}})
        assert result['sugerencias'] == []

    def test_sector_diversification_triggered(self):
        rule = SectorDiversificationRebalance(max_sector_exposure=25.0)
        result = rule.analyze({'concentracion_sector': {'Tecnología': 40.0}})
        assert len(result['sugerencias']) == 1
        assert result['sugerencias'][0]['sector'] == 'Tecnología'

    def test_sector_diversification_not_triggered(self):
        rule = SectorDiversificationRebalance(max_sector_exposure=25.0)
        result = rule.analyze({'concentracion_sector': {'Tecnología': 20.0}})
        assert result['sugerencias'] == []


@pytest.mark.django_db
class TestRebalanceEngine:

    def test_engine_has_four_rules(self):
        engine = RebalanceEngine()
        assert len(engine.rules) == 4

    def test_generate_rebalance_suggestions_returns_list(self):
        engine = RebalanceEngine()
        result = engine.generate_rebalance_suggestions()
        assert isinstance(result, list)

    def test_get_critical_actions_returns_list(self):
        engine = RebalanceEngine()
        result = engine.get_critical_actions()
        assert isinstance(result, list)

    def test_get_opportunity_actions_returns_list(self):
        engine = RebalanceEngine()
        result = engine.get_opportunity_actions()
        assert isinstance(result, list)