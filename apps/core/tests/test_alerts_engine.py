import pytest
from apps.core.services.alerts_engine import (
    AlertsEngine,
    ConcentrationAlert,
    CountryExposureAlert,
    LiquidityAlert,
    LossAlert,
    SectorExposureAlert,
)


class TestAlertRules:

    def test_concentration_alert_triggered(self):
        rule = ConcentrationAlert(threshold=15.0)
        alert = rule.check({'top_10_concentracion': 60.0})
        assert alert
        assert alert['tipo'] == 'concentracion_excesiva'
        assert alert['severidad'] == 'warning'

    def test_concentration_alert_not_triggered(self):
        rule = ConcentrationAlert(threshold=15.0)
        alert = rule.check({'top_10_concentracion': 40.0})
        assert not alert

    def test_liquidity_alert_triggered(self):
        rule = LiquidityAlert(threshold=40.0)
        alert = rule.check({'pct_liquidez_operativa': 55.0})
        assert alert
        assert alert['tipo'] == 'liquidez_excesiva'
        assert alert['severidad'] == 'info'

    def test_liquidity_alert_not_triggered(self):
        rule = LiquidityAlert(threshold=40.0)
        alert = rule.check({'pct_liquidez_operativa': 20.0})
        assert not alert

    def test_country_exposure_alert_triggered(self):
        rule = CountryExposureAlert(threshold=60.0)
        alert = rule.check({'concentracion_pais': {'USA': 75.0, 'Argentina': 25.0}})
        assert alert
        assert alert['tipo'] == 'exposicion_pais'
        assert 'USA' in alert['mensaje']

    def test_country_exposure_alert_not_triggered(self):
        rule = CountryExposureAlert(threshold=60.0)
        alert = rule.check({'concentracion_pais': {'USA': 50.0, 'Argentina': 50.0}})
        assert not alert

    def test_country_exposure_alert_empty(self):
        rule = CountryExposureAlert(threshold=60.0)
        alert = rule.check({'concentracion_pais': {}})
        assert not alert

    def test_sector_exposure_alert_triggered(self):
        rule = SectorExposureAlert(threshold=30.0)
        alert = rule.check({'concentracion_sector': {'Tecnología': 45.0}})
        assert alert
        assert alert['tipo'] == 'exposicion_sector'

    def test_sector_exposure_alert_not_triggered(self):
        rule = SectorExposureAlert(threshold=30.0)
        alert = rule.check({'concentracion_sector': {'Tecnología': 20.0}})
        assert not alert

    def test_loss_alert_returns_empty(self):
        rule = LossAlert()
        alert = rule.check({})
        assert not alert


@pytest.mark.django_db
class TestAlertsEngine:

    def test_generate_alerts_no_data(self):
        engine = AlertsEngine()
        alerts = engine.generate_alerts()
        assert isinstance(alerts, list)

    def test_generate_alerts_returns_list(self):
        engine = AlertsEngine()
        result = engine.generate_alerts()
        assert isinstance(result, list)
        for alert in result:
            assert 'tipo' in alert
            assert 'mensaje' in alert
            assert 'severidad' in alert

    def test_get_alerts_by_severity_warning(self):
        engine = AlertsEngine()
        alerts = engine.get_alerts_by_severity('warning')
        assert isinstance(alerts, list)
        for alert in alerts:
            assert alert['severidad'] == 'warning'

    def test_get_alerts_by_severity_critical(self):
        engine = AlertsEngine()
        alerts = engine.get_alerts_by_severity('critical')
        assert isinstance(alerts, list)

    def test_engine_has_five_rules(self):
        engine = AlertsEngine()
        assert len(engine.rules) == 5