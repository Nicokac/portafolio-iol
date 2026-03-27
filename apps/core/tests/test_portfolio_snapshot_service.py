import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal
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
            'liquidez_operativa': 1200.0,
            'fci_cash_management': 1000.0,
            'portafolio_invertido': 7000.0,
            'total_patrimonio_modelado': 10000.0,
            'cash_disponible_broker': 1200.0,
            'caucion_colocada': 800.0,
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
        assert snapshot.total_patrimonio_modelado == mock_kpis['total_patrimonio_modelado']
        assert snapshot.cash_disponible_broker == mock_kpis['cash_disponible_broker']
        assert snapshot.caucion_colocada == mock_kpis['caucion_colocada']

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
            total_patrimonio_modelado=5000,
            cash_disponible_broker=1000,
            caucion_colocada=0,
            rendimiento_total=3.0,
            exposicion_usa=60.0,
            exposicion_argentina=40.0,
        )
        snapshot = service.generate_daily_snapshot()
        assert snapshot.pk == existing.pk
        assert PortfolioSnapshot.objects.count() == 1
        snapshot.refresh_from_db()
        assert snapshot.total_iol == mock_kpis['total_iol']
        assert snapshot.total_patrimonio_modelado == mock_kpis['total_patrimonio_modelado']
        assert getattr(snapshot, '_refresh_action') == 'refreshed'

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
            'liquidez_operativa': 1200.0,
            'fci_cash_management': 1000.0,
            'portafolio_invertido': 7000.0,
            'total_patrimonio_modelado': 10000.0,
            'cash_disponible_broker': 1200.0,
            'caucion_colocada': 800.0,
            'rendimiento_total_porcentaje': 5.5,
        }
        mock_pais.return_value = {'USA': 5000.0, 'Argentina': 2000.0}
        mock_portafolio.return_value = {'inversion': [], 'liquidez': [], 'fci_cash_management': []}
        service.api_client.get_estado_cuenta.return_value = {
            'totalEnPesos': 26317309.04,
            'cuentas': [{
                'numero': '123',
                'tipo': 'CA',
                'moneda': 'peso_Argentino',
                'disponible': 1000.0,
                'comprometido': 0.0,
                'saldo': 1000.0,
                'titulosValorizados': 0.0,
                'total': 1000.0,
                'saldos': [
                    {
                        'liquidacion': 'inmediato',
                        'saldo': 1000.0,
                        'comprometido': 0.0,
                        'disponible': 1000.0,
                        'disponibleOperar': 1000.0,
                    }
                ],
                'estado': 'activa',
            }]
        }
        service.api_client.get_portafolio.return_value = {
            'activos': [{
                'titulo': {
                    'simbolo': 'AAPL',
                    'descripcion': 'Cedear Apple Inc.',
                    'pais': 'argentina',
                    'mercado': 'bcba',
                    'tipo': 'CEDEARS',
                    'moneda': 'peso_Argentino',
                    'plazo': 't1',
                },
                'cantidad': 64,
                'comprometido': 1,
                'puntosVariacion': 0,
                'variacionDiaria': 0.38,
                'ultimoPrecio': 18340,
                'ppc': 13755.812,
                'gananciaPorcentaje': 33.32,
                'gananciaDinero': 293388,
                'valorizado': 1173760,
                'parking': None,
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
        service.api_client.get_operaciones.assert_called_once()
        assert service.api_client.get_operaciones.call_args.args[0]["estado"] == "todas"
        assert service.api_client.get_operaciones.call_args.args[0]["pais"] == "argentina"
        assert "fecha_desde" in service.api_client.get_operaciones.call_args.args[0]
        assert ResumenCuentaSnapshot.objects.count() == 1
        resumen = ResumenCuentaSnapshot.objects.get()
        assert resumen.moneda == 'peso_Argentino'
        assert float(resumen.total_en_pesos) == 26317309.04
        assert resumen.saldos_detalle[0]['disponibleOperar'] == 1000.0
        assert ActivoPortafolioSnapshot.objects.count() == 1
        activo = ActivoPortafolioSnapshot.objects.get()
        assert activo.moneda == 'peso_Argentino'
        assert activo.plazo == 't1'
        assert activo.ppc == Decimal('13755.812000')
        assert activo.ultimo_precio == Decimal('18340.000000')
        assert activo.parking is None
        assert OperacionIOL.objects.count() == 1
        assert PortfolioSnapshot.objects.count() == 1

    def test_sync_iol_data_exception(self, service):
        service.api_client.get_estado_cuenta.side_effect = Exception('Network error')
        result = service.sync_iol_data()
        assert result["success"] is False

    def test_extract_country_exposures_normalizes_absolute_amounts(self, service):
        usa, argentina = service._extract_country_exposures(
            {
                'USA': 6428750.0,
                'Argentina': 4223603.6742,
                'Latam': 885150.0,
                'Europa': 780020.0,
            }
        )

        assert 0 <= usa <= 100
        assert 0 <= argentina <= 100
        assert usa == pytest.approx(52.1919, rel=1e-4)
        assert argentina == pytest.approx(34.2863, rel=1e-4)

    def test_extract_country_exposures_preserves_percentage_distribution(self, service):
        usa, argentina = service._extract_country_exposures(
            {
                'USA': 60.0,
                'Argentina': 40.0,
            }
        )

        assert usa == 60.0
        assert argentina == 40.0
