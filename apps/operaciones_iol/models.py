from django.db import models


class OperacionIOL(models.Model):
    numero = models.CharField(max_length=50, unique=True)
    fecha_orden = models.DateTimeField()
    fecha_alta = models.DateTimeField(null=True, blank=True)
    validez = models.DateTimeField(null=True, blank=True)
    fecha_operada = models.DateTimeField(null=True, blank=True)
    tipo = models.CharField(max_length=50)
    estado = models.CharField(max_length=50)
    estado_actual = models.CharField(max_length=50, blank=True)
    mercado = models.CharField(max_length=50)
    simbolo = models.CharField(max_length=20)
    moneda = models.CharField(max_length=50, blank=True)
    cantidad = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    monto = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    modalidad = models.CharField(max_length=50)
    precio = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    cantidad_operada = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    precio_operado = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    monto_operado = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    monto_operacion = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    aranceles_ars = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    aranceles_usd = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    plazo = models.CharField(max_length=50, null=True, blank=True)
    fondos_para_operacion = models.JSONField(null=True, blank=True)
    estados_detalle = models.JSONField(default=list, blank=True)
    aranceles_detalle = models.JSONField(default=list, blank=True)
    operaciones_detalle = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['-fecha_orden']
        indexes = [
            models.Index(fields=['fecha_orden']),
            models.Index(fields=['simbolo']),
            models.Index(fields=['estado']),
        ]

    def __str__(self):
        return f"{self.numero} - {self.simbolo} - {self.fecha_orden}"
