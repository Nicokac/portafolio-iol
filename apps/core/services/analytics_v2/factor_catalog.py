from __future__ import annotations

from dataclasses import dataclass

from apps.core.services.analytics_v2.schemas import FactorDefinition


@dataclass(frozen=True)
class FactorCatalogEntry:
    definition: FactorDefinition
    style_family: str

    def to_dict(self) -> dict:
        payload = self.definition.to_dict()
        payload["style_family"] = self.style_family
        return payload


FACTOR_CATALOG: tuple[FactorCatalogEntry, ...] = (
    FactorCatalogEntry(
        definition=FactorDefinition(
            factor_key="growth",
            label="Growth",
            description="Activos orientados a crecimiento esperado, reinversion y expansion de ingresos.",
            classification_notes="Tipico en tecnologia, e-commerce y companias con sesgo de expansion.",
        ),
        style_family="equity_style",
    ),
    FactorCatalogEntry(
        definition=FactorDefinition(
            factor_key="value",
            label="Value",
            description="Activos con sesgo a valuaciones relativamente bajas o descuento frente a fundamentales.",
            classification_notes="Usar solo cuando exista mapping explicito o proxy razonable; no forzar por defecto.",
        ),
        style_family="equity_style",
    ),
    FactorCatalogEntry(
        definition=FactorDefinition(
            factor_key="quality",
            label="Quality",
            description="Activos asociados a negocios robustos, balance solido o resiliencia operacional.",
            classification_notes="Aplicar de forma conservadora; priorizar mapping explicito sobre inferencia amplia.",
        ),
        style_family="equity_style",
    ),
    FactorCatalogEntry(
        definition=FactorDefinition(
            factor_key="dividend",
            label="Dividend",
            description="Activos orientados a distribucion de dividendos o renta recurrente.",
            classification_notes="Comun en telecom, consumo defensivo maduro y estrategias de renta.",
        ),
        style_family="income_style",
    ),
    FactorCatalogEntry(
        definition=FactorDefinition(
            factor_key="defensive",
            label="Defensive",
            description="Activos defensivos o de menor sensibilidad relativa al ciclo economico.",
            classification_notes="Compatible con utilities, salud, consumo defensivo y bloques estrategicos defensivos.",
        ),
        style_family="risk_style",
    ),
    FactorCatalogEntry(
        definition=FactorDefinition(
            factor_key="cyclical",
            label="Cyclical",
            description="Activos expuestos al ciclo economico, commodities o sectores mas sensibles a actividad.",
            classification_notes="Comun en energia, materiales, industriales y consumo ciclico.",
        ),
        style_family="risk_style",
    ),
)


class FactorCatalogService:
    """Catalogo cerrado de factores MVP para factor exposure proxy."""

    def list_factors(self) -> list[dict]:
        return [entry.to_dict() for entry in FACTOR_CATALOG]

    def get_factor(self, factor_key: str) -> dict | None:
        normalized = str(factor_key or "").strip().lower()
        for entry in FACTOR_CATALOG:
            if entry.definition.factor_key == normalized:
                return entry.to_dict()
        return None

    def require_factor(self, factor_key: str) -> dict:
        factor = self.get_factor(factor_key)
        if factor is None:
            raise ValueError(f"Unknown factor_key: {factor_key}")
        return factor
