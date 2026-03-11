from django.db.models import Max

from apps.parametros.models import ParametroActivo
from apps.portafolio_iol.models import ActivoPortafolioSnapshot


class MetadataAuditService:
    """Audita calidad de metadata para activos del snapshot más reciente."""

    VALID_PATRIMONIAL_TYPES = {
        "Equity",
        "Bond",
        "FCI",
        "Cash",
        "ETF",
        "Hard Assets",
        "Growth",
        "Defensivo",
        "Renta Fija",
        "Liquidez",
    }

    INVALID_VALUES = {"", "N/A", None}

    def run_audit(self):
        latest_date = ActivoPortafolioSnapshot.objects.aggregate(
            latest=Max("fecha_extraccion")
        )["latest"]

        if not latest_date:
            return {
                "total_assets": 0,
                "classified_assets": 0,
                "unclassified_assets_count": 0,
                "inconsistent_assets_count": 0,
                "unclassified_assets": [],
                "inconsistent_assets": [],
            }

        activos = list(ActivoPortafolioSnapshot.objects.filter(fecha_extraccion=latest_date))
        symbols = [a.simbolo for a in activos]
        params = {p.simbolo: p for p in ParametroActivo.objects.filter(simbolo__in=symbols)}

        unclassified_assets = []
        inconsistent_assets = []

        for activo in activos:
            param = params.get(activo.simbolo)
            if not param:
                unclassified_assets.append(
                    {
                        "symbol": activo.simbolo,
                        "reason": "missing_parametro_activo",
                    }
                )
                continue

            issues = []
            if param.sector in self.INVALID_VALUES:
                issues.append("empty_sector")
            if param.pais_exposicion in self.INVALID_VALUES:
                issues.append("empty_country")
            if param.tipo_patrimonial in self.INVALID_VALUES:
                issues.append("empty_patrimonial_type")
            elif param.tipo_patrimonial not in self.VALID_PATRIMONIAL_TYPES:
                issues.append("invalid_patrimonial_type")

            if issues:
                inconsistent_assets.append(
                    {
                        "symbol": activo.simbolo,
                        "issues": issues,
                        "sector": param.sector,
                        "country": param.pais_exposicion,
                        "patrimonial_type": param.tipo_patrimonial,
                    }
                )

        total_assets = len(activos)
        unclassified_count = len(unclassified_assets)
        inconsistent_count = len(inconsistent_assets)
        classified_assets = total_assets - unclassified_count

        return {
            "total_assets": total_assets,
            "classified_assets": classified_assets,
            "unclassified_assets_count": unclassified_count,
            "inconsistent_assets_count": inconsistent_count,
            "unclassified_assets": unclassified_assets,
            "inconsistent_assets": inconsistent_assets,
        }
