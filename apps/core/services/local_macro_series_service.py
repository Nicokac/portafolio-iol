from __future__ import annotations

from decimal import Decimal

import pandas as pd
from django.db import transaction

from apps.core.config.parametros_macro_local import ParametrosMacroLocal
from apps.core.models import MacroSeriesSnapshot
from apps.core.services.market_data.bcra_client import BCRAClient
from apps.core.services.market_data.datos_gob_client import DatosGobSeriesClient
from apps.portafolio_iol.models import PortfolioSnapshot


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
        badlar_latest = self._get_latest_snapshot("badlar_privada")
        ipc_snapshots = list(
            MacroSeriesSnapshot.objects.filter(series_key="ipc_nacional").order_by("-fecha")[:2]
        )
        ipc_latest = ipc_snapshots[0] if ipc_snapshots else None
        ipc_variation = None
        if len(ipc_snapshots) >= 2 and float(ipc_snapshots[1].value) != 0:
            ipc_variation = ((float(ipc_snapshots[0].value) / float(ipc_snapshots[1].value)) - 1) * 100
        ipc_variation_yoy = self._calculate_ipc_variation_yoy(ipc_latest)
        ipc_variation_ytd = self._calculate_ipc_variation_ytd(ipc_latest)

        total_iol_usd = None
        if total_iol and usdars_latest and float(usdars_latest.value) > 0:
            total_iol_usd = float(total_iol) / float(usdars_latest.value)
        portfolio_ytd = self._calculate_portfolio_ytd(ipc_variation_ytd)
        badlar_ytd = self._calculate_badlar_ytd()
        portfolio_excess_ytd_vs_badlar = None
        if (
            portfolio_ytd.get("portfolio_return_ytd_nominal") is not None and
            badlar_ytd is not None
        ):
            portfolio_excess_ytd_vs_badlar = portfolio_ytd["portfolio_return_ytd_nominal"] - badlar_ytd

        return {
            "usdars_oficial": float(usdars_latest.value) if usdars_latest else None,
            "usdars_oficial_date": usdars_latest.fecha if usdars_latest else None,
            "badlar_privada": float(badlar_latest.value) if badlar_latest else None,
            "badlar_privada_date": badlar_latest.fecha if badlar_latest else None,
            "badlar_ytd": round(badlar_ytd, 2) if badlar_ytd is not None else None,
            "ipc_nacional_index": float(ipc_latest.value) if ipc_latest else None,
            "ipc_nacional_date": ipc_latest.fecha if ipc_latest else None,
            "ipc_nacional_variation_mom": round(ipc_variation, 2) if ipc_variation is not None else None,
            "ipc_nacional_variation_yoy": round(ipc_variation_yoy, 2) if ipc_variation_yoy is not None else None,
            "ipc_nacional_variation_ytd": round(ipc_variation_ytd, 2) if ipc_variation_ytd is not None else None,
            "total_iol_usd_oficial": round(total_iol_usd, 2) if total_iol_usd is not None else None,
            "portfolio_excess_ytd_vs_badlar": round(portfolio_excess_ytd_vs_badlar, 2) if portfolio_excess_ytd_vs_badlar is not None else None,
            **portfolio_ytd,
        }

    def build_macro_comparison(self, days: int = 365, base_value: float = 100.0) -> dict:
        portfolio_df = self._build_portfolio_history(days=days)
        if portfolio_df.empty or len(portfolio_df.index) < 2:
            return {"series": [], "warning": "insufficient_history", "requested_days": days}

        usdars_df = self._build_macro_series_frame("usdars_oficial", days=days, extra_days=7)
        ipc_df = self._build_macro_series_frame("ipc_nacional", days=days, extra_days=45)
        if not usdars_df.empty:
            usdars_df = usdars_df.reindex(portfolio_df.index.union(usdars_df.index)).sort_index().ffill().reindex(portfolio_df.index)
        if not ipc_df.empty:
            ipc_df = ipc_df.reindex(portfolio_df.index.union(ipc_df.index)).sort_index().ffill().reindex(portfolio_df.index)

        df = portfolio_df.join(usdars_df, how="left").join(ipc_df, how="left")
        df = df.sort_index().ffill().dropna(subset=["portfolio", "usdars_oficial", "ipc_nacional"])
        if len(df.index) < 2:
            return {"series": [], "warning": "insufficient_history", "requested_days": days}

        normalized = pd.DataFrame(index=df.index)
        normalized["portfolio"] = self._normalize_series(df["portfolio"], base_value)
        normalized["usdars_oficial"] = self._normalize_series(df["usdars_oficial"], base_value)
        normalized["ipc_nacional"] = self._normalize_series(df["ipc_nacional"], base_value)

        series = [
            {
                "fecha": idx.date().isoformat(),
                "portfolio": round(float(row["portfolio"]), 2),
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
        if ipc_latest is None:
            return None

        previous_year = MacroSeriesSnapshot.objects.filter(
            series_key="ipc_nacional",
            fecha=ipc_latest.fecha.replace(year=ipc_latest.fecha.year - 1),
        ).first()
        if previous_year is None or float(previous_year.value) == 0:
            return None
        return ((float(ipc_latest.value) / float(previous_year.value)) - 1) * 100

    def _calculate_ipc_variation_ytd(self, ipc_latest):
        if ipc_latest is None:
            return None

        previous_december = MacroSeriesSnapshot.objects.filter(
            series_key="ipc_nacional",
            fecha__year=ipc_latest.fecha.year - 1,
            fecha__month=12,
        ).first()
        if previous_december is None or float(previous_december.value) == 0:
            return None
        return ((float(ipc_latest.value) / float(previous_december.value)) - 1) * 100

    def _calculate_portfolio_ytd(self, ipc_variation_ytd: float | None) -> dict:
        latest_snapshot = PortfolioSnapshot.objects.order_by("-fecha").first()
        if latest_snapshot is None:
            return {
                "portfolio_return_ytd_nominal": None,
                "portfolio_return_ytd_real": None,
                "portfolio_return_ytd_is_partial": False,
                "portfolio_return_ytd_base_date": None,
            }

        previous_year_end = latest_snapshot.fecha.replace(year=latest_snapshot.fecha.year - 1, month=12, day=31)
        baseline_snapshot = PortfolioSnapshot.objects.filter(fecha__lte=previous_year_end).order_by("-fecha").first()
        is_partial = False

        if baseline_snapshot is None:
            baseline_snapshot = PortfolioSnapshot.objects.filter(
                fecha__year=latest_snapshot.fecha.year
            ).order_by("fecha").first()
            is_partial = True

        if (
            baseline_snapshot is None or
            baseline_snapshot.fecha == latest_snapshot.fecha or
            float(baseline_snapshot.total_iol) <= 0
        ):
            return {
                "portfolio_return_ytd_nominal": None,
                "portfolio_return_ytd_real": None,
                "portfolio_return_ytd_is_partial": is_partial,
                "portfolio_return_ytd_base_date": baseline_snapshot.fecha if baseline_snapshot else None,
            }

        nominal_return = ((float(latest_snapshot.total_iol) / float(baseline_snapshot.total_iol)) - 1) * 100
        real_return = None
        if ipc_variation_ytd is not None:
            real_return = (((1 + (nominal_return / 100)) / (1 + (ipc_variation_ytd / 100))) - 1) * 100

        return {
            "portfolio_return_ytd_nominal": round(nominal_return, 2),
            "portfolio_return_ytd_real": round(real_return, 2) if real_return is not None else None,
            "portfolio_return_ytd_is_partial": is_partial,
            "portfolio_return_ytd_base_date": baseline_snapshot.fecha,
        }

    def _calculate_badlar_ytd(self):
        latest_snapshot = self._get_latest_snapshot("badlar_privada")
        if latest_snapshot is None:
            return None

        start_of_year = latest_snapshot.fecha.replace(month=1, day=1)
        qs = MacroSeriesSnapshot.objects.filter(
            series_key="badlar_privada",
            fecha__gte=start_of_year,
            fecha__lte=latest_snapshot.fecha,
        ).order_by("fecha")
        if not qs.exists():
            return None

        df = pd.DataFrame(list(qs.values("fecha", "value")))
        if df.empty:
            return None

        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna(subset=["value"])
        if df.empty:
            return None

        period_returns = (df["value"].astype(float) / 100.0) / 252.0
        cumulative = (1 + period_returns).prod() - 1
        return cumulative * 100

    def _fetch_rows(self, config: dict) -> list[dict]:
        if config["source"] == "bcra":
            return self.bcra_client.fetch_variable(config["external_id"])
        if config["source"] == "datos_gob_ar":
            return self.datos_client.fetch_series(config["external_id"])
        raise ValueError(f"Unsupported macro source: {config['source']}")

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

    @staticmethod
    def _normalize_series(series: pd.Series, base_value: float) -> pd.Series:
        initial_value = float(series.iloc[0])
        if initial_value <= 0:
            return pd.Series([base_value] * len(series.index), index=series.index, dtype=float)
        return (series.astype(float) / initial_value) * base_value
