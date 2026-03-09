from django.contrib import admin
from .models import ParametroActivo, ConfiguracionDashboard


@admin.register(ParametroActivo)
class ParametroActivoAdmin(admin.ModelAdmin):
    list_display = ['simbolo', 'sector', 'bloque_estrategico', 'pais_exposicion']
    list_filter = ['sector', 'bloque_estrategico', 'pais_exposicion']
    search_fields = ['simbolo', 'sector']


@admin.register(ConfiguracionDashboard)
class ConfiguracionDashboardAdmin(admin.ModelAdmin):
    list_display = ['clave', 'valor', 'descripcion']
    search_fields = ['clave', 'descripcion']
    list_editable = ['valor']