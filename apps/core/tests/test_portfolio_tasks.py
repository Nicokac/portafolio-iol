import pytest
from unittest.mock import patch, MagicMock
from apps.core.tasks.portfolio_tasks import (
    sync_portfolio_data,
    generate_daily_snapshot,
    generate_alerts,
    calculate_temporal_metrics,
    generate_rebalance_suggestions,
    comprehensive_portfolio_update,
)


@pytest.mark.django_db
class TestPortfolioTasks:

    @patch('apps.core.tasks.portfolio_tasks.PortfolioSnapshotService')
    def test_sync_portfolio_data_success(self, MockService):
        MockService.return_value.sync_iol_data.return_value = {
            'success': True, 'message': 'Sync OK'
        }
        result = sync_portfolio_data()
        assert result['success'] is True

    @patch('apps.core.tasks.portfolio_tasks.PortfolioSnapshotService')
    def test_sync_portfolio_data_failure(self, MockService):
        MockService.return_value.sync_iol_data.return_value = {
            'success': False, 'message': 'Sync failed'
        }
        result = sync_portfolio_data()
        assert result['success'] is False

    @patch('apps.core.tasks.portfolio_tasks.PortfolioSnapshotService')
    def test_sync_portfolio_data_exception(self, MockService):
        MockService.return_value.sync_iol_data.side_effect = Exception('Error')
        result = sync_portfolio_data()
        assert result['success'] is False
        assert 'Error' in result['message']

    @patch('apps.core.tasks.portfolio_tasks.PortfolioSnapshotService')
    def test_generate_daily_snapshot_success(self, MockService):
        MockService.return_value.generate_daily_snapshot.return_value = {
            'success': True, 'message': 'Snapshot OK'
        }
        result = generate_daily_snapshot()
        assert result['success'] is True

    @patch('apps.core.tasks.portfolio_tasks.PortfolioSnapshotService')
    def test_generate_daily_snapshot_exception(self, MockService):
        MockService.return_value.generate_daily_snapshot.side_effect = Exception('Error')
        result = generate_daily_snapshot()
        assert result['success'] is False

    @patch('apps.core.tasks.portfolio_tasks.AlertsEngine')
    def test_generate_alerts_success(self, MockEngine):
        MockEngine.return_value.generate_alerts.return_value = [
            {'severidad': 'high', 'mensaje': 'Test alert'}
        ]
        result = generate_alerts()
        assert result['success'] is True
        assert result['alerts_count'] == 1

    @patch('apps.core.tasks.portfolio_tasks.AlertsEngine')
    def test_generate_alerts_exception(self, MockEngine):
        MockEngine.return_value.generate_alerts.side_effect = Exception('Error')
        result = generate_alerts()
        assert result['success'] is False

    @patch('apps.core.tasks.portfolio_tasks.TemporalMetricsService')
    def test_calculate_temporal_metrics_success(self, MockService):
        MockService.return_value.get_portfolio_returns.return_value = 5.0
        MockService.return_value.get_portfolio_volatility.return_value = 2.0
        result = calculate_temporal_metrics()
        assert result['success'] is True
        assert result['periods_calculated'] == [7, 30, 90, 180]

    @patch('apps.core.tasks.portfolio_tasks.TemporalMetricsService')
    def test_calculate_temporal_metrics_exception(self, MockService):
        MockService.return_value.get_portfolio_returns.side_effect = Exception('Error')
        result = calculate_temporal_metrics()
        assert result['success'] is False

    @patch('apps.core.tasks.portfolio_tasks.RebalanceEngine')
    def test_generate_rebalance_suggestions_success(self, MockEngine):
        MockEngine.return_value.generate_rebalance_suggestions.return_value = ['s1', 's2']
        MockEngine.return_value.get_critical_actions.return_value = []
        result = generate_rebalance_suggestions()
        assert result['success'] is True
        assert result['suggestions_count'] == 2

    @patch('apps.core.tasks.portfolio_tasks.RebalanceEngine')
    def test_generate_rebalance_suggestions_exception(self, MockEngine):
        MockEngine.return_value.generate_rebalance_suggestions.side_effect = Exception('Error')
        result = generate_rebalance_suggestions()
        assert result['success'] is False

    @patch('apps.core.tasks.portfolio_tasks.sync_portfolio_data')
    @patch('apps.core.tasks.portfolio_tasks.generate_alerts')
    @patch('apps.core.tasks.portfolio_tasks.calculate_temporal_metrics')
    @patch('apps.core.tasks.portfolio_tasks.generate_rebalance_suggestions')
    def test_comprehensive_portfolio_update_success(
        self, mock_rebalance, mock_metrics, mock_alerts, mock_sync
    ):
        mock_sync.return_value = {'success': True, 'message': 'OK'}
        mock_alerts.return_value = {'success': True, 'message': 'OK'}
        mock_metrics.return_value = {'success': True, 'message': 'OK'}
        mock_rebalance.return_value = {'success': True, 'message': 'OK'}
        result = comprehensive_portfolio_update()
        assert result['success'] is True

    @patch('apps.core.tasks.portfolio_tasks.sync_portfolio_data')
    @patch('apps.core.tasks.portfolio_tasks.generate_alerts')
    @patch('apps.core.tasks.portfolio_tasks.calculate_temporal_metrics')
    @patch('apps.core.tasks.portfolio_tasks.generate_rebalance_suggestions')
    def test_comprehensive_portfolio_update_partial_failure(
        self, mock_rebalance, mock_metrics, mock_alerts, mock_sync
    ):
        mock_sync.return_value = {'success': False, 'message': 'Failed'}
        mock_alerts.return_value = {'success': True, 'message': 'OK'}
        mock_metrics.return_value = {'success': True, 'message': 'OK'}
        mock_rebalance.return_value = {'success': True, 'message': 'OK'}
        result = comprehensive_portfolio_update()
        assert result['success'] is False