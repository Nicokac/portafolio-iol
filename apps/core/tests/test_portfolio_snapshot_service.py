import pytest
from unittest.mock import MagicMock, patch
from django.utils import timezone
from apps.core.services.portfolio_snapshot_service import PortfolioSnapshotService
from apps.operaciones_iol.models import OperacionIOL
from apps.portafolio_iol.models import ActivoPortafolioSnapshot
from apps.portafolio_iol.models import PortfolioSnapshot
from apps.resumen_iol.models import ResumenCuentaSnapshot


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
        assert result["success"] is False

    def test_sync_iol_data_no_portafolio(self, service):
        service.api_client.get_estado_cuenta.return_value = {'cuentas': []}
        service.api_client.get_portafolio.return_value = None
        result = service.sync_iol_data()
        assert result["success"] is False

    @patch('apps.core.services.portfolio_snapshot_service.get_dashboard_kpis')
    @patch('apps.core.services.portfolio_snapshot_service.get_distribucion_pais')
    @patch('apps.core.services.portfolio_snapshot_service.get_portafolio_enriquecido_actual')
    def test_sync_iol_data_success(self, mock_portafolio, mock_pais, mock_kpis_fn, service):
        mock_kpis_fn.return_value = {
            'total_iol': 10000.0,
            'liquidez_operativa': 2000.0,
            'fci_cash_management': 1000.0,
            'portafolio_invertido': 7000.0,
            'rendimiento_total_porcentaje': 5.5,
        }
        mock_pais.return_value = {'USA': 5000.0, 'Argentina': 2000.0}
        mock_portafolio.return_value = {'inversion': [], 'liquidez': [], 'fci_cash_management': []}
        service.api_client.get_estado_cuenta.return_value = {
            'cuentas': [{
                'numero': '123',
                'tipo': 'CA',
                'moneda': 'ARS',
                'disponible': 1000.0,
                'comprometido': 0.0,
                'saldo': 1000.0,
                'titulosValorizados': 0.0,
                'total': 1000.0,
                'estado': 'activa',
            }]
        }
        service.api_client.get_portafolio.return_value = {
            'activos': [{
                'titulo': {
                    'simbolo': 'AAPL',
                    'descripcion': 'Apple Inc',
                    'pais': 'USA',
                    'mercado': 'NASDAQ',
                    'tipo': 'CEDEARS',
                    'moneda': 'ARS',
                    'plazo': None,
                },
                'cantidad': 10,
                'comprometido': 1,
                'puntosVariacion': 0.5,
                'variacionDiaria': 1.0,
                'ultimoPrecio': 100.0,
                'ppc': 90.0,
                'gananciaPorcentaje': 11.11,
                'gananciaDinero': 100.0,
                'valorizado': 1000.0,
            }]
        }
        service.api_client.get_operaciones.return_value = [{
            'numero': 1001,
            'fechaOrden': '2026-01-01T10:00:00+00:00',
            'tipo': 'Compra',
            'estado': 'Terminada',
            'mercado': 'BCBA',
            'simbolo': 'GGAL',
            'cantidad': 100,
            'monto': 5000.0,
            'modalidad': 'PRECIO_LIMITE',
        }]
        result = service.sync_iol_data()
        assert result["success"] is True
        assert result["snapshot_generated"] is True
        assert ResumenCuentaSnapshot.objects.count() == 1
        assert ActivoPortafolioSnapshot.objects.count() == 1
        assert OperacionIOL.objects.count() == 1
        assert PortfolioSnapshot.objects.count() == 1

    def test_sync_iol_data_exception(self, service):
        service.api_client.get_estado_cuenta.side_effect = Exception('Network error')
        result = service.sync_iol_data()
        assert result["success"] is False
