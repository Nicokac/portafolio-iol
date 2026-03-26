from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db.models import Count, Max

from apps.core.models import IOLFCICatalogSnapshot
from apps.core.services.iol_api_client import IOLAPIClient
from apps.core.services.iol_fci_catalog_service import IOLFCICatalogService


class IOLFCIAdminTaxonomyService:
    """Spike controlado para taxonomia remota de administradoras FCI con fallback local."""

    REMOTE_SOURCE_KEY = "iol_remote_admin_taxonomy"
    LOCAL_SOURCE_KEY = "latest_fci_catalog_snapshot"

    def __init__(
        self,
        client: IOLAPIClient | None = None,
        catalog_service: IOLFCICatalogService | None = None,
    ):
        self.client = client or IOLAPIClient()
        self.catalog_service = catalog_service or IOLFCICatalogService(client=self.client)

    def get_taxonomy_probe(
        self,
        administradora: str,
        *,
        tipo_fondo: str | None = None,
        limit: int = 25,
    ) -> dict:
        administradora_clean = str(administradora or "").strip()
        administradora_key = self.catalog_service._normalize_key(administradora_clean)
        if not administradora_key:
            return {
                "administradora": administradora_clean,
                "administradora_key": administradora_key,
                "feature_enabled": bool(settings.IOL_FCI_ADMIN_TAXONOMY_SPIKE_ENABLED),
                "remote_status": "invalid_request",
                "remote_reason": "Administradora vacia o invalida.",
                "local_taxonomy": self._empty_local_taxonomy(),
                "remote_taxonomy": {"count": 0, "items": []},
                "comparison": self._build_comparison_summary(local_count=0, remote_count=0, matched_count=0),
            }

        local_taxonomy = self._build_local_taxonomy(
            administradora=administradora_key,
            tipo_fondo=tipo_fondo,
            limit=limit,
        )
        remote_taxonomy = self._build_remote_taxonomy(
            administradora=administradora_clean,
            tipo_fondo=tipo_fondo,
            limit=limit,
        )

        matched_count = len(
            {
                self.catalog_service._normalize_key(
                    item.get("tipo_fondo")
                    or item.get("identificador_tipo_fondo_fci")
                    or item.get("identificadorTipoFondoFCI")
                    or ""
                )
                for item in remote_taxonomy["items"]
            }.intersection(
                {
                    self.catalog_service._normalize_key(
                        item.get("tipo_fondo")
                        or item.get("identificador_tipo_fondo_fci")
                        or item.get("identificadorTipoFondoFCI")
                        or ""
                    )
                    for item in local_taxonomy["items"]
                }
            )
        )

        return {
            "administradora": administradora_clean,
            "administradora_key": administradora_key,
            "tipo_fondo": str(tipo_fondo or "").strip(),
            "feature_enabled": bool(settings.IOL_FCI_ADMIN_TAXONOMY_SPIKE_ENABLED),
            "remote_status": remote_taxonomy["status"],
            "remote_reason": remote_taxonomy["reason"],
            "local_taxonomy": local_taxonomy,
            "remote_taxonomy": {
                "source": self.REMOTE_SOURCE_KEY,
                "count": remote_taxonomy["count"],
                "items": remote_taxonomy["items"],
            },
            "comparison": self._build_comparison_summary(
                local_count=local_taxonomy["count"],
                remote_count=remote_taxonomy["count"],
                matched_count=matched_count,
            ),
        }

    def _build_local_taxonomy(
        self,
        *,
        administradora: str,
        tipo_fondo: str | None,
        limit: int,
    ) -> dict:
        latest_date = IOLFCICatalogSnapshot.objects.aggregate(latest=Max("captured_date"))["latest"]
        if latest_date is None:
            return self._empty_local_taxonomy()

        queryset = IOLFCICatalogSnapshot.objects.filter(
            captured_date=latest_date,
            administradora_key=administradora,
        )
        if tipo_fondo:
            queryset = queryset.filter(tipo_fondo=str(tipo_fondo).strip())
            items = [
                self.catalog_service._serialize_item(item)
                for item in queryset.order_by("simbolo")[:limit]
            ]
            return {
                "source": self.LOCAL_SOURCE_KEY,
                "captured_date": latest_date.isoformat(),
                "count": len(items),
                "items": items,
                "mode": "funds_by_tipo_fondo",
            }

        aggregated = list(
            queryset.values("tipo_fondo").annotate(funds_count=Count("id")).order_by("tipo_fondo")
        )
        items = [
            {
                "administradora": administradora,
                "identificador_tipo_fondo_fci": row["tipo_fondo"],
                "nombre_tipo_fondo_fci": row["tipo_fondo"],
                "funds_count": row["funds_count"],
            }
            for row in aggregated[:limit]
        ]
        return {
            "source": self.LOCAL_SOURCE_KEY,
            "captured_date": latest_date.isoformat(),
            "count": len(items),
            "items": items,
            "mode": "tipo_fondos_by_administradora",
        }

    def _build_remote_taxonomy(
        self,
        *,
        administradora: str,
        tipo_fondo: str | None,
        limit: int,
    ) -> dict:
        if not settings.IOL_FCI_ADMIN_TAXONOMY_SPIKE_ENABLED:
            return {
                "status": "disabled",
                "reason": "Spike remoto deshabilitado por feature flag.",
                "count": 0,
                "items": [],
            }

        if tipo_fondo:
            rows = self.client.get_fci_admin_tipo_fondo_funds(administradora, tipo_fondo)
        else:
            rows = self.client.get_fci_admin_tipo_fondos(administradora)

        if rows is None:
            status_code = self.client.last_error.get("status_code")
            error_type = str(self.client.last_error.get("error_type") or "")
            if status_code == 403:
                status = "forbidden"
                reason = "IOL rechazo el endpoint remoto de administradoras con 403."
            elif status_code == 401:
                status = "unauthorized"
                reason = "IOL rechazo autenticacion para el endpoint remoto."
            elif error_type:
                status = "error"
                reason = self.client.last_error.get("message") or "Fallo remoto al consultar taxonomia de administradora."
            else:
                status = "unavailable"
                reason = "El endpoint remoto no devolvio una respuesta usable."
            return {
                "status": status,
                "reason": reason,
                "count": 0,
                "items": [],
            }

        return {
            "status": "available",
            "reason": "",
            "count": len(rows[:limit]),
            "items": [self._serialize_remote_item(row) for row in rows[:limit]],
        }

    @staticmethod
    def _build_comparison_summary(*, local_count: int, remote_count: int, matched_count: int) -> dict:
        return {
            "local_count": int(local_count or 0),
            "remote_count": int(remote_count or 0),
            "matched_count": int(matched_count or 0),
            "coverage_gap_count": max(int(local_count or 0) - int(matched_count or 0), 0),
        }

    @staticmethod
    def _empty_local_taxonomy() -> dict:
        return {
            "source": IOLFCIAdminTaxonomyService.LOCAL_SOURCE_KEY,
            "captured_date": None,
            "count": 0,
            "items": [],
            "mode": "empty",
        }

    @staticmethod
    def _serialize_remote_item(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "administradora": str(row.get("administradora") or "").strip(),
            "identificador_tipo_fondo_fci": str(
                row.get("identificadorTipoFondoFCI")
                or row.get("identificador")
                or row.get("tipoFondo")
                or ""
            ).strip(),
            "nombre_tipo_fondo_fci": str(
                row.get("nombreTipoFondoFCI")
                or row.get("nombre")
                or row.get("descripcion")
                or ""
            ).strip(),
            "simbolo": str(row.get("simbolo") or "").strip(),
            "descripcion": str(row.get("descripcion") or "").strip(),
        }
