from django.db import models


class ParametroActivo(models.Model):
    simbolo = models.CharField(max_length=20, unique=True)
    sector = models.CharField(max_length=100)
    bloque_estrategico = models.CharField(max_length=100)
    pais_exposicion = models.CharField(max_length=50)
    tipo_patrimonial = models.CharField(max_length=50)
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ['simbolo']

    def __str__(self):
        return f"{self.simbolo} - {self.sector}"


class ConfiguracionDashboard(models.Model):
    """Configuraciones generales del dashboard."""
    clave = models.CharField(max_length=100, unique=True)
    valor = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True)

    class Meta:
        verbose_name = "Configuración Dashboard"
        verbose_name_plural = "Configuraciones Dashboard"

    def __str__(self):
        return f"{self.clave}: {self.valor}"