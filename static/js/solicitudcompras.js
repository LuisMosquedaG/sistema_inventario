// SOLICITUDCOMPRAS.JS — Lógica para Gestión de Requisiciones

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const csrftoken = getCookie('csrftoken');

// --- INICIALIZACIÓN ---
function prepararNuevaSolicitud() {
    document.getElementById('formNuevaSolicitud').reset();
    document.getElementById('solicitud_id_edit').value = '';
    document.getElementById('tituloModalSolicitud').innerText = 'Nueva Solicitud de Compra';
    document.getElementById('cuerpoTablaSolicitud').innerHTML = '';
    document.getElementById('mensajeVacioSolicitud').style.display = 'block';
    
    // Ocultar sección de datos de pedido
    document.getElementById('seccion_datos_pedido').style.display = 'none';
    
    // Resetear sucursales general
    const genSuc = document.getElementById('gen_sucursal');
    genSuc.innerHTML = '<option value="">Seleccione proveedor primero...</option>';
    genSuc.disabled = true;

    // Resetear subcategorías del agregador (si hubiera, pero no hay aquí)
}

// --- LOGICA DE SUCURSALES ---
async function cargarSucursalesProveedor(proveedorId, targetSelectId, selectedSucursalId = null) {
    const select = document.getElementById(targetSelectId);
    if (!proveedorId) {
        select.innerHTML = '<option value="">Seleccione proveedor primero...</option>';
        select.disabled = true;
        return;
    }

    try {
        const response = await fetch(`/api/proveedores/${proveedorId}/`);
        const data = await response.json();
        
        select.innerHTML = '<option value="">Matriz / Única</option>';
        if (data.sucursales && data.sucursales.length > 0) {
            data.sucursales.forEach(s => {
                const sel = (selectedSucursalId == s.id) ? 'selected' : '';
                select.insertAdjacentHTML('beforeend', `<option value="${s.id}" ${sel}>${s.nombre}</option>`);
            });
        }
        select.disabled = false;
    } catch (error) {
        console.error("Error al cargar sucursales:", error);
    }
}

// --- AGREGAR ARTÍCULO MANUAL ---
function agregarArticuloManual() {
    const prodId = document.getElementById('add_producto').value;
    const prodNombre = document.getElementById('add_producto').options[document.getElementById('add_producto').selectedIndex].text;
    const listaId = document.getElementById('add_lista').value;
    const listaNombre = document.getElementById('add_lista').options[document.getElementById('add_lista').selectedIndex].text;
    const cantidad = document.getElementById('add_cantidad').value;
    const costo = document.getElementById('add_costo').value;

    if (!prodId) {
        alert("Selecciona un producto.");
        return;
    }

    // Obtener valores de Configuración General (Defaults)
    const provId = document.getElementById('gen_proveedor').value;
    const provNombre = provId ? document.getElementById('gen_proveedor').options[document.getElementById('gen_proveedor').selectedIndex].text : 'No asignado';
    
    const sucId = document.getElementById('gen_sucursal').value;
    const sucNombre = (sucId && !document.getElementById('gen_sucursal').disabled) ? 
                      document.getElementById('gen_sucursal').options[document.getElementById('gen_sucursal').selectedIndex].text : 
                      (provId ? 'Matriz' : '--');

    const almId = document.getElementById('gen_almacen').value;
    const almNombre = almId ? document.getElementById('gen_almacen').options[document.getElementById('gen_almacen').selectedIndex].text : 'No asignado';

    const monId = document.getElementById('gen_moneda').value;
    const monSiglas = document.getElementById('gen_moneda').options[document.getElementById('gen_moneda').selectedIndex].text;

    const datos = {
        producto_id: prodId,
        producto_nombre: prodNombre,
        cantidad: cantidad,
        proveedor_id: provId,
        proveedor_nombre: provNombre,
        sucursal_id: sucId,
        sucursal_nombre: sucNombre,
        almacen_id: almId,
        almacen_nombre: almNombre,
        costo_unitario: costo,
        moneda_id: monId,
        moneda_siglas: monSiglas,
        lista_id: listaId,
        lista_nombre: listaNombre
    };

    agregarFilaProducto(datos);

    // Limpiar agregador
    document.getElementById('add_producto').value = '';
    document.getElementById('add_lista').value = '';
    document.getElementById('add_cantidad').value = 1;
    document.getElementById('add_costo').value = '0.00';
}

// --- MANEJO DE FILAS DINÁMICAS ---
function agregarFilaProducto(datos) {
    const tbody = document.getElementById('cuerpoTablaSolicitud');
    document.getElementById('mensajeVacioSolicitud').style.display = 'none';
    
    const row = document.createElement('tr');
    row.style.fontSize = '0.85rem';

    row.innerHTML = `
        <td class="ps-3">
            <div class="fw-bold text-dark">${datos.producto_nombre}</div>
            <input type="hidden" name="producto_id[]" value="${datos.producto_id}">
            <input type="hidden" name="pedido_det_id[]" value="${datos.detalle_pedido_origen_id || ''}">
        </td>
        <td>
            <span class="text-muted small">${datos.lista_id ? datos.lista_nombre : 'Manual'}</span>
            <input type="hidden" name="lista_id[]" value="${datos.lista_id || ''}">
        </td>
        <td class="text-center">
            <span class="badge bg-light text-dark border">${datos.moneda_siglas}</span>
            <input type="hidden" name="moneda_id[]" value="${datos.moneda_id}">
        </td>
        <td>
            <div class="small">${datos.proveedor_nombre}</div>
            <input type="hidden" name="proveedor_id[]" value="${datos.proveedor_id || ''}">
        </td>
        <td>
            <div class="small text-muted">${datos.sucursal_nombre}</div>
            <input type="hidden" name="sucursal_id[]" value="${datos.sucursal_id || ''}">
        </td>
        <td>
            <div class="small">${datos.almacen_nombre}</div>
            <input type="hidden" name="almacen_id[]" value="${datos.almacen_id || ''}">
        </td>
        <td class="text-center fw-bold">
            ${datos.cantidad}
            <input type="hidden" name="cantidad[]" value="${datos.cantidad}">
        </td>
        <td class="text-end">
            $${parseFloat(datos.costo_unitario).toFixed(2)}
            <input type="hidden" name="costo_unitario[]" value="${datos.costo_unitario}">
        </td>
        <td class="text-center">
            <button type="button" class="btn btn-sm text-danger" onclick="eliminarFila(this)">
                <i class="bi bi-trash"></i>
            </button>
        </td>
    `;
    
    tbody.appendChild(row);
}

function eliminarFila(btn) {
    const row = btn.closest('tr');
    row.remove();
    if (document.getElementById('cuerpoTablaSolicitud').children.length === 0) {
        document.getElementById('mensajeVacioSolicitud').style.display = 'block';
    }
}

function actualizarCostoDefault(select) {
    const option = select.options[select.selectedIndex];
    const precio = option.getAttribute('data-precio') || '0.00';
    document.getElementById('add_costo').value = precio;
    // Resetear lista al cambiar producto
    document.getElementById('add_lista').value = '';
}

function aplicarListaCosto() {
    const selectProd = document.getElementById('add_producto');
    const selectLista = document.getElementById('add_lista');
    const inputCosto = document.getElementById('add_costo');

    if (!selectProd.value) return;

    const base = parseFloat(selectProd.options[selectProd.selectedIndex].getAttribute('data-precio')) || 0;
    const opt = selectLista.options[selectLista.selectedIndex];

    if (!selectLista.value) {
        inputCosto.value = base.toFixed(2);
        return;
    }

    const p = parseFloat(opt.getAttribute('data-porc')) || 0;
    const m = parseFloat(opt.getAttribute('data-monto')) || 0;

    let final = base;
    if (p !== 0) final = base + (base * (p / 100));
    else if (m !== 0) final = base + m;

    inputCosto.value = final.toFixed(2);
}

// --- GUARDAR ---
async function guardarSolicitud(event) {
    event.preventDefault();
    
    if (document.getElementById('cuerpoTablaSolicitud').children.length === 0) {
        alert("Debes agregar al menos un producto a la solicitud.");
        return;
    }

    const form = document.getElementById('formNuevaSolicitud');
    const id = document.getElementById('solicitud_id_edit').value;
    const url = id ? `/solicitudes-compras/actualizar/${id}/` : '/solicitudes-compras/crear-manual/';
    
    const formData = new FormData(form);
    const btn = document.getElementById('btnGuardarSolicitud');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Guardando...';
    
    try {
        const response = await fetch(url, {
            method: 'POST',
            body: formData,
            headers: { 'X-CSRFToken': csrftoken }
        });
        const result = await response.json();
        
        if (result.success) {
            location.reload();
        } else {
            alert("Error: " + result.error);
        }
    } catch (error) {
        console.error("Error:", error);
        alert("Ocurrió un error al guardar.");
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Guardar Solicitud';
    }
}

// --- VER / EDITAR ---
async function verSolicitud(id) {
    try {
        const response = await fetch(`/solicitudes-compras/api/solicitud/${id}/`);
        const data = await response.json();
        
        if (data.error) {
            alert(data.error);
            return;
        }

        document.getElementById('ver_folio_solicitud').innerText = `SOL-${String(id).padStart(4, '0')}`;
        document.getElementById('ver_estado_solicitud').innerText = data.estado_display;
        document.getElementById('ver_estado_solicitud').className = `status-pill status-${data.estado}`;
        document.getElementById('ver_solicitante_solicitud').innerText = data.solicitante_nombre;
        document.getElementById('ver_fecha_solicitud').innerText = data.fecha_creacion;
        document.getElementById('ver_notas_solicitud').innerText = data.notas || 'Sin notas.';
        document.getElementById('ver_pedido_origen').innerText = data.pedido_origen ? `PED-${String(data.pedido_origen.id).padStart(4, '0')}` : 'Manual';

        const tbody = document.getElementById('cuerpoVerSolicitud');
        tbody.innerHTML = '';
        let total = 0;

        data.detalles.forEach(d => {
            const subtotal = parseFloat(d.cantidad) * parseFloat(d.costo_unitario);
            total += subtotal;
            
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${d.producto_nombre}</td>
                <td class="text-center">${d.cantidad}</td>
                <td>${d.proveedor_nombre}</td>
                <td>${d.almacen_nombre}</td>
                <td class="text-end">$${parseFloat(d.costo_unitario).toLocaleString('en-US', {minimumFractionDigits:2})}</td>
                <td class="text-center">${d.moneda_siglas}</td>
                <td class="text-end fw-bold">$${subtotal.toLocaleString('en-US', {minimumFractionDigits:2})}</td>
            `;
            tbody.appendChild(tr);
        });

        document.getElementById('ver_total_solicitud').innerText = `$${total.toLocaleString('en-US', {minimumFractionDigits:2})}`;
        
        const modal = new bootstrap.Modal(document.getElementById('modalVerSolicitud'));
        modal.show();

    } catch (error) {
        console.error("Error:", error);
        alert("No se pudo cargar la información.");
    }
}

async function cargarParaEdicion(id) {
    try {
        const response = await fetch(`/solicitudes-compras/api/solicitud/${id}/`);
        const data = await response.json();
        
        if (data.error) {
            alert(data.error);
            return;
        }

        prepararNuevaSolicitud(); // Limpiar primero
        
        document.getElementById('solicitud_id_edit').value = id;
        document.getElementById('tituloModalSolicitud').innerText = `Editar Solicitud SOL-${String(id).padStart(4, '0')}`;
        document.getElementById('notas_solicitud').value = data.notas || '';
        
        // Manejar sección 0: Datos de Pedido
        const secPedido = document.getElementById('seccion_datos_pedido');
        if (data.pedido_origen) {
            secPedido.style.display = 'block';
            document.getElementById('edit_folio_cotizacion').innerText = data.pedido_origen.cotizacion_origen_id ? `COT-${String(data.pedido_origen.cotizacion_origen_id).padStart(4, '0')}` : '--';
            document.getElementById('edit_folio_pedido').innerText = `PED-${String(data.pedido_origen.id).padStart(4, '0')}`;
            document.getElementById('edit_cliente_pedido').innerText = data.pedido_origen.cliente.nombre_completo;
        } else {
            secPedido.style.display = 'none';
        }

        const tbody = document.getElementById('cuerpoTablaSolicitud');
        tbody.innerHTML = '';
        document.getElementById('mensajeVacioSolicitud').style.display = 'none';

        // Llenar tabla de artículos
        data.detalles.forEach(d => {
            // Buscamos el nombre de la lista si existe lista_id
            let lNombre = 'Manual';
            if (d.lista_id) {
                const lObj = listaCostos.find(lc => lc.id == d.lista_id);
                if (lObj) lNombre = lObj.nombre;
            }

            agregarFilaProducto({
                producto_id: d.producto_id,
                producto_nombre: d.producto_nombre,
                cantidad: d.cantidad,
                proveedor_id: d.proveedor_id,
                proveedor_nombre: d.proveedor_nombre,
                sucursal_id: d.sucursal_id,
                sucursal_nombre: d.sucursal_nombre || (d.proveedor_id ? 'Matriz' : '--'),
                almacen_id: d.almacen_id,
                almacen_nombre: d.almacen_nombre,
                costo_unitario: d.costo_unitario,
                moneda_id: d.moneda_id,
                moneda_siglas: d.moneda_siglas,
                lista_id: d.lista_id,
                lista_nombre: lNombre,
                detalle_pedido_origen_id: d.detalle_pedido_origen_id
            });
        });

        const modal = new bootstrap.Modal(document.getElementById('modalNuevaSolicitudManual'));
        modal.show();

    } catch (error) {
        console.error("Error:", error);
        alert("No se pudo cargar la solicitud para editar.");
    }
}


async function previsualizarAutorizacion(id) {
    if (!confirm(`¿Está seguro de autorizar la Solicitud SOL-${String(id).padStart(4, '0')}?\n\nSe generarán las órdenes de compra correspondientes agrupadas por proveedor.`)) {
        return;
    }

    try {
        const response = await fetch(`/solicitudes-compras/autorizar/${id}/`, {
            method: 'POST',
            headers: { 
                'X-CSRFToken': csrftoken,
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        const result = await response.json();
        
        if (result.success) {
            alert(result.message);
            location.reload();
        } else {
            alert("Error al autorizar: " + (result.error || result.message));
        }
    } catch (error) {
        console.error("Error:", error);
        alert("Ocurrió un error en el servidor.");
    }
}
