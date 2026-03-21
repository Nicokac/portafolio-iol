import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal
from django.utils import timezone
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
        operacion = OperacionIOL.objects.get()
        assert operacion.estado == 'Terminada'
        assert operacion.estado_actual == 'Terminada'
        assert operacion.moneda == ''

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

    def test_sync_operacion_detalle_success(self, service):
        service.client.get_operacion.return_value = {
            'numero': 167788363,
            'mercado': 'bcba',
            'simbolo': 'MCD',
            'moneda': 'peso_Argentino',
            'tipo': 'compra',
            'fechaAlta': '2026-03-18T14:05:53.323',
            'validez': '2026-03-18T17:00:00',
            'fechaOperado': '2026-03-18T14:05:57',
            'estadoActual': 'terminada',
            'estados': [
                {'detalle': 'Iniciada', 'fecha': '2026-03-18T14:05:53.323'},
                {'detalle': 'Terminada', 'fecha': '2026-03-18T14:05:58.507'},
            ],
            'aranceles': [
                {'tipo': 'Derechos De Mercado', 'neto': 39.36, 'iva': 8.27, 'moneda': 'PESO_ARGENTINO'},
                {'tipo': 'Comisión', 'neto': 393.6, 'iva': 82.66, 'moneda': 'PESO_ARGENTINO'},
            ],
            'operaciones': [
                {'fecha': '2026-03-18T14:05:57', 'cantidad': 4, 'precio': 19680},
            ],
            'precio': 19950,
            'cantidad': 4,
            'monto': 98300,
            'fondosParaOperacion': None,
            'montoOperacion': 78720,
            'modalidad': 'precio_Mercado',
            'arancelesARS': 523.89,
            'arancelesUSD': 0,
            'plazo': 'a24horas',
        }

        result = service.sync_operacion_detalle(167788363)

        assert result is True
        operacion = OperacionIOL.objects.get(numero='167788363')
        assert operacion.moneda == 'peso_Argentino'
        assert operacion.estado == 'terminada'
        assert operacion.estado_actual == 'terminada'
        assert operacion.estados_detalle[0]['detalle'] == 'Iniciada'
        assert operacion.aranceles_detalle[1]['tipo'] == 'Comisión'
        assert operacion.operaciones_detalle[0]['precio'] == 19680
        assert operacion.monto_operacion == Decimal('78720')
        assert operacion.aranceles_ars == Decimal('523.890000')
        assert operacion.aranceles_usd == Decimal('0')

    def test_sync_operacion_detalle_updates_existing_operacion(self, service):
        OperacionIOL.objects.create(
            numero='167788363',
            fecha_orden=timezone.make_aware(timezone.datetime(2026, 3, 18, 14, 5, 53, 323000)),
            tipo='Compra',
            estado='Pendiente',
            mercado='bcba',
            simbolo='MCD',
            cantidad=4,
            monto=98300,
            modalidad='precio_Mercado',
        )
        service.client.get_operacion.return_value = {
            'numero': 167788363,
            'mercado': 'bcba',
            'simbolo': 'MCD',
            'moneda': 'peso_Argentino',
            'tipo': 'compra',
            'fechaAlta': '2026-03-18T14:05:53.323',
            'validez': '2026-03-18T17:00:00',
            'fechaOperado': '2026-03-18T14:05:57',
            'estadoActual': 'terminada',
            'estados': [{'detalle': 'Terminada', 'fecha': '2026-03-18T14:05:58.507'}],
            'aranceles': [],
            'operaciones': [],
            'precio': 19950,
            'cantidad': 4,
            'monto': 98300,
            'modalidad': 'precio_Mercado',
            'montoOperacion': 78720,
            'arancelesARS': 523.89,
            'arancelesUSD': 0,
            'plazo': 'a24horas',
        }

        result = service.sync_operacion_detalle(167788363)

        assert result is True
        operacion = OperacionIOL.objects.get(numero='167788363')
        assert operacion.estado == 'terminada'
        assert operacion.moneda == 'peso_Argentino'
        assert timezone.localtime(operacion.validez).isoformat().startswith('2026-03-18T17:00:00')

    def test_sync_operacion_detalle_no_data(self, service):
        service.client.get_operacion.return_value = None

        result = service.sync_operacion_detalle(167788363)

        assert result is False

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
