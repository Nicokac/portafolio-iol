from django.db import models
from django.utils import timezone


class IOLToken(models.Model):
    """Modelo para almacenar tokens de acceso a la API de IOL."""

    access_token = models.TextField(help_text="JWT access token")
    refresh_token = models.TextField(blank=True, null=True, help_text="Refresh token")
    expires_at = models.DateTimeField(help_text="Fecha de expiración del access token")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"IOL Token expires {self.expires_at}"

    @property
    def is_expired(self):
        """Verifica si el token ha expirado."""
        return timezone.now() >= self.expires_at

    @classmethod
    def get_latest_valid_token(cls):
        """Obtiene el token más reciente que no haya expirado."""
        return cls.objects.filter(expires_at__gt=timezone.now()).first()

    @classmethod
    def save_token(cls, access_token: str, refresh_token: str = None, expires_in: int = 3600):
        """Guarda un nuevo token, eliminando tokens anteriores."""
        # Eliminar tokens anteriores
        cls.objects.all().delete()

        # Crear nuevo token
        expires_at = timezone.now() + timezone.timedelta(seconds=expires_in)
        return cls.objects.create(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at
        )


class PortfolioParameters(models.Model):
    """Modelo para almacenar parámetros de configuración del portafolio."""

    # Pesos objetivo por categoría
    liquidez_target = models.DecimalField(
        max_digits=5, decimal_places=2, default=20.00,
        help_text="Porcentaje objetivo para liquidez (%)"
    )
    usa_target = models.DecimalField(
        max_digits=5, decimal_places=2, default=40.00,
        help_text="Porcentaje objetivo para activos USA (%)"
    )
    argentina_target = models.DecimalField(
        max_digits=5, decimal_places=2, default=30.00,
        help_text="Porcentaje objetivo para activos Argentina (%)"
    )
    emerging_target = models.DecimalField(
        max_digits=5, decimal_places=2, default=10.00,
        help_text="Porcentaje objetivo para mercados emergentes (%)"
    )

    # Parámetros de riesgo
    max_single_position = models.DecimalField(
        max_digits=5, decimal_places=2, default=15.00,
        help_text="Máximo porcentaje por posición individual (%)"
    )
    risk_free_rate = models.DecimalField(
        max_digits=4, decimal_places=2, default=3.50,
        help_text="Tasa libre de riesgo (%)"
    )

    # Parámetros de rebalanceo
    rebalance_threshold = models.DecimalField(
        max_digits=4, decimal_places=2, default=5.00,
        help_text="Umbral para trigger de rebalanceo (%)"
    )

    # Configuración adicional
    is_active = models.BooleanField(default=True, help_text="Si estos parámetros están activos")
    name = models.CharField(max_length=100, default="Parámetros Principales",
                           help_text="Nombre descriptivo de la configuración")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Parámetro de Portafolio"
        verbose_name_plural = "Parámetros de Portafolio"

    def __str__(self):
        return f"{self.name} ({'Activo' if self.is_active else 'Inactivo'})"

    @property
    def total_target_allocation(self):
        """Calcula el total de la asignación objetivo."""
        return (self.liquidez_target + self.usa_target +
                self.argentina_target + self.emerging_target)

    def is_valid_allocation(self):
        """Verifica si la asignación suma 100%."""
        return abs(self.total_target_allocation - 100) < 0.01

    @classmethod
    def get_active_parameters(cls):
        """Obtiene los parámetros activos."""
        return cls.objects.filter(is_active=True).first()

    def get_target_weights_dict(self):
        """Retorna los pesos objetivo como diccionario."""
        return {
            'liquidez': float(self.liquidez_target),
            'usa': float(self.usa_target),
            'argentina': float(self.argentina_target),
            'emerging': float(self.emerging_target)
        }