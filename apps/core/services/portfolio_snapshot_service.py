import logging
from datetime import date
from typing import Dict, List

from django.db import transaction
from django.utils import timezone

from apps.core.services.iol_api_client import IOLAPIClient
from apps.dashboard.selectors import (
    get_concentracion_pais,
    get_concentracion_sector,
    get_concentracion_tipo_patrimonial,
    get_dashboard_kpis,
    get_distribucion_moneda,
    get_distribucion_pais,
    get_distribucion_sector,
    get_distribucion_tipo_patrimonial,
    get_portafolio_enriquecido_actual,
)
from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import PortfolioSnapshot, PositionSnapshot
from apps.resumen_iol.models import ResumenCuentaSnapshot

logger = logging.getLogger(__name__)


class PortfolioSnapshotService:
    """Servicio para generar snapshots diarios del portafolio."""

    def __init__(self):
        self.api_client = IOLAPIClient()

    def generate_daily_snapshot(self, target_date: date = None) -> PortfolioSnapshot:
        """
        Genera un snapshot diario del portafolio.

        Args:
            target_date: Fecha para el snapshot (por defecto hoy)

        Returns:
            PortfolioSnapshot: El snapshot creado
        """
        if target_date is None:
            target_date = timezone.now().date()

        logger.info(f"Generating portfolio snapshot for {target_date}")

        # Verificar si ya existe snapshot para esta fecha
        existing_snapshot = PortfolioSnapshot.objects.filter(fecha=target_date).first()
        if existing_snapshot:
            logger.warning(f"Snapshot already exists for {target_date}")
            return existing_snapshot

        # Obtener datos actuales
        kpis = get_dashboard_kpis()
        distribucion_pais = get_distribucion_pais()

        # Calcular exposiciones
        exposicion_usa = 0.0
        exposicion_argentina = 0.0

        for pais, valor in distribucion_pais.items():
            if pais.lower() in ['usa', 'estados unidos']:
                exposicion_usa = valor
            elif pais.lower() == 'argentina':
                exposicion_argentina = valor

        # Crear snapshot con transacción
        with transaction.atomic():
            snapshot = PortfolioSnapshot.objects.create(
                fecha=target_date,
                total_iol=kpis['total_iol'],
                liquidez_operativa=kpis['liquidez_operativa'],
                cash_management=kpis['fci_cash_management'],
                portafolio_invertido=kpis['portafolio_invertido'],
                rendimiento_total=kpis['rendimiento_total_porcentaje'],
                exposicion_usa=exposicion_usa,
                exposicion_argentina=exposicion_argentina,
            )

            # Crear posiciones detalladas
            self._create_position_snapshots(snapshot)

            logger.info(f"Created portfolio snapshot for {target_date} with {snapshot.positions.count()} positions")

        return snapshot

    def _create_position_snapshots(self, snapshot: PortfolioSnapshot):
        """Crea snapshots detallados de cada posición."""
        portafolio = get_portafolio_enriquecido_actual()

        # Obtener parámetros para metadata
        simbolos = [item['activo'].simbolo for item in portafolio['inversion']]
        parametros = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=simbolos)}

        # Procesar cada posición de inversión
        for item in portafolio['inversion']:
            activo = item['activo']
            parametro = parametros.get(activo.simbolo)

            PositionSnapshot.objects.create(
                snapshot=snapshot,
                simbolo=activo.simbolo,
                descripcion=getattr(activo, 'descripcion', ''),
                valorizado=float(activo.valorizado),
                peso=item.get('peso_porcentual', 0.0),
                sector=parametro.sector if parametro else '',
                pais=parametro.pais_exposicion if parametro else '',
                tipo=item.get('tipo_traducido', ''),
                bloque_estrategico=parametro.bloque_estrategico if parametro else '',
                ganancia_dinero=float(activo.ganancia_dinero),
                ganancia_porcentaje=float(activo.ganancia_porcentaje),
            )

    def sync_iol_data(self) -> bool:
        """
        Sincroniza datos desde la API de IOL.

        Returns:
            bool: True si la sincronización fue exitosa
        """
        logger.info("Starting IOL data synchronization")

        try:
            # Sincronizar estado de cuenta
            estado_cuenta = self.api_client.get_estado_cuenta()
            if estado_cuenta:
                self._save_estado_cuenta(estado_cuenta)
                logger.info("Estado de cuenta synchronized")
            else:
                logger.error("Failed to get estado de cuenta")
                return False

            # Sincronizar portafolio
            portafolio = self.api_client.get_portafolio()
            if portafolio:
                self._save_portafolio(portafolio)
                logger.info("Portafolio synchronized")
            else:
                logger.error("Failed to get portafolio")
                return False

            # Sincronizar operaciones (últimas 30 días)
            operaciones = self.api_client.get_operaciones({
                'fechaDesde': (timezone.now() - timezone.timedelta(days=30)).strftime('%Y-%m-%d')
            })
            if operaciones:
                self._save_operaciones(operaciones)
                logger.info("Operaciones synchronized")

            logger.info("IOL data synchronization completed successfully")
            return True

        except Exception as e:
            logger.error(f"Error during IOL data synchronization: {e}")
            return False

    def _save_estado_cuenta(self, data: Dict):
        """Guarda el estado de cuenta."""
        # Implementar según la estructura de respuesta de IOL
        pass

    def _save_portafolio(self, data: Dict):
        """Guarda el portafolio."""
        # Implementar según la estructura de respuesta de IOL
        pass

    def _save_operaciones(self, data: List[Dict]):
        """Guarda las operaciones."""
        # Implementar según la estructura de respuesta de IOL
        pass