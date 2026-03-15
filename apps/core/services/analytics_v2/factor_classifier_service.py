from __future__ import annotations

from apps.core.services.analytics_v2.schemas import FactorClassification, NormalizedPosition


class FactorClassifierService:
    """Clasificacion proxy MVP por activo con trazabilidad de origen."""

    EXPLICIT_SYMBOL_MAP = {
        "AAPL": ("growth", "high", "big_tech_explicit"),
        "MSFT": ("growth", "high", "big_tech_explicit"),
        "GOOGL": ("growth", "high", "big_tech_explicit"),
        "NVDA": ("growth", "high", "big_tech_explicit"),
        "CRM": ("growth", "high", "big_tech_explicit"),
        "AMZN": ("growth", "high", "growth_explicit"),
        "MELI": ("growth", "high", "growth_explicit"),
        "BABA": ("growth", "high", "growth_explicit"),
        "AMD": ("growth", "high", "growth_explicit"),
        "T": ("dividend", "high", "dividend_explicit"),
        "KO": ("dividend", "high", "dividend_explicit"),
        "MCD": ("dividend", "high", "dividend_explicit"),
        "XLU": ("defensive", "high", "defensive_explicit"),
        "XLV": ("defensive", "high", "defensive_explicit"),
        "BRKB": ("quality", "high", "quality_explicit"),
        "SPY": ("quality", "medium", "broad_market_proxy"),
        "DIA": ("value", "medium", "large_cap_value_proxy"),
        "EEM": ("cyclical", "medium", "emerging_markets_proxy"),
        "EWZ": ("cyclical", "medium", "emerging_markets_proxy"),
        "IEUR": ("value", "medium", "developed_ex_usa_proxy"),
        "NEM": ("cyclical", "medium", "commodity_proxy"),
        "VIST": ("cyclical", "medium", "energy_proxy"),
        "YPFD": ("cyclical", "medium", "energy_proxy"),
        "LOMA": ("cyclical", "medium", "materials_proxy"),
        "DISN": ("cyclical", "medium", "consumer_media_proxy"),
        "V": ("quality", "medium", "payments_proxy"),
    }

    STRATEGIC_BUCKET_MAP = {
        "growth": ("growth", "medium", "strategic_bucket"),
        "dividendos": ("dividend", "medium", "strategic_bucket"),
        "defensivo": ("defensive", "medium", "strategic_bucket"),
        "commodities": ("cyclical", "medium", "strategic_bucket"),
    }

    SECTOR_MAP = {
        "utilities": ("defensive", "medium", "sector"),
        "salud": ("defensive", "medium", "sector"),
        "consumo defensivo": ("defensive", "medium", "sector"),
        "telecom": ("dividend", "medium", "sector"),
        "energia": ("cyclical", "medium", "sector"),
        "materiales": ("cyclical", "medium", "sector"),
        "mineria": ("cyclical", "medium", "sector"),
    }

    def classify_position(self, position: NormalizedPosition) -> dict:
        symbol = (position.symbol or "").strip().upper()
        explicit = self.EXPLICIT_SYMBOL_MAP.get(symbol)
        if explicit:
            return FactorClassification(
                symbol=symbol,
                factor=explicit[0],
                confidence=explicit[1],
                source="explicit_symbol_map",
                notes=explicit[2],
            ).to_dict()

        strategic_bucket = (position.strategic_bucket or "").strip().lower()
        bucket_mapping = self.STRATEGIC_BUCKET_MAP.get(strategic_bucket)
        if bucket_mapping:
            return FactorClassification(
                symbol=symbol,
                factor=bucket_mapping[0],
                confidence=bucket_mapping[1],
                source=bucket_mapping[2],
                notes=f"strategic_bucket={position.strategic_bucket}",
            ).to_dict()

        sector = (position.sector or "").strip().lower()
        if sector.startswith("tecnolog"):
            return FactorClassification(
                symbol=symbol,
                factor="growth",
                confidence="medium",
                source="sector",
                notes=f"sector={position.sector}",
            ).to_dict()

        sector_mapping = self.SECTOR_MAP.get(sector)
        if sector_mapping:
            return FactorClassification(
                symbol=symbol,
                factor=sector_mapping[0],
                confidence=sector_mapping[1],
                source=sector_mapping[2],
                notes=f"sector={position.sector}",
            ).to_dict()

        asset_type = (position.asset_type or "").strip().lower()
        if asset_type in {"bond", "fci", "cash", "unknown"}:
            return FactorClassification(
                symbol=symbol,
                factor=None,
                confidence="low",
                source="unknown",
                notes=f"asset_type={position.asset_type or 'unknown'}",
            ).to_dict()

        return FactorClassification(
            symbol=symbol,
            factor=None,
            confidence="low",
            source="unknown",
            notes="no reliable factor proxy",
        ).to_dict()
