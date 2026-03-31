from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Producto, Transaccion, DetalleReceta
from django.contrib.auth.decorators import login_required
from panel.models import Empresa
from django.http import JsonResponse
from categorias.models import Categoria
from almacenes.models import Almacen
from proveedores.models import Proveedor
from django.core.paginator import Paginator
from recepciones.models import Recepcion, DetalleRecepcion, DetalleRecepcionExtra
from django.db.models import Sum, Q, Subquery, OuterRef, DecimalField, Avg, ExpressionWrapper, F, FloatField
from collections import defaultdict
from compras.models import OrdenCompra
from django.db import transaction
from .forms import ProductoForm
from ventas.models import DetalleOrdenVenta

# --- 1. FUNCIÓN AYUDANTE ESTÁNDAR ---
def get_empresa_actual(request):
    username = request.user.username
    if '@' in username:
        subdominio = username.split('@')[1]
        try:
            return Empresa.objects.get(subdominio=subdominio)
        except Empresa.DoesNotExist:
            return None
    return None

@login_required(login_url='/login/')
def punto_de_venta(request):
    empresa_actual = get_empresa_actual(request)
    
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)

    productos = Producto.objects.filter(empresa=empresa_actual)

    if request.method == 'POST':
        producto_id = request.POST.get('producto_id')
        cantidad = int(request.POST.get('cantidad', 1))

        try:
            # Verificamos que el producto exista Y pertenezca a la empresa
            producto = get_object_or_404(Producto, id=producto_id, empresa=empresa_actual)
            
            # Usamos el modelo Transaccion de CORE
            Transaccion.objects.create(
                producto=producto,
                tipo='venta',
                cantidad=cantidad,
                empresa=empresa_actual  # <--- CORREGIDO
            )
            
            messages.success(request, f'Vendido: {cantidad} x {producto.nombre}')
            return redirect('punto_de_venta')

        except Exception as e:
            messages.error(request, str(e))

    return render(request, 'core/vender.html', {'productos': productos})

@login_required(login_url='/login/')
def crear_producto_ajax(request):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            
            if not empresa_actual:
                return JsonResponse({'success': False, 'error': 'Empresa no detectada'})

            form = ProductoForm(request.POST)

            if form.is_valid():
                producto = form.save(commit=False)
                producto.empresa = empresa_actual
                
                # GUARDAR TEST DE CALIDAD
                test_id = request.POST.get('test_calidad')
                if test_id:
                    from produccion.models import Test
                    producto.test_calidad = Test.objects.filter(id=test_id, empresa=empresa_actual).first()
                
                producto.save()
                return JsonResponse({'success': True, 'message': 'Artículo creado correctamente.'})
            else:
                return JsonResponse({'success': False, 'error': form.errors})

        except Exception as e:
            print(f"ERROR CREANDO PRODUCTO: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required(login_url='/login/')
def obtener_producto_json(request, producto_id):
    try:
        empresa_actual = get_empresa_actual(request)
        
        # VERIFICACIÓN DE SEGURIDAD
        producto = get_object_or_404(Producto, id=producto_id, empresa=empresa_actual)

        data = {
            'id': producto.id,
            'nombre': producto.nombre,
            'descripcion': producto.descripcion,
            'tipo': producto.tipo,
            'tipo_abastecimiento': producto.tipo_abastecimiento,
            'estado': producto.estado,
            'categoria': producto.categoria or '',
            'subcategoria': producto.subcategoria or '',
            'marca': producto.marca or '',
            'modelo': producto.modelo or '',
            'linea': producto.linea or '',
            'unidad_medida': producto.unidad_medida,
            'iva': str(producto.iva),
            'ieps': str(producto.ieps),
            'precio_costo': str(producto.precio_costo),
            'precio_venta': str(producto.precio_venta),
            'precios_lista': producto.precios_lista,
            'costos_lista': producto.costos_lista,
            'stock_minimo': producto.stock_minimo,
            'stock_maximo': producto.stock_maximo,
            'maneja_lote': producto.maneja_lote,
            'maneja_serie': producto.maneja_serie,
            'test_calidad_id': producto.test_calidad.id if producto.test_calidad else "", # <--- VÍNCULO AL TEST
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=404)

@login_required(login_url='/login/')
def actualizar_producto_ajax(request, producto_id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            
            # VERIFICACIÓN DE SEGURIDAD
            producto = get_object_or_404(Producto, id=producto_id, empresa=empresa_actual)

            # Actualizar campos
            producto.nombre = request.POST.get('nombre')
            producto.descripcion = request.POST.get('descripcion')
            producto.tipo = request.POST.get('tipo')
            producto.tipo_abastecimiento = request.POST.get('tipo_abastecimiento')
            producto.estado = request.POST.get('estado')
            producto.categoria = request.POST.get('categoria')
            producto.subcategoria = request.POST.get('subcategoria')
            producto.marca = request.POST.get('marca')
            producto.modelo = request.POST.get('modelo')
            producto.linea = request.POST.get('linea')
            producto.unidad_medida = request.POST.get('unidad_medida')
            producto.iva = request.POST.get('iva', 0)
            producto.ieps = request.POST.get('ieps', 0)
            
            producto.precio_costo = request.POST.get('precio_costo')
            producto.precio_venta = request.POST.get('precio_venta')
            producto.stock_minimo = request.POST.get('stock_minimo')
            producto.stock_maximo = request.POST.get('stock_maximo')
            
            producto.maneja_lote = request.POST.get('maneja_lote') == 'on'
            producto.maneja_serie = request.POST.get('maneja_serie') == 'on'
            
            # GUARDAR TEST DE CALIDAD EN ACTUALIZACIÓN
            test_id = request.POST.get('test_calidad')
            if test_id:
                from produccion.models import Test
                producto.test_calidad = Test.objects.filter(id=test_id, empresa=empresa_actual).first()
            else:
                producto.test_calidad = None

            producto.save()
            
            return JsonResponse({'success': True, 'message': 'Artículo actualizado correctamente.'})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required(login_url='/login/')
def dashboard_inventario(request):
    empresa_actual = get_empresa_actual(request)
    
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)
    
    # ==========================================
    # 1. SUBCONSULTA: PRECIO PROMEDIO DE VENTA (CORREGIDO)
    # ==========================================
    # Agrupamos por producto primero, calculamos el promedio, y luego seleccionamos ese valor.
    # Esto evita el error de usar aggregate() directo dentro de Subquery.
    avg_venta_subquery = DetalleOrdenVenta.objects.filter(
        producto=OuterRef('pk')
    ).values('producto').annotate(
        promedio=Avg('precio_unitario')
    ).values('promedio')[:1]

    # ==========================================
    # 2. SUBCONSULTA: PRECIO MÁXIMO DE VENTA
    # ==========================================
    max_precio_venta = DetalleOrdenVenta.objects.filter(
        producto=OuterRef('pk')
    ).order_by('-precio_unitario').values('precio_unitario')[:1]

    # ==========================================
    # 3. SUBCONSULTA: COSTO MÁXIMO DE COMPRA (CONVERTIDO A PESOS)
    # ==========================================
    max_costo_compra = DetalleRecepcion.objects.filter(
        producto=OuterRef('pk')
    ).annotate(
        costo_pesos=ExpressionWrapper(
            F('costo_unitario') * F('recepcion__tipo_cambio'),
            output_field=DecimalField(max_digits=10, decimal_places=2)
        )
    ).order_by('-costo_pesos').values('costo_pesos')[:1]

    # ==========================================
    # 4. SUBCONSULTA: COSTO PROMEDIO HISTÓRICO DE COMPRAS (CONVERTIDO A PESOS)
    # Calcula el promedio ponderado por tipo de cambio de todas
    # las recepciones del producto.
    # ==========================================
    costo_promedio_subquery = DetalleRecepcion.objects.filter(
        producto=OuterRef('pk')
    ).annotate(
        costo_pesos=ExpressionWrapper(
            F('costo_unitario') * F('recepcion__tipo_cambio'),
            output_field=FloatField()
        )
    ).values('producto').annotate(
        promedio_historico=Avg('costo_pesos')
    ).values('promedio_historico')[:1]

    # ==========================================
    # 5. SUBCONSULTA: COSTO PROMEDIO DE INVENTARIO ACTUAL
    # Solo considera productos que tienen existencias actualmente.
    # Fórmula: suma(cantidad * costo_promedio) / suma(cantidad)
    # ==========================================
    from almacenes.models import Inventario

    costo_inventario_subquery = Inventario.objects.filter(
        producto=OuterRef('pk'),
        cantidad__gt=0
    ).values('producto').annotate(
        promedio_ponderado=Sum(
            ExpressionWrapper(
                F('cantidad') * F('costo_promedio'),
                output_field=FloatField()
            )
        ),
        total_unidades=Sum('cantidad')
    ).annotate(
        costo_final=ExpressionWrapper(
            F('promedio_ponderado') / F('total_unidades'),
            output_field=FloatField()
        )
    ).values('costo_final')[:1]

    # ==========================================
    # 6. EJECUCIÓN PRINCIPAL
    # ==========================================
    productos = Producto.objects.filter(empresa=empresa_actual).annotate(
        precio_promedio_venta=Subquery(avg_venta_subquery),
        precio_max_venta=Subquery(max_precio_venta),
        costo_max_compra=Subquery(max_costo_compra),
        costo_promedio_anotado=Subquery(costo_promedio_subquery),
        costo_inventario_anotado=Subquery(costo_inventario_subquery)
    ).order_by('nombre')
    
    todas_categorias = Categoria.objects.filter(empresa=empresa_actual).order_by('nombre')

    # NUEVO: Obtener Tests para el modal de Nuevo Artículo
    from produccion.models import Test
    tests_calidad = Test.objects.filter(empresa=empresa_actual).order_by('nombre')

    contexto = {
        'productos': productos,
        'categorias': todas_categorias,
        'tests_calidad': tests_calidad, # <--- PASAMOS LOS TESTS
        'section': 'inventario'
    }
    return render(request, 'dashboard_inventario.html', contexto)

@login_required
def api_detalle_producto_inventario(request, producto_id):
    try:
        empresa_actual = get_empresa_actual(request)
        
        # --- SEGURIDAD: Verificar que el producto pertenezca a la empresa antes de mostrar su historial ---
        producto = get_object_or_404(Producto, id=producto_id, empresa=empresa_actual)
        
        # --- TAB 1: POR PROVEEDOR / ORDEN ---
        # No hace falta filtrar por empresa aquí porque estamos filtrando por 'producto'
        # y ya verificamos que el producto es de la empresa correcta.
        detalles = DetalleRecepcion.objects.filter(
            producto_id=producto_id
        ).select_related('recepcion', 'detalle_compra__orden_compra').order_by('-recepcion__fecha')

        historial_data = []
        for d in detalles:
            folio_oc = "Directa"
            proveedor = "Directo / Sin OC"
            folio_rec = f"REC-{d.recepcion.id:04d}"
            
            if hasattr(d, 'detalle_compra') and d.detalle_compra and hasattr(d.detalle_compra, 'orden_compra') and d.detalle_compra.orden_compra:
                oc = d.detalle_compra.orden_compra
                folio_oc = f"OC-{oc.id:04d}"
                proveedor = oc.proveedor
            elif hasattr(d, 'recepcion') and d.recepcion and hasattr(d.recepcion, 'orden_compra') and d.recepcion.orden_compra:
                oc = d.recepcion.orden_compra
                folio_oc = f"OC-{oc.id:04d}"
                proveedor = oc.proveedor

            oc_id_num = None
            rec_id_num = d.recepcion.id 

            if d.detalle_compra and d.detalle_compra.orden_compra:
                oc_id_num = d.detalle_compra.orden_compra.id

            historial_data.append({
                'folio_oc': folio_oc,
                'oc_id': oc_id_num,
                'folio_rec': folio_rec,
                'rec_id': rec_id_num,
                'proveedor': str(proveedor),
                'fecha': d.recepcion.fecha.strftime('%d/%m/%Y'),
                'cantidad': d.cantidad_recibida,
                'costo': float(d.costo_unitario),
                'total': float(d.cantidad_recibida * d.costo_unitario)
            })

        # --- TAB 2 y 3: SERIES Y LOTES ---
        detalle_ids = DetalleRecepcion.objects.filter(
            producto_id=producto_id
        ).values_list('id', flat=True)

        extras = DetalleRecepcionExtra.objects.filter(
            detalle_recepcion_id__in=detalle_ids
        ).select_related('detalle_recepcion__recepcion', 'detalle_recepcion__detalle_compra__orden_compra')

        series_data = []
        lotes_data = []

        for extra in extras:
            dr = extra.detalle_recepcion
            rec = dr.recepcion
            
            fecha_ingreso = rec.fecha.strftime('%d/%m/%Y')
            folio_rec = f"REC-{rec.id:04d}"
            
            folio_oc = "Directa"
            proveedor = "Directo"
            
            if hasattr(dr, 'detalle_compra') and dr.detalle_compra and hasattr(dr.detalle_compra, 'orden_compra') and dr.detalle_compra.orden_compra:
                folio_oc = f"OC-{dr.detalle_compra.orden_compra.id:04d}"
                proveedor = dr.detalle_compra.orden_compra.proveedor
            
            if extra.tipo == 'serie':
                series_data.append({
                    'serie': extra.serie,
                    'folio_oc': folio_oc,
                    'folio_rec': folio_rec,
                    'proveedor': str(proveedor),
                    'fecha': fecha_ingreso
                })
            elif extra.tipo == 'lote':
                lotes_data.append({
                    'lote': extra.lote,
                    'cantidad': extra.cantidad_lote,
                    'folio_oc': folio_oc,
                    'folio_rec': folio_rec,
                    'proveedor': str(proveedor),
                    'fecha': fecha_ingreso
                })

        # --- TAB 4: IMPORTACIÓN (BLOQUE SEGURO) ---
        importaciones_data = []
        
        try:
            detalles_con_pedimento = DetalleRecepcion.objects.filter(
                producto_id=producto_id,
                recepcion__pedimento__isnull=False
            ).exclude(recepcion__pedimento='').select_related('recepcion')

            pedimentos_vistos = set()

            for dr in detalles_con_pedimento:
                rec = dr.recepcion
                if not rec or not rec.pedimento:
                    continue
                if rec.pedimento in pedimentos_vistos:
                    continue
                
                pedimentos_vistos.add(rec.pedimento)

                grupo_recepciones = Recepcion.objects.filter(
                    detalles__producto_id=producto_id,
                    pedimento=rec.pedimento
                )

                ocs_ids = grupo_recepciones.values_list('orden_compra__id', flat=True).distinct()
                ocs_formateadas = [f"OC-{oc_id:04d}" for oc_id in ocs_ids if oc_id]

                rec_ids = grupo_recepciones.values_list('id', flat=True).distinct()
                recs_formateadas = [f"REC-{rec_id:04d}" for rec_id in rec_ids if rec_id]
                
                importaciones_data.append({
                    'pedimento': rec.pedimento,
                    'aduana': rec.aduana or '',
                    'fecha': rec.fecha_pedimento.strftime('%d/%m/%Y') if rec.fecha_pedimento else '',
                    'ocs': ocs_formateadas,
                    'recs': recs_formateadas,
                })
        
        except Exception as e:
            print(f"ERROR EN CÁLCULO DE IMPORTACIÓN: {e}")
            importaciones_data = []

        return JsonResponse({
            'historial': historial_data,
            'series': series_data,
            'lotes': lotes_data,
            'importaciones': importaciones_data
        })

    except Exception as e:
        print(f"Error GENERAL en api_detalle_producto_inventario: {e}")
        return JsonResponse({'error': str(e)}, status=500)
    
@login_required
def api_detalle_documento(request):
    """
    API genérica para obtener detalles de una OC o una Recepción
    """
    doc_tipo = request.GET.get('tipo') # 'oc' o 'rec'
    doc_id = request.GET.get('id')
    empresa_actual = get_empresa_actual(request)

    try:
        data = {}
        if doc_tipo == 'oc':
            # --- SEGURIDAD: Solo ver OCs de mi empresa ---
            obj = get_object_or_404(OrdenCompra, id=doc_id, empresa=empresa_actual)
            data = {
                'titulo': 'Detalle Orden de Compra',
                'folio': f"OC-{obj.id:04d}",
                'proveedor': str(obj.proveedor),
                'fecha': obj.fecha.strftime('%d/%m/%Y') if obj.fecha else '-',
                'estado': obj.estado.upper(),
                'total': float(obj.total),
                'detalles': [
                    {
                        'producto': d.producto.nombre,
                        'cant': d.cantidad,
                        'precio': float(d.precio_costo),
                        'subtotal': float(d.cantidad * d.precio_costo)
                    } for d in obj.detalles.all()
                ]
            }
        
        elif doc_tipo == 'rec':
            # --- SEGURIDAD: Solo ver Recepciones de mi empresa ---
            obj = get_object_or_404(Recepcion, id=doc_id, empresa=empresa_actual)

            fp_str = obj.fecha_pedimento.strftime('%d/%m/%Y') if obj.fecha_pedimento else '-'

            data = {
                'titulo': 'Detalle Recepción',
                'folio': f"REC-{obj.id:04d}",
                'oc_folio': f"OC-{obj.orden_compra.id:04d}" if obj.orden_compra else '-',
                'oc_origen': f"OC-{obj.orden_compra.id:04d}" if obj.orden_compra else '-',
                'proveedor': str(obj.orden_compra.proveedor) if obj.orden_compra else "Directo / Sin OC",
                'almacen': str(obj.almacen),
                'fecha': obj.fecha.strftime('%d/%m/%Y'),
                'estado': obj.estado.upper(),
                'factura': obj.factura or '-',
                'total': float(obj.total),
                'pedimento': obj.pedimento or '-',
                'aduana': obj.aduana or '-',
                'fecha_pedimento': fp_str,
                'detalles': [
                    {
                        'producto': d.producto.nombre,
                        'cant': d.cantidad_recibida,
                        'precio': float(d.costo_unitario),
                        'subtotal': float(d.cantidad_recibida * d.costo_unitario)
                    } for d in obj.detalles.all()
                ]
            }
        
        return JsonResponse(data)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=404)
    
@login_required
@transaction.atomic
def guardar_receta(request):
    """ Guarda la lista de componentes para un producto de tipo 'produccion' """
    if request.method == 'POST':
        try:
            import json
            empresa_actual = get_empresa_actual(request)
            
            body_unicode = request.body.decode('utf-8')
            data = json.loads(body_unicode)

            producto_id = data.get('producto_id')
            componentes_json = data.get('componentes') 

            # --- SEGURIDAD: Verificar producto ---
            producto = get_object_or_404(Producto, id=producto_id, empresa=empresa_actual)

            if producto.tipo_abastecimiento != 'produccion':
                return JsonResponse({'success': False, 'error': 'Solo se puede configurar receta para productos de tipo PRODUCCIÓN.'})

            # 1. Borrar la receta anterior
            DetalleReceta.objects.filter(producto_padre=producto).delete()

            # 2. Crear la nueva receta
            if componentes_json:
                componentes = json.loads(componentes_json)
                for item in componentes:
                    comp_id = item.get('id')
                    cant = item.get('cant', 1)
                    if comp_id and cant > 0:
                        if int(comp_id) == int(producto_id):
                            return JsonResponse({'success': False, 'error': 'Un producto no puede ser componente de sí mismo.'})
                        
                        # Nota: Aquí asumimos que los componentes deben existir, 
                        # idealmente verificaríamos también que el componente pertenezca a la empresa.
                        componente = get_object_or_404(Producto, id=comp_id, empresa=empresa_actual)
                        
                        DetalleReceta.objects.create(
                            producto_padre=producto,
                            componente=componente,
                            cantidad=cant
                        )

            return JsonResponse({'success': True, 'message': 'Receta guardada correctamente.'})

        except Exception as e:
            print(f"ERROR EN guardar_receta: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
@transaction.atomic
def ejecutar_produccion(request):
    """ Resta componentes y suma producto terminado """
    if request.method == 'POST':
        try:
            from almacenes.models import Inventario
            from decimal import Decimal
            empresa_actual = get_empresa_actual(request)

            producto_id = request.POST.get('producto_id')
            almacen_id = request.POST.get('almacen_id')
            cantidad_producir = int(request.POST.get('cantidad'))

            # --- SEGURIDAD: Verificar Producto y Almacén ---
            producto = get_object_or_404(Producto, id=producto_id, empresa=empresa_actual)
            almacen = get_object_or_404(Almacen, id=almacen_id, empresa=empresa_actual)

            # 1. Obtener Receta
            receta = DetalleReceta.objects.filter(producto_padre=producto)
            if not receta.exists():
                return JsonResponse({'success': False, 'error': 'Este producto no tiene una receta configurada.'})

# 2. Obtener y BLOQUEAR todos los inventarios de componentes en una sola consulta
            # select_for_update() bloquea las filas hasta que termine la transacción,
            # evitando que otro usuario pueda leer o modificar el mismo stock al mismo tiempo.
            ids_componentes = [item.componente_id for item in receta]
            inventarios_bloqueados = Inventario.objects.select_for_update().filter(
                producto_id__in=ids_componentes,
                almacen=almacen
            )

            # Convertimos a dict para acceso rápido: { producto_id: inventario }
            inv_dict = {inv.producto_id: inv for inv in inventarios_bloqueados}

            # 3. Validar Stock de Componentes (usando los registros ya bloqueados)
            errores_stock = []
            for item in receta:
                inv_comp = inv_dict.get(item.componente_id)
                requerido = item.cantidad * cantidad_producir
                if not inv_comp:
                    errores_stock.append(f"No existe stock de {item.componente.nombre} en este almacén.")
                elif inv_comp.cantidad < requerido:
                    errores_stock.append(f"Falta {item.componente.nombre} (Tienes: {inv_comp.cantidad}, Necesitas: {requerido})")

            if errores_stock:
                return JsonResponse({'success': False, 'error': 'Stock insuficiente: ' + ', '.join(errores_stock)})

            # 4. Ejecutar Movimientos
            # A. Restar Componentes (usando los mismos objetos ya bloqueados, sin volver a consultar BD)
            for item in receta:
                inv_comp = inv_dict[item.componente_id]
                inv_comp.cantidad -= (item.cantidad * cantidad_producir)
                inv_comp.save()

            # B. Sumar Producto Terminado
            inv_final, created = Inventario.objects.get_or_create(
                producto=producto,
                almacen=almacen,
                defaults={'cantidad': 0, 'costo_promedio': Decimal('0.00')}
            )

            inv_final.cantidad += cantidad_producir
            inv_final.save()

            return JsonResponse({'success': True, 'message': f'Producción exitosa. Se agregaron {cantidad_producir} unidades de {producto.nombre}.'})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
def obtener_receta(request, producto_id):
    """ Para cargar la receta al editar """
    try:
        empresa_actual = get_empresa_actual(request)
        # Verificamos que el producto sea de la empresa
        producto = get_object_or_404(Producto, id=producto_id, empresa=empresa_actual)
        
        receta = DetalleReceta.objects.filter(producto_padre_id=producto_id)
        data = [
            {
                'id': r.componente.id,
                'nombre': r.componente.nombre,
                'cant': r.cantidad,
                'costo': float(r.componente.precio_costo)
            } for r in receta
        ]
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    
@login_required
def actualizar_precio_producto(request, producto_id):
    """Actualiza el costo y las listas de precios dinámicas"""
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            producto = get_object_or_404(Producto, id=producto_id, empresa=empresa_actual)

            # 1. Actualizar Costo Base
            nuevo_costo = request.POST.get('precio_costo')
            if nuevo_costo:
                producto.precio_costo = nuevo_costo

            # 2. Recibir y Guardar Lista de Precios (JSON desde el Frontend)
            precios_extra_json = request.POST.get('precios_extra')
            if precios_extra_json:
                import json
                try:
                    producto.precios_lista = json.loads(precios_extra_json)
                except json.JSONDecodeError:
                    pass # Si hay error, no romper, mantener lo anterior

            # 3. Recibir y Guardar Lista de Costos (JSON)
            costos_extra_json = request.POST.get('costos_extra')
            if costos_extra_json:
                try:
                    producto.costos_lista = json.loads(costos_extra_json)
                except json.JSONDecodeError:
                    pass

            producto.save()
            return JsonResponse({'success': True, 'message': 'Datos actualizados correctamente.'})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'})