from __future__ import annotations


class AnalyticsExplanationService:
    """Genera interpretaciones deterministicas a partir de resultados analiticos ya calculados."""

    @staticmethod
    def build_risk_contribution_explanation(result: dict) -> str:
        top_contributors = result.get("top_contributors") or []
        by_country = result.get("by_country") or []
        model_variant = str(result.get("model_variant") or "mvp_proxy")
        confidence = str(result.get("metadata", {}).get("confidence") or "low")

        top_symbols = [str(item.get("symbol")) for item in top_contributors[:2] if item.get("symbol")]
        if not top_symbols:
            base = "No hay datos suficientes para interpretar la contribución al riesgo del portafolio."
        elif len(top_symbols) == 1:
            base = f"El riesgo del portafolio está dominado por {top_symbols[0]}."
        else:
            base = f"El riesgo del portafolio está dominado por {top_symbols[0]} y {top_symbols[1]}."

        argentina_group = next(
            (group for group in by_country if str(group.get("key")).strip().lower() == "argentina"),
            None,
        )
        if argentina_group:
            weight_pct = float(argentina_group.get("weight_pct") or 0.0)
            contribution_pct = float(argentina_group.get("contribution_pct") or 0.0)
            if contribution_pct + 3 < weight_pct:
                geography = (
                    " Aunque Argentina representa una parte importante del patrimonio, "
                    "explica una fracción menor del riesgo bajo el modelo actual."
                )
            elif contribution_pct > weight_pct + 3:
                geography = (
                    " El bloque argentino explica más riesgo que el que su peso patrimonial sugeriría."
                )
            else:
                geography = " La contribución geográfica al riesgo luce bastante alineada con el peso patrimonial."
        else:
            geography = ""

        model_text = (
            " El modelo activo es covariance_aware, por lo que la lectura incorpora covarianza entre activos."
            if model_variant == "covariance_aware"
            else " El modelo activo es mvp_proxy, por lo que la lectura usa peso y volatilidad proxy sin matriz de covarianza."
        )
        confidence_text = f" Confianza del resultado: {confidence}."
        return f"{base}{geography}{model_text}{confidence_text}"

    @staticmethod
    def build_scenario_analysis_explanation(result: dict) -> str:
        worst_scenario = result.get("worst_scenario") or {}
        label = worst_scenario.get("label") or "Sin escenario dominante"
        total_impact_pct = worst_scenario.get("total_impact_pct")
        by_sector = worst_scenario.get("by_sector") or []
        top_negative_contributors = worst_scenario.get("top_negative_contributors") or []

        if total_impact_pct is None:
            return "No hay datos suficientes para interpretar el scenario analysis actual."

        dominant_sector = None
        if by_sector:
            dominant_sector = min(by_sector, key=lambda item: float(item.get("impact_pct") or 0.0))

        if dominant_sector and dominant_sector.get("key"):
            sector_text = f", con impacto concentrado en el bloque {dominant_sector['key']}"
        elif top_negative_contributors:
            sector_text = (
                f", con presión concentrada en {top_negative_contributors[0].get('symbol', 'los activos más vulnerables')}"
            )
        else:
            sector_text = ""

        return (
            f"El escenario más adverso corresponde a {label}, con impacto estimado de "
            f"{float(total_impact_pct):.2f}%{sector_text}."
        )

    @staticmethod
    def build_factor_exposure_explanation(result: dict) -> str:
        dominant_factor = result.get("dominant_factor")
        factors = result.get("factors") or []
        unknown_assets = result.get("unknown_assets") or []

        if not factors and not dominant_factor:
            return "No hay datos suficientes para interpretar la exposición factorial del portafolio."

        dominant_item = next(
            (item for item in factors if item.get("factor") == dominant_factor),
            None,
        )
        dominant_pct = float(dominant_item.get("exposure_pct") or 0.0) if dominant_item else 0.0

        if dominant_factor:
            base = (
                f"La exposición del portafolio está dominada por el factor {dominant_factor}, "
                f"con {dominant_pct:.2f}% del universo clasificado."
            )
        else:
            base = "La exposición factorial no muestra un factor dominante claro."

        if unknown_assets:
            unknown_text = f" Hay {len(unknown_assets)} activos sin clasificación factorial confiable."
        else:
            unknown_text = " No hay activos relevantes fuera del universo factorial clasificado."

        return f"{base}{unknown_text}"

    @staticmethod
    def build_stress_fragility_explanation(result: dict) -> str:
        fragility_score = result.get("fragility_score")
        total_loss_pct = result.get("total_loss_pct")
        vulnerable_sectors = result.get("vulnerable_sectors") or []

        if fragility_score is None or total_loss_pct is None:
            return "No hay datos suficientes para interpretar la fragilidad bajo stress del portafolio."

        if vulnerable_sectors and vulnerable_sectors[0].get("key"):
            sector_text = f" El daño se concentra primero en {vulnerable_sectors[0]['key']}."
        else:
            sector_text = ""

        return (
            f"La cartera muestra una fragilidad de {float(fragility_score):.0f} puntos bajo stress, "
            f"con pérdida estimada de {float(total_loss_pct):.2f}%."
            f"{sector_text}"
        )

    @staticmethod
    def build_expected_return_explanation(result: dict) -> str:
        expected_return_pct = result.get("expected_return_pct")
        real_expected_return_pct = result.get("real_expected_return_pct")
        buckets = result.get("by_bucket") or []

        if expected_return_pct is None:
            return "No hay datos suficientes para interpretar el retorno esperado estructural."

        dominant_bucket = max(
            buckets,
            key=lambda item: float(item.get("weight_pct") or 0.0),
            default=None,
        )

        if dominant_bucket and dominant_bucket.get("label"):
            bucket_text = f" El bucket dominante es {dominant_bucket['label']}."
        else:
            bucket_text = ""

        if real_expected_return_pct is not None:
            real_text = f" El retorno real esperado se ubica en {float(real_expected_return_pct):.2f}%."
        else:
            real_text = " No hay referencia real completa porque falta inflación actual."

        return (
            f"El retorno esperado estructural del portafolio se ubica en {float(expected_return_pct):.2f}%."
            f"{real_text}{bucket_text}"
        )
