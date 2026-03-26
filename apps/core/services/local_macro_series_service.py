from __future__ import annotations

from decimal import Decimal

import pandas as pd
from django.db import transaction
from django.db.models import Count, Max
from django.utils import timezone

from apps.core.config.parametros_macro_local import ParametrosMacroLocal
from apps.core.models import MacroSeriesSnapshot
from apps.core.services.local_macro_context import (
    annualize_change_pct,
    build_context_summary,
    build_fx_context_summary,
    calculate_badlar_ytd,
    calculate_fx_gap_change,
    calculate_gap_pct,
    calculate_ipc_variation_yoy,
    calculate_ipc_variation_ytd,
    calculate_portfolio_ytd,
    calculate_series_change,
    round_or_none,
)
from apps.core.services.market_data.bcra_client import BCRAClient
from apps.core.services.market_data.datos_gob_client import DatosGobSeriesClient
from apps.core.services.market_data.fx_json_client import FXJSONClient, OptionalSourceUnavailableError
from apps.portafolio_iol.models import PortfolioSnapshot


class LocalMacroSeriesService:
    SYNC_STATE_METRIC = "analytics_v2.local_macro.sync_status"
    STALENESS_DAYS_BY_FREQUENCY = {
        "daily": 7,
        "monthly": 45,
    }

    def __init__(
        self,
        bcra_client: BCRAClient | None = None,
        datos_client: DatosGobSeriesClient | None = None,
        fx_client: FXJSONClient | None = None,
    ):
        self.bcra_client = bcra_client or BCRAClient()
        self.datos_client = datos_client or DatosGobSeriesClient()
        self.fx_client = fx_client or FXJSONClient()

    def sync_all(self) -> dict:
        results = {}
        for series_key, config in ParametrosMacroLocal.SERIES.items():
            try:
                results[series_key] = self.sync_series(series_key)
            except Exception as exc:
                results[series_key] = {
                    "success": False,
                    "series_key": series_key,
                    "title": config["title"],
                    "source": config["source"],
                    "rows_received": 0,
                    "created": 0,
                    "updated": 0,
                    "error": str(exc),
                }
        return results

    def sync_series(self, series_key: str) -> dict:
        config = ParametrosMacroLocal.SERIES.get(series_key)
        if not config:
            raise ValueError(f"Unknown macro series key: {series_key}")

        try:
            rows = self._fetch_rows(config)
        except OptionalSourceUnavailableError as exc:
            if not config.get("optional"):
                raise
            return {
                "success": True,
                "series_key": series_key,
                "title": config["title"],
                "source": config["source"],
                "rows_received": 0,
                "created": 0,
                "updated": 0,
                "skipped": True,
                "reason": str(exc),
            }
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
        return build_context_summary(self, total_iol=total_iol)

    def get_status_summary(self) -> list[dict]:
        today = timezone.localdate()
        aggregated = {
            row["series_key"]: row
            for row in MacroSeriesSnapshot.objects.values("series_key").annotate(
                latest_date=Max("fecha"),
                rows_count=Count("id"),
            )
        }

        rows = []
        for series_key, config in ParametrosMacroLocal.SERIES.items():
            snapshot_row = aggregated.get(series_key)
            latest_date = snapshot_row["latest_date"] if snapshot_row else None
            rows_count = snapshot_row["rows_count"] if snapshot_row else 0
            configured = self._is_series_configured(series_key, config)
            is_optional = bool(config.get("optional"))
            stale_days = self.STALENESS_DAYS_BY_FREQUENCY.get(config["frequency"], 7)

            if is_optional and not configured:
                status = "not_configured"
            elif rows_count == 0 or latest_date is None:
                status = "missing"
            elif (today - latest_date).days > stale_days:
                status = "stale"
            else:
                status = "ready"

            rows.append(
                {
                    "series_key": series_key,
                    "title": config["title"],
                    "source": config["source"],
                    "frequency": config["frequency"],
                    "latest_date": latest_date,
                    "rows_count": rows_count,
                    "configured": configured,
                    "optional": is_optional,
                    "status": status,
                    "is_ready": status == "ready",
                }
            )
        return rows

    @classmethod
    def summarize_sync_result(cls, result: dict) -> dict:
        synced_series = []
        skipped_series = []
        failed_series = []

        for series_key, payload in (result or {}).items():
            if not isinstance(payload, dict):
                failed_series.append(str(series_key))
                continue
            if payload.get("success") is False:
                failed_series.append(str(series_key))
            elif payload.get("skipped"):
                skipped_series.append(str(series_key))
            else:
                synced_series.append(str(series_key))

        if failed_series:
            state = "failed"
        elif skipped_series:
            state = "success_with_skips"
        else:
            state = "success"

        return {
            "metric_name": cls.SYNC_STATE_METRIC,
            "state": state,
            "extra": {
                "synced_series": synced_series,
                "skipped_series": skipped_series,
                "failed_series": failed_series,
            },
        }

    def build_macro_comparison(self, days: int = 365, base_value: float = 100.0) -> dict:
        df = self._build_real_portfolio_frame(days=days)
        if df.empty or len(df.index) < 2:
            return {"series": [], "warning": "insufficient_history", "requested_days": days}

        normalized = pd.DataFrame(index=df.index)
        normalized["portfolio"] = self._normalize_series(df["portfolio"], base_value)
        normalized["portfolio_real"] = self._normalize_series(df["portfolio_real"], base_value)
        normalized["usdars_oficial"] = self._normalize_series(df["usdars_oficial"], base_value)
        normalized["ipc_nacional"] = self._normalize_series(df["ipc_nacional"], base_value)

        series = [
            {
                "fecha": idx.date().isoformat(),
                "portfolio": round(float(row["portfolio"]), 2),
                "portfolio_real": round(float(row["portfolio_real"]), 2),
                "usdars_oficial": round(float(row["usdars_oficial"]), 2),
                "ipc_nacional": round(float(row["ipc_nacional"]), 2),
            }
            for idx, row in normalized.iterrows()
        ]
        return {
            "series": series,
            "base_value": base_value,
            "requested_days": days,
            "observations": len(series),
            "max_drawdown_nominal": round(self._calculate_max_drawdown(normalized["portfolio"]), 2),
            "max_drawdown_real": round(self._calculate_max_drawdown(normalized["portfolio_real"]), 2),
        }

    def get_real_historical_metrics(self, days: int = 365) -> dict:
        df = self._build_real_portfolio_frame(days=days)
        if df.empty or len(df.index) < 2:
            return {
                "max_drawdown_real": None,
                "real_history_observations": 0,
            }

        normalized_real = self._normalize_series(df["portfolio_real"], 100.0)
        return {
            "max_drawdown_real": round(self._calculate_max_drawdown(normalized_real), 2),
            "real_history_observations": int(len(df.index)),
        }

    def build_rate_returns(self, series_key: str, dates, periods_per_year: int) -> pd.Series:
        normalized_dates = pd.to_datetime(list(dates))
        if len(normalized_dates) == 0:
            return pd.Series(dtype=float)

        series_df = self._build_macro_series_frame(series_key, days=int((normalized_dates.max() - normalized_dates.min()).days) + 30, extra_days=30)
        if series_df.empty:
            return pd.Series(dtype=float)

        series_df = series_df.reindex(normalized_dates.union(series_df.index)).sort_index().ffill().reindex(normalized_dates)
        if series_df.empty or series_key not in series_df:
            return pd.Series(dtype=float)

        rate_series = pd.to_numeric(series_df[series_key], errors="coerce") / 100.0
        return rate_series / periods_per_year

    def _get_latest_snapshot(self, series_key: str):
        return MacroSeriesSnapshot.objects.filter(series_key=series_key).order_by("-fecha").first()

    def _calculate_ipc_variation_yoy(self, ipc_latest):
        return calculate_ipc_variation_yoy(ipc_latest)

    def _calculate_ipc_variation_ytd(self, ipc_latest):
        return calculate_ipc_variation_ytd(ipc_latest)

    def _calculate_portfolio_ytd(self, ipc_variation_ytd: float | None) -> dict:
        return calculate_portfolio_ytd(ipc_variation_ytd)

    def _calculate_badlar_ytd(self):
        return calculate_badlar_ytd(self)

    def _calculate_series_change(self, series_key: str, *, lookback_days: int) -> dict:
        return calculate_series_change(self, series_key, lookback_days=lookback_days)

    def _calculate_fx_gap_change(self, *, lookback_days: int) -> dict:
        return calculate_fx_gap_change(self, lookback_days=lookback_days)

    def _fetch_rows(self, config: dict) -> list[dict]:
        if config["source"] == "bcra":
            return self.bcra_client.fetch_variable(config["external_id"])
        if config["source"] == "datos_gob_ar":
            return self.datos_client.fetch_series(config["external_id"])
        if config["source"] == "fx_json":
            if config["external_id"] == "usdars_mep":
                return self.fx_client.fetch_usdars_mep()
            if config["external_id"] == "usdars_ccl":
                return self.fx_client.fetch_usdars_ccl()
            if config["external_id"] == "riesgo_pais_arg":
                return self.fx_client.fetch_riesgo_pais()
            if config["external_id"] == "uva":
                return self.fx_client.fetch_uva()
            raise ValueError(f"Unsupported fx_json external_id: {config['external_id']}")
        raise ValueError(f"Unsupported macro source: {config['source']}")

    def _is_series_configured(self, series_key: str, config: dict) -> bool:
        if config["source"] != "fx_json":
            return True
        if series_key == "usdars_mep":
            return bool(self.fx_client.mep_url)
        if series_key == "usdars_ccl":
            return bool(self.fx_client.ccl_url)
        if series_key == "riesgo_pais_arg":
            return bool(self.fx_client.country_risk_url)
        if series_key == "uva":
            return bool(self.fx_client.uva_url)
        return False

    @staticmethod
    def _calculate_gap_pct(financial_value: float | None, official_value: float | None) -> float | None:
        return calculate_gap_pct(financial_value, official_value)

    @staticmethod
    def _round_or_none(value: float | None) -> float | None:
        return round_or_none(value)

    @staticmethod
    def _annualize_change_pct(change_pct: float | None, *, lookback_days: int) -> float | None:
        return annualize_change_pct(change_pct, lookback_days=lookback_days)

    def _build_fx_context_summary(
        self,
        *,
        official_snapshot,
        mep_snapshot,
        ccl_snapshot,
        lookback_days: int,
    ) -> dict:
        return build_fx_context_summary(
            self,
            official_snapshot=official_snapshot,
            mep_snapshot=mep_snapshot,
            ccl_snapshot=ccl_snapshot,
            lookback_days=lookback_days,
        )

    def _build_portfolio_history(self, days: int) -> pd.DataFrame:
        end_date = PortfolioSnapshot.objects.order_by("-fecha").first()
        if end_date is None:
            return pd.DataFrame()

        latest_date = end_date.fecha
        start_date = latest_date - pd.Timedelta(days=days)
        snapshots = PortfolioSnapshot.objects.filter(fecha__range=(start_date, latest_date)).order_by("fecha")
        if snapshots.count() >= 2:
            df = pd.DataFrame(list(snapshots.values("fecha", "total_iol")))
            df["fecha"] = pd.to_datetime(df["fecha"])
            df["total_iol"] = pd.to_numeric(df["total_iol"], errors="coerce")
            return df.dropna(subset=["total_iol"]).set_index("fecha").rename(columns={"total_iol": "portfolio"})

        from apps.dashboard.selectors import get_evolucion_historica

        evolution = get_evolucion_historica(days=days, max_points=days)
        if not evolution or not evolution.get("tiene_datos"):
            return pd.DataFrame()
        df = pd.DataFrame({"fecha": evolution.get("fechas", []), "portfolio": evolution.get("total_iol", [])})
        if df.empty:
            return pd.DataFrame()
        df["fecha"] = pd.to_datetime(df["fecha"])
        df["portfolio"] = pd.to_numeric(df["portfolio"], errors="coerce")
        return df.dropna(subset=["portfolio"]).set_index("fecha")

    def _build_macro_series_frame(self, series_key: str, days: int, extra_days: int) -> pd.DataFrame:
        latest = self._get_latest_snapshot(series_key)
        if latest is None:
            return pd.DataFrame()

        start_date = latest.fecha - pd.Timedelta(days=days + extra_days)
        qs = MacroSeriesSnapshot.objects.filter(series_key=series_key, fecha__gte=start_date).order_by("fecha")
        df = pd.DataFrame(list(qs.values("fecha", "value")))
        if df.empty:
            return pd.DataFrame()
        df["fecha"] = pd.to_datetime(df["fecha"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        return df.dropna(subset=["value"]).set_index("fecha").rename(columns={"value": series_key})

    def _build_real_portfolio_frame(self, days: int) -> pd.DataFrame:
        portfolio_df = self._build_portfolio_history(days=days)
        if portfolio_df.empty or len(portfolio_df.index) < 2:
            return pd.DataFrame()

        usdars_df = self._build_macro_series_frame("usdars_oficial", days=days, extra_days=7)
        ipc_df = self._build_macro_series_frame("ipc_nacional", days=days, extra_days=45)
        if usdars_df.empty or ipc_df.empty:
            return pd.DataFrame()
        if not usdars_df.empty:
            usdars_df = (
                usdars_df.reindex(portfolio_df.index.union(usdars_df.index))
                .sort_index()
                .ffill()
                .reindex(portfolio_df.index)
            )
        if not ipc_df.empty:
            ipc_df = (
                ipc_df.reindex(portfolio_df.index.union(ipc_df.index))
                .sort_index()
                .ffill()
                .reindex(portfolio_df.index)
            )

        df = portfolio_df.join(usdars_df, how="left").join(ipc_df, how="left")
        df = df.sort_index().ffill().dropna(subset=["portfolio", "usdars_oficial", "ipc_nacional"])
        if len(df.index) < 2:
            return pd.DataFrame()

        initial_ipc = float(df["ipc_nacional"].iloc[0])
        if initial_ipc <= 0:
            return pd.DataFrame()
        df["portfolio_real"] = df["portfolio"].astype(float) / (df["ipc_nacional"].astype(float) / initial_ipc)
        return df

    @staticmethod
    def _calculate_max_drawdown(series: pd.Series) -> float:
        running_max = series.astype(float).cummax()
        drawdown = (series.astype(float) / running_max - 1.0) * 100.0
        return float(drawdown.min())

    @staticmethod
    def _normalize_series(series: pd.Series, base_value: float) -> pd.Series:
        initial_value = float(series.iloc[0])
        if initial_value <= 0:
            return pd.Series([base_value] * len(series.index), index=series.index, dtype=float)
        return (series.astype(float) / initial_value) * base_value
