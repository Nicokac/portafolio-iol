class ParametrosMacroLocal:
    """Series macro locales priorizadas para analitica del portafolio."""

    SERIES = {
        "usdars_oficial": {
            "title": "USDARS mayorista BCRA",
            "source": "bcra",
            "external_id": "5",
            "frequency": "daily",
        },
        "usdars_mep": {
            "title": "USDARS MEP",
            "source": "fx_json",
            "external_id": "usdars_mep",
            "frequency": "daily",
            "optional": True,
        },
        "usdars_ccl": {
            "title": "USDARS CCL",
            "source": "fx_json",
            "external_id": "usdars_ccl",
            "frequency": "daily",
            "optional": True,
        },
        "riesgo_pais_arg": {
            "title": "Riesgo pais Argentina",
            "source": "fx_json",
            "external_id": "riesgo_pais_arg",
            "frequency": "daily",
            "optional": True,
        },
        "uva": {
            "title": "Indice UVA",
            "source": "fx_json",
            "external_id": "uva",
            "frequency": "daily",
            "optional": True,
        },
        "badlar_privada": {
            "title": "BADLAR bancos privados",
            "source": "bcra",
            "external_id": "7",
            "frequency": "daily",
        },
        "ipc_nacional": {
            "title": "IPC nacional mensual",
            "source": "datos_gob_ar",
            "external_id": "145.3_INGNACNAL_DICI_M_15",
            "frequency": "monthly",
        },
    }
