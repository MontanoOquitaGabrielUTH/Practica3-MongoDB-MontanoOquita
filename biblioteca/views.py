from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from .models import Libro, Prestamo, Multa
from datetime import datetime, timedelta
from django.http import JsonResponse
from .mongo_utils import get_mongo_db
from bson import ObjectId
import json

# Obtener conexión a MongoDB
db = get_mongo_db()

# Función helper para registrar logs en MongoDB (opcional)
def log_to_mongodb(collection_name, log_data):
    """
    Intenta registrar un log en MongoDB.
    Si falla, continúa silenciosamente sin interrumpir la aplicación.
    """
    try:
        db[collection_name].insert_one(log_data)
    except Exception:
        pass  # Ignorar errores de MongoDB


# ========================================
# VISTA: Página de Inicio
# ========================================
def inicio(request):
    """
    Página principal del sistema con resumen de estadísticas.
    Combina datos de MySQL (libros) y MongoDB (vistas/préstamos).
    """
    # Estadísticas de MySQL
    total_libros_mysql = Libro.objects.filter(activo=True).count()
    libros_disponibles = Libro.objects.filter(activo=True, stock__gt=0).count()
    
    # Estadísticas de MongoDB
    total_libros_mongo = 0
    top_libros = []
    mongodb_conectado = False
    
    try:
        from pymongo import MongoClient
        client = MongoClient(settings.MONGODB_CONNECTION_STRING)
        db_stats = client['biblioteca_estadisticas']
        
        # Contar documentos en MongoDB
        total_libros_mongo = db_stats.estadisticas.count_documents({})
        
        # Top 5 libros más vistos
        top_libros = list(db_stats.estadisticas.find().sort('views', -1).limit(5))
        
        mongodb_conectado = True
        client.close()
    except:
        pass
    
    context = {
        'total_libros_mysql': total_libros_mysql,
        'libros_disponibles': libros_disponibles,
        'total_libros_mongo': total_libros_mongo,
        'top_libros': top_libros,
        'mongodb_conectado': mongodb_conectado
    }

    return render(request, 'biblioteca/inicio.html', context)


# ========================================
# VISTA: Listar Libros
# ========================================
def listar_libros(request):
    """
    Lista todos los libros desde MySQL con búsqueda opcional.
    """
    # Buscar parámetro de búsqueda
    query = request.GET.get('q', '')
    
    if query:
        # Búsqueda en MySQL
        libros = Libro.objects.filter(
            titulo__icontains=query
        ) | Libro.objects.filter(
            autor__icontains=query
        )
    else:
        # Obtener todos los libros
        libros = Libro.objects.all()
    
    context = {
        'libros': libros,
        'query': query,
        'total_libros': libros.count()
    }
    
    return render(request, 'biblioteca/listar_libros.html', context)


# ========================================
# VISTA: Detalle de Libro
# ========================================
def detalle_libro(request, libro_id):
    """
    Muestra detalle de un libro desde MySQL.
    Registra la vista en MongoDB.
    """
    # Obtener libro desde MySQL
    libro = get_object_or_404(Libro, id=libro_id)
    
    # Obtener préstamos activos de este libro desde MySQL
    prestamos_activos = Prestamo.objects.filter(
        libro=libro,
        estado='ACTIVO'
    ).select_related('usuario')
    
    # Obtener estadísticas de MongoDB
    views = 0
    prestamos = 0
    
    try:
        client = settings.MONGO_CLIENT
        db_stats = client['biblioteca_estadisticas']
        
        # Buscar estadísticas del libro
        stats = db_stats.estadisticas.find_one({'libro_id': libro_id})
        
        if stats:
            views = stats.get('views', 0)
            prestamos = stats.get('prestamos', 0)
        
        # Incrementar vistas en MongoDB
        db_stats.estadisticas.update_one(
            {'libro_id': libro_id},
            {
                '$inc': {'views': 1},
                '$set': {
                    'titulo': libro.titulo,
                    'autor': libro.autor,
                    'ultima_vista': datetime.now()
                }
            },
            upsert=True
        )
        
        views += 1  # Actualizar contador local
        
    except Exception as e:
        # Si falla MongoDB, continuar sin estadísticas
        pass
    
    # Registrar en logs
    log_to_mongodb('logs', {
        'accion': 'ver_detalle',
        'libro_id': libro_id,
        'libro_titulo': libro.titulo,
        'timestamp': datetime.now()
    })
    
    context = {
        'libro': libro,
        'prestamos_activos': prestamos_activos,
        'disponible': libro.disponible,
        'views': views,
        'prestamos': prestamos
    }
    
    return render(request, 'biblioteca/detalle_libro.html', context)

# ========================================
# VISTA: Crear Libro
# ========================================
def crear_libro(request):
    """
    Formulario para agregar un nuevo libro.
    Guarda en MySQL y registra en MongoDB.
    """
    if request.method == 'POST':
        # Obtener datos del formulario
        titulo = request.POST.get('titulo')
        autor = request.POST.get('autor')
        isbn = request.POST.get('isbn')
        fecha_publicacion = request.POST.get('fecha_publicacion')
        precio = request.POST.get('precio')
        stock = request.POST.get('stock', 0)
        descripcion = request.POST.get('descripcion', '')

        try:
            # Verificar si el ISBN ya existe
            if Libro.objects.filter(isbn=isbn).exists():
                messages.error(request, f'❌ Ya existe un libro con el ISBN "{isbn}". Por favor usa un ISBN diferente.')
                return render(request, 'biblioteca/crear_libro.html', {
                    'titulo': titulo,
                    'autor': autor,
                    'isbn': isbn,
                    'fecha_publicacion': fecha_publicacion,
                    'precio': precio,
                    'stock': stock,
                    'descripcion': descripcion
                })

            # Guardar en MySQL usando Django ORM
            libro = Libro.objects.create(
                titulo=titulo,
                autor=autor,
                isbn=isbn,
                fecha_publicacion=fecha_publicacion,
                precio=precio,
                stock=stock,
                descripcion=descripcion
            )

            # Registrar en MongoDB (opcional)
            try:
                client = settings.MONGO_CLIENT
                
                # Crear documento en catálogo
                db_catalogo = client['biblioteca_catalogo']
                db_catalogo.libros.insert_one({
                    'libro_id': libro.id,
                    'titulo': titulo,
                    'autor': autor,
                    'isbn': isbn,
                    'fecha_creacion': datetime.now()
                })
                
                # Crear estadísticas iniciales
                db_stats = client['biblioteca_estadisticas']
                db_stats.estadisticas.insert_one({
                    'libro_id': libro.id,
                    'titulo': titulo,
                    'autor': autor,
                    'views': 0,
                    'prestamos': 0,
                    'calificacion_promedio': 0.0,
                    'fecha_creacion': datetime.now()
                })
            except:
                pass
            
            # Registrar en logs
            log_to_mongodb('logs', {
                'accion': 'crear_libro',
                'libro_id': libro.id,
                'libro_titulo': titulo,
                'isbn': isbn,
                'timestamp': datetime.now()
            })

            messages.success(request, f'✅ Libro "{titulo}" creado exitosamente con ISBN {isbn}')
            return redirect('listar_libros')

        except Exception as e:
            # Capturar error específico de ISBN duplicado
            if '1062' in str(e) or 'Duplicate entry' in str(e):
                messages.error(request, f'❌ El ISBN "{isbn}" ya está registrado. Usa un ISBN único.')
            else:
                messages.error(request, f'Error al crear libro: {str(e)}')

    return render(request, 'biblioteca/crear_libro.html')


def editar_libro(request, libro_id):
    libro = get_object_or_404(Libro, id=libro_id)

    if request.method == 'POST':
        nuevo_isbn = request.POST.get('isbn')

        try:
            # 1. Validar ISBN Duplicado en MySQL
            if nuevo_isbn != libro.isbn:
                if Libro.objects.filter(isbn=nuevo_isbn).exclude(id=libro_id).exists():
                    messages.error(request, f'❌ Ya existe otro libro con el ISBN "{nuevo_isbn}".')
                    return render(request, 'biblioteca/editar_libro.html', {'libro': libro})

            # 2. Actualizar campos y Guardar en MySQL
            libro.titulo = request.POST.get('titulo')
            libro.autor = request.POST.get('autor')
            libro.isbn = nuevo_isbn
            libro.fecha_publicacion = request.POST.get('fecha_publicacion')
            libro.precio = request.POST.get('precio')
            libro.stock = request.POST.get('stock', 0)
            libro.descripcion = request.POST.get('descripcion', '')
            libro.save()

            # 3. SINCRONIZACIÓN CON MONGODB (Dentro del POST y del TRY principal)
            try:
                # Usamos el diccionario de bases de datos de tu settings.py
                db_stats = settings.MONGODB_DATABASES['estadisticas']
                db_cat = settings.MONGODB_DATABASES['catalogo']
                
                # Buscamos por el ID numérico (tal cual está en tu Compass)
                filtro = {'libro_id': int(libro_id)}
                datos_nuevos = {
                    '$set': {
                        'titulo': libro.titulo,
                        'autor': libro.autor,
                        'isbn': libro.isbn,
                        'ultima_actualizacion': datetime.now()
                    }
                }
                
                # Actualizamos en ambas colecciones
                res1 = db_stats.estadisticas.update_one(filtro, datos_nuevos)
                res2 = db_cat.libros.update_one(filtro, datos_nuevos)
                
                print(f"✅ Mongo Sync: Estadísticas({res1.modified_count}) Catálogo({res2.modified_count})")

            except Exception as mongo_err:
                print(f"⚠️ Error sincronizando con MongoDB Atlas: {mongo_err}")

            # 4. Registrar Log de actividad
            log_to_mongodb('logs', {
                'accion': 'editar_libro',
                'libro_id': libro_id,
                'libro_titulo': libro.titulo,
                'timestamp': datetime.now()
            })

            messages.success(request, f'✅ Libro "{libro.titulo}" actualizado correctamente en todo el sistema.')
            return redirect('detalle_libro', libro_id=libro_id)

        except Exception as e:
            messages.error(request, f'Error general al actualizar: {str(e)}')

    return render(request, 'biblioteca/editar_libro.html', {'libro': libro})


# ========================================
# VISTA: Eliminar Libro
# ========================================
def eliminar_libro(request, libro_id):
    libro = get_object_or_404(Libro, id=libro_id)

    if request.method == 'POST':
        titulo = libro.titulo
        try:
            client = settings.MONGO_CLIENT
            id_busqueda = int(libro_id)

            # 1. PASO A ELIMINADOS: Insertar en la colección de auditoría
            db_logs = client['biblioteca_logs']
            db_logs.libros_eliminados.insert_one({
                'libro_id': id_busqueda,
                'titulo': titulo,
                'autor': str(libro.autor),
                'isbn': libro.isbn,
                'fecha_eliminacion': datetime.now(),
                'motivo': request.POST.get('motivo', 'No especificado')
            })

            # 2. QUITAR DE LIBROS: Borrar de la colección activa en catálogo
            # Esto hace que ya no aparezca en las búsquedas de MongoDB
            client['biblioteca_catalogo'].libros.delete_one({'libro_id': id_busqueda})
            
            # 3. OPCIONAL: Quitar también de estadísticas si no quieres rastrearlo más
            client['biblioteca_estadisticas'].estadisticas.delete_one({'libro_id': id_busqueda})

            print(f"✅ Libro {id_busqueda} movido a 'eliminados' y quitado de 'catalogo'.")

            # 4. ELIMINAR DE MYSQL: El paso final
            libro.delete()

            messages.success(request, f'Libro "{titulo}" movido al archivo de eliminados.')
            return redirect('listar_libros')

        except Exception as e:
            print(f"❌ Error al mover datos: {e}")
            messages.error(request, f'Error en el proceso: {str(e)}')

    return render(request, 'biblioteca/confirmar_eliminacion.html', {'libro': libro})

# ========================================
# VISTA: Estadísticas
# ========================================
def estadisticas(request):
    """
    Dashboard con métricas y gráficas desde MySQL y MongoDB.
    """
    # Estadísticas de MySQL
    from django.db.models import Sum
    total_libros = Libro.objects.count()
    total_stock = Libro.objects.aggregate(Sum('stock'))['stock__sum'] or 0
    libros_activos = Libro.objects.filter(activo=True).count()
    libros_disponibles = Libro.objects.filter(activo=True, stock__gt=0).count()

    # Estadísticas de MongoDB
    total_views = 0
    top_vistos = []
    top_prestados = []

    try:
        from pymongo import MongoClient
        client = MongoClient(settings.MONGODB_CONNECTION_STRING)
        db_stats = client['biblioteca_estadisticas']

        # Total de vistas (suma de todos los views)
        pipeline = [
            {'$group': {'_id': None, 'total_views': {'$sum': '$views'}}}
        ]
        result = list(db_stats.estadisticas.aggregate(pipeline))
        total_views = result[0]['total_views'] if result else 0

        # Top 10 más vistos
        top_vistos = list(db_stats.estadisticas.find().sort('views', -1).limit(10))

        # Top 10 más prestados
        top_prestados = list(db_stats.estadisticas.find().sort('prestamos', -1).limit(10))

        client.close()
    except Exception as e:
        # Si falla MongoDB, continuar con valores vacíos
        pass

    # Actividad reciente (últimos 20 logs de MongoDB)
    try:
        logs_recientes = list(db.logs.find().sort('timestamp', -1).limit(20))
    except:
        logs_recientes = []

    # Registrar acceso al dashboard
    log_to_mongodb('logs', {
        'accion': 'ver_estadisticas',
        'timestamp': datetime.now()
    })

    context = {
        'total_libros': total_libros,
        'total_stock': total_stock,
        'libros_activos': libros_activos,
        'libros_disponibles': libros_disponibles,
        'total_views': total_views,
        'top_vistos': top_vistos,
        'top_prestados': top_prestados,
        'logs_recientes': logs_recientes
    }

    return render(request, 'biblioteca/estadisticas.html', context)


# ========================================
# VISTA: Dashboard
# ========================================
def dashboard(request):
    """
    Panel de control con métricas del sistema.
    Combina datos de MySQL y MongoDB.
    """
    # Estadísticas de MySQL
    total_prestamos_activos = Prestamo.objects.filter(estado='ACTIVO').count()
    total_prestamos_historico = Prestamo.objects.count()
    total_libros = Libro.objects.count()
    libros_disponibles = Libro.objects.filter(activo=True, stock__gt=0).count()
    
    # Estadísticas de MongoDB
    mongodb_stats = {
        'logs_count': 0,
        'libros_count': 0,
        'estadisticas_count': 0,
        'usuarios_count': 0,
        'total_documentos': 0,
        'mongodb_conectado': False
    }
    
    try:
        # Contar documentos en cada colección de MongoDB
        mongodb_stats['logs_count'] = db.logs.count_documents({})
        
        # Contar en otras bases de datos
        client = settings.MONGO_CLIENT
        mongodb_stats['libros_count'] = client['biblioteca_catalogo'].libros.count_documents({})
        mongodb_stats['estadisticas_count'] = client['biblioteca_estadisticas'].estadisticas.count_documents({})
        mongodb_stats['usuarios_count'] = client['biblioteca_usuarios'].usuarios.count_documents({})
        
        # Total de documentos en MongoDB
        mongodb_stats['total_documentos'] = (
            mongodb_stats['logs_count'] + 
            mongodb_stats['libros_count'] + 
            mongodb_stats['estadisticas_count'] + 
            mongodb_stats['usuarios_count']
        )
        mongodb_stats['mongodb_conectado'] = True
        
    except Exception as e:
        # Si MongoDB no está disponible, mantener valores en 0
        mongodb_stats['mongodb_conectado'] = False
    
    # Registrar acceso al dashboard
    log_to_mongodb('logs', {
        'accion': 'acceso_dashboard',
        'timestamp': datetime.now(),
        'ip': request.META.get('REMOTE_ADDR', 'unknown')
    })
    
    context = {
        'total_prestamos_activos': total_prestamos_activos,
        'total_prestamos_historico': total_prestamos_historico,
        'total_libros': total_libros,
        'libros_disponibles': libros_disponibles,
        'mongodb_stats': mongodb_stats,
    }
    
    return render(request, 'biblioteca/dashboard.html', context)


# ========================================
# VISTAS ADICIONALES: Préstamos
# ========================================

@login_required
def prestar_libro(request, libro_id):
    """
    Crea un préstamo en MySQL.
    """
    if request.method == 'POST':
        libro = get_object_or_404(Libro, id=libro_id)
        
        if libro.stock <= 0 or not libro.activo:
            messages.error(request, f"El libro '{libro.titulo}' no tiene stock disponible")
            return redirect('detalle_libro', libro_id=libro_id)
        
        prestamo_existente = Prestamo.objects.filter(
            libro=libro,
            usuario=request.user,
            estado='ACTIVO'
        ).exists()
        
        if prestamo_existente:
            messages.warning(request, "Ya tienes un préstamo activo de este libro")
            return redirect('detalle_libro', libro_id=libro_id)
        
        try:
            prestamo = Prestamo.objects.create(
                libro=libro,
                usuario=request.user,
                dias_prestamo=14
            )
            
            libro.stock -= 1
            libro.save()
            
            # Registrar en MongoDB
            try:
                client = settings.MONGO_CLIENT
                db_stats = client['biblioteca_estadisticas']
                
                db_stats.estadisticas.update_one(
                    {'libro_id': libro_id},
                    {'$inc': {'prestamos': 1}},
                    upsert=True
                )
            except:
                pass
            
            log_to_mongodb('logs', {
                "timestamp": datetime.now(),
                "usuario": request.user.username,
                "accion": "PRESTAMO_CREADO",
                "libro_id": libro.id,
                "prestamo_id": prestamo.id,
                "detalles": f"Préstamo del libro '{libro.titulo}'"
            })
            
            messages.success(
                request, 
                f"✅ Préstamo registrado exitosamente. Fecha de devolución: "
                f"{(timezone.now() + timedelta(days=14)).strftime('%d/%m/%Y')}"
            )
            
            return redirect('mis_prestamos')
            
        except Exception as e:
            messages.error(request, f"Error al crear préstamo: {str(e)}")
            return redirect('detalle_libro', libro_id=libro_id)
    
    return redirect('detalle_libro', libro_id=libro_id)


@login_required
def devolver_libro(request, prestamo_id):
    """
    Marca préstamo como devuelto en MySQL.
    """
    prestamo = get_object_or_404(Prestamo, id=prestamo_id, usuario=request.user)
    
    if prestamo.estado != 'ACTIVO':
        messages.warning(request, "Este préstamo ya fue devuelto")
        return redirect('mis_prestamos')
    
    try:
        prestamo.estado = 'DEVUELTO'
        prestamo.fecha_devolucion = timezone.now()
        prestamo.save()
        
        libro = prestamo.libro
        libro.stock += 1
        libro.save()
        
        log_to_mongodb('logs', {
            "timestamp": datetime.now(),
            "usuario": request.user.username,
            "accion": "DEVOLUCION",
            "libro_id": prestamo.libro.id,
            "prestamo_id": prestamo.id
        })
        
        messages.success(request, "✅ Libro devuelto exitosamente")
        
    except Exception as e:
        messages.error(request, f"Error al devolver libro: {str(e)}")
    
    return redirect('mis_prestamos')


@login_required
def mis_prestamos(request):
    """
    Lista préstamos del usuario desde MySQL.
    """
    prestamos = Prestamo.objects.filter(
        usuario=request.user
    ).select_related('libro').order_by('-fecha_prestamo')
    
    context = {
        'prestamos': prestamos,
        'total_prestamos': prestamos.count()
    }
    
    return render(request, 'biblioteca/mis_prestamos.html', context)