from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.core.models import Alert
from apps.core.tasks.portfolio_tasks import (
    _normalize_alert,
    calculate_temporal_metrics,
    comprehensive_portfolio_update,
    generate_alerts,
    generate_daily_snapshot,
    generate_rebalance_suggestions,
    sync_portfolio_data,
)


@pytest.mark.django_db
@pytest.mark.celery_always_eager
class TestPortfolioTasks:
    def test_normalize_alert_fills_defaults_and_maps_severity(self):
        normalized = _normalize_alert({"severidad": "high"})

        assert normalized["tipo"] == "concentracion_excesiva"
        assert normalized["mensaje"] == "Alerta sin detalle"
        assert normalized["severidad"] == "critical"

    def test_normalize_alert_falls_back_for_unknown_severity(self):
        normalized = _normalize_alert({"tipo": "custom", "mensaje": "x", "severidad": "rare"})

        assert normalized["tipo"] == "custom"
        assert normalized["severidad"] == "warning"

    @patch("apps.core.tasks.portfolio_tasks.PortfolioSnapshotService")
    def test_sync_portfolio_data_success(self, MockService):
        MockService.return_value.sync_iol_data.return_value = {
            "success": True,
            "message": "Sync OK",
        }
        result = sync_portfolio_data()
        assert result["success"] is True

    @patch("apps.core.tasks.portfolio_tasks.PortfolioSnapshotService")
    def test_sync_portfolio_data_failure(self, MockService):
        MockService.return_value.sync_iol_data.return_value = {
            "success": False,
            "message": "Sync failed",
        }
        result = sync_portfolio_data()
        assert result["success"] is False

    @patch("apps.core.tasks.portfolio_tasks.PortfolioSnapshotService")
    def test_sync_portfolio_data_exception(self, MockService):
        MockService.return_value.sync_iol_data.side_effect = Exception("Error")
        result = sync_portfolio_data()
        assert result["success"] is False
        assert "Error" in result["message"]

    @patch("apps.core.tasks.portfolio_tasks.PortfolioSnapshotService")
    def test_sync_portfolio_data_wraps_non_dict_results(self, MockService):
        MockService.return_value.sync_iol_data.return_value = True

        result = sync_portfolio_data()

        assert result == {"success": True, "message": "Sync OK"}

    @patch("apps.core.tasks.portfolio_tasks.PortfolioSnapshotService")
    def test_generate_daily_snapshot_success(self, MockService):
        MockService.return_value.generate_daily_snapshot.return_value = {
            "success": True,
            "message": "Snapshot OK",
        }
        result = generate_daily_snapshot()
        assert result["success"] is True

    @patch("apps.core.tasks.portfolio_tasks.PortfolioSnapshotService")
    def test_generate_daily_snapshot_exception(self, MockService):
        MockService.return_value.generate_daily_snapshot.side_effect = Exception("Error")
        result = generate_daily_snapshot()
        assert result["success"] is False

    @patch("apps.core.tasks.portfolio_tasks.PortfolioSnapshotService")
    def test_generate_daily_snapshot_wraps_snapshot_object(self, MockService):
        MockService.return_value.generate_daily_snapshot.return_value = MagicMock(fecha="2026-03-13")

        result = generate_daily_snapshot()

        assert result["success"] is True
        assert "2026-03-13" in result["message"]

    @patch("apps.core.tasks.portfolio_tasks.PortfolioSnapshotService")
    def test_generate_daily_snapshot_wraps_none_as_failure(self, MockService):
        MockService.return_value.generate_daily_snapshot.return_value = None

        result = generate_daily_snapshot()

        assert result == {"success": False, "message": "Snapshot failed"}

    @patch("apps.core.tasks.portfolio_tasks.AlertsEngine")
    def test_generate_alerts_success(self, MockEngine):
        MockEngine.return_value.generate_alerts.return_value = [
            {"severidad": "high", "mensaje": "Test alert"}
        ]
        result = generate_alerts()
        assert result["success"] is True
        assert result["alerts_count"] == 1

    @patch("apps.core.tasks.portfolio_tasks.AlertsEngine")
    def test_generate_alerts_exception(self, MockEngine):
        MockEngine.return_value.generate_alerts.side_effect = Exception("Error")
        result = generate_alerts()
        assert result["success"] is False

    @patch("apps.core.tasks.portfolio_tasks.AlertsEngine")
    def test_generate_alerts_skips_existing_and_deactivates_expired(self, MockEngine):
        Alert.objects.create(
            tipo="concentracion_excesiva",
            mensaje="Existente",
            severidad="warning",
            is_active=True,
            is_acknowledged=False,
        )
        expired = Alert.objects.create(
            tipo="liquidez_excesiva",
            mensaje="Expirada",
            severidad="warning",
            is_active=True,
            is_acknowledged=False,
        )
        MockEngine.return_value.generate_alerts.return_value = [
            {"tipo": "concentracion_excesiva", "mensaje": "Existente", "severidad": "high"}
        ]

        result = generate_alerts()

        expired.refresh_from_db()
        assert result["success"] is True
        assert result["new_alerts_count"] == 0
        assert expired.is_active is False

    @patch("apps.core.tasks.portfolio_tasks.TemporalMetricsService")
    def test_calculate_temporal_metrics_success(self, MockService):
        MockService.return_value.get_portfolio_returns.return_value = 5.0
        MockService.return_value.get_portfolio_volatility.return_value = 2.0
        result = calculate_temporal_metrics()
        assert result["success"] is True
        assert result["periods_calculated"] == [7, 30, 90, 180]

    @patch("apps.core.tasks.portfolio_tasks.TemporalMetricsService")
    def test_calculate_temporal_metrics_exception(self, MockService):
        MockService.return_value.get_portfolio_returns.side_effect = Exception("Error")
        result = calculate_temporal_metrics()
        assert result["success"] is False

    @patch("apps.core.tasks.portfolio_tasks.RebalanceEngine")
    def test_generate_rebalance_suggestions_success(self, MockEngine):
        MockEngine.return_value.generate_rebalance_suggestions.return_value = ["s1", "s2"]
        MockEngine.return_value.get_critical_actions.return_value = []
        result = generate_rebalance_suggestions()
        assert result["success"] is True
        assert result["suggestions_count"] == 2

    @patch("apps.core.tasks.portfolio_tasks.RebalanceEngine")
    def test_generate_rebalance_suggestions_exception(self, MockEngine):
        MockEngine.return_value.generate_rebalance_suggestions.side_effect = Exception("Error")
        result = generate_rebalance_suggestions()
        assert result["success"] is False

    @patch("apps.core.tasks.portfolio_tasks.RebalanceEngine")
    def test_generate_rebalance_suggestions_counts_critical_actions(self, MockEngine):
        MockEngine.return_value.generate_rebalance_suggestions.return_value = ["s1"]
        MockEngine.return_value.get_critical_actions.return_value = ["c1", "c2"]

        result = generate_rebalance_suggestions()

        assert result["critical_actions_count"] == 2

    @patch("apps.core.tasks.portfolio_tasks.generate_rebalance_suggestions.delay")
    @patch("apps.core.tasks.portfolio_tasks.calculate_temporal_metrics.delay")
    @patch("apps.core.tasks.portfolio_tasks.generate_alerts.delay")
    @patch("apps.core.tasks.portfolio_tasks.generate_daily_snapshot.delay")
    @patch("apps.core.tasks.portfolio_tasks.sync_portfolio_data.delay")
    @patch("apps.core.tasks.portfolio_tasks.timezone.now")
    def test_comprehensive_portfolio_update_launches_snapshot_at_6am(
        self,
        mock_now,
        mock_sync,
        mock_snapshot,
        mock_alerts,
        mock_metrics,
        mock_rebalance,
    ):
        mock_now.return_value = datetime(2026, 3, 13, 6, 0, tzinfo=timezone.get_current_timezone())
        mock_sync.return_value = MagicMock(id="sync")
        mock_snapshot.return_value = MagicMock(id="snapshot")
        mock_alerts.return_value = MagicMock(id="alerts")
        mock_metrics.return_value = MagicMock(id="metrics")
        mock_rebalance.return_value = MagicMock(id="rebalance")

        result = comprehensive_portfolio_update()

        assert result["snapshot_launched"] is True
        assert result["task_ids"]["snapshot"] == "snapshot"

    @patch("apps.core.tasks.portfolio_tasks.generate_rebalance_suggestions.delay")
    @patch("apps.core.tasks.portfolio_tasks.calculate_temporal_metrics.delay")
    @patch("apps.core.tasks.portfolio_tasks.generate_alerts.delay")
    @patch("apps.core.tasks.portfolio_tasks.generate_daily_snapshot.delay")
    @patch("apps.core.tasks.portfolio_tasks.sync_portfolio_data.delay")
    @patch("apps.core.tasks.portfolio_tasks.timezone.now")
    def test_comprehensive_portfolio_update_skips_snapshot_outside_6am(
        self,
        mock_now,
        mock_sync,
        mock_snapshot,
        mock_alerts,
        mock_metrics,
        mock_rebalance,
    ):
        mock_now.return_value = datetime(2026, 3, 13, 9, 0, tzinfo=timezone.get_current_timezone())
        mock_sync.return_value = MagicMock(id="sync")
        mock_alerts.return_value = MagicMock(id="alerts")
        mock_metrics.return_value = MagicMock(id="metrics")
        mock_rebalance.return_value = MagicMock(id="rebalance")

        result = comprehensive_portfolio_update()

        mock_snapshot.assert_not_called()
        assert result["snapshot_launched"] is False
        assert "snapshot" not in result["task_ids"]
