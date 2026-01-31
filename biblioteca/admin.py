from django.contrib import admin
from .models import Libro

# Registrar modelo Libro con configuración personalizada
@admin.register(Libro)
class LibroAdmin(admin.ModelAdmin):
    """Configuración del admin para el modelo Libro"""
    
    # Campos a mostrar en la lista
    list_display = [
        'titulo', 
        'autor', 
        'isbn', 
        'precio', 
        'stock', 
        'disponible',
        'activo'
    ]
    
    # Filtros laterales
    list_filter = [
        'activo',
        'fecha_publicacion', 
        'fecha_creacion'
    ]
    
    # Campos de búsqueda
    search_fields = [
        'titulo', 
        'autor', 
        'isbn'
    ]
    
    # Campos editables en la lista
    list_editable = [
        'precio', 
        'stock', 
        'activo'
    ]
    
    # Ordenamiento
    ordering = ['-fecha_creacion']
    
    # Campos de solo lectura
    readonly_fields = [
        'fecha_creacion', 
        'fecha_actualizacion'
    ]
    
    # Jerarquía de fechas
    date_hierarchy = 'fecha_creacion'
    
    # Paginación
    list_per_page = 25

# Personalización del sitio admin
admin.site.site_header = "Sistema de Biblioteca UTH"
admin.site.site_title = "Biblioteca UTH Admin"
admin.site.index_title = "Panel de Administración"