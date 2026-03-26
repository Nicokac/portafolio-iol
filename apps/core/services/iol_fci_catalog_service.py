from __future__ import annotations

import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction
from django.db.models import Max, QuerySet
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.core.models import IOLFCICatalogSnapshot
from apps.core.services.iol_api_client import IOLAPIClient


class IOLFCICatalogService:
    """Persistencia y lectura del catalogo diario de FCI expuesto por IOL."""

    SOURCE_KEY = "iol"

    def __init__(self, client: IOLAPIClient | None = None):
        self.client = client or IOLAPIClient()

    def sync_catalog(self, *, captured_at=None) -> dict:
        captured_at = captured_at or timezone.now()
        raw_rows = self.client.get_fci_list()
        if raw_rows is None:
            return {
                "success": False,
                "rows_received": 0,
                "created": 0,
                "updated": 0,
                "captured_date": captured_at.date().isoformat(),
                "error": self.client.last_error.get("message") or "FCI catalog unavailable",
            }

        created = 0
        updated = 0

        with transaction.atomic():
            for raw_row in raw_rows:
                normalized = self._normalize_row(raw_row, captured_at=captured_at)
                _, was_created = IOLFCICatalogSnapshot.objects.update_or_create(
                    simbolo=normalized["simbolo"],
                    source=self.SOURCE_KEY,
                    captured_date=normalized["captured_date"],
                    defaults=normalized,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        return {
            "success": True,
            "rows_received": len(raw_rows),
            "created": created,
            "updated": updated,
            "captured_date": captured_at.date().isoformat(),
            "error": "",
        }

    def list_latest_catalog(
        self,
        *,
        tipo_fondo: str | None = None,
        moneda: str | None = None,
        rescate: str | None = None,
        perfil_inversor: str | None = None,
        administradora: str | None = None,
        limit: int | None = None,
    ) -> dict:
        latest_date = IOLFCICatalogSnapshot.objects.aggregate(latest=Max("captured_date"))["latest"]
        if latest_date is None:
            return {"captured_date": None, "count": 0, "items": []}

        queryset = IOLFCICatalogSnapshot.objects.filter(captured_date=latest_date).order_by("simbolo")
        queryset = self._apply_filters(
            queryset,
            tipo_fondo=tipo_fondo,
            moneda=moneda,
            rescate=rescate,
            perfil_inversor=perfil_inversor,
            administradora=administradora,
        )
        if limit:
            queryset = queryset[:limit]

        return {
            "captured_date": latest_date.isoformat(),
            "count": queryset.count() if hasattr(queryset, "count") else len(queryset),
            "items": [self._serialize_item(item) for item in queryset],
        }

    def _apply_filters(
        self,
        queryset: QuerySet[IOLFCICatalogSnapshot],
        *,
        tipo_fondo: str | None,
        moneda: str | None,
        rescate: str | None,
        perfil_inversor: str | None,
        administradora: str | None,
    ) -> QuerySet[IOLFCICatalogSnapshot]:
        if tipo_fondo:
            queryset = queryset.filter(tipo_fondo=str(tipo_fondo).strip())
        if moneda:
            queryset = queryset.filter(moneda=str(moneda).strip())
        if rescate:
            queryset = queryset.filter(rescate=str(rescate).strip().lower())
        if perfil_inversor:
            queryset = queryset.filter(perfil_inversor_key=self._normalize_key(perfil_inversor))
        if administradora:
            queryset = queryset.filter(administradora_key=self._normalize_key(administradora))
        return queryset

    def _normalize_row(self, raw_row: dict[str, Any], *, captured_at) -> dict[str, Any]:
        perfil_inversor = self._as_str(raw_row.get("perfilInversor"))
        administradora = self._as_str(raw_row.get("tipoAdministradoraTituloFCI"))
        return {
            "simbolo": self._as_str(raw_row.get("simbolo")),
            "descripcion": self._as_str(raw_row.get("descripcion")),
            "source": self.SOURCE_KEY,
            "captured_at": captured_at,
            "captured_date": captured_at.date(),
            "administradora": administradora,
            "administradora_key": self._normalize_key(administradora),
            "tipo_fondo": self._as_str(raw_row.get("tipoFondo")),
            "horizonte_inversion": self._as_str(raw_row.get("horizonteInversion")),
            "rescate": self._as_str(raw_row.get("rescate")).lower(),
            "perfil_inversor": perfil_inversor,
            "perfil_inversor_key": self._normalize_key(perfil_inversor),
            "moneda": self._as_str(raw_row.get("moneda")),
            "pais": self._as_str(raw_row.get("pais")),
            "mercado": self._as_str(raw_row.get("mercado")),
            "ultimo_operado": self._as_decimal(raw_row.get("ultimoOperado")),
            "variacion": self._as_decimal(raw_row.get("variacion")),
            "variacion_mensual": self._as_decimal(raw_row.get("variacionMensual")),
            "variacion_anual": self._as_decimal(raw_row.get("variacionAnual")),
            "monto_minimo": self._as_decimal(raw_row.get("montoMinimo")),
            "fecha_corte": self._as_datetime(raw_row.get("fechaCorte")),
            "metadata": {
                "codigo_bloomberg": raw_row.get("codigoBloomberg"),
                "plazo": raw_row.get("plazo"),
                "tipo": raw_row.get("tipo"),
                "invierte": raw_row.get("invierte"),
                "aviso_horario_ejecucion": raw_row.get("avisoHorarioEjecucion"),
                "informe_mensual": raw_row.get("informeMensual"),
                "reglamento_gestion": raw_row.get("reglamentoGestion"),
            },
        }

    @staticmethod
    def _serialize_item(item: IOLFCICatalogSnapshot) -> dict:
        return {
            "simbolo": item.simbolo,
            "descripcion": item.descripcion,
            "administradora": item.administradora,
            "tipo_fondo": item.tipo_fondo,
            "horizonte_inversion": item.horizonte_inversion,
            "rescate": item.rescate,
            "perfil_inversor": item.perfil_inversor,
            "moneda": item.moneda,
            "pais": item.pais,
            "mercado": item.mercado,
            "ultimo_operado": float(item.ultimo_operado) if item.ultimo_operado is not None else None,
            "variacion": float(item.variacion) if item.variacion is not None else None,
            "variacion_mensual": float(item.variacion_mensual) if item.variacion_mensual is not None else None,
            "variacion_anual": float(item.variacion_anual) if item.variacion_anual is not None else None,
            "monto_minimo": float(item.monto_minimo) if item.monto_minimo is not None else None,
            "fecha_corte": item.fecha_corte.isoformat() if item.fecha_corte else None,
            "metadata": item.metadata,
        }

    @staticmethod
    def _as_str(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _as_datetime(value: Any):
        if not value:
            return None
        parsed = parse_datetime(str(value))
        if parsed is None:
            return None
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed

    @staticmethod
    def _as_decimal(value: Any):
        if value in (None, ""):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None

    @staticmethod
    def _normalize_key(value: Any) -> str:
        normalized = unicodedata.normalize("NFKD", str(value or "").strip().lower())
        ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
        return "_".join(part for part in ascii_text.replace("/", " ").split() if part)
