from django.db import models


class ResumenCuentaSnapshot(models.Model):
    fecha_extraccion = models.DateTimeField()
    numero_cuenta = models.CharField(max_length=50)
    tipo_cuenta = models.CharField(max_length=50)
    moneda = models.CharField(max_length=10)
    disponible = models.DecimalField(max_digits=15, decimal_places=2)
    comprometido = models.DecimalField(max_digits=15, decimal_places=2)
    saldo = models.DecimalField(max_digits=15, decimal_places=2)
    titulos_valorizados = models.DecimalField(max_digits=15, decimal_places=2)
    total = models.DecimalField(max_digits=15, decimal_places=2)
    margen_descubierto = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    estado = models.CharField(max_length=50)

    class Meta:
        ordering = ['-fecha_extraccion']
        indexes = [
            models.Index(fields=['fecha_extraccion']),
            models.Index(fields=['numero_cuenta']),
        ]

    def __str__(self):
        return f"{self.numero_cuenta} - {self.fecha_extraccion}"