from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import CajaBanco, PagoPedido, Ingreso, PagoCompra, Egreso
from panel.models import Empresa
from preferencias.models import Moneda
from pedidos.models import Pedido
from compras.models import OrdenCompra
from django.db import transaction
from preferencias.permissions import require_treasury_permission

# --- FUNCIÓN AYUDANTE ---
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
@require_treasury_permission('egresos', 'ver')
def lista_egresos(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)
    
    egresos = Egreso.objects.filter(empresa=empresa_actual).select_related('moneda', 'caja_banco', 'pago_compra__orden_compra__proveedor').order_by('-fecha', '-id')
    
    contexto = {
        'egresos': egresos,
        'section': 'tesoreria_egresos'
    }
    return render(request, 'tesoreria/dashboard_egresos.html', contexto)

@login_required
@transaction.atomic
def api_registrar_pago_compra(request):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            compra_id = request.POST.get('compra_id')
            compra = get_object_or_404(OrdenCompra, id=compra_id, empresa=empresa_actual)
            
            caja_banco_id = request.POST.get('caja_banco_id')
            caja_banco = get_object_or_404(CajaBanco, id=caja_banco_id, empresa=empresa_actual)
            
            moneda_id = request.POST.get('moneda_id')
            moneda = get_object_or_404(Moneda, id=moneda_id, empresa=empresa_actual)
            
            monto = float(request.POST.get('monto', 0))
            tipo_cambio = float(request.POST.get('tipo_cambio', 1.0))
            monto_mxn = monto * tipo_cambio
            fecha_pago = request.POST.get('fecha_pago')
            forma_pago = request.POST.get('forma_pago')
            referencia = request.POST.get('referencia', '')
            
            pago = PagoCompra.objects.create(
                empresa=empresa_actual,
                orden_compra=compra,
                fecha_pago=fecha_pago,
                forma_pago=forma_pago,
                caja_banco=caja_banco,
                referencia=referencia,
                moneda=moneda,
                tipo_cambio=tipo_cambio,
                monto=monto,
                monto_mxn=monto_mxn
            )
            
            # --- REGISTRO EN EGRESOS ---
            Egreso.objects.create(
                empresa=empresa_actual,
                fecha=fecha_pago,
                concepto=f"Pago de Orden de Compra OC-{compra.id:04d} - {compra.proveedor.razon_social}",
                monto=monto,
                moneda=moneda,
                tipo_cambio=tipo_cambio,
                monto_mxn=monto_mxn,
                forma_pago=forma_pago,
                caja_banco=caja_banco,
                referencia=referencia,
                pago_compra=pago
            )
            
            return JsonResponse({'success': True, 'message': 'Pago registrado correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
@transaction.atomic
@require_treasury_permission('egresos', 'cancelar', json_response=True)
def api_cancelar_egreso(request, id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            egreso = get_object_or_404(Egreso, id=id, empresa=empresa_actual)
            
            if egreso.estado == 'cancelado':
                return JsonResponse({'success': False, 'error': 'Este egreso ya está cancelado.'})
            
            egreso.estado = 'cancelado'
            egreso.save()
            
            # 2. Si tiene un pago vinculado, marcarlo como cancelado para regresar el saldo
            if egreso.pago_compra:
                pago = egreso.pago_compra
                pago.estado = 'cancelado'
                pago.save()
            
            return JsonResponse({'success': True, 'message': 'Egreso cancelado correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required(login_url='/login/')
@require_treasury_permission('ingresos', 'ver')
def lista_ingresos(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)
    
    ingresos = Ingreso.objects.filter(empresa=empresa_actual).select_related('moneda', 'caja_banco', 'pago_pedido__pedido__cliente').order_by('-fecha', '-id')
    
    contexto = {
        'ingresos': ingresos,
        'section': 'tesoreria_ingresos'
    }
    return render(request, 'tesoreria/dashboard_ingresos.html', contexto)

@login_required
@transaction.atomic
@require_treasury_permission('ingresos', 'cancelar', json_response=True)
def api_cancelar_ingreso(request, id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            ingreso = get_object_or_404(Ingreso, id=id, empresa=empresa_actual)
            
            if ingreso.estado == 'cancelado':
                return JsonResponse({'success': False, 'error': 'Este ingreso ya está cancelado.'})
            
            # 1. Marcar ingreso como cancelado
            ingreso.estado = 'cancelado'
            ingreso.save()
            
            # 2. Si tiene un pago vinculado, marcarlo como cancelado para regresar el saldo
            if ingreso.pago_pedido:
                pago = ingreso.pago_pedido
                pago.estado = 'cancelado'
                pago.save()
            
            return JsonResponse({'success': True, 'message': 'Ingreso cancelado correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
@transaction.atomic
def api_registrar_pago_pedido(request):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            pedido_id = request.POST.get('pedido_id')
            pedido = get_object_or_404(Pedido, id=pedido_id, empresa=empresa_actual)
            
            caja_banco_id = request.POST.get('caja_banco_id')
            caja_banco = get_object_or_404(CajaBanco, id=caja_banco_id, empresa=empresa_actual)
            
            moneda_id = request.POST.get('moneda_id')
            moneda = get_object_or_404(Moneda, id=moneda_id, empresa=empresa_actual)
            
            monto = float(request.POST.get('monto', 0))
            tipo_cambio = float(request.POST.get('tipo_cambio', 1.0))
            monto_mxn = monto * tipo_cambio
            fecha_pago = request.POST.get('fecha_pago')
            forma_pago = request.POST.get('forma_pago')
            referencia = request.POST.get('referencia', '')
            
            pago = PagoPedido.objects.create(
                empresa=empresa_actual,
                pedido=pedido,
                fecha_pago=fecha_pago,
                forma_pago=forma_pago,
                caja_banco=caja_banco,
                referencia=referencia,
                moneda=moneda,
                tipo_cambio=tipo_cambio,
                monto=monto,
                monto_mxn=monto_mxn
            )
            
            # --- REGISTRO EN INGRESOS ---
            Ingreso.objects.create(
                empresa=empresa_actual,
                fecha=fecha_pago,
                concepto=f"Pago de Pedido PED-{pedido.id:04d} - {pedido.cliente.nombre_completo}",
                monto=monto,
                moneda=moneda,
                tipo_cambio=tipo_cambio,
                monto_mxn=monto_mxn,
                forma_pago=forma_pago,
                caja_banco=caja_banco,
                referencia=referencia,
                pago_pedido=pago
            )
            
            return JsonResponse({'success': True, 'message': 'Pago registrado correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required(login_url='/login/')
@require_treasury_permission('cajas_bancos', 'ver')
def lista_cajas_bancos(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)
    
    cajas = CajaBanco.objects.filter(empresa=empresa_actual, activo=True).order_by('nombre')
    monedas = Moneda.objects.filter(empresa=empresa_actual)
    
    contexto = {
        'cajas': cajas,
        'monedas': monedas,
        'section': 'tesoreria_catalogos'
    }
    return render(request, 'tesoreria/dashboard_cajas_bancos.html', contexto)

@login_required
@require_treasury_permission('cajas_bancos', 'crear', json_response=True)
def api_crear_caja_banco(request):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            tipo = request.POST.get('tipo')
            nombre = request.POST.get('nombre')
            moneda_id = request.POST.get('moneda')
            
            moneda = get_object_or_404(Moneda, id=moneda_id, empresa=empresa_actual)
            
            data = {
                'empresa': empresa_actual,
                'tipo': tipo,
                'nombre': nombre,
                'moneda': moneda,
            }
            
            if tipo == 'banco':
                data['banco_nombre'] = request.POST.get('banco_nombre')
                data['cuenta'] = request.POST.get('cuenta')
                data['clabe'] = request.POST.get('clabe')
                
            CajaBanco.objects.create(**data)
            return JsonResponse({'success': True, 'message': 'Registro creado correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
def api_detalle_caja_banco(request, id):
    empresa_actual = get_empresa_actual(request)
    caja = get_object_or_404(CajaBanco, id=id, empresa=empresa_actual)
    return JsonResponse({
        'id': caja.id,
        'tipo': caja.tipo,
        'nombre': caja.nombre,
        'moneda_id': caja.moneda.id,
        'banco_nombre': caja.banco_nombre or '',
        'cuenta': caja.cuenta or '',
        'clabe': caja.clabe or ''
    })

@login_required
@require_treasury_permission('cajas_bancos', 'editar', json_response=True)
def api_actualizar_caja_banco(request, id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            caja = get_object_or_404(CajaBanco, id=id, empresa=empresa_actual)
            
            tipo = request.POST.get('tipo')
            caja.tipo = tipo
            caja.nombre = request.POST.get('nombre')
            moneda_id = request.POST.get('moneda')
            caja.moneda = get_object_or_404(Moneda, id=moneda_id, empresa=empresa_actual)
            
            if tipo == 'banco':
                caja.banco_nombre = request.POST.get('banco_nombre')
                caja.cuenta = request.POST.get('cuenta')
                caja.clabe = request.POST.get('clabe')
            else:
                caja.banco_nombre = ""
                caja.cuenta = ""
                caja.clabe = ""
                
            caja.save()
            return JsonResponse({'success': True, 'message': 'Registro actualizado correctamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})
