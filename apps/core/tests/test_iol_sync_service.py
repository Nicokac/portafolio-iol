import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal
from apps.core.services.iol_sync_service import IOLSyncService
from apps.portafolio_iol.models import ActivoPortafolioSnapshot
from apps.resumen_iol.models import ResumenCuentaSnapshot
from apps.operaciones_iol.models import OperacionIOL


@pytest.mark.django_db
class TestIOLSyncService:

    @pytest.fixture
    def service(self):
        service = IOLSyncService()
        service.client = MagicMock()
        return service

    # --- sync_estado_cuenta ---

    def test_sync_estado_cuenta_no_data(self, service):
        service.client.get_estado_cuenta.return_value = None
        result = service.sync_estado_cuenta()
        assert result is False

    def test_sync_estado_cuenta_success(self, service):
        service.client.get_estado_cuenta.return_value = {
            'totalEnPesos': 26317309.04,
            'cuentas': [{
                'numero': '12345',
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
        result = service.sync_estado_cuenta()
        assert result is True
        assert ResumenCuentaSnapshot.objects.count() == 1
        snapshot = ResumenCuentaSnapshot.objects.get()
        assert snapshot.moneda == 'peso_Argentino'
        assert float(snapshot.total_en_pesos) == 26317309.04
        assert snapshot.saldos_detalle[0]['liquidacion'] == 'inmediato'
        assert snapshot.saldos_detalle[0]['disponibleOperar'] == 1000.0

    def test_sync_estado_cuenta_empty_cuentas(self, service):
        service.client.get_estado_cuenta.return_value = {'cuentas': []}
        result = service.sync_estado_cuenta()
        assert result is True
        assert ResumenCuentaSnapshot.objects.count() == 0

    # --- sync_portafolio ---

    def test_sync_portafolio_no_data(self, service):
        service.client.get_portafolio.return_value = None
        result = service.sync_portafolio()
        assert result is False

    def test_sync_portafolio_success(self, service):
        service.client.get_portafolio.return_value = {
            'activos': [{
                'titulo': {
                    'simbolo': 'AAPL',
                    'descripcion': 'Apple Inc',
                    'pais': 'argentina',
                    'mercado': 'bcba',
                    'tipo': 'CEDEARS',
                    'moneda': 'peso_Argentino',
                    'plazo': 't1',
                },
                'cantidad': 46765.7428,
                'comprometido': 0,
                'puntosVariacion': 0.137598,
                'variacionDiaria': 0.37,
                'ultimoPrecio': 37.128598,
                'ppc': 20.207,
                'gananciaPorcentaje': 83.74,
                'gananciaDinero': 791346.46,
                'valorizado': 1736346.4645925944,
                'parking': None,
            }]
        }
        result = service.sync_portafolio()
        assert result is True
        assert ActivoPortafolioSnapshot.objects.count() == 1
        snapshot = ActivoPortafolioSnapshot.objects.get()
        assert snapshot.moneda == 'peso_Argentino'
        assert snapshot.plazo == 't1'
        assert snapshot.mercado == 'bcba'
        assert snapshot.cantidad == Decimal('46765.7428')
        assert snapshot.puntos_variacion == Decimal('0.137598')
        assert snapshot.ultimo_precio == Decimal('37.128598')
        assert snapshot.ppc == Decimal('20.207000')
        assert snapshot.valorizado == Decimal('1736346.464593')
        assert snapshot.parking is None

    def test_sync_portafolio_missing_key_skips(self, service):
        service.client.get_portafolio.return_value = {
            'activos': [{'titulo': {}}]  # Faltan campos requeridos
        }
        result = service.sync_portafolio()
        assert result is True
        assert ActivoPortafolioSnapshot.objects.count() == 0

    def test_sync_portafolio_empty_activos(self, service):
        service.client.get_portafolio.return_value = {'activos': []}
        result = service.sync_portafolio()
        assert result is True

    # --- sync_operaciones ---

    def test_sync_operaciones_no_data(self, service):
        service.client.get_operaciones.return_value = None
        result = service.sync_operaciones()
        assert result is False

    def test_sync_operaciones_success(self, service):
        service.client.get_operaciones.return_value = [{
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
        result = service.sync_operaciones()
        assert result is True
        assert OperacionIOL.objects.count() == 1

    def test_sync_operaciones_no_duplicate(self, service):
        service.client.get_operaciones.return_value = [{
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
        service.sync_operaciones()
        service.sync_operaciones()
        assert OperacionIOL.objects.count() == 1

    def test_sync_operaciones_missing_key_skips(self, service):
        service.client.get_operaciones.return_value = [{'numero': 1001}]
        result = service.sync_operaciones()
        assert result is True
        assert OperacionIOL.objects.count() == 0

    # --- sync_all ---

    def test_sync_all(self, service):
        service.client.get_estado_cuenta.return_value = None
        service.client.get_portafolio.return_value = None
        service.client.get_operaciones.return_value = None
        results = service.sync_all()
        assert 'estado_cuenta' in results
        assert 'portafolio_argentina' in results
        assert 'operaciones' in results
        assert 'portfolio_snapshot' in results

    @patch('apps.core.services.iol_sync_service.PortfolioSnapshotService', create=True)
    def test_sync_all_generates_snapshot_after_success(self, mock_snapshot_service, service):
        service.client.get_estado_cuenta.return_value = {'cuentas': []}
        service.client.get_portafolio.return_value = {'activos': []}
        service.client.get_operaciones.return_value = []
        mock_snapshot_service.return_value.generate_daily_snapshot.return_value = object()

        results = service.sync_all()

        assert results['portfolio_snapshot'] is True
