// --- FUNCIÓN AUXILIAR CSRF ---
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

// ---------------------------------------------------------
// 1. FUNCIÓN PRINCIPAL: Cargar Items (AJAX)
// ---------------------------------------------------------

function cargarItemsOrdenCompra() {
    const selectOC = document.getElementById('selectOrdenCompra');
    if (!selectOC) return;
    
    const ocId = selectOC.value;
    const tbody = document.getElementById('tablaCuerpoRecepcion');
    const mensaje = document.getElementById('mensajeVacioRecepcion');
    const selectAlmacen = document.getElementById('selectAlmacen');
    
    const dispMoneda = document.getElementById('dispMonedaOC');
    const dispTC = document.getElementById('dispTipoCambioOC');

    if (!tbody || !mensaje) return;

    tbody.innerHTML = '';
    
    if (!ocId) {
        mensaje.style.display = 'block';
        mensaje.innerText = "Seleccione una Orden de Compra para cargar los productos.";
        if(dispMoneda) dispMoneda.value = '-';
        if(dispTC) dispTC.value = '-';
        calcularTotalRecepcion();
        return;
    }

    const selectedOption = selectOC.options[selectOC.selectedIndex];
    const almacenId = selectedOption.getAttribute('data-almacen');
    if(almacenId && selectAlmacen) selectAlmacen.value = almacenId;

    mensaje.style.display = 'block';
    mensaje.innerText = "Consultando servidor...";

    fetch(`/recepciones/api/obtener-items-oc/${ocId}/`)
        .then(response => {
            if (!response.ok) throw new Error("Error en la conexión.");
            return response.json();
        })
        .then(data => {
            tbody.innerHTML = '';
            mensaje.style.display = 'none';

            if (dispMoneda) dispMoneda.value = data.moneda || 'MXN';
            if (dispTC) dispTC.value = data.tipo_cambio || '1.0000';

            const items = data.items || [];
            if (items.length === 0) {
                mensaje.innerText = "No hay artículos pendientes.";
                mensaje.style.display = 'block';
                return;
            }

            items.forEach(item => {
                const cant_faltante = item.cant_ordenada - item.cant_recibida_anterior;
                if (cant_faltante <= 0) return;

                let inputHtml = '';
                
                if (item.maneja_serie) {
                    inputHtml = `
                        <div class="serie-container">
                            <div id="lista-series-${item.id}" class="d-flex flex-column gap-1"></div>
                            <input type="hidden" name="cantidad_recibida[]" class="hidden-cant" id="hidden-cant-${item.id}" value="0">
                            <input type="hidden" name="extra_data_${item.id}" id="extra-data-${item.id}">
                        </div>
                    `;
                    setTimeout(() => { for(let i=0; i<cant_faltante; i++) agregarFilaSerie(item.id); }, 100);

                } else if (item.maneja_lote) {
                    inputHtml = `
                        <div class="lote-container">
                            <div id="lista-lotes-${item.id}" class="lote-serie-container"></div>
                            <input type="hidden" name="cantidad_recibida[]" class="hidden-cant" id="hidden-cant-${item.id}" value="0">
                            <input type="hidden" name="extra_data_${item.id}" id="extra-data-${item.id}">
                        </div>
                    `;
                    setTimeout(() => agregarFilaLote(item.id), 100);

                } else {
                    inputHtml = `
                        <input type="number" name="cantidad_recibida[]" 
                            class="form-control form-control-sm text-center input-cant-recibir" 
                            value="${cant_faltante}" 
                            min="0" max="${cant_faltante}" 
                            onchange="recalcularFila(this, ${item.costo})" oninput="recalcularFila(this, ${item.costo})">
                    `;
                }

                const subtotal = (cant_faltante * item.costo).toFixed(2);
                
                const filaHtml = `
                    <tr data-detalle-id="${item.id}" data-costo="${item.costo}" data-tipo="${item.maneja_serie ? 'serie' : (item.maneja_lote ? 'lote' : 'normal')}">
                        <td class="ps-3">
                            <div class="fw-semibold small text-dark">${item.nombre}</div>
                            <input type="hidden" name="detalle_compra_id[]" value="${item.id}">
                        </td>
                        <td class="text-center small">${item.cant_ordenada}</td>
                        <td class="text-center small text-muted">${item.cant_recibida_anterior}</td>
                        <td class="text-center">${inputHtml}</td>
                        <td class="text-end small text-muted">
                            $${parseFloat(item.costo).toFixed(2)}
                            <input type="hidden" name="costo_unitario[]" value="${item.costo}">
                        </td>
                        <td class="text-end fw-bold small text-dark row-subtotal">$${subtotal}</td>
                    </tr>
                `;
                tbody.insertAdjacentHTML('beforeend', filaHtml);
            });
            
            if (tbody.children.length === 0) {
                mensaje.innerText = "Orden ya recibida.";
                mensaje.style.display = 'block';
            }
            calcularTotalRecepcion();
        })
        .catch(error => {
            console.error('Error:', error);
            mensaje.innerText = "Error: " + error.message;
            mensaje.style.display = 'block';
        });
}

// --- SERIES ---
function agregarFilaSerie(id) {
    const container = document.getElementById(`lista-series-${id}`);
    if(!container) return;
    const div = document.createElement('div');
    div.className = 'item-row';
    div.innerHTML = `
        <div class="flex-grow-1"><input type="text" class="form-control form-control-sm input-serie" placeholder="Nº Serie" oninput="actualizarContadoresSeries(${id})"></div>
        <button class="btn btn-sm btn-add-custom" style="width:32px; height:32px;" type="button" onclick="agregarFilaSerie(${id})"><i class="bi bi-plus"></i></button>
        <button class="btn btn-sm btn-outline-danger" style="width:32px; height:32px;" type="button" onclick="this.closest('.item-row').remove(); actualizarContadoresSeries(${id});"><i class="bi bi-x-lg"></i></button>
    `;
    container.appendChild(div);
    actualizarContadoresSeries(id);
}

function actualizarContadoresSeries(id) {
    const inputs = document.querySelectorAll(`#lista-series-${id} .input-serie`);
    const h = document.getElementById(`hidden-cant-${id}`);
    if(h) h.value = inputs.length;
    const d = []; inputs.forEach(i => d.push({ tipo: 'serie', serie: i.value }));
    const ex = document.getElementById(`extra-data-${id}`);
    if(ex) ex.value = JSON.stringify(d);
    recalcularFilaPorId(id);
}

// --- LOTES ---
function agregarFilaLote(id) {
    const container = document.getElementById(`lista-lotes-${id}`);
    if(!container) return;
    const div = document.createElement('div');
    div.className = 'item-row';
    div.innerHTML = `
        <input type="text" class="form-control form-control-sm input-lote-nombre" placeholder="Lote" style="flex:3;" oninput="actualizarContadoresLotes(${id})">
        <input type="number" class="form-control form-control-sm input-lote-cant" placeholder="0" style="flex:1;" min="1" oninput="actualizarContadoresLotes(${id})">
        <button class="btn btn-sm btn-add-custom" style="width:32px; height:32px;" type="button" onclick="agregarFilaLote(${id})"><i class="bi bi-plus"></i></button>
        <button class="btn btn-sm btn-outline-danger" style="width:32px; height:32px;" type="button" onclick="this.closest('.item-row').remove(); actualizarContadoresLotes(${id});"><i class="bi bi-x-lg"></i></button>
    `;
    container.appendChild(div);
    actualizarContadoresLotes(id);
}

function actualizarContadoresLotes(id) {
    const rows = document.querySelectorAll(`#lista-lotes-${id} .item-row`);
    let t = 0; const d = [];
    rows.forEach(r => {
        const n = r.querySelector('.input-lote-nombre').value;
        const c = parseInt(r.querySelector('.input-lote-cant').value) || 0;
        t += c; if(n && c > 0) d.push({ tipo: 'lote', lote: n, cantidad_lote: c });
    });
    const h = document.getElementById(`hidden-cant-${id}`);
    if(h) h.value = t;
    const ex = document.getElementById(`extra-data-${id}`);
    if(ex) ex.value = JSON.stringify(d);
    recalcularFilaPorId(id);
}

function recalcularFilaPorId(id) {
    const tr = document.querySelector(`tr[data-detalle-id="${id}"]`);
    if(!tr) return;
    const h = document.getElementById(`hidden-cant-${id}`);
    const c = h ? parseFloat(h.value) : 0;
    const sub = c * parseFloat(tr.getAttribute('data-costo'));
    const subLabel = tr.querySelector('.row-subtotal');
    if(subLabel) subLabel.innerText = '$' + sub.toFixed(2);
    calcularTotalRecepcion();
}

function recalcularFila(input, costo) {
    const fila = input.closest('tr');
    const subLabel = fila.querySelector('.row-subtotal');
    if(subLabel) subLabel.innerText = '$' + (parseFloat(input.value || 0) * costo).toFixed(2);
    calcularTotalRecepcion();
}

function calcularTotalRecepcion() {
    let t = 0;
    document.querySelectorAll('.row-subtotal').forEach(s => t += parseFloat(s.innerText.replace('$', '')));
    const gt = document.getElementById('granTotalRecepcion');
    if(gt) gt.innerText = '$' + t.toFixed(2);
}

function verDetalleRecepcion(id) {
    window.currentRecId = id;
    fetch(`/recepciones/api/detalle-recepcion/${id}/`)
        .then(r => r.json())
        .then(data => {
            document.getElementById('recModalTitleText').innerText = data.folio;
            document.getElementById('recModalFecha').innerText = data.fecha;
            document.getElementById('recModalProveedor').innerText = data.proveedor;
            document.getElementById('recModalTotal').innerText = `$${data.total.toFixed(2)}`;
            const st = document.getElementById('recModalEstado');
            st.innerText = data.estado; st.className = 'status-pill status-' + data.estado.toLowerCase();
            document.getElementById('recModalOC').innerText = data.oc_folio.replace('OC-', '');
            document.getElementById('recModalAlmacen').innerText = data.almacen || '-';
            document.getElementById('recModalFactura').innerText = data.factura || '-';
            document.getElementById('recModalPedimento').innerText = data.pedimento || '-';
            document.getElementById('recModalAduana').innerText = data.aduana || '-';
            document.getElementById('recModalFechaPedimento').innerText = data.fecha_pedimento || '-';
            document.getElementById('recCardLogistica').style.display = 'block';
            const tbody = document.getElementById('recModalTableBody');
            tbody.innerHTML = '';
            data.detalles.forEach(d => {
                tbody.insertAdjacentHTML('beforeend', `<tr><td class="ps-3">${d.producto}</td><td class="text-center">${d.cant}</td><td class="text-end">$${d.precio.toFixed(2)}</td><td class="text-end pe-3 fw-bold">$${d.subtotal.toFixed(2)}</td></tr>`);
            });
            document.getElementById('btnCancelarRecepcion').style.display = (data.estado !== 'CANCELADA') ? 'inline-block' : 'none';
            new bootstrap.Modal(document.getElementById('modalDetalleRecepcion')).show();
        });
}

document.getElementById('formRecepcion').addEventListener('submit', function(e) {
    e.preventDefault();
    const btn = this.querySelector('button[type="submit"]');
    btn.disabled = true; btn.innerText = "Procesando...";
    fetch(this.action, { method: 'POST', body: new FormData(this), headers: { 'X-CSRFToken': getCookie('csrftoken') } })
    .then(r => r.json()).then(d => { if(d.success) { alert(d.message); location.reload(); } else { throw new Error(d.error); } })
    .catch(e => { alert(e.message); btn.disabled = false; btn.innerText = "Procesar Entrada"; });
});

function cancelarRecepcionDesdeTabla(id) {
    if(confirm('¿Seguro que deseas cancelar?')) {
        fetch(`/recepciones/cancelar/${id}/`, { method: 'POST', headers: { 'X-CSRFToken': getCookie('csrftoken') } })
        .then(r => r.json()).then(d => { if(d.success) location.reload(); else alert(d.error); });
    }
}

function cambiarEstadoRecepcion(id, estado) {
    if(confirm(`¿Finalizar recepción?`)) {
        fetch(`/recepciones/cambiar-estado/${id}/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCookie('csrftoken'), 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `estado=${estado}`
        }).then(r => r.json()).then(d => { if(d.success) location.reload(); else alert(d.error); });
    }
}