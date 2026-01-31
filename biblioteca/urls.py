from django.urls import path
from . import views

urlpatterns = [
    # Dashboard e Inicio
    path('', views.dashboard, name='dashboard'),
    path('inicio/', views.inicio, name='inicio'),
    
    # CRUD de libros
    path('libros/', views.listar_libros, name='listar_libros'),
    path('libro/crear/', views.crear_libro, name='crear_libro'),
    path('libro/<int:libro_id>/', views.detalle_libro, name='detalle_libro'),
    path('libro/<int:libro_id>/editar/', views.editar_libro, name='editar_libro'),
    path('libro/<int:libro_id>/eliminar/', views.eliminar_libro, name='eliminar_libro'),
    
    # Préstamos
    path('prestamo/crear/<int:libro_id>/', views.prestar_libro, name='prestar_libro'),
    path('prestamo/devolver/<int:prestamo_id>/', views.devolver_libro, name='devolver_libro'),
    path('prestamos/mis-prestamos/', views.mis_prestamos, name='mis_prestamos'),
    
    # Estadísticas
    path('estadisticas/', views.estadisticas, name='estadisticas'),
]