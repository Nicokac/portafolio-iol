import logging
from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.core.services.iol_api_client import IOLAPIClient
from apps.dashboard.selectors import (
    get_dashboard_kpis,
    get_distribucion_pais,
    get_portafolio_enriquecido_actual,
)
from apps.operaciones_iol.models import OperacionIOL
from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import (
    ActivoPortafolioSnapshot,
    PortfolioSnapshot,
    PositionSnapshot,
)
from apps.resumen_iol.models import ResumenCuentaSnapshot

logger = logging.getLogger(__name__)


class PortfolioSnapshotService:
    """Service to generate and sync portfolio snapshots."""

    def __init__(self):
        self.api_client = IOLAPIClient()

    def generate_daily_snapshot(self, target_date: date = None) -> PortfolioSnapshot:
        if target_date is None:
            target_date = timezone.now().date()

        logger.info(f"Generating portfolio snapshot for {target_date}")

        existing_snapshot = PortfolioSnapshot.objects.filter(fecha=target_date).first()
        if existing_snapshot:
            logger.warning(f"Snapshot already exists for {target_date}")
            return existing_snapshot

        kpis = get_dashboard_kpis()
        distribucion_pais = get_distribucion_pais()

        exposicion_usa = 0.0
        exposicion_argentina = 0.0

        for pais, valor in distribucion_pais.items():
            if pais.lower() in ["usa", "estados unidos"]:
                exposicion_usa = valor
            elif pais.lower() == "argentina":
                exposicion_argentina = valor

        with transaction.atomic():
            snapshot = PortfolioSnapshot.objects.create(
                fecha=target_date,
                total_iol=kpis["total_iol"],
                liquidez_operativa=kpis["liquidez_operativa"],
                cash_management=kpis["fci_cash_management"],
                portafolio_invertido=kpis["portafolio_invertido"],
                rendimiento_total=kpis["rendimiento_total_porcentaje"],
                exposicion_usa=exposicion_usa,
                exposicion_argentina=exposicion_argentina,
            )

            self._create_position_snapshots(snapshot)
            logger.info(
                f"Created portfolio snapshot for {target_date} with {snapshot.positions.count()} positions"
            )

        return snapshot

    def _create_position_snapshots(self, snapshot: PortfolioSnapshot):
        portafolio = get_portafolio_enriquecido_actual()
        simbolos = [item["activo"].simbolo for item in portafolio["inversion"]]
        parametros = {
            p.simbolo: p
            for p in ParametroActivo.objects.filter(simbolo__in=simbolos)
        }

        for item in portafolio["inversion"]:
            activo = item["activo"]
            parametro = parametros.get(activo.simbolo)

            PositionSnapshot.objects.create(
                snapshot=snapshot,
                simbolo=activo.simbolo,
                descripcion=getattr(activo, "descripcion", ""),
                valorizado=float(activo.valorizado),
                peso=item.get("peso_porcentual", 0.0),
                sector=parametro.sector if parametro else "",
                pais=parametro.pais_exposicion if parametro else "",
                tipo=item.get("tipo_traducido", ""),
                bloque_estrategico=parametro.bloque_estrategico if parametro else "",
                ganancia_dinero=float(activo.ganancia_dinero),
                ganancia_porcentaje=float(activo.ganancia_porcentaje),
            )

    def sync_iol_data(self) -> bool:
        logger.info("Starting IOL data synchronization")

        try:
            estado_cuenta = self.api_client.get_estado_cuenta()
            if not estado_cuenta:
                logger.error("Failed to get estado de cuenta")
                return False
            self._save_estado_cuenta(estado_cuenta)
            logger.info("Estado de cuenta synchronized")

            portafolio = self.api_client.get_portafolio()
            if not portafolio:
                logger.error("Failed to get portafolio")
                return False
            self._save_portafolio(portafolio)
            logger.info("Portafolio synchronized")

            operaciones = self.api_client.get_operaciones(
                {"fechaDesde": (timezone.now() - timezone.timedelta(days=30)).strftime("%Y-%m-%d")}
            )
            if operaciones:
                self._save_operaciones(operaciones)
                logger.info("Operaciones synchronized")

            logger.info("IOL data synchronization completed successfully")
            return True

        except Exception as e:
            logger.error(f"Error during IOL data synchronization: {e}")
            return False

    def _save_estado_cuenta(self, data: dict):
        cuentas = data.get("cuentas", [])
        fecha_extraccion = timezone.now()

        for cuenta in cuentas:
            numero_cuenta = cuenta.get("numero")
            tipo_cuenta = cuenta.get("tipo")
            moneda = cuenta.get("moneda")
            estado = cuenta.get("estado")
            if not all([numero_cuenta, tipo_cuenta, moneda, estado]):
                continue

            ResumenCuentaSnapshot.objects.create(
                fecha_extraccion=fecha_extraccion,
                numero_cuenta=numero_cuenta,
                tipo_cuenta=tipo_cuenta,
                moneda=moneda,
                disponible=cuenta.get("disponible", 0),
                comprometido=cuenta.get("comprometido", 0),
                saldo=cuenta.get("saldo", 0),
                titulos_valorizados=cuenta.get("titulosValorizados", 0),
                total=cuenta.get("total", 0),
                margen_descubierto=cuenta.get("margenDescubierto"),
                estado=estado,
            )

    def _save_portafolio(self, data: dict):
        activos = data.get("activos", [])
        fecha_extraccion = timezone.now()

        for activo in activos:
            titulo = activo.get("titulo", {})
            simbolo = titulo.get("simbolo") or titulo.get("symbol")
            descripcion = titulo.get("descripcion") or titulo.get("description")
            if not simbolo or not descripcion:
                continue

            cantidad = activo.get("cantidad", 0)
            comprometido = activo.get("comprometido", 0)

            ActivoPortafolioSnapshot.objects.create(
                fecha_extraccion=fecha_extraccion,
                pais_consulta="argentina",
                simbolo=simbolo,
                descripcion=descripcion,
                cantidad=cantidad,
                comprometido=comprometido,
                disponible_inmediato=cantidad - comprometido,
                puntos_variacion=activo.get("puntosVariacion", 0),
                variacion_diaria=activo.get("variacionDiaria", 0),
                ultimo_precio=activo.get("ultimoPrecio", 0),
                ppc=activo.get("ppc", 0),
                ganancia_porcentaje=activo.get("gananciaPorcentaje", 0),
                ganancia_dinero=activo.get("gananciaDinero", 0),
                valorizado=activo.get("valorizado", 0),
                pais_titulo=titulo.get("pais") or titulo.get("country", ""),
                mercado=titulo.get("mercado", ""),
                tipo=titulo.get("tipo", ""),
                plazo=titulo.get("plazo"),
                moneda=titulo.get("moneda", ""),
            )

    def _save_operaciones(self, data: list[dict]):
        for operacion in data:
            numero = operacion.get("numero")
            if numero is None:
                continue

            OperacionIOL.objects.get_or_create(
                numero=str(numero),
                defaults={
                    "fecha_orden": operacion.get("fechaOrden") or timezone.now(),
                    "tipo": operacion.get("tipo", ""),
                    "estado": operacion.get("estado", ""),
                    "mercado": operacion.get("mercado", ""),
                    "simbolo": operacion.get("simbolo", ""),
                    "cantidad": operacion.get("cantidad"),
                    "monto": operacion.get("monto"),
                    "modalidad": operacion.get("modalidad", ""),
                    "precio": operacion.get("precio"),
                    "fecha_operada": operacion.get("fechaOperada"),
                    "cantidad_operada": operacion.get("cantidadOperada"),
                    "precio_operado": operacion.get("precioOperado"),
                    "monto_operado": operacion.get("montoOperado"),
                    "plazo": operacion.get("plazo"),
                },
            )
