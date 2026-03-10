import pytest
from unittest.mock import MagicMock, patch
from django.utils import timezone
from apps.core.services.portfolio_snapshot_service import PortfolioSnapshotService
from apps.portafolio_iol.models import PortfolioSnapshot


@pytest.mark.django_db
class TestPortfolioSnapshotService:

    @pytest.fixture
    def service(self):
        service = PortfolioSnapshotService()
        service.api_client = MagicMock()
        return service

    @pytest.fixture
    def mock_kpis(self):
        return {
            'total_iol': 10000.0,
            'liquidez_operativa': 2000.0,
            'fci_cash_management': 1000.0,
            'portafolio_invertido': 7000.0,
            'rendimiento_total_porcentaje': 5.5,
        }

    @patch('apps.core.services.portfolio_snapshot_service.get_dashboard_kpis')
    @patch('apps.core.services.portfolio_snapshot_service.get_distribucion_pais')
    @patch('apps.core.services.portfolio_snapshot_service.get_portafolio_enriquecido_actual')
    def test_generate_daily_snapshot_success(
        self, mock_portafolio, mock_pais, mock_kpis_fn, service, mock_kpis
    ):
        mock_kpis_fn.return_value = mock_kpis
        mock_pais.return_value = {'USA': 5000.0, 'Argentina': 2000.0}
        mock_portafolio.return_value = {'inversion': [], 'liquidez': [], 'fci_cash_management': []}

        snapshot = service.generate_daily_snapshot()
        assert isinstance(snapshot, PortfolioSnapshot)
        assert PortfolioSnapshot.objects.count() == 1

    @patch('apps.core.services.portfolio_snapshot_service.get_dashboard_kpis')
    @patch('apps.core.services.portfolio_snapshot_service.get_distribucion_pais')
    @patch('apps.core.services.portfolio_snapshot_service.get_portafolio_enriquecido_actual')
    def test_generate_daily_snapshot_existing(
        self, mock_portafolio, mock_pais, mock_kpis_fn, service, mock_kpis
    ):
        mock_kpis_fn.return_value = mock_kpis
        mock_pais.return_value = {}
        mock_portafolio.return_value = {'inversion': [], 'liquidez': [], 'fci_cash_management': []}

        today = timezone.now().date()
        existing = PortfolioSnapshot.objects.create(
            fecha=today,
            total_iol=5000,
            liquidez_operativa=1000,
            cash_management=500,
            portafolio_invertido=3500,
            rendimiento_total=3.0,
            exposicion_usa=60.0,
            exposicion_argentina=40.0,
        )
        snapshot = service.generate_daily_snapshot()
        assert snapshot.pk == existing.pk
        assert PortfolioSnapshot.objects.count() == 1

    def test_sync_iol_data_no_estado_cuenta(self, service):
        service.api_client.get_estado_cuenta.return_value = None
        result = service.sync_iol_data()
        assert result is False

    def test_sync_iol_data_no_portafolio(self, service):
        service.api_client.get_estado_cuenta.return_value = {'cuentas': []}
        service.api_client.get_portafolio.return_value = None
        result = service.sync_iol_data()
        assert result is False

    def test_sync_iol_data_success(self, service):
        service.api_client.get_estado_cuenta.return_value = {'cuentas': []}
        service.api_client.get_portafolio.return_value = {'activos': []}
        service.api_client.get_operaciones.return_value = []
        result = service.sync_iol_data()
        assert result is True

    def test_sync_iol_data_exception(self, service):
        service.api_client.get_estado_cuenta.side_effect = Exception('Network error')
        result = service.sync_iol_data()
        assert result is False