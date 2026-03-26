from __future__ import annotations

import pandas as pd

from apps.core.models import MacroSeriesSnapshot
from apps.portafolio_iol.models import PortfolioSnapshot


def build_context_summary(service, *, total_iol: float | None = None) -> dict:
    usdars_latest = service._get_latest_snapshot("usdars_oficial")
    usdars_mep_latest = service._get_latest_snapshot("usdars_mep")
    usdars_ccl_latest = service._get_latest_snapshot("usdars_ccl")
    riesgo_pais_latest = service._get_latest_snapshot("riesgo_pais_arg")
    uva_latest = service._get_latest_snapshot("uva")
    badlar_latest = service._get_latest_snapshot("badlar_privada")
    ipc_snapshots = list(
        MacroSeriesSnapshot.objects.filter(series_key="ipc_nacional").order_by("-fecha")[:2]
    )
    ipc_latest = ipc_snapshots[0] if ipc_snapshots else None
    ipc_variation = None
    if len(ipc_snapshots) >= 2 and float(ipc_snapshots[1].value) != 0:
        ipc_variation = ((float(ipc_snapshots[0].value) / float(ipc_snapshots[1].value)) - 1) * 100
    ipc_variation_yoy = calculate_ipc_variation_yoy(ipc_latest)
    ipc_variation_ytd = calculate_ipc_variation_ytd(ipc_latest)

    total_iol_usd = None
    if total_iol and usdars_latest and float(usdars_latest.value) > 0:
        total_iol_usd = float(total_iol) / float(usdars_latest.value)
    fx_context = build_fx_context_summary(
        service,
        official_snapshot=usdars_latest,
        mep_snapshot=usdars_mep_latest,
        ccl_snapshot=usdars_ccl_latest,
        lookback_days=30,
    )
    riesgo_pais_change_30d = calculate_series_change(service, "riesgo_pais_arg", lookback_days=30)
    uva_change_30d = calculate_series_change(service, "uva", lookback_days=30)
    uva_annualized_30d = annualize_change_pct(uva_change_30d.get("change_pct"), lookback_days=30)
    real_rate_badlar_vs_uva_30d = None
    if badlar_latest and uva_annualized_30d is not None:
        real_rate_badlar_vs_uva_30d = float(badlar_latest.value) - uva_annualized_30d
    portfolio_ytd = calculate_portfolio_ytd(ipc_variation_ytd)
    badlar_ytd = calculate_badlar_ytd(service)
    portfolio_excess_ytd_vs_badlar = None
    if (
        portfolio_ytd.get("portfolio_return_ytd_nominal") is not None and
        badlar_ytd is not None
    ):
        portfolio_excess_ytd_vs_badlar = portfolio_ytd["portfolio_return_ytd_nominal"] - badlar_ytd

    return {
        "usdars_oficial": float(usdars_latest.value) if usdars_latest else None,
        "usdars_oficial_date": usdars_latest.fecha if usdars_latest else None,
        "usdars_mep": float(usdars_mep_latest.value) if usdars_mep_latest else None,
        "usdars_mep_date": usdars_mep_latest.fecha if usdars_mep_latest else None,
        "usdars_ccl": float(usdars_ccl_latest.value) if usdars_ccl_latest else None,
        "usdars_ccl_date": usdars_ccl_latest.fecha if usdars_ccl_latest else None,
        "usdars_financial": fx_context["financial_value"],
        "usdars_financial_source": fx_context["financial_source"],
        "fx_gap_pct": fx_context["fx_gap_pct"],
        "fx_gap_mep_pct": fx_context["fx_gap_mep_pct"],
        "fx_gap_ccl_pct": fx_context["fx_gap_ccl_pct"],
        "fx_gap_change_30d": fx_context["fx_gap_change_30d"],
        "fx_gap_change_pct_30d": fx_context["fx_gap_change_pct_30d"],
        "fx_gap_base_date_30d": fx_context["fx_gap_base_date_30d"],
        "fx_mep_ccl_spread_pct": fx_context["fx_mep_ccl_spread_pct"],
        "fx_signal_state": fx_context["fx_signal_state"],
        "riesgo_pais_arg": float(riesgo_pais_latest.value) if riesgo_pais_latest else None,
        "riesgo_pais_arg_date": riesgo_pais_latest.fecha if riesgo_pais_latest else None,
        "riesgo_pais_arg_change_30d": (
            round(riesgo_pais_change_30d["change"], 2) if riesgo_pais_change_30d.get("change") is not None else None
        ),
        "riesgo_pais_arg_change_pct_30d": (
            round(riesgo_pais_change_30d["change_pct"], 2)
            if riesgo_pais_change_30d.get("change_pct") is not None else None
        ),
        "riesgo_pais_arg_base_date_30d": riesgo_pais_change_30d.get("base_date"),
        "uva": float(uva_latest.value) if uva_latest else None,
        "uva_date": uva_latest.fecha if uva_latest else None,
        "uva_change_30d": round(uva_change_30d["change"], 2) if uva_change_30d.get("change") is not None else None,
        "uva_change_pct_30d": (
            round(uva_change_30d["change_pct"], 2) if uva_change_30d.get("change_pct") is not None else None
        ),
        "uva_base_date_30d": uva_change_30d.get("base_date"),
        "uva_annualized_pct_30d": round(uva_annualized_30d, 2) if uva_annualized_30d is not None else None,
        "real_rate_badlar_vs_uva_30d": (
            round(real_rate_badlar_vs_uva_30d, 2) if real_rate_badlar_vs_uva_30d is not None else None
        ),
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


def calculate_ipc_variation_yoy(ipc_latest):
    if ipc_latest is None:
        return None

    previous_year = MacroSeriesSnapshot.objects.filter(
        series_key="ipc_nacional",
        fecha=ipc_latest.fecha.replace(year=ipc_latest.fecha.year - 1),
    ).first()
    if previous_year is None or float(previous_year.value) == 0:
        return None
    return ((float(ipc_latest.value) / float(previous_year.value)) - 1) * 100


def calculate_ipc_variation_ytd(ipc_latest):
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


def calculate_portfolio_ytd(ipc_variation_ytd: float | None) -> dict:
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


def calculate_badlar_ytd(service):
    latest_snapshot = service._get_latest_snapshot("badlar_privada")
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


def calculate_series_change(service, series_key: str, *, lookback_days: int) -> dict:
    latest_snapshot = service._get_latest_snapshot(series_key)
    if latest_snapshot is None:
        return {"change": None, "change_pct": None, "base_date": None}

    cutoff_date = latest_snapshot.fecha - pd.Timedelta(days=lookback_days)
    base_snapshot = (
        MacroSeriesSnapshot.objects.filter(series_key=series_key, fecha__lte=cutoff_date)
        .order_by("-fecha")
        .first()
    )
    if base_snapshot is None:
        return {"change": None, "change_pct": None, "base_date": None}

    latest_value = float(latest_snapshot.value)
    base_value = float(base_snapshot.value)
    change_pct = None
    if base_value != 0:
        change_pct = ((latest_value / base_value) - 1) * 100

    return {
        "change": latest_value - base_value,
        "change_pct": change_pct,
        "base_date": base_snapshot.fecha,
    }


def calculate_fx_gap_change(service, *, lookback_days: int) -> dict:
    latest_official = service._get_latest_snapshot("usdars_oficial")
    latest_mep = service._get_latest_snapshot("usdars_mep")
    latest_ccl = service._get_latest_snapshot("usdars_ccl")
    if latest_official is None or (latest_mep is None and latest_ccl is None):
        return {"change": None, "change_pct": None, "base_date": None}

    latest_official_value = float(latest_official.value)
    if latest_official_value <= 0:
        return {"change": None, "change_pct": None, "base_date": None}
    latest_financial_values = [
        float(snapshot.value)
        for snapshot in (latest_mep, latest_ccl)
        if snapshot is not None
    ]
    latest_gap = calculate_gap_pct(
        sum(latest_financial_values) / len(latest_financial_values) if latest_financial_values else None,
        latest_official_value,
    )
    if latest_gap is None:
        return {"change": None, "change_pct": None, "base_date": None}

    latest_dates = [latest_official.fecha]
    if latest_mep is not None:
        latest_dates.append(latest_mep.fecha)
    if latest_ccl is not None:
        latest_dates.append(latest_ccl.fecha)
    cutoff_date = min(latest_dates) - pd.Timedelta(days=lookback_days)
    base_official = (
        MacroSeriesSnapshot.objects.filter(series_key="usdars_oficial", fecha__lte=cutoff_date)
        .order_by("-fecha")
        .first()
    )
    base_mep = (
        MacroSeriesSnapshot.objects.filter(series_key="usdars_mep", fecha__lte=cutoff_date)
        .order_by("-fecha")
        .first()
    )
    base_ccl = (
        MacroSeriesSnapshot.objects.filter(series_key="usdars_ccl", fecha__lte=cutoff_date)
        .order_by("-fecha")
        .first()
    )
    if base_official is None or (base_mep is None and base_ccl is None):
        return {"change": None, "change_pct": None, "base_date": None}

    base_official_value = float(base_official.value)
    if base_official_value <= 0:
        return {"change": None, "change_pct": None, "base_date": None}
    base_financial_values = [
        float(snapshot.value)
        for snapshot in (base_mep, base_ccl)
        if snapshot is not None
    ]
    base_gap = calculate_gap_pct(
        sum(base_financial_values) / len(base_financial_values) if base_financial_values else None,
        base_official_value,
    )
    if base_gap is None:
        return {"change": None, "change_pct": None, "base_date": None}
    change_pct = None
    if base_gap != 0:
        change_pct = ((latest_gap / base_gap) - 1) * 100

    base_dates = [base_official.fecha]
    if base_mep is not None:
        base_dates.append(base_mep.fecha)
    if base_ccl is not None:
        base_dates.append(base_ccl.fecha)
    return {
        "change": latest_gap - base_gap,
        "change_pct": change_pct,
        "base_date": min(base_dates),
    }


def calculate_gap_pct(financial_value: float | None, official_value: float | None) -> float | None:
    if financial_value is None or official_value is None or official_value <= 0:
        return None
    return ((financial_value / official_value) - 1) * 100


def round_or_none(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def annualize_change_pct(change_pct: float | None, *, lookback_days: int) -> float | None:
    if change_pct is None or lookback_days <= 0:
        return None
    growth_factor = 1 + (float(change_pct) / 100.0)
    if growth_factor <= 0:
        return None
    return ((growth_factor ** (365.0 / lookback_days)) - 1.0) * 100.0


def build_fx_context_summary(
    service,
    *,
    official_snapshot,
    mep_snapshot,
    ccl_snapshot,
    lookback_days: int,
) -> dict:
    official_value = float(official_snapshot.value) if official_snapshot else None
    mep_value = float(mep_snapshot.value) if mep_snapshot else None
    ccl_value = float(ccl_snapshot.value) if ccl_snapshot else None

    current_financial_values = [value for value in (mep_value, ccl_value) if value is not None]
    financial_value = None
    financial_source = None
    if len(current_financial_values) == 2:
        financial_value = sum(current_financial_values) / 2.0
        financial_source = "blend_mep_ccl"
    elif mep_value is not None:
        financial_value = mep_value
        financial_source = "mep"
    elif ccl_value is not None:
        financial_value = ccl_value
        financial_source = "ccl"

    mep_gap_pct = calculate_gap_pct(mep_value, official_value)
    ccl_gap_pct = calculate_gap_pct(ccl_value, official_value)
    fx_gap_pct = calculate_gap_pct(financial_value, official_value)
    fx_gap_change = calculate_fx_gap_change(service, lookback_days=lookback_days)

    mep_ccl_spread_pct = None
    if mep_value is not None and ccl_value is not None and mep_value > 0:
        mep_ccl_spread_pct = abs((ccl_value / mep_value) - 1.0) * 100.0

    signal_state = "normal"
    if mep_ccl_spread_pct is not None and mep_ccl_spread_pct >= 3.0:
        signal_state = "divergent"
    elif (
        (fx_gap_pct is not None and fx_gap_pct >= 20.0)
        or (fx_gap_change.get("change") is not None and float(fx_gap_change["change"]) >= 5.0)
        or (fx_gap_change.get("change_pct") is not None and float(fx_gap_change["change_pct"]) >= 25.0)
    ):
        signal_state = "tensioned"

    return {
        "financial_value": round_or_none(financial_value),
        "financial_source": financial_source,
        "fx_gap_pct": round_or_none(fx_gap_pct),
        "fx_gap_mep_pct": round_or_none(mep_gap_pct),
        "fx_gap_ccl_pct": round_or_none(ccl_gap_pct),
        "fx_gap_change_30d": round_or_none(fx_gap_change.get("change")),
        "fx_gap_change_pct_30d": round_or_none(fx_gap_change.get("change_pct")),
        "fx_gap_base_date_30d": fx_gap_change.get("base_date"),
        "fx_mep_ccl_spread_pct": round_or_none(mep_ccl_spread_pct),
        "fx_signal_state": signal_state,
    }
