from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# ========================================
# MODELO: Libro
# ========================================

class Libro(models.Model):
    """
    Modelo principal para almacenar libros en MySQL.
    Este modelo define la estructura relacional de los datos.
    """
    # Campos principales
    titulo = models.CharField(
        max_length=200, 
        verbose_name="Título del Libro",
        help_text="Título completo del libro (máximo 200 caracteres)"
    )
    
    autor = models.CharField(
        max_length=100, 
        verbose_name="Autor",
        help_text="Nombre del autor o autores"
    )
    
    isbn = models.CharField(
        max_length=17, 
        unique=True, 
        verbose_name="ISBN",
        help_text="Código ISBN único (formato: 978-3-16-148410-0)"
    )
    
    fecha_publicacion = models.DateField(
        verbose_name="Fecha de Publicación",
        help_text="Fecha original de publicación del libro"
    )
    
    precio = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        verbose_name="Precio",
        help_text="Precio del libro (formato: 000000.00)"
    )
    
    stock = models.PositiveIntegerField(
        default=0,
        verbose_name="Stock Disponible",
        help_text="Cantidad de ejemplares en inventario"
    )
    
    descripcion = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Descripción",
        help_text="Descripción opcional del contenido del libro"
    )
    
    # Campos de auditoría (automáticos)
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación"
    )
    
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Última Actualización"
    )
    
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo",
        help_text="Si está marcado, el libro está disponible en el sistema"
    )

    class Meta:
        verbose_name = "Libro"
        verbose_name_plural = "Libros"
        ordering = ['-fecha_creacion']  # Ordenar por fecha de creación descendente
        indexes = [
            models.Index(fields=['isbn']),  # Índice para búsquedas por ISBN
            models.Index(fields=['autor']),  # Índice para búsquedas por autor
            models.Index(fields=['titulo']),  # Índice para búsquedas por título
        ]

    def __str__(self):
        """Representación en string del objeto libro"""
        return f"{self.titulo} - {self.autor}"
    
    def get_absolute_url(self):
        """URL para ver los detalles del libro"""
        from django.urls import reverse
        return reverse('detalle_libro', args=[str(self.id)])
    
    @property
    def disponible(self):
        """Verifica si el libro está disponible (stock > 0 y activo)"""
        return self.activo and self.stock > 0
    
    @property 
    def precio_formateado(self):
        """Retorna el precio formateado con símbolo de moneda"""
        return f"${self.precio:,.2f}"
    
    def reducir_stock(self, cantidad=1):
        """Reduce el stock del libro (útil para préstamos)"""
        if self.stock >= cantidad:
            self.stock -= cantidad
            self.save()
            return True
        return False
    
    def aumentar_stock(self, cantidad=1):
        """Aumenta el stock del libro (útil para devoluciones)"""
        self.stock += cantidad
        self.save()
    
    def save(self, *args, **kwargs):
        """Sobrescribe el método save para validaciones adicionales"""
        # Convertir título a title case
        self.titulo = self.titulo.title()
        
        # Validar ISBN básico (solo números y guiones)
        import re
        if not re.match(r'^[\d-]+$', self.isbn):
            raise ValueError("El ISBN solo puede contener números y guiones")
        
        super().save(*args, **kwargs)


# ========================================
# MODELO: Préstamo
# ========================================

class Prestamo(models.Model):
    """
    Modelo para préstamos (se guarda en MySQL)
    """
    
    # Relación con el libro
    libro = models.ForeignKey(
        'Libro',
        on_delete=models.CASCADE,
        verbose_name="Libro"
    )
    
    # Relación con usuario de Django
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Usuario"
    )
    
    # Fechas del préstamo
    fecha_prestamo = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Préstamo"
    )
    
    fecha_devolucion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de Devolución"
    )
    
    # Estado del préstamo
    ESTADOS = [
        ('ACTIVO', 'Activo'),
        ('DEVUELTO', 'Devuelto'),
        ('VENCIDO', 'Vencido'),
    ]
    
    estado = models.CharField(
        max_length=10,
        choices=ESTADOS,
        default='ACTIVO',
        verbose_name="Estado"
    )
    
    # Días de préstamo (se calculará desde MongoDB)
    dias_prestamo = models.IntegerField(
        default=14,
        verbose_name="Días de Préstamo"
    )
    
    class Meta:
        db_table = 'biblioteca_prestamo'
        verbose_name = 'Préstamo'
        verbose_name_plural = 'Préstamos'
        ordering = ['-fecha_prestamo']
    
    def __str__(self):
        return f"Préstamo #{self.id} - {self.libro.titulo}"


# ========================================
# MODELO: Multa
# ========================================

class Multa(models.Model):
    """Modelo para multas por retraso en devolución"""
    
    prestamo = models.ForeignKey(
        Prestamo,
        on_delete=models.CASCADE,
        verbose_name="Préstamo"
    )
    
    monto = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        verbose_name="Monto"
    )
    
    pagada = models.BooleanField(
        default=False,
        verbose_name="Pagada"
    )
    
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación"
    )
    
    class Meta:
        db_table = 'biblioteca_multa'
        verbose_name = 'Multa'
        verbose_name_plural = 'Multas'
    
    def __str__(self):
        return f"Multa ${self.monto} - Préstamo #{self.prestamo.id}"