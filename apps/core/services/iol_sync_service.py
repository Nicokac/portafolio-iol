import logging
from typing import List, Optional

from django.utils.dateparse import parse_datetime
from django.utils import timezone

from apps.core.services.iol_api_client import IOLAPIClient
from apps.core.services.observability import timed
from apps.operaciones_iol.models import OperacionIOL
from apps.portafolio_iol.models import ActivoPortafolioSnapshot
from apps.resumen_iol.models import ResumenCuentaSnapshot


logger = logging.getLogger(__name__)


class IOLSyncService:
    """Servicio para sincronizar datos desde IOL."""

    def __init__(self):
        self.client = IOLAPIClient()
        self.last_diagnostics = {}

    def sync_estado_cuenta(self) -> bool:
        """Sincroniza el estado de cuenta."""
        logger.info("Starting estado cuenta sync", extra={"event": "iol_sync_estado_start"})
        with timed("iol.api.estado_cuenta.latency_ms"):
            data = self.client.get_estado_cuenta()
        if not data:
            self.last_diagnostics["estado_cuenta"] = dict(self.client.last_error)
            if self.client.last_error:
                logger.error("Estado cuenta sync failed diagnostics: %s", self.client.last_error)
            return False

        fecha_extraccion = timezone.now()
        total_en_pesos = data.get("totalEnPesos")
        for cuenta in data.get('cuentas', []):
            ResumenCuentaSnapshot.objects.create(
                fecha_extraccion=fecha_extraccion,
                numero_cuenta=cuenta['numero'],
                tipo_cuenta=cuenta['tipo'],
                moneda=cuenta['moneda'],
                disponible=cuenta['disponible'],
                comprometido=cuenta['comprometido'],
                saldo=cuenta['saldo'],
                titulos_valorizados=cuenta['titulosValorizados'],
                total=cuenta['total'],
                total_en_pesos=total_en_pesos,
                margen_descubierto=cuenta.get('margenDescubierto'),
                saldos_detalle=cuenta.get('saldos', []),
                estado=cuenta['estado'],
            )
        logger.info(
            "Estado cuenta sync completed",
            extra={
                "event": "iol_sync_estado_end",
                "extra_data": {"cuentas": len(data.get('cuentas', []))},
            },
        )
        return True

    def sync_portafolio(self, pais: str = 'argentina') -> bool:
        """Sincroniza el portafolio."""
        logger.info(
            "Starting portafolio sync",
            extra={"event": "iol_sync_portafolio_start", "extra_data": {"pais": pais}},
        )
        with timed("iol.api.portafolio.latency_ms"):
            data = self.client.get_portafolio(pais)
        if not data:
            self.last_diagnostics[f"portafolio_{pais}"] = dict(self.client.last_error)
            if self.client.last_error:
                logger.error("Portafolio sync failed diagnostics (%s): %s", pais, self.client.last_error)
            return False

        fecha_extraccion = timezone.now()
        for activo in data.get('activos', []):
            try:
                titulo = activo.get('titulo', {})
                ActivoPortafolioSnapshot.objects.create(
                    fecha_extraccion=fecha_extraccion,
                    pais_consulta=pais,
                    simbolo=titulo.get('simbolo') or titulo.get('symbol'),
                    descripcion=titulo.get('descripcion') or titulo.get('description'),
                    cantidad=activo['cantidad'],
                    comprometido=activo['comprometido'],
                    disponible_inmediato=activo['cantidad'] - activo['comprometido'],  # Calcular disponible inmediato
                    puntos_variacion=activo['puntosVariacion'],
                    variacion_diaria=activo['variacionDiaria'],
                    ultimo_precio=activo['ultimoPrecio'],
                    ppc=activo['ppc'],
                    ganancia_porcentaje=activo['gananciaPorcentaje'],
                    ganancia_dinero=activo['gananciaDinero'],
                    valorizado=activo['valorizado'],
                    pais_titulo=titulo.get('pais') or titulo.get('country'),
                    mercado=titulo.get('mercado'),
                    tipo=titulo.get('tipo'),
                    plazo=titulo.get('plazo'),
                    moneda=titulo.get('moneda'),
                    parking=activo.get('parking'),
                )
            except KeyError as e:
                logger.error(f"Missing key in activo data: {e}, data: {activo}")
                continue
        logger.info(
            "Portafolio sync completed",
            extra={
                "event": "iol_sync_portafolio_end",
                "extra_data": {"pais": pais, "activos": len(data.get('activos', []))},
            },
        )
        return True

    def sync_operaciones(self, params: Optional[dict] = None) -> bool:
        """Sincroniza las operaciones."""
        logger.info("Starting operaciones sync", extra={"event": "iol_sync_operaciones_start"})
        with timed("iol.api.operaciones.latency_ms"):
            data = self.client.get_operaciones(params)
        if not data:
            self.last_diagnostics["operaciones"] = dict(self.client.last_error)
            if self.client.last_error:
                logger.error("Operaciones sync failed diagnostics: %s", self.client.last_error)
            return False

        synced_count = 0
        for operacion in data:
            logger.debug(f"Operacion data: {operacion}")  # Debug: ver estructura
            try:
                _, created = OperacionIOL.objects.get_or_create(
                    numero=operacion['numero'],
                    defaults=self._build_operacion_defaults(operacion),
                )
                if created:
                    synced_count += 1
            except KeyError as e:
                logger.error(f"Missing key in operacion data: {e}, data: {operacion}")
                continue
            except Exception as e:
                logger.error(f"Error syncing operacion: {e}, data: {operacion}")
                continue
        logger.info(
            "Operaciones sync completed",
            extra={
                "event": "iol_sync_operaciones_end",
                "extra_data": {"new_operaciones": synced_count},
            },
        )
        return True

    def sync_operacion_detalle(self, numero: str | int) -> bool:
        """Sincroniza el detalle de una operacion puntual."""
        logger.info(
            "Starting operacion detail sync",
            extra={"event": "iol_sync_operacion_detail_start", "extra_data": {"numero": str(numero)}},
        )
        with timed("iol.api.operacion_detail.latency_ms"):
            data = self.client.get_operacion(numero)
        if not data:
            self.last_diagnostics["operacion_detalle"] = dict(self.client.last_error)
            if self.client.last_error:
                logger.error("Operacion detail sync failed diagnostics: %s", self.client.last_error)
            return False

        try:
            OperacionIOL.objects.update_or_create(
                numero=str(data["numero"]),
                defaults=self._build_operacion_defaults(data),
            )
        except KeyError as e:
            logger.error("Missing key in operacion detail data: %s, data: %s", e, data)
            return False

        logger.info(
            "Operacion detail sync completed",
            extra={"event": "iol_sync_operacion_detail_end", "extra_data": {"numero": str(numero)}},
        )
        return True

    def _build_operacion_defaults(self, operacion: dict) -> dict:
        return {
            'fecha_orden': self._normalize_datetime(operacion.get('fechaOrden') or operacion.get('fechaAlta')),
            'fecha_alta': self._normalize_datetime(operacion.get('fechaAlta') or operacion.get('fechaOrden')),
            'validez': self._normalize_datetime(operacion.get('validez')),
            'tipo': operacion['tipo'],
            'estado': operacion.get('estado') or operacion.get('estadoActual', ''),
            'estado_actual': operacion.get('estadoActual') or operacion.get('estado', ''),
            'mercado': operacion['mercado'],
            'simbolo': operacion['simbolo'],
            'moneda': operacion.get('moneda', ''),
            'cantidad': operacion.get('cantidad'),
            'monto': operacion.get('monto'),
            'modalidad': operacion.get('modalidad', ''),
            'precio': operacion.get('precio'),
            'fecha_operada': self._normalize_datetime(operacion.get('fechaOperada') or operacion.get('fechaOperado')),
            'cantidad_operada': operacion.get('cantidadOperada'),
            'precio_operado': operacion.get('precioOperado'),
            'monto_operado': operacion.get('montoOperado'),
            'monto_operacion': operacion.get('montoOperacion'),
            'aranceles_ars': operacion.get('arancelesARS'),
            'aranceles_usd': operacion.get('arancelesUSD'),
            'plazo': operacion.get('plazo'),
            'fondos_para_operacion': operacion.get('fondosParaOperacion'),
            'estados_detalle': operacion.get('estados', []),
            'aranceles_detalle': operacion.get('aranceles', []),
            'operaciones_detalle': operacion.get('operaciones', []),
        }

    def _normalize_datetime(self, value):
        if not value:
            return value
        if isinstance(value, str):
            parsed = parse_datetime(value)
            if parsed is None:
                return value
            value = parsed
        if timezone.is_naive(value):
            return timezone.make_aware(value, timezone.get_current_timezone())
        return value

    def sync_all(self) -> dict:
        """Sincroniza todos los datos."""
        self.last_diagnostics = {}
        results = {}
        results['estado_cuenta'] = self.sync_estado_cuenta()
        results['portafolio_argentina'] = self.sync_portafolio('argentina')
        results['operaciones'] = self.sync_operaciones()
        results['portfolio_snapshot'] = False

        if results['estado_cuenta'] and results['portafolio_argentina']:
            try:
                from apps.core.services.portfolio_snapshot_service import PortfolioSnapshotService

                snapshot = PortfolioSnapshotService().generate_daily_snapshot()
                results['portfolio_snapshot'] = snapshot is not None
            except Exception as exc:
                logger.error("Failed to generate portfolio snapshot after sync: %s", exc)

        return results
