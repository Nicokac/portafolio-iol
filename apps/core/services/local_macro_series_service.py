from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from apps.core.config.parametros_macro_local import ParametrosMacroLocal
from apps.core.models import MacroSeriesSnapshot
from apps.core.services.market_data.bcra_client import BCRAClient
from apps.core.services.market_data.datos_gob_client import DatosGobSeriesClient


class LocalMacroSeriesService:
    def __init__(
        self,
        bcra_client: BCRAClient | None = None,
        datos_client: DatosGobSeriesClient | None = None,
    ):
        self.bcra_client = bcra_client or BCRAClient()
        self.datos_client = datos_client or DatosGobSeriesClient()

    def sync_all(self) -> dict:
        return {
            series_key: self.sync_series(series_key)
            for series_key in ParametrosMacroLocal.SERIES
        }

    def sync_series(self, series_key: str) -> dict:
        config = ParametrosMacroLocal.SERIES.get(series_key)
        if not config:
            raise ValueError(f"Unknown macro series key: {series_key}")

        rows = self._fetch_rows(config)
        created = 0
        updated = 0

        with transaction.atomic():
            for row in rows:
                _, was_created = MacroSeriesSnapshot.objects.update_or_create(
                    series_key=series_key,
                    source=config["source"],
                    fecha=row["fecha"],
                    defaults={
                        "external_id": config["external_id"],
                        "frequency": config["frequency"],
                        "value": Decimal(str(row["value"])),
                        "metadata": {"title": config["title"]},
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        return {
            "success": True,
            "series_key": series_key,
            "title": config["title"],
            "source": config["source"],
            "rows_received": len(rows),
            "created": created,
            "updated": updated,
        }

    def get_context_summary(self, total_iol: float | None = None) -> dict:
        usdars_latest = self._get_latest_snapshot("usdars_oficial")
        ipc_snapshots = list(
            MacroSeriesSnapshot.objects.filter(series_key="ipc_nacional").order_by("-fecha")[:2]
        )
        ipc_latest = ipc_snapshots[0] if ipc_snapshots else None
        ipc_variation = None
        if len(ipc_snapshots) >= 2 and float(ipc_snapshots[1].value) != 0:
            ipc_variation = ((float(ipc_snapshots[0].value) / float(ipc_snapshots[1].value)) - 1) * 100

        total_iol_usd = None
        if total_iol and usdars_latest and float(usdars_latest.value) > 0:
            total_iol_usd = float(total_iol) / float(usdars_latest.value)

        return {
            "usdars_oficial": float(usdars_latest.value) if usdars_latest else None,
            "usdars_oficial_date": usdars_latest.fecha if usdars_latest else None,
            "ipc_nacional_index": float(ipc_latest.value) if ipc_latest else None,
            "ipc_nacional_date": ipc_latest.fecha if ipc_latest else None,
            "ipc_nacional_variation_mom": round(ipc_variation, 2) if ipc_variation is not None else None,
            "total_iol_usd_oficial": round(total_iol_usd, 2) if total_iol_usd is not None else None,
        }

    def _get_latest_snapshot(self, series_key: str):
        return MacroSeriesSnapshot.objects.filter(series_key=series_key).order_by("-fecha").first()

    def _fetch_rows(self, config: dict) -> list[dict]:
        if config["source"] == "bcra":
            return self.bcra_client.fetch_variable(config["external_id"])
        if config["source"] == "datos_gob_ar":
            return self.datos_client.fetch_series(config["external_id"])
        raise ValueError(f"Unsupported macro source: {config['source']}")
