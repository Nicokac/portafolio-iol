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
    CASH_MANAGEMENT_SYMBOLS = frozenset({"ADBAICA", "IOLPORA", "PRPEDOB", "IOLCAMA"})

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

    def get_profiles_for_symbols(self, simbolos: list[str]) -> dict[str, dict]:
        normalized_symbols = [self._as_str(simbolo).upper() for simbolo in simbolos if self._as_str(simbolo)]
        if not normalized_symbols:
            return {}

        latest_date = IOLFCICatalogSnapshot.objects.aggregate(latest=Max("captured_date"))["latest"]
        if latest_date is None:
            return {}

        queryset = IOLFCICatalogSnapshot.objects.filter(
            captured_date=latest_date,
            simbolo__in=normalized_symbols,
        ).order_by("simbolo")

        return {item.simbolo.upper(): self._serialize_item(item) for item in queryset}

    def get_fci_detail(self, simbolo: str, *, fallback_live: bool = True) -> dict | None:
        symbol = self._as_str(simbolo).upper()
        if not symbol:
            return None

        latest_date = IOLFCICatalogSnapshot.objects.aggregate(latest=Max("captured_date"))["latest"]
        snapshot = None
        if latest_date is not None:
            snapshot = (
                IOLFCICatalogSnapshot.objects.filter(captured_date=latest_date, simbolo=symbol)
                .order_by("simbolo")
                .first()
            )

        if snapshot is not None:
            payload = self._serialize_item(snapshot)
            payload["metadata"]["detail_source"] = "latest_catalog_snapshot"
            payload["metadata"]["captured_date"] = latest_date.isoformat()
            return payload

        if not fallback_live:
            return None

        raw_row = self.client.get_fci(symbol)
        if not raw_row:
            return None

        normalized = self._normalize_row(raw_row, captured_at=timezone.now())
        payload = self._serialize_normalized_row(normalized)
        payload["metadata"]["detail_source"] = "iol_live_detail"
        return payload

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

    def _serialize_item(self, item: IOLFCICatalogSnapshot) -> dict:
        return self._serialize_normalized_row(
            {
                "simbolo": item.simbolo,
                "descripcion": item.descripcion,
                "administradora": item.administradora,
                "administradora_key": item.administradora_key,
                "tipo_fondo": item.tipo_fondo,
                "horizonte_inversion": item.horizonte_inversion,
                "rescate": item.rescate,
                "perfil_inversor": item.perfil_inversor,
                "perfil_inversor_key": item.perfil_inversor_key,
                "moneda": item.moneda,
                "pais": item.pais,
                "mercado": item.mercado,
                "ultimo_operado": item.ultimo_operado,
                "variacion": item.variacion,
                "variacion_mensual": item.variacion_mensual,
                "variacion_anual": item.variacion_anual,
                "monto_minimo": item.monto_minimo,
                "fecha_corte": item.fecha_corte,
                "metadata": item.metadata or {},
            }
        )

    def _serialize_normalized_row(self, normalized: dict[str, Any]) -> dict:
        strategy_profile = self._build_strategy_profile(normalized)
        return {
            "simbolo": normalized["simbolo"],
            "descripcion": normalized["descripcion"],
            "administradora": normalized["administradora"],
            "tipo_fondo": normalized["tipo_fondo"],
            "horizonte_inversion": normalized["horizonte_inversion"],
            "rescate": normalized["rescate"],
            "perfil_inversor": normalized["perfil_inversor"],
            "moneda": normalized["moneda"],
            "pais": normalized["pais"],
            "mercado": normalized["mercado"],
            "ultimo_operado": float(normalized["ultimo_operado"]) if normalized["ultimo_operado"] is not None else None,
            "variacion": float(normalized["variacion"]) if normalized["variacion"] is not None else None,
            "variacion_mensual": float(normalized["variacion_mensual"]) if normalized["variacion_mensual"] is not None else None,
            "variacion_anual": float(normalized["variacion_anual"]) if normalized["variacion_anual"] is not None else None,
            "monto_minimo": float(normalized["monto_minimo"]) if normalized["monto_minimo"] is not None else None,
            "fecha_corte": normalized["fecha_corte"].isoformat() if normalized["fecha_corte"] else None,
            "strategy_profile": strategy_profile,
            "metadata": {
                **(normalized["metadata"] or {}),
                "administradora_key": normalized.get("administradora_key", ""),
                "perfil_inversor_key": normalized.get("perfil_inversor_key", ""),
            },
        }

    def _build_strategy_profile(self, normalized: dict[str, Any]) -> dict:
        tipo_fondo = self._as_str(normalized.get("tipo_fondo"))
        perfil = self._as_str(normalized.get("perfil_inversor"))
        horizonte = self._as_str(normalized.get("horizonte_inversion"))
        rescate = self._as_str(normalized.get("rescate")).lower()
        simbolo = self._as_str(normalized.get("simbolo")).upper()

        is_cash_management = self._is_cash_management_candidate(
            simbolo=simbolo,
            tipo_fondo=tipo_fondo,
            perfil_inversor=perfil,
            horizonte_inversion=horizonte,
            rescate=rescate,
        )
        return {
            "classification": "cash_management" if is_cash_management else "return_seeking",
            "label": "Liquidez / cash management" if is_cash_management else "FCI de retorno / asignacion",
            "risk_label": self._map_risk_label(perfil),
            "liquidity_label": self._map_liquidity_label(rescate),
            "horizon_label": horizonte or "No informado",
        }

    def _is_cash_management_candidate(
        self,
        *,
        simbolo: str,
        tipo_fondo: str,
        perfil_inversor: str,
        horizonte_inversion: str,
        rescate: str,
    ) -> bool:
        if simbolo in self.CASH_MANAGEMENT_SYMBOLS:
            return True

        tipo_key = self._normalize_key(tipo_fondo)
        perfil_key = self._normalize_key(perfil_inversor)
        horizonte_key = self._normalize_key(horizonte_inversion)

        if tipo_key.startswith("plazo_fijo_"):
            return True

        return (
            tipo_key in {"renta_fija_pesos", "renta_fija_dolares"}
            and perfil_key == "conservador"
            and "corto" in horizonte_key
            and rescate in {"t0", "t1"}
        )

    @staticmethod
    def _map_liquidity_label(rescate: str) -> str:
        mapping = {
            "t0": "Liquidez inmediata",
            "t1": "Liquidez 24h",
            "t2": "Liquidez 48h+",
        }
        return mapping.get(rescate, f"Rescate {rescate}" if rescate else "Rescate no informado")

    @staticmethod
    def _map_risk_label(perfil_inversor: str) -> str:
        perfil_key = IOLFCICatalogService._normalize_key(perfil_inversor)
        mapping = {
            "conservador": "Riesgo bajo",
            "moderado": "Riesgo medio",
            "agresivo": "Riesgo alto",
        }
        return mapping.get(perfil_key, "Riesgo no informado")

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
