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
    document.getElementById('item_indice_edicion').value = '-1';
    document.getElementById('tituloModalSolicitud').innerText = 'Nueva Solicitud de Compra';
    document.getElementById('cuerpoTablaSolicitud').innerHTML = '';
    document.getElementById('mensajeVacioSolicitud').style.display = 'block';
    
    // Resetear totales
    document.getElementById('solicitudSubtotal').innerText = '$0.00';
    document.getElementById('solicitudIvaTotal').innerText = '$0.00';
    document.getElementById('granTotalSolicitud').innerText = '$0.00';
    
    // Resetear botón de agregar
    const btn = document.getElementById('btnAddItem');
    if (btn) {
        btn.innerHTML = '<i class="bi bi-plus-lg"></i>';
        btn.classList.remove('btn-success');
        btn.classList.add('btn-brand');
    }

    // Ocultar sección de datos de pedido
    document.getElementById('seccion_datos_pedido').style.display = 'none';
    
    // Resetear sucursales general
    const genSuc = document.getElementById('gen_sucursal');
    genSuc.innerHTML = '<option value="">Seleccione proveedor primero...</option>';
    genSuc.disabled = true;
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

// --- AGREGAR / ACTUALIZAR ARTÍCULO ---
function agregarArticuloManual() {
    const selectP = document.getElementById('add_producto');
    const prodId = selectP.value;
    const prodNombre = selectP.options[selectP.selectedIndex].text;
    const ivaPorc = parseFloat(selectP.options[selectP.selectedIndex].getAttribute('data-iva')) || 0;
    
    const listaId = document.getElementById('add_lista').value;
    const listaNombre = document.getElementById('add_lista').options[document.getElementById('add_lista').selectedIndex].text;
    const cantidad = parseFloat(document.getElementById('add_cantidad').value) || 0;
    const costo = parseFloat(document.getElementById('add_costo').value) || 0;

    if (!prodId || cantidad <= 0) {
        alert("Selecciona un producto y cantidad válida.");
        return;
    }

    // Cálculos
    const subtotal = cantidad * costo;
    const ivaMonto = subtotal * (ivaPorc / 100);
    const total = subtotal + ivaMonto;

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
        subtotal: subtotal,
        iva_porcentaje: ivaPorc,
        iva_monto: ivaMonto,
        total: total,
        moneda_id: monId,
        moneda_siglas: monSiglas,
        lista_id: listaId,
        lista_nombre: listaNombre,
        detalle_pedido_origen_id: document.getElementById('edit_item_pedido_det_id').value
    };

    const indiceEdicion = parseInt(document.getElementById('item_indice_edicion').value);

    if (indiceEdicion >= 0) {
        const tbody = document.getElementById('cuerpoTablaSolicitud');
        const row = tbody.rows[indiceEdicion];
        if (row) {
            actualizarFilaHtml(row, datos);
        }
        document.getElementById('item_indice_edicion').value = '-1';
        document.getElementById('edit_item_pedido_det_id').value = '';
        const btn = document.getElementById('btnAddItem');
        btn.innerHTML = '<i class="bi bi-plus-lg"></i>';
        btn.classList.replace('btn-success', 'btn-brand');
    } else {
        agregarFilaProducto(datos);
    }

    document.getElementById('add_producto').value = '';
    document.getElementById('add_lista').value = '';
    document.getElementById('add_cantidad').value = 1;
    document.getElementById('add_costo').value = '0.00';
    calcularTotalSolicitud();
}

// --- MANEJO DE FILAS DINÁMICAS ---
function agregarFilaProducto(datos) {
    const tbody = document.getElementById('cuerpoTablaSolicitud');
    document.getElementById('mensajeVacioSolicitud').style.display = 'none';
    
    const row = document.createElement('tr');
    row.style.fontSize = '0.85rem';
    
    actualizarFilaHtml(row, datos);
    tbody.appendChild(row);
}

function actualizarFilaHtml(row, datos) {
    row.innerHTML = `
        <td class="ps-3">
            <div class="fw-bold text-dark text-truncate" style="max-width: 200px;">${datos.producto_nombre}</div>
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
            <div class="small text-truncate" style="max-width: 150px;">${datos.proveedor_nombre}</div>
            <input type="hidden" name="proveedor_id[]" value="${datos.proveedor_id || ''}">
            <input type="hidden" name="sucursal_id[]" value="${datos.sucursal_id || ''}">
        </td>
        <td>
            <div class="small text-truncate" style="max-width: 120px;">${datos.almacen_nombre}</div>
            <input type="hidden" name="almacen_id[]" value="${datos.almacen_id || ''}">
        </td>
        <td class="text-center">
            <span class="small">${datos.cantidad}</span>
            <input type="hidden" name="cantidad[]" value="${datos.cantidad}">
        </td>
        <td class="text-end">
            <span class="small text-muted">$${parseFloat(datos.costo_unitario).toFixed(2)}</span>
            <input type="hidden" name="costo_unitario[]" value="${datos.costo_unitario}">
        </td>
        <td class="text-end">
            <span class="small text-dark">$${parseFloat(datos.subtotal).toFixed(2)}</span>
        </td>
        <td class="text-end">
            <span class="small text-muted">$${parseFloat(datos.iva_monto).toFixed(2)}</span>
            <input type="hidden" name="iva_porcentaje[]" value="${datos.iva_porcentaje}">
        </td>
        <td class="text-end pe-3">
            <span class="fw-bold small text-dark">$${parseFloat(datos.total).toFixed(2)}</span>
        </td>
        <td class="text-center">
            <div class="d-flex justify-content-center gap-1">
                <button type="button" class="icon-action" onclick="cargarItemParaEdicion(this)" title="Editar Partida">
                    <i class="bi bi-pencil-square"></i>
                </button>
                <button type="button" class="icon-action icon-action-danger" onclick="eliminarFila(this)" title="Eliminar">
                    <i class="bi bi-x-circle"></i>
                </button>
            </div>
        </td>
    `;
}

function calcularTotalSolicitud() {
    let subtotalTotal = 0;
    let ivaTotal = 0;
    let granTotal = 0;

    document.querySelectorAll('#cuerpoTablaSolicitud tr').forEach(fila => {
        const sub = parseFloat(fila.cells[7].innerText.replace('$', '').replace(',', '')) || 0;
        const iva = parseFloat(fila.cells[8].innerText.replace('$', '').replace(',', '')) || 0;
        const tot = parseFloat(fila.cells[9].innerText.replace('$', '').replace(',', '')) || 0;
        
        subtotalTotal += sub;
        ivaTotal += iva;
        granTotal += tot;
    });

    document.getElementById('solicitudSubtotal').innerText = '$' + subtotalTotal.toLocaleString('en-US', {minimumFractionDigits: 2});
    document.getElementById('solicitudIvaTotal').innerText = '$' + ivaTotal.toLocaleString('en-US', {minimumFractionDigits: 2});
    document.getElementById('granTotalSolicitud').innerText = '$' + granTotal.toLocaleString('en-US', {minimumFractionDigits: 2});
}

function cargarItemParaEdicion(btn) {
    const row = btn.closest('tr');
    const index = row.rowIndex - 1; 
    
    const prodId = row.querySelector('[name="producto_id[]"]').value;
    const pedDetId = row.querySelector('[name="pedido_det_id[]"]')?.value || '';
    const listaId = row.querySelector('[name="lista_id[]"]').value;
    const monId = row.querySelector('[name="moneda_id[]"]').value;
    const provId = row.querySelector('[name="proveedor_id[]"]').value;
    const sucId = row.querySelector('[name="sucursal_id[]"]').value;
    const almId = row.querySelector('[name="almacen_id[]"]').value;
    const cant = row.querySelector('[name="cantidad[]"]').value;
    const costo = row.querySelector('[name="costo_unitario[]"]').value;

    document.getElementById('add_producto').value = prodId;
    document.getElementById('add_lista').value = listaId;
    document.getElementById('add_cantidad').value = cant;
    document.getElementById('add_costo').value = costo;
    document.getElementById('edit_item_pedido_det_id').value = pedDetId;
    
    document.getElementById('gen_proveedor').value = provId;
    document.getElementById('gen_almacen').value = almId;
    document.getElementById('gen_moneda').value = monId;
    
    cargarSucursalesProveedor(provId, 'gen_sucursal', sucId);

    document.getElementById('item_indice_edicion').value = index;
    const btnAdd = document.getElementById('btnAddItem');
    btnAdd.innerHTML = '<i class="bi bi-check-lg"></i>';
    
    document.querySelector('.modal-body').scrollTop = 0;
}

// --- LÓGICA: APLICAR TODO ---
function toggleAplicarTodo() {
    const isChecked = document.getElementById('switchAplicarTodo').checked;
    if (isChecked) {
        sincronizarSiAplicarTodo('proveedor');
        sincronizarSiAplicarTodo('sucursal');
        sincronizarSiAplicarTodo('almacen');
        sincronizarSiAplicarTodo('moneda');
    }
}

function sincronizarSiAplicarTodo(campo) {
    const isChecked = document.getElementById('switchAplicarTodo').checked;
    if (!isChecked) return;

    const tbody = document.getElementById('cuerpoTablaSolicitud');
    const rows = tbody.rows;

    let newValue = "";
    let newText = "";

    switch(campo) {
        case 'proveedor':
            const selProv = document.getElementById('gen_proveedor');
            newValue = selProv.value;
            newText = newValue ? selProv.options[selProv.selectedIndex].text : 'No asignado';
            for (let i = 0; i < rows.length; i++) {
                rows[i].querySelector('[name="proveedor_id[]"]').value = newValue;
                rows[i].cells[3].querySelector('div').innerText = newText;
            }
            break;
        case 'sucursal':
            const selSuc = document.getElementById('gen_sucursal');
            newValue = selSuc.value;
            newText = (newValue && !selSuc.disabled) ? selSuc.options[selSuc.selectedIndex].text : (document.getElementById('gen_proveedor').value ? 'Matriz' : '--');
            for (let i = 0; i < rows.length; i++) {
                rows[i].querySelector('[name="sucursal_id[]"]').value = newValue;
            }
            break;
        case 'almacen':
            const selAlm = document.getElementById('gen_almacen');
            newValue = selAlm.value;
            newText = newValue ? selAlm.options[selAlm.selectedIndex].text : 'No asignado';
            for (let i = 0; i < rows.length; i++) {
                rows[i].querySelector('[name="almacen_id[]"]').value = newValue;
                rows[i].cells[4].querySelector('div').innerText = newText;
            }
            break;
        case 'moneda':
            const selMon = document.getElementById('gen_moneda');
            newValue = selMon.value;
            newText = selMon.options[selMon.selectedIndex].text;
            for (let i = 0; i < rows.length; i++) {
                rows[i].querySelector('[name="moneda_id[]"]').value = newValue;
                rows[i].cells[2].querySelector('.badge').innerText = newText;
            }
            break;
    }
}

function eliminarFila(btn) {
    const row = btn.closest('tr');
    row.remove();
    if (document.getElementById('cuerpoTablaSolicitud').children.length === 0) {
        document.getElementById('mensajeVacioSolicitud').style.display = 'block';
    }
    calcularTotalSolicitud();
}

function actualizarCostoDefault(select) {
    const option = select.options[select.selectedIndex];
    const precio = option.getAttribute('data-precio') || '0.00';
    document.getElementById('add_costo').value = precio;
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
        
        const elPed = document.getElementById('ver_pedido_origen');
        if (data.pedido_origen) {
            elPed.innerHTML = `<a href="javascript:void(0)" onclick="verPedido(${data.pedido_origen.id})" class="text-brand fw-bold text-decoration-none">
                                    <i class="bi bi-link-45deg me-1"></i>PED-${String(data.pedido_origen.id).padStart(4, '0')}
                               </a>`;
        } else {
            elPed.innerText = 'Manual';
        }

        const tbody = document.getElementById('cuerpoVerSolicitud');
        tbody.innerHTML = '';

        if (data.grupos && data.grupos.length > 0) {
            data.grupos.forEach(grupo => {
                // Fila de Encabezado de Grupo (Estilo Árbol)
                const isDirect = grupo.nombre === "Compras Directas / Reabastecimiento";
                const trGrupo = document.createElement('tr');
                trGrupo.style.backgroundColor = '#f8f9fa';
                trGrupo.innerHTML = `
                    <td colspan="9" class="ps-3 py-2">
                        <div class="d-flex align-items-center">
                            <i class="bi ${isDirect ? 'bi-cart-fill' : 'bi-gear-wide-connected'} me-2 text-brand" style="font-size: 1rem;"></i>
                            <span class="fw-bold text-dark uppercase" style="font-size: 0.75rem; letter-spacing: 0.5px;">
                                ${grupo.nombre}
                            </span>
                        </div>
                    </td>
                `;
                tbody.appendChild(trGrupo);

                // Filas de Items del Grupo
                grupo.items.forEach(d => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td class="ps-5">
                            <div class="d-flex align-items-center">
                                <i class="bi bi-arrow-return-right text-muted me-2"></i>
                                <span class="text-dark small">${d.producto_nombre}</span>
                            </div>
                        </td>
                        <td class="text-center small">${d.cantidad}</td>
                        <td class="small text-muted text-truncate" style="max-width: 150px;">${d.proveedor_nombre}</td>
                        <td class="small text-muted text-truncate" style="max-width: 120px;">${d.almacen_nombre}</td>
                        <td class="text-end small">$${parseFloat(d.costo_unitario).toLocaleString('en-US', {minimumFractionDigits:2})}</td>
                        <td class="text-center small text-muted">${d.tipo_cambio}</td>
                        <td class="text-end small text-dark">$${parseFloat(d.subtotal).toLocaleString('en-US', {minimumFractionDigits:2})}</td>
                        <td class="text-end small text-muted">$${parseFloat(d.iva_monto).toLocaleString('en-US', {minimumFractionDigits:2})}</td>
                        <td class="text-end pe-3 fw-bold small text-dark">$${parseFloat(d.total).toLocaleString('en-US', {minimumFractionDigits:2})}</td>
                    `;
                    tbody.appendChild(tr);
                });
            });
        } else {
            tbody.innerHTML = '<tr><td colspan="9" class="text-center py-3 text-muted fst-italic">No hay artículos en esta solicitud.</td></tr>';
        }

        document.getElementById('ver_solicitud_subtotal').innerText = `$${parseFloat(data.subtotal_total || 0).toLocaleString('en-US', {minimumFractionDigits:2})}`;
        document.getElementById('ver_solicitud_iva_total').innerText = `$${parseFloat(data.iva_total || 0).toLocaleString('en-US', {minimumFractionDigits:2})}`;
        document.getElementById('ver_total_solicitud').innerText = `$${parseFloat(data.gran_total || 0).toLocaleString('en-US', {minimumFractionDigits:2})}`;
        
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

        prepararNuevaSolicitud(); 
        
        document.getElementById('solicitud_id_edit').value = id;
        document.getElementById('tituloModalSolicitud').innerText = `Editar Solicitud SOL-${String(id).padStart(4, '0')}`;
        document.getElementById('notas_solicitud').value = data.notas || '';
        
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

        data.detalles.forEach(d => {
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
                subtotal: d.subtotal,
                iva_porcentaje: d.iva_porcentaje,
                iva_monto: d.iva_monto,
                total: d.total,
                moneda_id: d.moneda_id,
                moneda_siglas: d.moneda_siglas,
                lista_id: d.lista_id,
                lista_nombre: lNombre,
                detalle_pedido_origen_id: d.detalle_pedido_origen_id
            });
        });
        
        calcularTotalSolicitud();

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
