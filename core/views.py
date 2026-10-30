from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from .models import Producto, Transaccion, DetalleReceta, CodigoBarrasAdicional
from django.contrib.auth.decorators import login_required
from panel.models import Empresa
import json
import re
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
import datetime
from datetime import datetime, date
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Q, Subquery, OuterRef, DecimalField, Avg, ExpressionWrapper, F, FloatField, IntegerField, Case, When, Value, CharField
from django.db.models.functions import Coalesce
from collections import defaultdict
from categorias.models import Categoria, Subcategoria
from almacenes.models import Almacen, Inventario
from proveedores.models import Proveedor
from preferencias.models import Moneda, Sucursal
from django.core.paginator import Paginator
from recepciones.models import Recepcion, DetalleRecepcion, DetalleRecepcionExtra
from compras.models import OrdenCompra
from ventas.models import DetalleOrdenVenta

from django.views.decorators.http import require_POST
from preferencias.permissions import require_inventory_permission

@login_required(login_url='/login/')
@require_inventory_permission('inventario', 'crear')
def descargar_plantilla_articulos(request):
    empresa_actual = get_empresa_actual(request)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Layout-articulos"

    # Estilos basados en los exportadores del módulo de contratistas (Layout-detalle-contrato)
    fill_main = PatternFill(start_color="00b8b9", end_color="00b8b9", fill_type="solid")
    fill_head = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    border = Border(
        left=Side(style='thin', color="B2B2B2"),
        right=Side(style='thin', color="B2B2B2"),
        top=Side(style='thin', color="B2B2B2"),
        bottom=Side(style='thin', color="B2B2B2")
    )
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # 5 Grupos principales (Fila 1)
    groups = [
        {'title': 'Identificación', 'start_col': 1, 'end_col': 6},
        {'title': 'Clasificación', 'start_col': 7, 'end_col': 14},
        {'title': 'Inventario y precios', 'start_col': 15, 'end_col': 27},
        {'title': 'Códigos de barras', 'start_col': 28, 'end_col': 28},
        {'title': 'Existencias', 'start_col': 29, 'end_col': 33},
    ]

    # Encabezados de columnas (Fila 2)
    headers = [
        # Identificación (1-6)
        'Clave', 'Nombre*', 'Tipo', 'Descripción', 'Estado', 'Tipo de abastecimiento',
        # Clasificación (7-14)
        'Categoría', 'Subcategoría', 'Marca', 'Modelo', 'Línea', 'Unidad de medida', 'IVA (%)', 'IEPS (%)',
        # Inventario y precios (15-27)
        'Costo base*', 'Venta base*', 'Stock mínimo', 'Stock máximo', 'Lote', 'Serie', 'Caducidad', 'FIFO', 'LIFO', 'FEFO', 'IVA incluido', 'POS', 'Modificadores',
        # Códigos de barras (28)
        'Código de barras (separar con ",")',
        # Existencias (29-33)
        'Existencias', 'Lote', 'Fecha de caducidad (YYYY-MM-DD)', 'Almacén', 'Sucursal'
    ]

    # Fila de ejemplo (Fila 3)
    sample_row = [
        # Identificación
        'ART-001', 'Artículo de Muestra', 'producto', 'Descripción de ejemplo del producto', 'activo', 'compra',
        # Clasificación
        'General', 'Subgeneral', 'Genérica', 'STD-100', 'Línea A', 'H87', 16, 0,
        # Inventario y precios
        100.00, 150.00, 5, 100, 'si', 'no', 'si', 'si', 'no', 'no', 'si', 'si', 'no',
        # Códigos de barras
        '7501000123456, 7501000123457',
        # Existencias
        10, 'LOTE-2026-A', '2027-12-31', 'Almacén Principal', 'Matriz'
    ]

    # 1. Aplicar Fila 1 (Grupos con estilo corporativo 00b8b9 y texto blanco)
    font_group = Font(name='Calibri', size=11, bold=True, color='FFFFFF')

    for g in groups:
        if g['start_col'] != g['end_col']:
            ws.merge_cells(start_row=1, start_column=g['start_col'], end_row=1, end_column=g['end_col'])
        cell_start = ws.cell(row=1, column=g['start_col'])
        cell_start.value = g['title']
        for c in range(g['start_col'], g['end_col'] + 1):
            cell = ws.cell(row=1, column=c)
            cell.fill = fill_main
            cell.font = font_group
            cell.alignment = center_align
            # Separador blanco nítido al borde derecho de cada grupo para delimitación limpia
            if c == g['end_col']:
                cell.border = Border(
                    left=Side(style='thin', color="B2B2B2"),
                    right=Side(style='medium', color="FFFFFF"),
                    top=Side(style='thin', color="B2B2B2"),
                    bottom=Side(style='thin', color="B2B2B2")
                )
            else:
                cell.border = border

    # 2. Aplicar Fila 2 (Cabeceras de Columnas estilo fill_head F2F2F2, negrita, B2B2B2)
    font_head = Font(name='Calibri', size=10, bold=True, color='000000')

    for col_idx, header_text in enumerate(headers, 1):
        cell = ws.cell(row=2, column=col_idx, value=header_text)
        cell.font = font_head
        cell.fill = fill_head
        cell.alignment = center_align
        cell.border = border

    # 3. Aplicar Fila 3 (Ejemplo con formatos numéricos y alineaciones estándar de layout)
    font_data = Font(name='Calibri', size=10, color='000000')

    for col_idx, val in enumerate(sample_row, 1):
        cell = ws.cell(row=3, column=col_idx, value=val)
        cell.font = font_data
        cell.border = border

        # Formatos y alineaciones por columna
        if col_idx in [15, 16]:  # Costo y Venta
            cell.number_format = '"$"#,##0.00'
            cell.alignment = Alignment(horizontal='right', vertical='center')
        elif col_idx in [13, 14]:  # IVA y IEPS
            cell.number_format = '0.00'
            cell.alignment = Alignment(horizontal='right', vertical='center')
        elif col_idx in [17, 18, 29]:  # Stocks y Existencias
            cell.number_format = '#,##0'
            cell.alignment = Alignment(horizontal='right', vertical='center')
        elif col_idx in [1, 28, 30]:  # Clave, Códigos de barras, Lote
            cell.number_format = '@'
            cell.alignment = Alignment(horizontal='center', vertical='center')
        elif col_idx == 31:  # Fecha de caducidad
            cell.number_format = 'yyyy-mm-dd'
            cell.alignment = Alignment(horizontal='center', vertical='center')
        elif str(val).lower() in ['si', 'no', 'activo', 'compra', 'producto', 'stock', 'produccion', 'h87', 'e48']:
            cell.alignment = Alignment(horizontal='center', vertical='center')
        else:
            cell.alignment = Alignment(horizontal='left', vertical='center')

    # Ajuste de anchos de columna (mínimo 18 como en Layout-detalle-contrato)
    for col_idx in range(1, len(headers) + 1):
        col_letter = get_column_letter(col_idx)
        header_len = len(str(headers[col_idx - 1]))
        sample_len = len(str(sample_row[col_idx - 1]))
        max_len = max(header_len, sample_len)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 18)

    # 4. Obtener catálogos dinámicos del sistema para esta empresa
    cat_filter = {'empresa': empresa_actual} if empresa_actual else {}
    categorias_qs = Categoria.objects.filter(**cat_filter).values_list('nombre', flat=True).order_by('nombre')
    categorias_list = [c.strip() for c in categorias_qs if c and c.strip()] or ['General']

    subcategorias_qs = Subcategoria.objects.filter(**cat_filter).values_list('nombre', flat=True).order_by('nombre')
    subcategorias_list = [s.strip() for s in subcategorias_qs if s and s.strip()] or ['General']

    prod_filter = {'empresa': empresa_actual} if empresa_actual else {}
    marcas_qs = Producto.objects.filter(**prod_filter).exclude(marca__isnull=True).exclude(marca='').values_list('marca', flat=True).distinct().order_by('marca')
    marcas_list = [m.strip() for m in marcas_qs if m and m.strip()] or ['Genérica']

    modelos_qs = Producto.objects.filter(**prod_filter).exclude(modelo__isnull=True).exclude(modelo='').values_list('modelo', flat=True).distinct().order_by('modelo')
    modelos_list = [m.strip() for m in modelos_qs if m and m.strip()] or ['Estándar']

    lineas_qs = Producto.objects.filter(**prod_filter).exclude(linea__isnull=True).exclude(linea='').values_list('linea', flat=True).distinct().order_by('linea')
    lineas_list = [l.strip() for l in lineas_qs if l and l.strip()] or ['Principal']

    udm_list = [opt[0] for opt in Producto.UNIDAD_OPCIONES]

    alm_filter = {'empresa': empresa_actual} if empresa_actual else {}
    almacenes_qs = Almacen.objects.filter(**alm_filter).values_list('nombre', flat=True).order_by('nombre')
    almacenes_list = [a.strip() for a in almacenes_qs if a and a.strip()] or ['Almacén Principal']

    suc_filter = {'empresa': empresa_actual} if empresa_actual else {}
    sucursales_qs = Sucursal.objects.filter(**suc_filter).values_list('nombre', flat=True).order_by('nombre')
    sucursales_list = [s.strip() for s in sucursales_qs if s and s.strip()] or ['Matriz']

    # 5. Hoja de Catálogos (referencia para listas desplegables)
    ws_cat = wb.create_sheet(title="Catalogos")
    cat_columns = [
        ('Categorías', categorias_list, 1),
        ('Subcategorías', subcategorias_list, 2),
        ('Marcas', marcas_list, 3),
        ('Modelos', modelos_list, 4),
        ('Líneas', lineas_list, 5),
        ('Unidades de Medida', udm_list, 6),
        ('Almacenes', almacenes_list, 7),
        ('Sucursales', sucursales_list, 8),
    ]

    for title, data_list, col_num in cat_columns:
        cell_h = ws_cat.cell(row=1, column=col_num, value=title)
        cell_h.font = font_head
        cell_h.fill = fill_head
        cell_h.border = border
        cell_h.alignment = center_align
        for r_idx, val in enumerate(data_list, start=2):
            cell_v = ws_cat.cell(row=r_idx, column=col_num, value=val)
            cell_v.border = border
        ws_cat.column_dimensions[get_column_letter(col_num)].width = max(len(title) + 5, 20)

    # 6. Definición y Asignación de Listas Desplegables (DataValidation)
    # A) Predefinidos fijos del sistema
    # Tipo (Col C: C3:C1000)
    dv_tipo = DataValidation(type="list", formula1='"producto,servicio"', allow_blank=True)
    dv_tipo.error = 'Seleccione "producto" o "servicio"'
    dv_tipo.errorTitle = 'Tipo inválido'
    ws.add_data_validation(dv_tipo)
    dv_tipo.add('C3:C1000')

    # Estado (Col E: E3:E1000)
    dv_estado = DataValidation(type="list", formula1='"activo,inactivo,descontinuado,revision"', allow_blank=True)
    dv_estado.error = 'Seleccione activo, inactivo, descontinuado o revision'
    dv_estado.errorTitle = 'Estado inválido'
    ws.add_data_validation(dv_estado)
    dv_estado.add('E3:E1000')

    # Tipo de abastecimiento (Col F: F3:F1000)
    dv_abast = DataValidation(type="list", formula1='"stock,produccion,compra"', allow_blank=True)
    dv_abast.error = 'Seleccione stock, produccion o compra'
    dv_abast.errorTitle = 'Abastecimiento inválido'
    ws.add_data_validation(dv_abast)
    dv_abast.add('F3:F1000')

    # Indicadores Booleanos Sí / No (Cols S a AA: S3:AA1000)
    # Lote, Serie, Caducidad, FIFO, LIFO, FEFO, IVA incluido, POS, Modificadores
    dv_sino = DataValidation(type="list", formula1='"si,no"', allow_blank=True)
    dv_sino.error = 'Seleccione "si" o "no"'
    dv_sino.errorTitle = 'Opción inválida'
    ws.add_data_validation(dv_sino)
    dv_sino.add('S3:AA1000')

    # B) Catálogos dinámicos basados en la base de datos (con showErrorMessage=False para permitir altas manuales si se requiere)
    # Categoría (Col G: G3:G1000)
    dv_cat = DataValidation(type="list", formula1=f"Catalogos!$A$2:$A${len(categorias_list)+1}", allow_blank=True)
    dv_cat.showErrorMessage = False
    ws.add_data_validation(dv_cat)
    dv_cat.add('G3:G1000')

    # Subcategoría (Col H: H3:H1000)
    dv_sub = DataValidation(type="list", formula1=f"Catalogos!$B$2:$B${len(subcategorias_list)+1}", allow_blank=True)
    dv_sub.showErrorMessage = False
    ws.add_data_validation(dv_sub)
    dv_sub.add('H3:H1000')

    # Marca (Col I: I3:I1000)
    dv_marca = DataValidation(type="list", formula1=f"Catalogos!$C$2:$C${len(marcas_list)+1}", allow_blank=True)
    dv_marca.showErrorMessage = False
    ws.add_data_validation(dv_marca)
    dv_marca.add('I3:I1000')

    # Modelo (Col J: J3:J1000)
    dv_modelo = DataValidation(type="list", formula1=f"Catalogos!$D$2:$D${len(modelos_list)+1}", allow_blank=True)
    dv_modelo.showErrorMessage = False
    ws.add_data_validation(dv_modelo)
    dv_modelo.add('J3:J1000')

    # Línea (Col K: K3:K1000)
    dv_linea = DataValidation(type="list", formula1=f"Catalogos!$E$2:$E${len(lineas_list)+1}", allow_blank=True)
    dv_linea.showErrorMessage = False
    ws.add_data_validation(dv_linea)
    dv_linea.add('K3:K1000')

    # Unidad de medida (Col L: L3:L1000)
    dv_udm = DataValidation(type="list", formula1=f"Catalogos!$F$2:$F${len(udm_list)+1}", allow_blank=True)
    ws.add_data_validation(dv_udm)
    dv_udm.add('L3:L1000')

    # Almacén (Col AF: AF3:AF1000)
    dv_alm = DataValidation(type="list", formula1=f"Catalogos!$G$2:$G${len(almacenes_list)+1}", allow_blank=True)
    dv_alm.showErrorMessage = False
    ws.add_data_validation(dv_alm)
    dv_alm.add('AF3:AF1000')

    # Sucursal (Col AG: AG3:AG1000)
    dv_suc = DataValidation(type="list", formula1=f"Catalogos!$H$2:$H${len(sucursales_list)+1}", allow_blank=True)
    dv_suc.showErrorMessage = False
    ws.add_data_validation(dv_suc)
    dv_suc.add('AG3:AG1000')

    # Asegurar que la hoja principal sea la que aparezca activa al abrir el archivo
    wb.active = ws

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="Layout_Plantilla_Articulos.xlsx"'
    wb.save(response)
    return response

@login_required(login_url='/login/')
@require_inventory_permission('inventario', 'crear', json_response=True)
def importar_articulos_ajax(request):
    if request.method == 'POST' and request.FILES.get('archivo_articulos'):
        empresa_actual = get_empresa_actual(request)
        excel_file = request.FILES['archivo_articulos']
        
        try:
            wb = openpyxl.load_workbook(excel_file, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            
            if len(rows) < 2:
                return JsonResponse({'success': False, 'error': 'El archivo está vacío.'})
            
            # Detectar si la fila 1 contiene nombres de grupos ("identificacion"...)
            first_row_txt = " ".join([str(c or '').lower() for c in rows[0][:8]])
            if 'identific' in first_row_txt:
                data_rows = rows[2:]
                start_excel_idx = 3
            else:
                data_rows = rows[1:]
                start_excel_idx = 2

            def to_bool_val(val, default=False):
                if val is None:
                    return default
                s = str(val).strip().lower()
                if s in ['si', 'sí', 's', 'true', '1', 'yes', 'y']:
                    return True
                if s in ['no', 'n', 'false', '0']:
                    return False
                return default

            def to_float_val(val, default=0.0):
                if val is None:
                    return default
                try:
                    s = str(val).strip().replace('$', '').replace(',', '')
                    return float(s)
                except (ValueError, TypeError):
                    return default

            def to_int_val(val, default=0):
                if val is None:
                    return default
                try:
                    s = str(val).strip().replace(',', '')
                    return int(float(s))
                except (ValueError, TypeError):
                    return default

            def parse_date_val(val):
                if not val:
                    return None
                if isinstance(val, date):
                    return val
                if isinstance(val, datetime):
                    return val.date()
                val_str = str(val).strip()
                for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d'):
                    try:
                        return datetime.strptime(val_str, fmt).date()
                    except ValueError:
                        pass
                return None

            creados = 0
            actualizados = 0
            errores = []
            
            for idx, row in enumerate(data_rows, start=start_excel_idx):
                if not any(row): continue
                
                try:
                    with transaction.atomic():
                        clave = str(row[0] or '').strip()
                        nombre = str(row[1] or '').strip()

                        if not nombre:
                            errores.append(f"Fila {idx}: El nombre es obligatorio.")
                            continue

                        is_33_cols = len(row) >= 20

                        if is_33_cols:
                            # Formato completo de 33 columnas
                            val_tipo = str(row[2] or '').strip().lower()
                            val_desc = str(row[3] or '').strip()
                            val_estado = str(row[4] or '').strip().lower()
                            val_abast = str(row[5] or '').strip().lower()

                            val_cat = str(row[6] or '').strip()
                            val_sub = str(row[7] or '').strip()
                            val_marca = str(row[8] or '').strip()
                            val_modelo = str(row[9] or '').strip()
                            val_linea = str(row[10] or '').strip()
                            val_unidad = str(row[11] or '').strip().upper()
                            val_iva = to_float_val(row[12]) if row[12] is not None else None
                            val_ieps = to_float_val(row[13]) if row[13] is not None else None

                            val_costo = to_float_val(row[14]) if row[14] is not None else None
                            val_venta = to_float_val(row[15]) if row[15] is not None else None
                            val_stock_min = to_int_val(row[16]) if row[16] is not None else None
                            val_stock_max = to_int_val(row[17]) if row[17] is not None else None

                            val_lote = to_bool_val(row[18]) if len(row) > 18 and row[18] is not None else None
                            val_serie = to_bool_val(row[19]) if len(row) > 19 and row[19] is not None else None
                            val_caducidad = to_bool_val(row[20]) if len(row) > 20 and row[20] is not None else None
                            val_fifo = to_bool_val(row[21]) if len(row) > 21 and row[21] is not None else None
                            val_lifo = to_bool_val(row[22]) if len(row) > 22 and row[22] is not None else None
                            val_fefo = to_bool_val(row[23]) if len(row) > 23 and row[23] is not None else None
                            val_tiene_iva = to_bool_val(row[24]) if len(row) > 24 and row[24] is not None else None
                            val_pos = to_bool_val(row[25]) if len(row) > 25 and row[25] is not None else None
                            val_modificadores = to_bool_val(row[26]) if len(row) > 26 and row[26] is not None else None

                            val_barcodes = str(row[27] or '').strip() if len(row) > 27 else ''
                            val_existencias = to_int_val(row[28]) if len(row) > 28 and row[28] is not None else 0
                            val_lote_stock = str(row[29] or '').strip() if len(row) > 29 else ''
                            val_caducidad_stock = parse_date_val(row[30]) if len(row) > 30 and row[30] is not None else None
                            val_almacen_stock = str(row[31] or '').strip() if len(row) > 31 else ''
                            val_sucursal_stock = str(row[32] or '').strip() if len(row) > 32 else ''
                        else:
                            # Formato anterior (17 columnas)
                            val_tipo = str(row[2] or '').strip().lower()
                            val_desc = ''
                            val_abast = str(row[3] or '').strip().lower()
                            val_cat = str(row[4] or '').strip()
                            val_sub = str(row[5] or '').strip()
                            val_marca = str(row[6] or '').strip()
                            val_modelo = str(row[7] or '').strip()
                            val_linea = ''
                            val_unidad = str(row[8] or '').strip().upper()
                            val_costo = to_float_val(row[9]) if row[9] is not None else None
                            val_venta = to_float_val(row[10]) if row[10] is not None else None
                            val_iva = to_float_val(row[11]) if row[11] is not None else None
                            val_ieps = None
                            val_stock_min = to_int_val(row[12]) if row[12] is not None else None
                            val_stock_max = to_int_val(row[13]) if row[13] is not None else None
                            val_lote = to_bool_val(row[14]) if len(row) > 14 and row[14] is not None else None
                            val_serie = to_bool_val(row[15]) if len(row) > 15 and row[15] is not None else None
                            val_caducidad = None
                            val_fifo = None
                            val_lifo = None
                            val_fefo = None
                            val_tiene_iva = None
                            val_pos = None
                            val_modificadores = None
                            val_estado = str(row[16] or '').strip().lower() if len(row) > 16 and row[16] is not None else ''
                            val_barcodes = ''
                            val_existencias = 0
                            val_lote_stock = ''
                            val_caducidad_stock = None
                            val_almacen_stock = ''
                            val_sucursal_stock = ''

                        # Buscar producto existente
                        if not clave:
                            producto = Producto.objects.filter(
                                Q(clave__isnull=True) | Q(clave=''),
                                nombre=nombre,
                                empresa=empresa_actual
                            ).first()
                        else:
                            producto = Producto.objects.filter(
                                clave=clave,
                                nombre=nombre,
                                empresa=empresa_actual
                            ).first()
                            if not producto:
                                producto = Producto.objects.filter(
                                    clave=clave,
                                    empresa=empresa_actual
                                ).first()

                        if producto:
                            # --- ACTUALIZAR PRODUCTO EXISTENTE ---
                            if val_tipo in ['producto', 'servicio']: producto.tipo = val_tipo
                            if val_desc: producto.descripcion = val_desc
                            if val_estado in ['activo', 'inactivo', 'descontinuado', 'revision']: producto.estado = val_estado
                            if val_abast in ['stock', 'produccion', 'compra']: producto.tipo_abastecimiento = val_abast

                            if val_cat:
                                producto.categoria = val_cat
                                cat_obj, _ = Categoria.objects.get_or_create(nombre=val_cat, empresa=empresa_actual)
                                if val_sub:
                                    producto.subcategoria = val_sub
                                    Subcategoria.objects.get_or_create(nombre=val_sub, categoria=cat_obj, empresa=empresa_actual)

                            if val_marca: producto.marca = val_marca
                            if val_modelo: producto.modelo = val_modelo
                            if val_linea: producto.linea = val_linea
                            if val_unidad: producto.unidad_medida = val_unidad
                            if val_iva is not None: producto.iva = val_iva
                            if val_ieps is not None: producto.ieps = val_ieps

                            if val_costo is not None: producto.precio_costo = val_costo
                            if val_venta is not None: producto.precio_venta = val_venta
                            if val_stock_min is not None: producto.stock_minimo = val_stock_min
                            if val_stock_max is not None: producto.stock_maximo = val_stock_max

                            if val_lote is not None: producto.maneja_lote = val_lote
                            if val_serie is not None: producto.maneja_serie = val_serie
                            if val_caducidad is not None: producto.maneja_caducidad = val_caducidad
                            if val_fifo is not None: producto.maneja_fifo = val_fifo
                            if val_lifo is not None: producto.maneja_lifo = val_lifo
                            if val_fefo is not None: producto.maneja_fefo = val_fefo
                            if val_tiene_iva is not None: producto.tiene_iva = val_tiene_iva
                            if val_pos is not None: producto.mostrar_en_pos = val_pos
                            if val_modificadores is not None: producto.permitir_modificadores = val_modificadores

                            producto.save()
                            actualizados += 1
                        else:
                            # --- CREAR NUEVO PRODUCTO ---
                            if val_cat:
                                cat_obj, _ = Categoria.objects.get_or_create(nombre=val_cat, empresa=empresa_actual)
                                if val_sub:
                                    Subcategoria.objects.get_or_create(nombre=val_sub, categoria=cat_obj, empresa=empresa_actual)

                            nuevo_estado = val_estado if val_estado in ['activo', 'inactivo', 'descontinuado', 'revision'] else 'activo'
                            nuevo_tipo = val_tipo if val_tipo in ['producto', 'servicio'] else 'producto'
                            nuevo_abast = val_abast if val_abast in ['stock', 'produccion', 'compra'] else 'compra'

                            producto = Producto.objects.create(
                                empresa=empresa_actual,
                                clave=clave,
                                nombre=nombre,
                                tipo=nuevo_tipo,
                                descripcion=val_desc or '',
                                estado=nuevo_estado,
                                tipo_abastecimiento=nuevo_abast,
                                categoria=val_cat,
                                subcategoria=val_sub,
                                marca=val_marca,
                                modelo=val_modelo,
                                linea=val_linea,
                                unidad_medida=val_unidad if val_unidad else 'H87',
                                iva=val_iva if val_iva is not None else 0.00,
                                ieps=val_ieps if val_ieps is not None else 0.00,
                                precio_costo=val_costo if val_costo is not None else 0.00,
                                precio_venta=val_venta if val_venta is not None else 0.00,
                                stock_minimo=val_stock_min if val_stock_min is not None else 0,
                                stock_maximo=val_stock_max if val_stock_max is not None else 1000,
                                maneja_lote=val_lote if val_lote is not None else False,
                                maneja_serie=val_serie if val_serie is not None else False,
                                maneja_caducidad=val_caducidad if val_caducidad is not None else False,
                                maneja_fifo=val_fifo if val_fifo is not None else False,
                                maneja_lifo=val_lifo if val_lifo is not None else False,
                                maneja_fefo=val_fefo if val_fefo is not None else False,
                                tiene_iva=val_tiene_iva if val_tiene_iva is not None else True,
                                mostrar_en_pos=val_pos if val_pos is not None else True,
                                permitir_modificadores=val_modificadores if val_modificadores is not None else False,
                            )
                            creados += 1

                        # Procesar códigos de barras adicionales (separados por coma)
                        if val_barcodes:
                            bcs = [b.strip() for b in val_barcodes.split(',') if b.strip()]
                            for bc in bcs:
                                existing_bc = CodigoBarrasAdicional.objects.filter(codigo=bc).first()
                                if existing_bc:
                                    if existing_bc.producto_id != producto.id:
                                        existing_bc.producto = producto
                                        existing_bc.save(update_fields=['producto'])
                                else:
                                    CodigoBarrasAdicional.objects.create(producto=producto, codigo=bc)

                        # Procesar existencias iniciales si cantidad > 0
                        if val_existencias > 0 and producto.tipo != 'servicio':
                            almacen_obj = None
                            if val_almacen_stock:
                                almacen_obj = Almacen.objects.filter(empresa=empresa_actual, nombre__iexact=val_almacen_stock).first()
                                if not almacen_obj:
                                    almacen_obj = Almacen.objects.filter(empresa=empresa_actual, nombre__icontains=val_almacen_stock).first()

                            sucursal_obj = None
                            if val_sucursal_stock:
                                sucursal_obj = Sucursal.objects.filter(empresa=empresa_actual, nombre__iexact=val_sucursal_stock).first()
                                if not sucursal_obj:
                                    sucursal_obj = Sucursal.objects.filter(empresa=empresa_actual, nombre__icontains=val_sucursal_stock).first()

                            if not almacen_obj:
                                if sucursal_obj:
                                    almacen_obj = Almacen.objects.filter(empresa=empresa_actual, sucursal=sucursal_obj).first()
                                if not almacen_obj:
                                    almacen_obj = Almacen.objects.filter(empresa=empresa_actual).first()

                            if not almacen_obj:
                                almacen_obj = Almacen.objects.create(
                                    empresa=empresa_actual,
                                    sucursal=sucursal_obj,
                                    nombre=val_almacen_stock or "Almacén Principal"
                                )

                            costo_u = producto.precio_costo if producto.precio_costo else Decimal('0.00')

                            Inventario.registrar_ingreso(
                                almacen=almacen_obj,
                                producto=producto,
                                cantidad_ingreso=val_existencias,
                                costo_unitario=costo_u,
                                referencia="Importación Inicial Excel",
                                lote=val_lote_stock if val_lote_stock else None,
                                usuario=request.user
                            )

                            if val_lote_stock or val_caducidad_stock:
                                DetalleRecepcionExtra.objects.create(
                                    producto=producto,
                                    almacen=almacen_obj,
                                    tipo='lote' if val_lote_stock else 'caducidad',
                                    lote=val_lote_stock or '',
                                    cantidad_lote=val_existencias,
                                    fecha_caducidad=val_caducidad_stock
                                )

                            # Actualizar flags del producto si se definió lote o caducidad
                            update_flags = []
                            if val_lote_stock and not producto.maneja_lote:
                                producto.maneja_lote = True
                                update_flags.append('maneja_lote')
                            if val_caducidad_stock and not producto.maneja_caducidad:
                                producto.maneja_caducidad = True
                                update_flags.append('maneja_caducidad')
                            if update_flags:
                                producto.save(update_fields=update_flags)

                except Exception as row_err:
                    errores.append(f"Fila {idx}: {str(row_err)}")
            
            if creados == 0 and actualizados == 0 and errores:
                return JsonResponse({'success': False, 'error': f"No se pudo procesar ningún artículo. Primer error: {errores[0]}"})

            msg = f'Importación finalizada.\nArtículos creados: {creados}\nArtículos actualizados: {actualizados}\n'
            if errores:
                msg += f'\nFilas con error: {len(errores)}\n'
                msg += '\nDetalle de primeros errores:\n'
                msg += "\n".join(errores[:10])
                if len(errores) > 10:
                    msg += "\n... (revisa el resto de tu archivo Excel)"
                
            return JsonResponse({'success': True, 'message': msg})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Solicitud inválida.'})

@login_required(login_url='/login/')
@require_inventory_permission('inventario', 'ver')
def exportar_existencias_excel(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return HttpResponse("No autorizado", status=403)

    # --- Filtrado (Misma lógica que el dashboard) ---
    q = request.GET.get('q', '')
    almacen_id = request.GET.get('almacen', '')
    sucursal_id = request.GET.get('sucursal', '')
    categoria = request.GET.get('categoria', '')
    estado = request.GET.get('estado', '')
    stock_status = request.GET.get('existencias', '')

    productos_qs = Producto.objects.filter(empresa=empresa_actual)

    if q:
        productos_qs = productos_qs.filter(
            Q(nombre__icontains=q) | Q(clave__icontains=q) | Q(marca__icontains=q) | Q(modelo__icontains=q) |
            Q(categoria__icontains=q) | Q(subcategoria__icontains=q)
        )
    if estado:
        productos_qs = productos_qs.filter(estado=estado)
    if categoria:
        productos_qs = productos_qs.filter(categoria=categoria)

    # --- Anotaciones de Stock (Misma lógica que el dashboard) ---
    def get_stock_sub(field):
        qs = Inventario.objects.filter(producto=OuterRef('pk'))
        if sucursal_id and sucursal_id != 'all': qs = qs.filter(sucursal_id=sucursal_id)
        if almacen_id and almacen_id != 'all': qs = qs.filter(almacen_id=almacen_id)
        return qs.values('producto').annotate(total=Sum(field)).values('total')[:1]

    # Para el costo promedio, si hay filtro de almacén/sucursal usamos el promedio de esa zona
    # Si no, el costo_promedio_global del modelo (o anotación similar)
    costo_prom_qs = Inventario.objects.filter(producto=OuterRef('pk'))
    if sucursal_id and sucursal_id != 'all': costo_prom_qs = costo_prom_qs.filter(sucursal_id=sucursal_id)
    if almacen_id and almacen_id != 'all': costo_prom_qs = costo_prom_qs.filter(almacen_id=almacen_id)
    
    costo_prom_subquery = costo_prom_qs.values('producto').annotate(avg=Avg('costo_promedio')).values('avg')[:1]

    productos = productos_qs.annotate(
        stock_fisico_anotado=Coalesce(Subquery(get_stock_sub('cantidad')), 0),
        stock_res_anotado=Coalesce(Subquery(get_stock_sub('reservado')), 0),
        costo_prom_anotado=Coalesce(Subquery(costo_prom_subquery), F('precio_costo'))
    ).annotate(
        stock_disponible_anotado=F('stock_fisico_anotado') - F('stock_res_anotado')
    )

    vista = request.GET.get('vista', 'existencias')
    if vista not in ['minimos_y_maximos', 'productos']:
        if stock_status == 'con':
            productos = productos.filter(stock_fisico_anotado__gt=0)
        elif stock_status == 'sin':
            productos = productos.filter(stock_fisico_anotado__lte=0)

    # --- Generar Excel ---
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Existencias Inventario"

    # Determinar nombre del almacén para la columna
    nombre_almacen_col = "GLOBAL"
    if almacen_id and almacen_id != 'all':
        alm_obj = Almacen.objects.filter(id=almacen_id).first()
        if alm_obj: nombre_almacen_col = alm_obj.nombre
    elif sucursal_id and sucursal_id != 'all':
        from preferencias.models import Sucursal
        suc_obj = Sucursal.objects.filter(id=sucursal_id).first()
        if suc_obj: nombre_almacen_col = f"SUC: {suc_obj.nombre}"

    headers = [
        'Clave', 'Producto', 'Zona/Almacén', 'Stock Físico', 'Reservado', 'Disponible', 
        'Unidad de medida', 'Costo Unit.', 'Costo Promedio', 'Valor Inventario'
    ]
    ws.append(headers)

    for p in productos:
        valor = float(p.stock_fisico_anotado) * float(p.costo_prom_anotado)
        # Obtener el nombre legible de la unidad de medida
        um_display = dict(p.UNIDAD_OPCIONES).get(p.unidad_medida, p.unidad_medida)
        
        ws.append([
            p.clave or '', p.nombre, nombre_almacen_col, p.stock_fisico_anotado, p.stock_res_anotado, p.stock_disponible_anotado,
            um_display, p.precio_costo, p.costo_prom_anotado, valor
        ])

    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except: pass
        ws.column_dimensions[column].width = max_length + 2

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Existencias_{empresa_actual.nombre}.xlsx"'
    wb.save(response)
    return response

@login_required(login_url='/login/')
@require_inventory_permission('inventario', 'crear')
def descargar_plantilla_recetas(request):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Plantilla Recetas"
    
    # Encabezados
    headers = ['Clave Producto Final (Producción)', 'Clave Componente (Stock/Compra)', 'Cantidad Requerida']
    ws.append(headers)
    
    # Ajustar ancho
    for col_idx, header in enumerate(headers, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = 35

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="Plantilla_Recetas_Masivas.xlsx"'
    wb.save(response)
    return response

@login_required(login_url='/login/')
@require_inventory_permission('inventario', 'crear', json_response=True)
def importar_recetas_ajax(request):
    if request.method == 'POST' and request.FILES.get('archivo_articulos'):
        empresa_actual = get_empresa_actual(request)
        excel_file = request.FILES['archivo_articulos']
        
        try:
            wb = openpyxl.load_workbook(excel_file)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            
            if len(rows) < 2:
                return JsonResponse({'success': False, 'error': 'El archivo está vacío.'})
            
            data_rows = rows[1:]
            
            # Agrupar por Producto Final
            recetas_data = defaultdict(list)
            for idx, row in enumerate(data_rows, start=2):
                if not any(row): continue
                clave_padre = str(row[0] or '').strip()
                clave_comp = str(row[1] or '').strip()
                cant = row[2] or 0
                
                if not clave_padre or not clave_comp: continue
                
                recetas_data[clave_padre].append({
                    'clave_comp': clave_comp,
                    'cantidad': cant,
                    'fila': idx
                })

            creadas = 0
            errores = []
            
            for clave_padre, items in recetas_data.items():
                try:
                    with transaction.atomic():
                        # 1. Validar Padre
                        padre = Producto.objects.filter(clave=clave_padre, empresa=empresa_actual).first()
                        if not padre:
                            errores.append(f"Padre '{clave_padre}': No existe en el catálogo.")
                            continue
                        
                        if padre.tipo_abastecimiento != 'produccion':
                            errores.append(f"Padre '{clave_padre}': No es de tipo producción.")
                            continue

                        # Limpiar receta anterior para evitar duplicados
                        DetalleReceta.objects.filter(producto_padre=padre).delete()

                        # 2. Validar y crear componentes
                        for item in items:
                            comp = Producto.objects.filter(clave=item['clave_comp'], empresa=empresa_actual).first()
                            if not comp:
                                errores.append(f"Padre '{clave_padre}', Fila {item['fila']}: El componente '{item['clave_comp']}' no existe.")
                                continue
                            
                            if comp.tipo_abastecimiento not in ['stock', 'compra']:
                                errores.append(f"Padre '{clave_padre}', Fila {item['fila']}: El componente '{item['clave_comp']}' debe ser Stock o Compra.")
                                continue
                            
                            DetalleReceta.objects.create(
                                producto_padre=padre,
                                componente=comp,
                                cantidad=item['cantidad']
                            )
                        
                        # Recalcular costo base del padre a partir de la receta importada
                        padre.recalcular_costo_desde_receta()
                        
                        creadas += 1
                except Exception as e:
                    errores.append(f"Padre '{clave_padre}': {str(e)}")
            
            if creadas == 0 and errores:
                return JsonResponse({'success': False, 'error': f"No se pudo procesar ninguna receta. Primer error: {errores[0]}"})

            msg = f'Importación de recetas finalizada.\nRecetas configuradas: {creadas}\n'
            if errores:
                msg += f'\nFilas/Padres con error: {len(errores)}\n'
                msg += '\nDetalle de primeros errores:\n'
                msg += "\n".join(errores[:10])
                if len(errores) > 10:
                    msg += "\n... (revisa el resto de tu archivo Excel)"
                
            return JsonResponse({'success': True, 'message': msg})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
            
    return JsonResponse({'success': False, 'error': 'Solicitud inválida.'})

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

@require_POST
@login_required(login_url='/login/')
@require_inventory_permission('inventario', 'crear', json_response=True)
def crear_producto_rapido(request):
    empresa = get_empresa_actual(request)
    if not empresa:
        return JsonResponse({'success': False, 'error': 'No se encontró la empresa'}, status=403)
    
    try:
        nombre = request.POST.get('nombre')
        tipo = request.POST.get('tipo', 'producto')
        tipo_abastecimiento = request.POST.get('tipo_abastecimiento', 'compra')
        categoria_id = request.POST.get('categoria', '')
        subcategoria = request.POST.get('subcategoria', '')
        
        categoria_nombre = ""
        if categoria_id:
            from categorias.models import Categoria as CategoriaCatalogo
            cat_obj = CategoriaCatalogo.objects.filter(id=categoria_id, empresa=empresa).first()
            if cat_obj:
                categoria_nombre = cat_obj.nombre
        
        if not nombre:
            return JsonResponse({'success': False, 'error': 'El nombre es obligatorio'}, status=400)

        # SIEMPRE NACEN EN REVISIÓN DESDE EL ALTA RÁPIDA
        estado = 'revision'

        producto = Producto.objects.create(
            nombre=nombre,
            tipo=tipo,
            tipo_abastecimiento=tipo_abastecimiento,
            categoria=categoria_nombre,
            subcategoria=subcategoria,
            estado=estado,
            precio_costo=0.00,
            precio_venta=0.00,
            iva=16.00,
            tiene_iva=True,
            empresa=empresa
        )
        
        return JsonResponse({
            'success': True,
            'id': producto.id,
            'nombre': producto.nombre,
            'precio_venta': str(producto.precio_venta),
            'iva': str(producto.iva)
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

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
            producto = get_object_or_404(Producto, id=producto_id, empresa=empresa_actual)
            
            # Buscamos un almacén por defecto para la venta directa
            from almacenes.models import Almacen
            almacen = Almacen.objects.filter(empresa=empresa_actual).first()
            
            if not almacen:
                raise ValueError("No hay almacenes configurados para realizar la venta.")

            Transaccion.objects.create(
                producto=producto, 
                almacen=almacen,
                tipo='venta', 
                cantidad=cantidad, 
                empresa=empresa_actual,
                usuario=request.user,
                referencia="Venta Directa (POS)",
                estado='recibida'
            )
            messages.success(request, f'Vendido: {cantidad} x {producto.nombre}')
            return redirect('punto_de_venta')
        except Exception as e:
            messages.error(request, str(e))
    return render(request, 'core/vender.html', {'productos': productos})

@login_required(login_url='/login/')
@require_inventory_permission('inventario', 'crear', json_response=True)
def crear_producto_ajax(request):
    if request.method == 'POST':
        try:
            from .forms import ProductoForm
            empresa_actual = get_empresa_actual(request)
            if not empresa_actual:
                return JsonResponse({'success': False, 'error': 'Empresa no detectada'})
            
            # Control de espacio en disco
            imagen_file = request.FILES.get('imagen')
            if imagen_file:
                from panel.views import calcular_uso_disco_mb
                uso_actual = calcular_uso_disco_mb(empresa_actual)
                size_mb = imagen_file.size / (1024 * 1024)
                if uso_actual + size_mb > empresa_actual.limite_espacio_disco:
                    return JsonResponse({
                        'success': False, 
                        'error': f'Límite de espacio en disco excedido ({empresa_actual.limite_espacio_disco} MB). No puedes subir más archivos.'
                    })

            form = ProductoForm(request.POST, request.FILES)
            if form.is_valid():
                producto = form.save(commit=False)
                producto.empresa = empresa_actual
                
                # Manejo manual de switches
                producto.maneja_lote = request.POST.get('maneja_lote') == 'on'
                producto.maneja_serie = request.POST.get('maneja_serie') == 'on'
                producto.maneja_caducidad = request.POST.get('maneja_caducidad') == 'on'
                producto.maneja_fifo = request.POST.get('maneja_fifo') == 'on'
                producto.maneja_lifo = request.POST.get('maneja_lifo') == 'on'
                producto.maneja_fefo = request.POST.get('maneja_fefo') == 'on'
                if producto.maneja_fifo:
                    producto.maneja_lifo = False
                    producto.maneja_fefo = False
                elif producto.maneja_lifo:
                    producto.maneja_fefo = False
                producto.tiene_iva = request.POST.get('tiene_iva') == 'on'
                producto.mostrar_en_pos = request.POST.get('mostrar_en_pos') == 'on'
                producto.permitir_modificadores = request.POST.get('permitir_modificadores') == 'on'

                if not producto.tiene_iva:
                    producto.iva = 0.00

                test_id = request.POST.get('test_calidad')
                if test_id:
                    from produccion.models import Test
                    producto.test_calidad = Test.objects.filter(id=test_id, empresa=empresa_actual).first()

                # Validación de códigos de barras adicionales
                from core.models import CodigoBarrasAdicional
                barcodes_list = request.POST.getlist('barcodes_adicionales')
                for code in barcodes_list:
                    code_clean = code.strip()
                    if not code_clean:
                        continue
                    
                    qs_dupe = CodigoBarrasAdicional.objects.filter(codigo=code_clean, producto__empresa=empresa_actual)
                    dupe = qs_dupe.first()
                    if dupe:
                        return JsonResponse({'success': False, 'error': f'El código de barras "{code_clean}" ya está registrado en el artículo "{dupe.producto.nombre}".'})
                    
                    qs_prod = Producto.objects.filter(clave=code_clean, empresa=empresa_actual)
                    dupe_prod = qs_prod.first()
                    if dupe_prod:
                        return JsonResponse({'success': False, 'error': f'El código de barras "{code_clean}" ya es la clave principal de otro artículo: "{dupe_prod.nombre}".'})

                with transaction.atomic():
                    producto.save()
                    # Guardar códigos de barras adicionales
                    for code in barcodes_list:
                        code_clean = code.strip()
                        if code_clean:
                            CodigoBarrasAdicional.objects.create(producto=producto, codigo=code_clean)

                return JsonResponse({'success': True, 'message': 'Artículo creado correctamente.'})
            else:
                return JsonResponse({'success': False, 'error': form.errors})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required(login_url='/login/')
@require_inventory_permission('inventario', 'ver')
def dashboard_inventario(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return render(request, 'error_sin_empresa.html', status=403)
    
    # --- FILTROS ---
    sucursal_sesion_id = request.session.get('sucursal_id')
    sucursal_id = request.GET.get('sucursal')
    almacen_id = request.GET.get('almacen')
    
    # Solo aplicamos la sucursal de sesión si NO hay filtros explícitos de sucursal o almacén
    # Y si el usuario no ha pedido explícitamente "ver todo" (sucursal='')
    if sucursal_id is None and almacen_id is None and sucursal_sesion_id:
        sucursal_id = str(sucursal_sesion_id)
        
    q = request.GET.get('q')
    estado = request.GET.get('estado')
    vista = request.GET.get('vista', 'existencias')
    stock_status = request.GET.get('existencias', 'con')
    if stock_status not in ['con', 'sin']:
        stock_status = 'con'
    categoria_id = request.GET.get('categoria')
    orden = request.GET.get('orden', '')
    direccion = request.GET.get('dir', 'asc')

    if vista == 'lotes_y_caducidades':
        from recepciones.models import DetalleRecepcionExtra
        extras_qs = DetalleRecepcionExtra.objects.filter(
            producto__empresa=empresa_actual,
            cantidad_lote__gt=0
        ).select_related('producto', 'almacen')
        
        if sucursal_id:
            extras_qs = extras_qs.filter(almacen__sucursal_id=sucursal_id)
        if almacen_id:
            extras_qs = extras_qs.filter(almacen_id=almacen_id)
            
        if q:
            extras_qs = extras_qs.filter(
                Q(producto__nombre__icontains=q) | Q(lote__icontains=q) | Q(producto__clave__icontains=q)
            )
        if estado:
            extras_qs = extras_qs.filter(producto__estado=estado)
        if categoria_id:
            extras_qs = extras_qs.filter(producto__categoria=categoria_id)
            
        # Ordenamiento dinámico para lotes_y_caducidades
        prefix = '-' if direccion == 'desc' else ''
        orden_map_lotes = {
            'nombre': f'{prefix}producto__nombre',
            'lote': f'{prefix}lote',
            'caducidad': f'{prefix}fecha_caducidad',
            'existencias': f'{prefix}cantidad_lote',
            'reservado': f'{prefix}id', # Lotes no manejan reserva diferenciada
            'disponible': f'{prefix}cantidad_lote',
        }
        campo_orden_lote = orden_map_lotes.get(orden, 'producto__nombre')
        extras_qs = extras_qs.order_by(campo_orden_lote, 'id')
        
        # Calcular totales consolidados
        totales_resumen = extras_qs.aggregate(
            total_stock_fisico=Sum('cantidad_lote')
        )
        total_costo_agg = extras_qs.aggregate(
            total_costo=Sum(ExpressionWrapper(F('cantidad_lote') * F('producto__precio_costo'), output_field=FloatField()))
        )
        resumen_totales = {
            'costo_inventario': total_costo_agg.get('total_costo') or 0.0,
            'stock_fisico': totales_resumen.get('total_stock_fisico') or 0,
            'stock_reservado': 0,
            'stock_disponible': totales_resumen.get('total_stock_fisico') or 0,
        }
        
        # --- PAGINACIÓN ---
        paginator = Paginator(extras_qs, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
    else:
        productos_qs = Producto.objects.filter(empresa=empresa_actual)

        # NOTA: El filtrado por sucursal/almacén NO debe reducir el catálogo de productos.
        # Solo debe afectar a las cantidades que se muestran en las columnas de Stock.
        # El filtrado de la lista (QuerySet) solo se aplica para búsqueda, estado o categoría.

        if q:
            productos_qs = productos_qs.filter(
                Q(nombre__icontains=q) | Q(marca__icontains=q) | Q(modelo__icontains=q) |
                Q(categoria__icontains=q) | Q(subcategoria__icontains=q)
            )
        if estado:
            productos_qs = productos_qs.filter(estado=estado)

        if categoria_id:
            productos_qs = productos_qs.filter(categoria=categoria_id)

        # 1. PRECIO PROMEDIO VENTA (GLOBAL)
        avg_venta_subquery = DetalleOrdenVenta.objects.filter(producto=OuterRef('pk')).values('producto').annotate(promedio=Avg('precio_unitario')).values('promedio')[:1]
        # 2. ÚLTIMO PRECIO VENTA (GLOBAL)
        ultimo_precio_venta = DetalleOrdenVenta.objects.filter(
            producto=OuterRef('pk')
        ).exclude(
            orden_venta__estado='cancelado'
        ).order_by('-orden_venta__fecha_creacion', '-id').values('precio_unitario')[:1]
        # 3. COSTO MÁXIMO COMPRA (GLOBAL, EN PESOS)
        max_costo_compra = DetalleRecepcion.objects.filter(
            producto=OuterRef('pk')
        ).exclude(
            recepcion__estado='cancelada'
        ).annotate(
            costo_pesos=ExpressionWrapper(F('costo_unitario') * F('recepcion__tipo_cambio'), output_field=DecimalField(max_digits=10, decimal_places=2))
        ).order_by('-costo_pesos').values('costo_pesos')[:1]

        # 3.1 ÚLTIMO COSTO COMPRA (RECEPCIÓN MÁS RECIENTE, EN PESOS)
        ultimo_costo_subquery = DetalleRecepcion.objects.filter(
            producto=OuterRef('pk')
        ).exclude(
            recepcion__estado='cancelada'
        ).annotate(
            costo_pesos=ExpressionWrapper(
                F('costo_unitario') * Coalesce(F('recepcion__tipo_cambio'), 1.0),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        ).order_by('-recepcion__fecha', '-id').values('costo_pesos')[:1]

        # 4. COSTO PROMEDIO (PONDERADO POR ALMACÉN O GLOBAL)
        if almacen_id:
            inv_cost_sub = Inventario.objects.filter(
                producto=OuterRef('pk'), almacen_id=almacen_id, costo_promedio__gt=0
            ).values('costo_promedio')[:1]
        else:
            inv_cost_qs = Inventario.objects.filter(producto=OuterRef('pk'), costo_promedio__gt=0)
            if sucursal_id:
                inv_cost_qs = inv_cost_qs.filter(sucursal_id=sucursal_id)
            inv_cost_sub = inv_cost_qs.values('producto').annotate(avg=Avg('costo_promedio')).values('avg')[:1]

        costo_promedio_expr = Coalesce(
            Subquery(inv_cost_sub, output_field=DecimalField(max_digits=10, decimal_places=2)),
            Case(
                When(costo_promedio__gt=0, then=F('costo_promedio')),
                default=F('precio_costo'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            ),
            output_field=DecimalField(max_digits=10, decimal_places=2)
        )

        # 5. VALOR TOTAL INVENTARIO (POR ALMACÉN SI SE FILTRA)
        inv_val_filter = Q(producto=OuterRef('pk'), cantidad__gt=0)
        if sucursal_id:
            inv_val_filter &= Q(sucursal_id=sucursal_id)
        if almacen_id:
            inv_val_filter &= Q(almacen_id=almacen_id)

        costo_unit_val = Case(
            When(costo_promedio__gt=0, then=F('costo_promedio')),
            default=F('producto__precio_costo'),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )
        costo_inventario_subquery = Inventario.objects.filter(inv_val_filter).values('producto').annotate(
            valor_total=Sum(ExpressionWrapper(F('cantidad') * costo_unit_val, output_field=FloatField()))
        ).values('valor_total')[:1]

        # 6. STOCK FISICO Y RESERVADO (DINÁMICO)
        def get_stock_sub(field):
            qs = Inventario.objects.filter(producto=OuterRef('pk'))
            if sucursal_id: qs = qs.filter(sucursal_id=sucursal_id)
            if almacen_id: qs = qs.filter(almacen_id=almacen_id)
            return qs.values('producto').annotate(total=Sum(field)).values('total')[:1]

        productos = productos_qs.annotate(
            precio_promedio_venta=Subquery(avg_venta_subquery),
            ultimo_precio_venta=Subquery(ultimo_precio_venta),
            precio_max_venta=Subquery(ultimo_precio_venta),
            costo_max_compra=Subquery(max_costo_compra),
            ultimo_costo_anotado=Coalesce(
                Subquery(ultimo_costo_subquery),
                Case(
                    When(ultimo_costo__gt=0, then=F('ultimo_costo')),
                    default=F('precio_costo'),
                    output_field=DecimalField(max_digits=10, decimal_places=2)
                ),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            ),
            costo_promedio_anotado=costo_promedio_expr,
            costo_inventario_anotado=Coalesce(Subquery(costo_inventario_subquery), 0.0, output_field=FloatField()),
            stock_fisico=Coalesce(Subquery(get_stock_sub('cantidad')), 0),
            stock_res=Coalesce(Subquery(get_stock_sub('reservado')), 0)
        ).annotate(
            stock_disponible_anotado=ExpressionWrapper(
                F('stock_fisico') - F('stock_res'),
                output_field=IntegerField()
            )
        )

        if vista not in ['minimos_y_maximos', 'productos']:
            if stock_status == 'con':
                productos = productos.filter(stock_fisico__gt=0)
            elif stock_status == 'sin':
                productos = productos.filter(stock_fisico__lte=0)

        # Ordenamiento dinámico para existencias, productos y minimos_y_maximos
        prefix = '-' if direccion == 'desc' else ''
        orden_map_productos = {
            'nombre': f'{prefix}nombre',
            'existencias': f'{prefix}stock_fisico',
            'costo_base': f'{prefix}precio_costo',
            'precio_base': f'{prefix}precio_venta',
            'costo_inventario': f'{prefix}costo_inventario_anotado',
            'minimos': f'{prefix}stock_minimo',
            'maximos': f'{prefix}stock_maximo',
        }
        campo_orden_prod = orden_map_productos.get(orden, 'nombre')
        productos = productos.order_by(campo_orden_prod, 'id')
        
        # Calcular totales consolidados (del total de productos filtrados, no solo de la página)
        totales_resumen = productos.aggregate(
            total_costo_inventario=Sum('costo_inventario_anotado'),
            total_stock_fisico=Sum('stock_fisico'),
            total_stock_reservado=Sum('stock_res'),
            total_stock_disponible=Sum('stock_disponible_anotado')
        )
        resumen_totales = {
            'costo_inventario': totales_resumen.get('total_costo_inventario') or 0.0,
            'stock_fisico': totales_resumen.get('total_stock_fisico') or 0,
            'stock_reservado': totales_resumen.get('total_stock_reservado') or 0,
            'stock_disponible': totales_resumen.get('total_stock_disponible') or 0,
        }
        
        # --- PAGINACIÓN ---
        paginator = Paginator(productos, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

    from preferencias.models import Sucursal
    sucursales = Sucursal.objects.filter(empresa=empresa_actual).order_by('nombre')

    almacenes_todos = Almacen.objects.filter(empresa=empresa_actual).order_by('nombre')
    almacenes = almacenes_todos
    if sucursal_id:
        almacenes = almacenes.filter(sucursal_id=sucursal_id)

    todas_categorias = Categoria.objects.filter(empresa=empresa_actual).order_by('nombre')
    from produccion.models import Test
    tests_calidad = Test.objects.filter(empresa=empresa_actual).order_by('nombre')
    productos_padre_receta = Producto.objects.filter(
        empresa=empresa_actual,
        tipo_abastecimiento='produccion'
    ).order_by('nombre')
    productos_componentes_receta = Producto.objects.filter(
        empresa=empresa_actual
    ).order_by('nombre')

    # Monedas para conversión en modal
    monedas = Moneda.objects.filter(empresa=empresa_actual)

    # 5 artículos próximos a caducar
    from recepciones.models import DetalleRecepcionExtra
    proximos_caducar_qs = DetalleRecepcionExtra.objects.filter(
        producto__empresa=empresa_actual,
        cantidad_lote__gt=0,
        fecha_caducidad__isnull=False
    ).select_related('producto', 'almacen')
    
    if sucursal_id:
        proximos_caducar_qs = proximos_caducar_qs.filter(almacen__sucursal_id=sucursal_id)
    if almacen_id:
        proximos_caducar_qs = proximos_caducar_qs.filter(almacen_id=almacen_id)
        
    proximos_caducar = proximos_caducar_qs.annotate(
        costo_valorizado=ExpressionWrapper(F('cantidad_lote') * F('producto__precio_costo'), output_field=FloatField())
    ).order_by('fecha_caducidad')[:5]

    # Artículos con stock por debajo o próximos al stock mínimo requerido
    def get_stock_min_sub(field):
        qs_sub = Inventario.objects.filter(producto=OuterRef('pk'))
        if sucursal_id:
            qs_sub = qs_sub.filter(sucursal_id=sucursal_id)
        if almacen_id:
            qs_sub = qs_sub.filter(almacen_id=almacen_id)
        return qs_sub.values('producto').annotate(total=Sum(field)).values('total')[:1]

    articulos_stock_minimo_qs = Producto.objects.filter(
        empresa=empresa_actual,
        stock_minimo__gt=0
    ).annotate(
        stock_fisico_calc=Coalesce(Subquery(get_stock_min_sub('cantidad')), 0),
        stock_res_calc=Coalesce(Subquery(get_stock_min_sub('reservado')), 0)
    ).annotate(
        stock_disp_calc=ExpressionWrapper(
            F('stock_fisico_calc') - F('stock_res_calc'),
            output_field=IntegerField()
        ),
        diferencia_minimo=ExpressionWrapper(
            F('stock_minimo') - (F('stock_fisico_calc') - F('stock_res_calc')),
            output_field=IntegerField()
        )
    ).annotate(
        nivel_riesgo=Case(
            When(stock_disp_calc__lte=0, then=Value('agotado')),
            When(stock_disp_calc__lt=F('stock_minimo'), then=Value('bajo')),
            When(stock_disp_calc=F('stock_minimo'), then=Value('minimo')),
            default=Value('proximo'),
            output_field=CharField()
        )
    ).filter(
        stock_disp_calc__lte=ExpressionWrapper(F('stock_minimo') * 1.25, output_field=IntegerField())
    ).order_by('-diferencia_minimo', 'stock_disp_calc')[:10]

    # Catálogo completo de productos activos con conversiones para el modal de Solicitud de Compra
    lista_productos_qs = Producto.objects.filter(
        empresa=empresa_actual,
        estado='activo'
    ).prefetch_related('conversiones').order_by('nombre')

    unidad_dict = dict(Producto.UNIDAD_OPCIONES)
    productos_todos_solmin = []
    for p in lista_productos_qs:
        u_full = unidad_dict.get(p.unidad_medida, p.unidad_medida or 'Pieza')
        m_u = re.search(r'\((.*?)\)', u_full)
        u_nom = m_u.group(1).strip() if m_u else u_full.strip()
        convs = []
        for c in p.conversiones.all():
            if not c.activo:
                continue
            sat_d = unidad_dict.get(c.unidad_destino, c.unidad_destino)
            nom_c = getattr(c, 'unidad_destino_nombre', sat_d)
            m_c = re.search(r'\((.*?)\)', nom_c)
            nom_limpio = m_c.group(1).strip() if m_c else nom_c.strip()
            convs.append({
                'id': c.id,
                'unidad_destino': c.unidad_destino,
                'unidad_destino_nombre': nom_limpio,
                'factor_equivalencia': float(c.factor_equivalencia)
            })
        productos_todos_solmin.append({
            'id': p.id,
            'nombre': p.nombre,
            'clave': p.clave or '',
            'categoria': p.categoria or 'Sin categoría',
            'precio_costo': float(p.precio_costo or 0),
            'stock_minimo': p.stock_minimo or 0,
            'stock_maximo': p.stock_maximo or 0,
            'unidad_medida': p.unidad_medida or 'H87',
            'unidad_medida_display': u_nom,
            'conversiones': convs
        })

    contexto = {
        'page_obj': page_obj,
        'proximos_caducar': proximos_caducar,
        'articulos_stock_minimo': articulos_stock_minimo_qs,
        'productos_todos_solmin': productos_todos_solmin,
        'productos_todos_json': json.dumps(productos_todos_solmin),
        'almacenes': almacenes,
        'almacenes_todos': almacenes_todos,
        'sucursales': sucursales,
        'categorias': todas_categorias,
        'tests_calidad': tests_calidad,
        'productos_padre_receta': productos_padre_receta,
        'productos_componentes_receta': productos_componentes_receta,
        'monedas': monedas,
        'resumen_totales': resumen_totales,
        'filtros': {
            'sucursal': sucursal_id or '',
            'almacen': almacen_id or '', 
            'q': q or '',
            'estado': estado or '',
            'vista': vista,
            'existencias': stock_status or '',
            'categoria': categoria_id or '',
            'orden': orden or '',
            'dir': direccion or 'asc'
        },
        'section': 'inventario'
    }
    return render(request, 'dashboard_inventario.html', contexto)

@login_required
@require_inventory_permission('inventario', 'existencias', json_response=True)
def api_detalle_producto_inventario(request, producto_id):
    try:
        empresa_actual = get_empresa_actual(request)
        producto = get_object_or_404(Producto, id=producto_id, empresa=empresa_actual)
        
        # 1. HISTORIAL DE RECEPCIONES (EXISTENCIAS)
        detalles = DetalleRecepcion.objects.filter(producto_id=producto_id).select_related('recepcion', 'detalle_compra__orden_compra').order_by('-recepcion__fecha')
        historial_data = []
        for d in detalles:
            folio_oc, proveedor = "Directa", "Directo / Sin OC"
            if d.detalle_compra and d.detalle_compra.orden_compra:
                oc = d.detalle_compra.orden_compra
                folio_oc, proveedor = f"OC-{oc.id:04d}", oc.proveedor
            historial_data.append({
                'folio_oc': folio_oc, 'oc_id': d.detalle_compra.orden_compra.id if d.detalle_compra and d.detalle_compra.orden_compra else None,
                'folio_rec': f"REC-{d.recepcion.id:04d}", 'rec_id': d.recepcion.id, 'proveedor': str(proveedor),
                'fecha': d.recepcion.fecha.strftime('%d/%m/%Y'), 'cantidad': d.cantidad_recibida,
                'costo': float(d.costo_unitario), 'total': float(d.cantidad_recibida * d.costo_unitario)
            })

        # 2. LOTES Y SERIES (DESDE EXTRAS)
        extras = DetalleRecepcionExtra.objects.filter(
            Q(detalle_recepcion__producto_id=producto_id) | Q(producto_id=producto_id)
        ).select_related('almacen', 'detalle_recepcion__recepcion')
        
        lotes_data = []
        series_data = []
        
        for e in extras:
            # Determinar fecha: prioridad a recepción, luego fecha creación propia
            fecha_disp = "--"
            if e.detalle_recepcion and e.detalle_recepcion.recepcion:
                fecha_disp = e.detalle_recepcion.recepcion.fecha.strftime('%d/%m/%Y')
            elif e.fecha_creacion:
                fecha_disp = e.fecha_creacion.strftime('%d/%m/%Y')

            if e.tipo in ['lote', 'caducidad']:
                if (e.cantidad_lote or 0) <= 0:
                    continue
                lote_label = e.lote or (f"Cad: {e.fecha_caducidad.strftime('%d/%m/%Y')}" if e.fecha_caducidad else 'Sin lote')
                lotes_data.append({
                    'lote': lote_label,
                    'cantidad': e.cantidad_lote,
                    'almacen': e.almacen.nombre if e.almacen else 'N/A',
                    'fecha': fecha_disp,
                    'fecha_caducidad': e.fecha_caducidad.strftime('%d/%m/%Y') if e.fecha_caducidad else '--'
                })
            elif e.tipo == 'serie':
                series_data.append({
                    'serie': e.serie,
                    'almacen': e.almacen.nombre if e.almacen else 'N/A',
                    'fecha': fecha_disp
                })

        # 3. PEDIMENTOS (DESDE RECEPCIÓN)
        # Obtenemos las recepciones únicas que tengan pedimento para este producto
        recepciones_con_pedimento = Recepcion.objects.filter(detalles__producto_id=producto_id, pedimento__isnull=False).exclude(pedimento='').distinct()
        pedimentos_data = []
        for r in recepciones_con_pedimento:
            pedimentos_data.append({
                'pedimento': r.pedimento,
                'aduana': r.aduana or 'N/A',
                'fecha': r.fecha_pedimento.strftime('%d/%m/%Y') if r.fecha_pedimento else 'N/A',
                'folio_rec': f"REC-{r.id:04d}",
                'rec_id': r.id
            })

        return JsonResponse({
            'historial': historial_data,
            'lotes': lotes_data,
            'series': series_data,
            'pedimentos': pedimentos_data
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@login_required
@require_inventory_permission('inventario', 'ver', json_response=True)
def obtener_producto_json(request, producto_id):
    try:
        empresa_actual = get_empresa_actual(request)
        producto = get_object_or_404(Producto, id=producto_id, empresa=empresa_actual)
        
        # Obtener plantillas globales de listas
        from categorias.models import ListaPrecioCosto
        listas_maestras = ListaPrecioCosto.objects.filter(empresa=empresa_actual).values(
            'id', 'nombre', 'porcentaje_extra', 'monto_extra', 'tipo'
        )
        
        return JsonResponse({
            'id': producto.id, 'clave': producto.clave or '', 'nombre': producto.nombre, 'descripcion': producto.descripcion,
            'tipo': producto.tipo, 'tipo_abastecimiento': producto.tipo_abastecimiento, 'estado': producto.estado,
            'categoria': producto.categoria or '', 'subcategoria': producto.subcategoria or '',
            'marca': producto.marca or '', 'modelo': producto.modelo or '', 'linea': producto.linea or '',
            'unidad_medida': producto.unidad_medida, 'iva': str(producto.iva), 'ieps': str(producto.ieps),
            'precio_costo': str(producto.precio_costo), 'precio_venta': str(producto.precio_venta),
            'ultimo_costo': str(producto.ultimo_costo if producto.ultimo_costo is not None else producto.precio_costo),
            'costo_promedio': str(producto.costo_promedio if producto.costo_promedio is not None else producto.precio_costo),
            'precios_lista': producto.precios_lista, 'costos_lista': producto.costos_lista,
            'listas_maestras': list(listas_maestras),
            'stock_minimo': producto.stock_minimo, 'stock_maximo': producto.stock_maximo,
            'maneja_lote': producto.maneja_lote, 'maneja_serie': producto.maneja_serie,
            'maneja_caducidad': producto.maneja_caducidad,
            'maneja_fifo': producto.maneja_fifo,
            'maneja_lifo': producto.maneja_lifo,
            'maneja_fefo': producto.maneja_fefo,
            'tiene_iva': producto.tiene_iva,
            'mostrar_en_pos': producto.mostrar_en_pos,
            'permitir_modificadores': producto.permitir_modificadores,
            'test_calidad_id': producto.test_calidad.id if producto.test_calidad else "",
            'imagen_url': producto.imagen.url if producto.imagen else '',
            'barcodes': list(producto.barcodes.values_list('codigo', flat=True)),
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=404)

@login_required(login_url='/login/')
@require_inventory_permission('inventario', 'editar', json_response=True)
def actualizar_producto_ajax(request, producto_id):
    if request.method == 'POST':
        try:
            from .forms import ProductoForm
            empresa_actual = get_empresa_actual(request)
            producto = get_object_or_404(Producto, id=producto_id, empresa=empresa_actual)

            # Control de espacio en disco y borrado
            imagen_file = request.FILES.get('imagen')
            eliminar_imagen = request.POST.get('eliminar_imagen') == 'true'

            if eliminar_imagen:
                if producto.imagen:
                    producto.imagen.delete(save=False)
                producto.imagen = None

            if imagen_file:
                # Borrar imagen previa si existe para liberar espacio en disco
                if producto.imagen:
                    producto.imagen.delete(save=False)

                from panel.views import calcular_uso_disco_mb
                uso_actual = calcular_uso_disco_mb(empresa_actual)
                size_mb = imagen_file.size / (1024 * 1024)
                if uso_actual + size_mb > empresa_actual.limite_espacio_disco:
                    return JsonResponse({
                        'success': False, 
                        'error': f'Límite de espacio en disco excedido ({empresa_actual.limite_espacio_disco} MB). No puedes subir más archivos.'
                    })

            form = ProductoForm(request.POST, request.FILES, instance=producto)
            if form.is_valid():
                producto = form.save(commit=False)
                # Maneja el switch manual para lote/serie ya que vienen como 'on'
                producto.maneja_lote = request.POST.get('maneja_lote') == 'on'
                producto.maneja_serie = request.POST.get('maneja_serie') == 'on'
                producto.maneja_caducidad = request.POST.get('maneja_caducidad') == 'on'
                producto.maneja_fifo = request.POST.get('maneja_fifo') == 'on'
                producto.maneja_lifo = request.POST.get('maneja_lifo') == 'on'
                producto.maneja_fefo = request.POST.get('maneja_fefo') == 'on'
                if producto.maneja_fifo:
                    producto.maneja_lifo = False
                    producto.maneja_fefo = False
                elif producto.maneja_lifo:
                    producto.maneja_fefo = False
                producto.tiene_iva = request.POST.get('tiene_iva') == 'on'
                producto.mostrar_en_pos = request.POST.get('mostrar_en_pos') == 'on'
                producto.permitir_modificadores = request.POST.get('permitir_modificadores') == 'on'
                
                if not producto.tiene_iva:
                    producto.iva = 0.00
                
                test_id = request.POST.get('test_calidad')
                if test_id:
                    from produccion.models import Test
                    producto.test_calidad = Test.objects.filter(id=test_id, empresa=empresa_actual).first()
                else:
                    producto.test_calidad = None
                
                # Validación de códigos de barras adicionales
                from core.models import CodigoBarrasAdicional
                barcodes_list = request.POST.getlist('barcodes_adicionales')
                for code in barcodes_list:
                    code_clean = code.strip()
                    if not code_clean:
                        continue
                    
                    qs_dupe = CodigoBarrasAdicional.objects.filter(codigo=code_clean, producto__empresa=empresa_actual)
                    if producto.id:
                        qs_dupe = qs_dupe.exclude(producto_id=producto.id)
                    dupe = qs_dupe.first()
                    if dupe:
                        return JsonResponse({'success': False, 'error': f'El código de barras "{code_clean}" ya está registrado en el artículo "{dupe.producto.nombre}".'})
                    
                    qs_prod = Producto.objects.filter(clave=code_clean, empresa=empresa_actual)
                    if producto.id:
                        qs_prod = qs_prod.exclude(id=producto.id)
                    dupe_prod = qs_prod.first()
                    if dupe_prod:
                        return JsonResponse({'success': False, 'error': f'El código de barras "{code_clean}" ya es la clave principal de otro artículo: "{dupe_prod.nombre}".'})

                with transaction.atomic():
                    producto.save()
                    # Eliminar códigos previos y guardar nuevos
                    producto.barcodes.all().delete()
                    for code in barcodes_list:
                        code_clean = code.strip()
                        if code_clean:
                            CodigoBarrasAdicional.objects.create(producto=producto, codigo=code_clean)

                return JsonResponse({'success': True, 'message': 'Artículo actualizado correctamente.'})
            else:
                return JsonResponse({'success': False, 'error': form.errors})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
@require_POST
def eliminar_producto_ajax(request, producto_id):
    empresa_actual = get_empresa_actual(request)
    producto = get_object_or_404(Producto, id=producto_id, empresa=empresa_actual)

    # 1. Verificar asociaciones con otros registros
    from almacenes.models import Inventario, Kardex, DetalleTomaInventario
    from compras.models import DetalleCompra
    from recepciones.models import DetalleRecepcion, DetalleRecepcionExtra, DetalleDevolucionRecepcion
    from ventas.models import DetalleOrdenVenta
    from pedidos.models import DetallePedido
    from cotizaciones.models import DetalleCotizacion
    from solicitudcompras.models import DetalleSolicitudCompra
    from produccion.models import OrdenProduccion, DetalleOrdenProduccion
    from core.models import DetalleReceta

    asociaciones = []

    # Stock en almacén mayor a cero
    stock_agg = Inventario.objects.filter(producto=producto).aggregate(
        total=Sum('cantidad'),
        res=Sum('reservado')
    )
    total_stock = stock_agg.get('total') or 0
    total_res = stock_agg.get('res') or 0
    if total_stock > 0 or total_res > 0:
        asociaciones.append("Existencias en almacén (stock mayor a cero)")

    if Kardex.objects.filter(producto=producto).exists():
        asociaciones.append("Movimientos en Kardex")

    if DetalleCompra.objects.filter(producto=producto).exists():
        asociaciones.append("Órdenes de compra")

    if DetalleRecepcion.objects.filter(producto=producto).exists() or DetalleRecepcionExtra.objects.filter(producto=producto).exists():
        asociaciones.append("Recepciones de mercancía / Lotes")

    if DetalleDevolucionRecepcion.objects.filter(producto=producto).exists():
        asociaciones.append("Devoluciones de compra")

    if DetalleOrdenVenta.objects.filter(producto=producto).exists():
        asociaciones.append("Ventas registradas")

    if DetallePedido.objects.filter(producto=producto).exists():
        asociaciones.append("Pedidos de clientes")

    if DetalleCotizacion.objects.filter(producto=producto).exists():
        asociaciones.append("Cotizaciones")

    if DetalleSolicitudCompra.objects.filter(producto=producto).exists():
        asociaciones.append("Solicitudes de compra")

    if OrdenProduccion.objects.filter(producto=producto).exists() or DetalleOrdenProduccion.objects.filter(producto=producto).exists():
        asociaciones.append("Órdenes de producción")

    if DetalleReceta.objects.filter(componente=producto).exists():
        asociaciones.append("Recetas activas (se utiliza como componente)")

    if asociaciones:
        asociaciones_str = ", ".join(asociaciones)
        return JsonResponse({
            'success': False,
            'error': f"No se puede eliminar el artículo '{producto.nombre}' porque tiene asociación con otros registros en el sistema ({asociaciones_str})."
        })

    try:
        with transaction.atomic():
            # Limpiar registros dependientes que no impiden la eliminación
            producto.barcodes.all().delete()
            producto.conversiones.all().delete()
            producto.receta.all().delete()
            producto.modificadores.all().delete()
            producto.detalles_toma_inventario.all().delete()
            Inventario.objects.filter(producto=producto).delete()
            from proveedores.models import MapeoProductoProveedor
            MapeoProductoProveedor.objects.filter(producto=producto).delete()

            nombre_prod = producto.nombre
            producto.delete()

            return JsonResponse({
                'success': True,
                'message': f"El artículo '{nombre_prod}' ha sido eliminado correctamente."
            })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f"Ocurrió un error al intentar eliminar el artículo: {str(e)}"
        })

@login_required
@require_inventory_permission('inventario', 'ver', json_response=True)
def api_detalle_documento(request):
    doc_tipo, doc_id = request.GET.get('tipo'), request.GET.get('id')
    empresa_actual = get_empresa_actual(request)
    try:
        if doc_tipo == 'oc':
            obj = get_object_or_404(OrdenCompra, id=doc_id, empresa=empresa_actual)
            data = {'titulo': 'Detalle Orden de Compra', 'folio': f"OC-{obj.id:04d}", 'proveedor': str(obj.proveedor), 'fecha': obj.fecha.strftime('%d/%m/%Y'), 'estado': obj.estado.upper(), 'total': float(obj.total), 'detalles': [{'producto': d.producto.nombre, 'cant': d.cantidad, 'precio': float(d.precio_costo), 'subtotal': float(d.cantidad * d.precio_costo)} for d in obj.detalles.all()]}
        elif doc_tipo == 'rec':
            obj = get_object_or_404(Recepcion, id=doc_id, empresa=empresa_actual)
            data = {'titulo': 'Detalle Recepción', 'folio': f"REC-{obj.id:04d}", 'oc_folio': f"OC-{obj.orden_compra.id:04d}" if obj.orden_compra else '-', 'proveedor': str(obj.orden_compra.proveedor) if obj.orden_compra else "Directo / Sin OC", 'almacen': str(obj.almacen), 'fecha': obj.fecha.strftime('%d/%m/%Y'), 'estado': obj.estado.upper(), 'factura': obj.factura or '-', 'total': float(obj.total), 'pedimento': obj.pedimento or '-', 'aduana': obj.aduana or '-', 'fecha_pedimento': obj.fecha_pedimento.strftime('%d/%m/%Y') if obj.fecha_pedimento else '-', 'detalles': [{'producto': d.producto.nombre, 'cant': d.cantidad_recibida, 'precio': float(d.costo_unitario), 'subtotal': float(d.cantidad_recibida * d.costo_unitario)} for d in obj.detalles.all()]}
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=404)

@login_required
@transaction.atomic
@require_inventory_permission('inventario', 'receta', json_response=True)
def guardar_receta(request):
    if request.method == 'POST':
        try:
            import json
            empresa_actual, data = get_empresa_actual(request), json.loads(request.body.decode('utf-8'))
            producto = get_object_or_404(Producto, id=data.get('producto_id'), empresa=empresa_actual)
            if producto.tipo_abastecimiento != 'produccion': return JsonResponse({'success': False, 'error': 'Solo para productos de PRODUCCIÓN.'})
            DetalleReceta.objects.filter(producto_padre=producto).delete()
            if data.get('componentes'):
                for item in json.loads(data.get('componentes')):
                    if int(item.get('id')) == producto.id: continue
                    DetalleReceta.objects.create(producto_padre=producto, componente=get_object_or_404(Producto, id=item.get('id'), empresa=empresa_actual), cantidad=item.get('cant', 1))
            
            # Recalcular el costo base del producto padre a partir de la nueva receta
            producto.recalcular_costo_desde_receta()
            
            return JsonResponse({'success': True, 'message': 'Receta guardada correctamente.'})
        except Exception as e: return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
@transaction.atomic
@require_inventory_permission('inventario', 'recetas', json_response=True)
def ejecutar_produccion(request):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            producto, almacen = get_object_or_404(Producto, id=request.POST.get('producto_id'), empresa=empresa_actual), get_object_or_404(Almacen, id=request.POST.get('almacen_id'), empresa=empresa_actual)
            cant_prod, receta = int(request.POST.get('cantidad')), DetalleReceta.objects.filter(producto_padre=producto)
            if not receta.exists(): return JsonResponse({'success': False, 'error': 'Sin receta configurada.'})
            invs = {inv.producto_id: inv for inv in Inventario.objects.select_for_update().filter(producto_id__in=[r.componente_id for r in receta], almacen=almacen)}
            errs = [f"Falta {r.componente.nombre}" for r in receta if invs.get(r.componente_id, Inventario(cantidad=0)).cantidad < (r.cantidad * cant_prod)]
            if errs: return JsonResponse({'success': False, 'error': 'Stock insuficiente: ' + ', '.join(errs)})
            for r in receta:
                # Usamos el modelo Transacción para un log centralizado
                Transaccion.objects.create(
                    producto=r.componente,
                    almacen=almacen,
                    tipo='produccion',
                    cantidad=-(r.cantidad * cant_prod),
                    empresa=empresa_actual,
                    usuario=request.user,
                    referencia=f"PROD-MANUAL: {producto.nombre}",
                    estado='recibida'
                )

            # Usamos el modelo Transacción para la entrada del producto final
            Transaccion.objects.create(
                producto=producto,
                almacen=almacen,
                tipo='produccion',
                cantidad=cant_prod,
                total=Decimal(cant_prod) * Decimal(producto.precio_costo),
                empresa=empresa_actual,
                usuario=request.user,
                referencia=f"PROD-MANUAL: Ensamble",
                estado='recibida'
            )
            return JsonResponse({'success': True, 'message': f'Producción exitosa: {cant_prod} {producto.nombre}.'})
        except Exception as e: return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
@require_inventory_permission('inventario', 'recetas', json_response=True)
def obtener_receta(request, producto_id):
    try:
        empresa_actual = get_empresa_actual(request)
        get_object_or_404(Producto, id=producto_id, empresa=empresa_actual)
        receta_data = []
        for r in DetalleReceta.objects.filter(producto_padre_id=producto_id):
            imagen_url = r.componente.imagen.url if r.componente.imagen else None
            receta_data.append({
                'id': r.componente.id, 
                'nombre': r.componente.nombre, 
                'cant': r.cantidad, 
                'costo': float(r.componente.precio_costo),
                'iva': float(r.componente.iva),
                'tiene_iva': r.componente.tiene_iva,
                'imagen_url': imagen_url
            })
        return JsonResponse(receta_data, safe=False)
    except Exception as e: return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_inventory_permission('inventario', 'precios', json_response=True)
def actualizar_precio_producto(request, producto_id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            producto = get_object_or_404(Producto, id=producto_id, empresa=empresa_actual)
            
            nuevo_costo = request.POST.get('precio_costo')
            nueva_venta = request.POST.get('precio_venta')
            
            if nuevo_costo: producto.precio_costo = nuevo_costo
            if nueva_venta: producto.precio_venta = nueva_venta
            
            if request.POST.get('precios_extra'): 
                producto.precios_lista = json.loads(request.POST.get('precios_extra'))
            if request.POST.get('costos_extra'): 
                producto.costos_lista = json.loads(request.POST.get('costos_extra'))
                
            producto.save()
            return JsonResponse({'success': True, 'message': 'Datos actualizados.'})
        except Exception as e: return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

from decimal import Decimal
from core.models import ModificadorProducto

@login_required
@require_inventory_permission('inventario', 'ver', json_response=True)
def obtener_modificadores_json(request, producto_id):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return JsonResponse({'success': False, 'error': 'Empresa no encontrada.'})
    
    producto = get_object_or_404(Producto, id=producto_id, empresa=empresa_actual)
    
    # Modificadores ya configurados
    modificadores = ModificadorProducto.objects.filter(producto_padre=producto).select_related('producto_modificador')
    mods_list = []
    for m in modificadores:
        mods_list.append({
            'id': m.id,
            'producto_modificador_id': m.producto_modificador.id,
            'nombre': m.producto_modificador.nombre,
            'permite_extra': m.permite_extra,
            'permite_sin': m.permite_sin,
            'precio_extra': float(m.precio_extra),
            'cantidad_modificadora': float(m.cantidad_modificadora)
        })
        
    # Todos los productos disponibles para ser modificadores (activos de la misma empresa)
    productos_disponibles = Producto.objects.filter(empresa=empresa_actual, estado='activo').exclude(id=producto.id).order_by('nombre')
    prods_list = [{'id': p.id, 'nombre': p.nombre} for p in productos_disponibles]
    
    return JsonResponse({
        'success': True,
        'modificadores': mods_list,
        'productos_disponibles': prods_list
    })

@login_required
@require_inventory_permission('inventario', 'editar', json_response=True)
def guardar_modificador_ajax(request):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            if not empresa_actual:
                return JsonResponse({'success': False, 'error': 'Empresa no encontrada.'})
                
            producto_padre_id = request.POST.get('producto_padre_id')
            producto_modificador_id = request.POST.get('producto_modificador_id')
            
            permite_extra = request.POST.get('permite_extra') == 'true'
            permite_sin = request.POST.get('permite_sin') == 'true'
            precio_extra = Decimal(request.POST.get('precio_extra', '0.00'))
            cantidad_modificadora = Decimal(request.POST.get('cantidad_modificadora', '1.0000'))
            
            producto_padre = get_object_or_404(Producto, id=producto_padre_id, empresa=empresa_actual)
            producto_modificador = get_object_or_404(Producto, id=producto_modificador_id, empresa=empresa_actual)
            
            modificador_id = request.POST.get('modificador_id')
            if modificador_id:
                modificador = get_object_or_404(ModificadorProducto, id=modificador_id, empresa=empresa_actual)
                modificador.producto_modificador = producto_modificador
                modificador.permite_extra = permite_extra
                modificador.permite_sin = permite_sin
                modificador.precio_extra = precio_extra
                modificador.cantidad_modificadora = cantidad_modificadora
                modificador.save()
            else:
                modificador, created = ModificadorProducto.objects.get_or_create(
                    empresa=empresa_actual,
                    producto_padre=producto_padre,
                    producto_modificador=producto_modificador,
                    defaults={
                        'permite_extra': permite_extra,
                        'permite_sin': permite_sin,
                        'precio_extra': precio_extra,
                        'cantidad_modificadora': cantidad_modificadora
                    }
                )
                if not created:
                    modificador.permite_extra = permite_extra
                    modificador.permite_sin = permite_sin
                    modificador.precio_extra = precio_extra
                    modificador.cantidad_modificadora = cantidad_modificadora
                    modificador.save()
                
            return JsonResponse({'success': True, 'message': 'Modificador guardado exitosamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
@require_inventory_permission('inventario', 'editar', json_response=True)
def eliminar_modificador_ajax(request, modificador_id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            if not empresa_actual:
                return JsonResponse({'success': False, 'error': 'Empresa no encontrada.'})
                
            modificador = get_object_or_404(ModificadorProducto, id=modificador_id, empresa=empresa_actual)
            modificador.delete()
            return JsonResponse({'success': True, 'message': 'Modificador eliminado exitosamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})


# --- CONVERSIONES DE UNIDAD (PRESENTACIONES MÚLTIPLES) ---
from core.models import ConversionUnidad

@login_required
def api_listar_conversiones(request, producto_id):
    try:
        empresa_actual = get_empresa_actual(request)
        if not empresa_actual:
            return JsonResponse({'success': False, 'error': 'Empresa no encontrada.'})
        
        producto = get_object_or_404(Producto, id=producto_id, empresa=empresa_actual)
        
        # Calcular stock base total disponible
        from almacenes.models import Inventario
        invs = Inventario.objects.filter(producto=producto)
        stock_total = sum((inv.cantidad - inv.reservado) for inv in invs) if invs.exists() else 0
        
        conversiones = ConversionUnidad.objects.filter(producto=producto).order_by('id')
        conversiones_list = []
        
        for c in conversiones:
            stock_en_presentacion = 0
            stock_texto = "0"
            sat_display = dict(Producto.UNIDAD_OPCIONES).get(c.unidad_destino, c.unidad_destino)
            nombre_amigable = getattr(c, 'unidad_destino_nombre', sat_display)

            if c.factor_equivalencia > 0:
                stock_en_presentacion = round(float(stock_total) / float(c.factor_equivalencia), 2)
                cajas_enteras = int(stock_total // c.factor_equivalencia)
                sobrante = float(stock_total % c.factor_equivalencia)
                unidad_nombre = producto.get_unidad_medida_display() or producto.unidad_medida
                if sobrante > 0:
                    stock_texto = f"{stock_en_presentacion} ({cajas_enteras} compl. + {sobrante:g} {unidad_nombre})"
                else:
                    stock_texto = f"{cajas_enteras} compl."

            conversiones_list.append({
                'id': c.id,
                'unidad_destino': c.unidad_destino,
                'unidad_destino_display': sat_display,
                'unidad_destino_nombre': nombre_amigable,
                'factor_equivalencia': float(c.factor_equivalencia),
                'precio_venta': float(c.precio_venta) if c.precio_venta is not None else float(c.precio_efectivo),
                'precio_venta_raw': float(c.precio_venta) if c.precio_venta is not None else None,
                'codigo_barras': c.codigo_barras or '',
                'activo': c.activo,
                'stock_calculado': stock_en_presentacion,
                'stock_texto': stock_texto
            })
            
        u_disp = producto.get_unidad_medida_display() or producto.unidad_medida
        m_u = re.search(r'\((.*?)\)', u_disp) if u_disp else None
        u_nom = m_u.group(1) if m_u else u_disp

        return JsonResponse({
            'success': True,
            'producto': {
                'id': producto.id,
                'nombre': producto.nombre,
                'clave': producto.clave or '',
                'unidad_medida': u_nom or 'Pieza',
                'unidad_medida_full': u_disp or 'Pieza',
                'unidad_medida_code': producto.unidad_medida,
                'precio_costo': float(producto.precio_costo or 0),
                'precio_venta': float(producto.precio_venta or 0),
                'stock_total': float(stock_total)
            },
            'unidades_sat': [
                {'codigo': code, 'nombre': label} for code, label in Producto.UNIDAD_OPCIONES
            ],
            'conversiones': conversiones_list
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@require_inventory_permission('inventario', 'editar', json_response=True)
def api_guardar_conversion(request):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            if not empresa_actual:
                return JsonResponse({'success': False, 'error': 'Empresa no encontrada.'})
                
            producto_id = request.POST.get('producto_id')
            conversion_id = request.POST.get('conversion_id')
            unidad_destino = request.POST.get('unidad_destino', '').strip()
            factor_equivalencia = request.POST.get('factor_equivalencia')
            precio_venta = request.POST.get('precio_venta', '').strip()
            codigo_barras = request.POST.get('codigo_barras', '').strip() or None
            
            if not unidad_destino:
                return JsonResponse({'success': False, 'error': 'Debes seleccionar una unidad de medida SAT del listado desplegable.'})
                
            producto = get_object_or_404(Producto, id=producto_id, empresa=empresa_actual)

            # Evitar error: seleccionar la misma unidad base del artículo
            if unidad_destino == producto.unidad_medida:
                return JsonResponse({
                    'success': False, 
                    'error': f'La presentación no puede ser la misma unidad base ({producto.get_unidad_medida_display()}) del artículo.'
                })
                
            try:
                factor_equivalencia = Decimal(factor_equivalencia)
                if factor_equivalencia <= 0:
                    raise ValueError()
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'error': 'El factor de equivalencia debe ser un número mayor a 0.'})
                
            precio_decimal = None
            if precio_venta:
                try:
                    precio_decimal = Decimal(precio_venta)
                    if precio_decimal < 0:
                        raise ValueError()
                except (ValueError, TypeError):
                    return JsonResponse({'success': False, 'error': 'El precio de venta debe ser un número válido mayor o igual a 0.'})
            
            nombre_unidad_sat = dict(Producto.UNIDAD_OPCIONES).get(unidad_destino, unidad_destino)
            
            if conversion_id:
                conversion = get_object_or_404(ConversionUnidad, id=conversion_id, producto=producto, empresa=empresa_actual)
                dupe = ConversionUnidad.objects.filter(producto=producto, unidad_destino__iexact=unidad_destino).exclude(id=conversion_id).first()
                if dupe:
                    return JsonResponse({'success': False, 'error': f'Ya existe una presentación con la unidad "{nombre_unidad_sat}" para este artículo.'})
                conversion.unidad_destino = unidad_destino
                conversion.factor_equivalencia = factor_equivalencia
                conversion.precio_venta = precio_decimal
                conversion.codigo_barras = codigo_barras
                conversion.save()
            else:
                dupe = ConversionUnidad.objects.filter(producto=producto, unidad_destino__iexact=unidad_destino).first()
                if dupe:
                    return JsonResponse({'success': False, 'error': f'Ya existe una presentación con la unidad "{nombre_unidad_sat}" para este artículo.'})
                ConversionUnidad.objects.create(
                    empresa=empresa_actual,
                    producto=producto,
                    unidad_destino=unidad_destino,
                    factor_equivalencia=factor_equivalencia,
                    precio_venta=precio_decimal,
                    codigo_barras=codigo_barras
                )
                
            return JsonResponse({'success': True, 'message': 'Conversión guardada exitosamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
@require_inventory_permission('inventario', 'editar', json_response=True)
def api_eliminar_conversion(request, conversion_id):
    if request.method == 'POST':
        try:
            empresa_actual = get_empresa_actual(request)
            if not empresa_actual:
                return JsonResponse({'success': False, 'error': 'Empresa no encontrada.'})
                
            conversion = get_object_or_404(ConversionUnidad, id=conversion_id, empresa=empresa_actual)
            conversion.delete()
            return JsonResponse({'success': True, 'message': 'Conversión eliminada exitosamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

@login_required
@require_inventory_permission('inventario', 'ver', json_response=True)
def api_articulos_stock_minimo(request):
    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return JsonResponse({'success': False, 'articulos': [], 'error': 'Empresa no encontrada.'})

    sucursal_id = request.GET.get('sucursal')
    almacen_id = request.GET.get('almacen')
    estado_riesgo = request.GET.get('riesgo', 'todos')
    tipo_abast = request.GET.get('tipo_abastecimiento', 'todos')
    categoria_id = request.GET.get('categoria', '')

    def get_stock_min_sub(field):
        qs_sub = Inventario.objects.filter(producto=OuterRef('pk'))
        if sucursal_id:
            qs_sub = qs_sub.filter(almacen__sucursal_id=sucursal_id)
        if almacen_id:
            qs_sub = qs_sub.filter(almacen_id=almacen_id)
        return qs_sub.values('producto').annotate(total=Sum(field)).values('total')[:1]

    qs = Producto.objects.filter(
        empresa=empresa_actual,
        stock_minimo__gt=0,
        estado='activo'
    ).annotate(
        stock_fisico_calc=Coalesce(Subquery(get_stock_min_sub('cantidad')), 0),
        stock_res_calc=Coalesce(Subquery(get_stock_min_sub('reservado')), 0)
    ).annotate(
        stock_disp_calc=ExpressionWrapper(
            F('stock_fisico_calc') - F('stock_res_calc'),
            output_field=IntegerField()
        ),
        diferencia_minimo=ExpressionWrapper(
            F('stock_minimo') - (F('stock_fisico_calc') - F('stock_res_calc')),
            output_field=IntegerField()
        )
    ).annotate(
        nivel_riesgo=Case(
            When(stock_disp_calc__lte=0, then=Value('agotado')),
            When(stock_disp_calc__lt=F('stock_minimo'), then=Value('bajo')),
            When(stock_disp_calc=F('stock_minimo'), then=Value('minimo')),
            default=Value('proximo'),
            output_field=CharField()
        )
    )

    if tipo_abast and tipo_abast != 'todos':
        qs = qs.filter(tipo_abastecimiento=tipo_abast)

    if categoria_id and categoria_id != 'todas' and categoria_id != '':
        qs = qs.filter(categoria=categoria_id)

    if estado_riesgo == 'agotado':
        qs = qs.filter(stock_disp_calc__lte=0)
    elif estado_riesgo == 'bajo':
        qs = qs.filter(stock_disp_calc__gt=0, stock_disp_calc__lt=F('stock_minimo'))
    elif estado_riesgo == 'minimo':
        qs = qs.filter(stock_disp_calc=F('stock_minimo'))
    elif estado_riesgo == 'proximo':
        qs = qs.filter(stock_disp_calc__gt=F('stock_minimo'), stock_disp_calc__lte=ExpressionWrapper(F('stock_minimo') * 1.25, output_field=IntegerField()))
    else:
        qs = qs.filter(stock_disp_calc__lte=ExpressionWrapper(F('stock_minimo') * 1.25, output_field=IntegerField()))

    qs = qs.prefetch_related('conversiones').order_by('-diferencia_minimo', 'nombre')

    items = []
    for p in qs:
        # Default de cantidad a solicitar: Stock máximo configurado en el artículo
        if p.stock_maximo and p.stock_maximo > 0:
            cant_default = p.stock_maximo
        elif p.diferencia_minimo and p.diferencia_minimo > 0:
            cant_default = p.diferencia_minimo
        else:
            cant_default = p.stock_minimo or 1

        unidad_disp = dict(Producto.UNIDAD_OPCIONES).get(p.unidad_medida, p.unidad_medida or 'Pieza')
        m_u = re.search(r'\((.*?)\)', unidad_disp)
        unidad_nombre = m_u.group(1).strip() if m_u else unidad_disp.strip()

        # Conversiones de unidad configuradas para el artículo
        convs_list = []
        for c in p.conversiones.all():
            if not c.activo:
                continue
            sat_display = dict(Producto.UNIDAD_OPCIONES).get(c.unidad_destino, c.unidad_destino)
            nombre_amigable = getattr(c, 'unidad_destino_nombre', sat_display)
            m_c = re.search(r'\((.*?)\)', nombre_amigable)
            nombre_limpio = m_c.group(1).strip() if m_c else nombre_amigable.strip()
            convs_list.append({
                'id': c.id,
                'unidad_destino': c.unidad_destino,
                'unidad_destino_display': sat_display,
                'unidad_destino_nombre': nombre_limpio,
                'factor_equivalencia': float(c.factor_equivalencia),
            })

        items.append({
            'id': p.id,
            'clave': p.clave or '',
            'nombre': p.nombre,
            'categoria': p.categoria or 'Sin categoría',
            'tipo_abastecimiento': p.tipo_abastecimiento or 'compra',
            'tipo_abastecimiento_display': p.get_tipo_abastecimiento_display() if hasattr(p, 'get_tipo_abastecimiento_display') else (p.tipo_abastecimiento or 'Compra'),
            'unidad_medida': p.unidad_medida or 'H87',
            'unidad_medida_display': unidad_disp,
            'unidad_medida_nombre': unidad_nombre,
            'conversiones': convs_list,
            'stock_fisico': p.stock_fisico_calc,
            'stock_disponible': p.stock_disp_calc,
            'stock_minimo': p.stock_minimo,
            'stock_maximo': p.stock_maximo,
            'cantidad_default': cant_default,
            'precio_costo': float(p.precio_costo or 0),
            'nivel_riesgo': p.nivel_riesgo,
        })

    return JsonResponse({'success': True, 'articulos': items, 'total': len(items)})

@login_required
@require_inventory_permission('inventario', 'crear', json_response=True)
@transaction.atomic
def api_crear_solicitud_stock_minimo(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido.'})

    empresa_actual = get_empresa_actual(request)
    if not empresa_actual:
        return JsonResponse({'success': False, 'error': 'Empresa no detectada.'})

    import json
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST

    items_data = data.get('items', [])
    if isinstance(items_data, str):
        try:
            items_data = json.loads(items_data)
        except Exception:
            items_data = []

    if not items_data:
        return JsonResponse({'success': False, 'error': 'No se seleccionó ningún artículo para solicitar.'})

    almacen_id = data.get('almacen_id')
    sucursal_id = data.get('sucursal_id')
    notas = (data.get('notas') or '').strip()
    if not notas:
        notas = "Solicitud generada automáticamente desde Inventario por Stock Mínimo."

    almacen_obj = None
    if almacen_id:
        almacen_obj = Almacen.objects.filter(id=almacen_id, empresa=empresa_actual).first()
    if not almacen_obj:
        almacen_obj = Almacen.objects.filter(empresa=empresa_actual).first()

    sucursal_obj = None
    if sucursal_id:
        from preferencias.models import Sucursal
        sucursal_obj = Sucursal.objects.filter(id=sucursal_id, empresa=empresa_actual).first()
    elif almacen_obj and almacen_obj.sucursal:
        sucursal_obj = almacen_obj.sucursal

    from solicitudcompras.models import SolicitudCompra, DetalleSolicitudCompra

    # 1. Crear UNA SOLA solicitud de compra para todos los materiales
    solicitud = SolicitudCompra.objects.create(
        solicitante=request.user,
        empresa=empresa_actual,
        sucursal=sucursal_obj,
        estado='borrador',
        notas=notas,
        aplica_iva=True
    )

    creados = 0
    for it in items_data:
        prod_id = it.get('producto_id') or it.get('id')
        try:
            cant = int(float(it.get('cantidad', 0)))
        except (ValueError, TypeError):
            cant = 0

        if not prod_id or cant <= 0:
            continue

        prod = Producto.objects.filter(id=prod_id, empresa=empresa_actual).first()
        if not prod:
            continue

        item_alm_id = it.get('almacen_id') or (almacen_obj.id if almacen_obj else None)

        u_compra = it.get('unidad_compra')
        try:
            f_conv = Decimal(str(it.get('factor_conversion', '1.0000')))
        except Exception:
            f_conv = Decimal('1.0000')

        if not u_compra or u_compra == 'BASE':
            u_compra = prod.unidad_medida
            f_conv = Decimal('1.0000')

        costo_base = prod.precio_costo or Decimal('0.00')
        costo_unitario = costo_base * f_conv
        cant_inventario = Decimal(str(cant)) * f_conv

        from preferencias.models import Moneda
        moneda_sol_default = Moneda.objects.filter(empresa=empresa_actual, siglas='MXN').first() or Moneda.objects.filter(empresa=empresa_actual).first()

        DetalleSolicitudCompra.objects.create(
            solicitud=solicitud,
            producto=prod,
            cantidad_solicitada=cant,
            costo_unitario=costo_unitario,
            almacen_id=item_alm_id,
            moneda=moneda_sol_default,
            unidad_compra=u_compra,
            factor_conversion=f_conv,
            cantidad_inventario=cant_inventario
        )
        creados += 1

    if creados == 0:
        solicitud.delete()
        return JsonResponse({'success': False, 'error': 'No se pudo crear ninguna partida válida para la solicitud.'})

    return JsonResponse({
        'success': True,
        'solicitud_id': solicitud.id,
        'partidas_creadas': creados,
        'mensaje': f'Se ha generado con éxito la Solicitud de Compra #{solicitud.id} con {creados} materiales.',
        'url_solicitudes': '/solicitudes-compras/'
    })

