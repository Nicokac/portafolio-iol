from django.urls import resolve, reverse


def test_resumen_iol_route_is_not_shadowed():
    match = resolve("/resumen/")
    assert match.app_names == ["resumen_iol"]
    assert match.url_name == "resumen_list"


def test_dashboard_resumen_route_uses_panel_prefix():
    assert reverse("dashboard:resumen") == "/panel/resumen/"
    match = resolve("/panel/resumen/")
    assert match.app_names == ["dashboard"]
    assert match.url_name == "resumen"
