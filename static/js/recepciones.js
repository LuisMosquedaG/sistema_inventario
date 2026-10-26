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

                const factor = parseFloat(item.factor_conversion || 1.0);
                const tieneConversion = factor > 0 && factor !== 1.0;
                const cantInvFaltante = (cant_faltante * factor).toFixed(2).replace(/\.00$/, '');
                const uBase = item.unidad_base || 'Pieza';
                const uCompra = item.unidad_compra || uBase;
                const uCompraDisplay = item.unidad_compra_display || uCompra;

                let inputHtml = '';
                
                if (item.maneja_serie) {
                    inputHtml = `
                        <div class="serie-container">
                            <div id="lista-series-${item.id}" class="d-flex flex-column gap-1"></div>
                            <input type="hidden" name="cantidad_recibida[]" class="hidden-cant" id="hidden-cant-${item.id}" value="0">
                            <input type="hidden" name="extra_data_${item.id}" id="extra-data-${item.id}">
                            ${tieneConversion ? `
                            <div class="small text-muted mt-1 text-center" style="font-size: 0.75rem;">
                                ↳ Entrada Inv: <span class="fw-bold text-success entrada-inv-span" id="inv-span-${item.id}">0</span> ${uBase}
                            </div>` : ''}
                        </div>
                    `;
                    setTimeout(() => { for(let i=0; i<cant_faltante; i++) agregarFilaSerie(item.id); }, 100);

                } else if (item.maneja_lote || item.maneja_caducidad) {
                    inputHtml = `
                        <div class="lote-container">
                            <div id="lista-extras-${item.id}" class="lote-serie-container"></div>
                            <input type="hidden" name="cantidad_recibida[]" class="hidden-cant" id="hidden-cant-${item.id}" value="0">
                            <input type="hidden" name="extra_data_${item.id}" id="extra-data-${item.id}">
                            ${tieneConversion ? `
                            <div class="small text-muted mt-1 text-center" style="font-size: 0.75rem;">
                                ↳ Entrada Inv: <span class="fw-bold text-success entrada-inv-span" id="inv-span-${item.id}">0</span> ${uBase}
                            </div>` : ''}
                        </div>
                    `;
                    setTimeout(() => agregarFilaExtras(item.id, item.maneja_lote, item.maneja_caducidad), 100);

                } else {
                    inputHtml = `
                        <div class="d-flex flex-column align-items-center">
                            <input type="number" name="cantidad_recibida[]" 
                                class="form-control form-control-sm text-center input-cant-recibir mx-auto" 
                                style="max-width: 85px;"
                                value="${cant_faltante}" 
                                min="0" max="${cant_faltante}" 
                                data-factor="${factor}"
                                data-unidad-base="${uBase}"
                                onchange="recalcularFila(this, ${item.costo}, ${item.iva_porcentaje})" oninput="recalcularFila(this, ${item.costo}, ${item.iva_porcentaje})">
                            ${tieneConversion ? `
                            <div class="small text-muted mt-1 text-center" style="font-size: 0.75rem;">
                                ↳ Entrada Inv: <span class="fw-bold text-success entrada-inv-span" id="inv-span-${item.id}">${cantInvFaltante}</span> ${uBase}
                            </div>` : ''}
                        </div>
                    `;
                }

                const subtotal = cant_faltante * item.costo;
                const ivaMonto = subtotal * (item.iva_porcentaje / 100);
                const total = subtotal + ivaMonto;
                
                const filaHtml = `
                    <tr data-detalle-id="${item.id}" data-costo="${item.costo}" data-iva-porc="${item.iva_porcentaje}" data-factor="${factor}" data-unidad-base="${uBase}" data-tipo="${item.maneja_serie ? 'serie' : (item.maneja_lote ? 'lote' : (item.maneja_caducidad ? 'caducidad' : 'normal'))}">
                        <td class="ps-3">
                            <div class="fw-semibold small text-dark text-truncate" style="max-width: 100%;" title="${item.nombre}">
                                ${item.nombre}
                            </div>
                            <input type="hidden" name="detalle_compra_id[]" value="${item.id}">
                        </td>
                        <td class="text-center small">
                            <div class="fw-semibold">${item.cant_ordenada}</div>
                            <span class="badge bg-light text-secondary border d-inline-block mt-1 fw-normal" style="font-size: 0.68rem;" title="${uCompraDisplay}">${uCompra}</span>
                        </td>
                        <td class="text-center small">
                            <div class="fw-bold text-brand">${cant_faltante}</div>
                            <span class="text-muted d-block" style="font-size: 0.7rem;">${uCompra}</span>
                        </td>
                        <td class="text-center">${inputHtml}</td>
                        <td class="text-end small text-muted">
                            <div>$${parseFloat(item.costo).toFixed(2)}</div>
                            <span class="text-muted" style="font-size: 0.68rem;">/${uCompra}</span>
                            <input type="hidden" name="costo_unitario[]" value="${item.costo}">
                        </td>
                        <td class="text-end small text-dark row-subtotal">$${subtotal.toFixed(2)}</td>
                        <td class="text-end small text-muted row-iva">$${ivaMonto.toFixed(2)}</td>
                        <td class="text-end pe-3 fw-bold small text-dark row-total">$${total.toFixed(2)}</td>
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
    div.className = 'item-row d-flex align-items-center gap-1 mb-1';
    div.innerHTML = `
        <div class="flex-grow-1"><input type="text" class="form-control form-control-sm input-serie px-2 py-0" placeholder="Nº Serie" style="font-size: 0.8rem;" oninput="actualizarContadoresSeries(${id})"></div>
        <button class="btn btn-sm btn-add-custom d-flex align-items-center justify-content-center p-0" style="width:26px; height:26px; min-width:26px;" type="button" title="Agregar serie" onclick="agregarFilaSerie(${id})"><i class="bi bi-plus fs-6"></i></button>
        <button class="btn btn-sm btn-outline-danger d-flex align-items-center justify-content-center p-0" style="width:26px; height:26px; min-width:26px;" type="button" title="Eliminar serie" onclick="this.closest('.item-row').remove(); actualizarContadoresSeries(${id});"><i class="bi bi-x fs-6"></i></button>
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

// --- LOTES Y CADUCIDADES UNIFICADOS ---
function agregarFilaExtras(id, manejaLote, manejaCaducidad) {
    const container = document.getElementById(`lista-extras-${id}`);
    if(!container) return;
    const div = document.createElement('div');
    div.className = 'item-row d-flex align-items-center gap-1 mb-1';
    
    let inputsHtml = '';
    if (manejaLote && manejaCaducidad) {
        inputsHtml += `<input type="text" class="form-control form-control-sm input-lote-nombre px-1 py-0 text-center" placeholder="Lote" style="flex: 1.1; min-width: 65px; font-size: 0.78rem;" oninput="actualizarContadoresExtras(${id}, ${manejaLote}, ${manejaCaducidad})">`;
        inputsHtml += `<input type="date" class="form-control form-control-sm input-caducidad-fecha px-1 py-0 text-center" style="flex: 1.2; min-width: 95px; font-size: 0.75rem;" onchange="actualizarContadoresExtras(${id}, ${manejaLote}, ${manejaCaducidad})">`;
    } else if (manejaLote) {
        inputsHtml += `<input type="text" class="form-control form-control-sm input-lote-nombre px-2 py-0" placeholder="Lote" style="flex: 2; min-width: 80px; font-size: 0.8rem;" oninput="actualizarContadoresExtras(${id}, ${manejaLote}, ${manejaCaducidad})">`;
    } else if (manejaCaducidad) {
        inputsHtml += `<input type="date" class="form-control form-control-sm input-caducidad-fecha px-1 py-0 text-center" style="flex: 2; min-width: 100px; font-size: 0.78rem;" onchange="actualizarContadoresExtras(${id}, ${manejaLote}, ${manejaCaducidad})">`;
    }
    
    inputsHtml += `
        <input type="number" class="form-control form-control-sm input-lote-cant text-center fw-bold px-1 py-0" placeholder="Cant" title="Pzs a recibir" style="flex: 1; min-width: 65px; max-width: 75px; font-size: 0.82rem;" min="1" oninput="actualizarContadoresExtras(${id}, ${manejaLote}, ${manejaCaducidad})">
        <button class="btn btn-sm btn-add-custom d-flex align-items-center justify-content-center p-0" style="width:26px; height:26px; min-width:26px;" type="button" title="Agregar fila" onclick="agregarFilaExtras(${id}, ${manejaLote}, ${manejaCaducidad})"><i class="bi bi-plus fs-6"></i></button>
        <button class="btn btn-sm btn-outline-danger d-flex align-items-center justify-content-center p-0" style="width:26px; height:26px; min-width:26px;" type="button" title="Quitar fila" onclick="this.closest('.item-row').remove(); actualizarContadoresExtras(${id}, ${manejaLote}, ${manejaCaducidad});"><i class="bi bi-x fs-6"></i></button>
    `;
    div.innerHTML = inputsHtml;
    container.appendChild(div);
    actualizarContadoresExtras(id, manejaLote, manejaCaducidad);
}

function actualizarContadoresExtras(id, manejaLote, manejaCaducidad) {
    const rows = document.querySelectorAll(`#lista-extras-${id} .item-row`);
    let t = 0; const d = [];
    rows.forEach(r => {
        const inputLote = r.querySelector('.input-lote-nombre');
        const inputFecha = r.querySelector('.input-caducidad-fecha');
        const inputCant = r.querySelector('.input-lote-cant');

        const loteVal = inputLote ? inputLote.value : null;
        const fechaVal = inputFecha ? inputFecha.value : null;
        const cantVal = inputCant ? parseInt(inputCant.value) || 0 : 0;

        t += cantVal;
        
        if (cantVal > 0 && (loteVal || fechaVal)) {
            const itemType = manejaLote ? 'lote' : 'caducidad';
            d.push({
                tipo: itemType,
                lote: loteVal,
                fecha_caducidad: fechaVal,
                cantidad_lote: cantVal
            });
        }
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
    const cant = h ? parseFloat(h.value) : 0;
    const costo = parseFloat(tr.getAttribute('data-costo'));
    const ivaPorc = parseFloat(tr.getAttribute('data-iva-porc')) || 0;
    const factor = parseFloat(tr.getAttribute('data-factor') || 1.0);

    const spanInv = tr.querySelector('.entrada-inv-span');
    if (spanInv) {
        spanInv.innerText = (cant * factor).toFixed(2).replace(/\.00$/, '');
    }

    const sub = cant * costo;
    const iva = sub * (ivaPorc / 100);
    const total = sub + iva;

    const subLabel = tr.querySelector('.row-subtotal');
    if(subLabel) subLabel.innerText = '$' + sub.toFixed(2);

    const ivaLabel = tr.querySelector('.row-iva');
    if(ivaLabel) ivaLabel.innerText = '$' + iva.toFixed(2);

    const totLabel = tr.querySelector('.row-total');
    if(totLabel) totLabel.innerText = '$' + total.toFixed(2);

    calcularTotalRecepcion();
}

function recalcularFila(input, costo, ivaPorc) {
    const fila = input.closest('tr');
    const cant = parseFloat(input.value || 0);
    const factor = parseFloat(input.getAttribute('data-factor') || fila.getAttribute('data-factor') || 1.0);

    const spanInv = fila.querySelector('.entrada-inv-span');
    if (spanInv) {
        spanInv.innerText = (cant * factor).toFixed(2).replace(/\.00$/, '');
    }

    const sub = cant * costo;
    const iva = sub * (ivaPorc / 100);
    const total = sub + iva;

    const subLabel = fila.querySelector('.row-subtotal');
    if(subLabel) subLabel.innerText = '$' + sub.toFixed(2);

    const ivaLabel = fila.querySelector('.row-iva');
    if(ivaLabel) ivaLabel.innerText = '$' + iva.toFixed(2);

    const totLabel = fila.querySelector('.row-total');
    if(totLabel) totLabel.innerText = '$' + total.toFixed(2);

    calcularTotalRecepcion();
}

function calcularTotalRecepcion() {
    let subAcum = 0;
    let ivaAcum = 0;
    let totAcum = 0;

    document.querySelectorAll('.row-subtotal').forEach(s => subAcum += parseFloat(s.innerText.replace('$', '').replace(',', '')) || 0);
    document.querySelectorAll('.row-iva').forEach(s => ivaAcum += parseFloat(s.innerText.replace('$', '').replace(',', '')) || 0);
    document.querySelectorAll('.row-total').forEach(s => totAcum += parseFloat(s.innerText.replace('$', '').replace(',', '')) || 0);

    const elSub = document.getElementById('recepcionSubtotal');
    if(elSub) elSub.innerText = '$' + subAcum.toLocaleString('en-US', {minimumFractionDigits: 2});

    const elIva = document.getElementById('recepcionIvaTotal');
    if(elIva) elIva.innerText = '$' + ivaAcum.toLocaleString('en-US', {minimumFractionDigits: 2});

    const gt = document.getElementById('granTotalRecepcion');
    if(gt) gt.innerText = '$' + totAcum.toLocaleString('en-US', {minimumFractionDigits: 2});
}

function verRecepcion(id) {
    const tbody = document.getElementById('ver_rec_tabla_cuerpo');
    tbody.innerHTML = '<tr><td colspan="4" class="text-center py-3"><div class="spinner-border spinner-border-sm text-primary"></div> Cargando...</td></tr>';
    
    fetch(`/recepciones/api/detalle-recepcion/${id}/`)
        .then(r => r.json())
        .then(data => {
            if(data.error) { alert(data.error); return; }

            document.getElementById('ver_rec_folio').innerText = data.folio;
            
            // SECCIÓN 1: DATOS DE COMPRA
            document.getElementById('ver_rec_proveedor').innerText = data.proveedor;
            document.getElementById('ver_rec_sucursal').innerText = data.sucursal;
            document.getElementById('ver_rec_oc_folio').innerText = data.oc_folio;
            document.getElementById('ver_rec_oc_fecha').innerText = data.oc_fecha;

            // SECCIÓN 2: DATOS DE RECEPCIÓN
            document.getElementById('ver_rec_almacen').innerText = data.almacen;
            document.getElementById('ver_rec_folio_val').innerText = data.folio;
            document.getElementById('ver_rec_fecha').innerText = data.fecha;
            document.getElementById('ver_rec_factura').innerText = data.factura;
            document.getElementById('ver_rec_fecha_fact').innerText = data.fecha_comprobante; 
            document.getElementById('ver_rec_pedimento').innerText = data.pedimento;
            document.getElementById('ver_rec_fecha_ped').innerText = data.fecha_pedimento;
            document.getElementById('ver_rec_aduana').innerText = data.aduana;

            // SECCIÓN 3: LISTADO DE ARTÍCULOS
            tbody.innerHTML = '';
            
            if (data.detalles && data.detalles.length > 0) {
                data.detalles.forEach(det => {
                    const tieneConv = det.factor_conversion && det.factor_conversion !== 1;
                    const uCompra = det.unidad_compra || det.unidad_base || '';
                    const cantDisplay = `
                        <div class="fw-semibold">${det.cant} <span class="text-muted small">${uCompra}</span></div>
                        ${tieneConv ? `<div class="small text-success fw-semibold" style="font-size: 0.72rem;">(= ${det.cantidad_inventario} ${det.unidad_base})</div>` : ''}
                    `;
                    const fila = `
                        <tr>
                            <td class="ps-3">
                                <div class="fw-semibold small text-dark text-truncate" style="max-width: 100%;" title="${det.producto}">
                                    ${det.producto}
                                </div>
                            </td>
                            <td class="text-center small">${cantDisplay}</td>
                            <td class="text-end small text-muted">$${parseFloat(det.precio).toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                            <td class="text-end small text-dark">$${parseFloat(det.subtotal).toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                            <td class="text-end small text-muted">$${parseFloat(det.iva_monto || 0).toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                            <td class="text-end pe-3 fw-bold small text-dark">$${parseFloat(det.total).toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                        </tr>
                    `;
                    tbody.insertAdjacentHTML('beforeend', fila);
                });
            } else {
                tbody.innerHTML = '<tr><td colspan="6" class="text-center py-3 text-muted fst-italic">No hay artículos en esta recepción.</td></tr>';
            }

            const elSub = document.getElementById('ver_rec_subtotal');
            if (elSub) elSub.innerText = '$' + parseFloat(data.subtotal_total || 0).toLocaleString('en-US', {minimumFractionDigits: 2});

            const elIva = document.getElementById('ver_rec_iva_total');
            if (elIva) elIva.innerText = '$' + parseFloat(data.iva_total || 0).toLocaleString('en-US', {minimumFractionDigits: 2});

            const elTotal = document.getElementById('ver_rec_gran_total');
            if (elTotal) elTotal.innerText = '$' + parseFloat(data.gran_total || 0).toLocaleString('en-US', {minimumFractionDigits: 2});
            
            const modal = new bootstrap.Modal(document.getElementById('modalVerRecepcion'));
            modal.show();
        })
        .catch(err => {
            console.error('Error:', err);
            alert('No se pudo cargar la información de la recepción.');
        });
}

const formRecEl = document.getElementById('formRecepcion');
if (formRecEl) {
    formRecEl.addEventListener('submit', function(e) {
        e.preventDefault();
        const btn = this.querySelector('button[type="submit"]');
        btn.disabled = true; btn.innerText = "Procesando...";
        fetch(this.action, { method: 'POST', body: new FormData(this), headers: { 'X-CSRFToken': getCookie('csrftoken') } })
        .then(r => r.json()).then(d => { 
            if(d.success) { 
                alert(d.message); 
                // Redirigir a la URL limpia para que no se vuelva a abrir el modal por el parámetro oc_id
                window.location.href = "/recepciones/"; 
            } else { 
                throw new Error(d.error); 
            } 
        })
        .catch(e => { alert(e.message); btn.disabled = false; btn.innerText = "Procesar Entrada"; });
    });
}

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

// ---------------------------------------------------------
// DEVOLUCIONES DE RECEPCIÓN (COMPLETAS O PARCIALES)
// ---------------------------------------------------------

function abrirModalDevolucionRecepcion(id) {
    const tbody = document.getElementById('dev_rec_tabla_cuerpo');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="7" class="text-center py-3"><div class="spinner-border spinner-border-sm text-primary"></div> Cargando partidas...</td></tr>';

    const inputMotivo = document.getElementById('dev_rec_motivo');
    if (inputMotivo) inputMotivo.value = '';
    const inputRecId = document.getElementById('dev_rec_id');
    if (inputRecId) inputRecId.value = id;

    fetch(`/recepciones/api/detalle-recepcion/${id}/`)
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                alert(data.error);
                return;
            }

            document.getElementById('dev_rec_folio').innerText = data.folio;
            document.getElementById('dev_rec_proveedor').innerText = data.proveedor;
            document.getElementById('dev_rec_sucursal').innerText = data.sucursal;
            document.getElementById('dev_rec_oc_folio').innerText = data.oc_folio;
            document.getElementById('dev_rec_oc_fecha').innerText = data.oc_fecha;

            document.getElementById('dev_rec_almacen').innerText = data.almacen;
            document.getElementById('dev_rec_fecha').innerText = data.fecha;
            document.getElementById('dev_rec_factura').innerText = data.factura;

            tbody.innerHTML = '';
            let hayDisponible = false;

            if (data.detalles && data.detalles.length > 0) {
                data.detalles.forEach(det => {
                    const cantRecibida = parseInt(det.cant || 0);
                    const cantDevuelta = parseInt(det.cant_devuelta || 0);
                    const cantDisponible = parseInt(det.cant_disponible !== undefined ? det.cant_disponible : (cantRecibida - cantDevuelta));
                    const precio = parseFloat(det.precio || 0);
                    const ivaPorc = parseFloat(det.iva_porcentaje || 0);
                    const extras = det.extras || [];
                    const tieneExtras = extras.length > 0;

                    if (cantDisponible > 0) hayDisponible = true;

                    let inputHtml = '';
                    if (cantDisponible <= 0) {
                        inputHtml = `<span class="badge bg-secondary-subtle text-secondary">Agotado</span>`;
                    } else if (det.maneja_serie && tieneExtras) {
                        let seriesItemsHtml = '';
                        extras.forEach(ex => {
                            const disp = parseInt(ex.disponible || 0) > 0;
                            const serieLabel = ex.serie || `Serie #${ex.id}`;
                            if (disp) {
                                seriesItemsHtml += `
                                    <label class="d-flex align-items-center gap-1 small bg-white border rounded px-2 py-1" style="cursor:pointer; font-size:0.74rem;">
                                        <input type="checkbox" class="form-check-input m-0 check-serie-devolver"
                                            data-detalle-id="${det.id}"
                                            data-extra-id="${ex.id}"
                                            onchange="actualizarDevolucionPorExtras(${det.id})">
                                        <span class="font-monospace text-dark">${serieLabel}</span>
                                    </label>
                                `;
                            } else {
                                seriesItemsHtml += `
                                    <span class="badge bg-light text-muted border text-decoration-line-through font-monospace" style="font-size:0.7rem;" title="Ya no está en este almacén">
                                        ${serieLabel}
                                    </span>
                                `;
                            }
                        });
                        inputHtml = `
                            <div class="d-flex flex-column gap-1 text-start" style="max-height:130px; overflow-y:auto;">
                                ${seriesItemsHtml}
                            </div>
                            <input type="hidden"
                                class="input-cant-devolver-rec"
                                id="dev-cant-hidden-${det.id}"
                                data-detalle-id="${det.id}"
                                data-disponible="${cantDisponible}"
                                data-precio="${precio}"
                                data-iva-porc="${ivaPorc}"
                                data-modo="serie"
                                value="0">
                        `;
                    } else if ((det.maneja_lote || det.maneja_caducidad) && tieneExtras) {
                        let lotesItemsHtml = '';
                        extras.forEach(ex => {
                            const dispLote = Math.min(parseInt(ex.disponible || 0), cantDisponible);
                            const partes = [];
                            if (ex.lote) partes.push(`Lote: <strong>${ex.lote}</strong>`);
                            if (ex.fecha_caducidad) partes.push(`Cad: <strong>${ex.fecha_caducidad}</strong>`);
                            const etiqueta = partes.length > 0 ? partes.join(' | ') : `Reg #${ex.id}`;

                            if (dispLote > 0) {
                                lotesItemsHtml += `
                                    <div class="d-flex align-items-center justify-content-between gap-2 bg-white border rounded px-2 py-1" style="font-size:0.73rem;">
                                        <div class="text-start text-dark" style="line-height:1.15;">
                                            <div>${etiqueta}</div>
                                            <small class="text-muted">Disp: ${dispLote}</small>
                                        </div>
                                        <input type="number"
                                            class="form-control form-control-sm text-center input-lote-devolver"
                                            style="width: 65px; height: 26px; font-size:0.78rem;"
                                            data-detalle-id="${det.id}"
                                            data-extra-id="${ex.id}"
                                            data-disponible="${dispLote}"
                                            value="0"
                                            min="0"
                                            max="${dispLote}"
                                            oninput="actualizarDevolucionPorExtras(${det.id})"
                                            onchange="actualizarDevolucionPorExtras(${det.id})">
                                    </div>
                                `;
                            } else {
                                lotesItemsHtml += `
                                    <div class="d-flex align-items-center justify-content-between bg-light border rounded px-2 py-1 text-muted" style="font-size:0.72rem;">
                                        <span>${etiqueta}</span>
                                        <span class="badge bg-secondary-subtle text-secondary">Sin stock</span>
                                    </div>
                                `;
                            }
                        });
                        inputHtml = `
                            <div class="d-flex flex-column gap-1" style="max-height:130px; overflow-y:auto;">
                                ${lotesItemsHtml}
                            </div>
                            <input type="hidden"
                                class="input-cant-devolver-rec"
                                id="dev-cant-hidden-${det.id}"
                                data-detalle-id="${det.id}"
                                data-disponible="${cantDisponible}"
                                data-precio="${precio}"
                                data-iva-porc="${ivaPorc}"
                                data-modo="lote"
                                value="0">
                        `;
                    } else {
                        inputHtml = `
                            <input type="number"
                                class="form-control form-control-sm text-center mx-auto input-cant-devolver-rec"
                                style="max-width: 85px;"
                                data-detalle-id="${det.id}"
                                data-disponible="${cantDisponible}"
                                data-precio="${precio}"
                                data-iva-porc="${ivaPorc}"
                                data-modo="normal"
                                value="0"
                                min="0"
                                max="${cantDisponible}"
                                oninput="recalcularFilaDevolucionRecepcion(this)"
                                onchange="recalcularFilaDevolucionRecepcion(this)">
                        `;
                    }

                    const fila = `
                        <tr data-detalle-id="${det.id}">
                            <td class="ps-3">
                                <div class="fw-semibold small text-dark text-truncate" style="max-width: 100%;" title="${det.producto}">
                                    ${det.producto}
                                </div>
                            </td>
                            <td class="text-center small">${cantRecibida}</td>
                            <td class="text-center small text-muted">${cantDevuelta}</td>
                            <td class="text-center small fw-bold ${cantDisponible > 0 ? 'text-success' : 'text-muted'}">${cantDisponible}</td>
                            <td class="text-center">${inputHtml}</td>
                            <td class="text-end small text-muted">$${precio.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                            <td class="text-end pe-3 fw-bold small text-dark dev-row-total" data-sub="0" data-iva="0" data-tot="0">$0.00</td>
                        </tr>
                    `;
                    tbody.insertAdjacentHTML('beforeend', fila);
                });
            } else {
                tbody.innerHTML = '<tr><td colspan="7" class="text-center py-3 text-muted fst-italic">No hay artículos en esta recepción.</td></tr>';
            }

            const btnConfirmar = document.getElementById('btnConfirmarDevolucionRecepcion');
            if (btnConfirmar) {
                btnConfirmar.disabled = !hayDisponible;
            }

            calcularTotalDevolucionRecepcion();

            const modal = new bootstrap.Modal(document.getElementById('modalDevolucionRecepcion'));
            modal.show();
        })
        .catch(err => {
            console.error('Error:', err);
            alert('No se pudo cargar la información de la recepción para devolución.');
        });
}

function actualizarDevolucionPorExtras(detId) {
    const hiddenInput = document.getElementById(`dev-cant-hidden-${detId}`);
    if (!hiddenInput) return;

    const maxDispFila = parseInt(hiddenInput.getAttribute('data-disponible') || 0);
    const modo = hiddenInput.getAttribute('data-modo');
    let suma = 0;

    if (modo === 'serie') {
        const checks = document.querySelectorAll(`.check-serie-devolver[data-detalle-id="${detId}"]:checked`);
        if (checks.length > maxDispFila) {
            checks[checks.length - 1].checked = false;
        }
        suma = document.querySelectorAll(`.check-serie-devolver[data-detalle-id="${detId}"]:checked`).length;
    } else if (modo === 'lote') {
        const inputsLote = document.querySelectorAll(`.input-lote-devolver[data-detalle-id="${detId}"]`);
        inputsLote.forEach(inp => {
            const maxLote = parseInt(inp.getAttribute('data-disponible') || 0);
            let val = parseInt(inp.value || 0);
            if (isNaN(val) || val < 0) val = 0;
            if (val > maxLote) {
                val = maxLote;
                inp.value = maxLote;
            }
            if (suma + val > maxDispFila) {
                val = Math.max(0, maxDispFila - suma);
                inp.value = val;
            }
            suma += val;
        });
    }

    hiddenInput.value = suma;
    recalcularFilaDevolucionRecepcion(hiddenInput);
}

function recalcularFilaDevolucionRecepcion(input) {
    const maxDisp = parseInt(input.getAttribute('data-disponible') || 0);
    let cant = parseInt(input.value || 0);
    if (isNaN(cant) || cant < 0) cant = 0;
    if (cant > maxDisp) {
        cant = maxDisp;
        input.value = maxDisp;
    }

    const precio = parseFloat(input.getAttribute('data-precio') || 0);
    const ivaPorc = parseFloat(input.getAttribute('data-iva-porc') || 0);

    const sub = cant * precio;
    const iva = sub * (ivaPorc / 100);
    const tot = sub + iva;

    const tr = input.closest('tr');
    if (tr) {
        const totCell = tr.querySelector('.dev-row-total');
        if (totCell) {
            totCell.setAttribute('data-sub', sub.toFixed(4));
            totCell.setAttribute('data-iva', iva.toFixed(4));
            totCell.setAttribute('data-tot', tot.toFixed(4));
            totCell.innerText = '$' + tot.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
        }
    }

    calcularTotalDevolucionRecepcion();
}

function calcularTotalDevolucionRecepcion() {
    let subAcum = 0;
    let ivaAcum = 0;
    let totAcum = 0;

    document.querySelectorAll('#dev_rec_tabla_cuerpo .dev-row-total').forEach(cell => {
        subAcum += parseFloat(cell.getAttribute('data-sub') || 0);
        ivaAcum += parseFloat(cell.getAttribute('data-iva') || 0);
        totAcum += parseFloat(cell.getAttribute('data-tot') || 0);
    });

    const elSub = document.getElementById('dev_rec_subtotal');
    if (elSub) elSub.innerText = '$' + subAcum.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});

    const elIva = document.getElementById('dev_rec_iva_total');
    if (elIva) elIva.innerText = '$' + ivaAcum.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});

    const elTot = document.getElementById('dev_rec_gran_total');
    if (elTot) elTot.innerText = '$' + totAcum.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
}

function seleccionarTodoDevolucionRecepcion() {
    document.querySelectorAll('#dev_rec_tabla_cuerpo .input-cant-devolver-rec').forEach(inp => {
        const detId = inp.getAttribute('data-detalle-id');
        const modo = inp.getAttribute('data-modo') || 'normal';
        const maxDisp = parseInt(inp.getAttribute('data-disponible') || 0);

        if (modo === 'serie') {
            let tomados = 0;
            document.querySelectorAll(`.check-serie-devolver[data-detalle-id="${detId}"]`).forEach(chk => {
                if (tomados < maxDisp) {
                    chk.checked = true;
                    tomados++;
                } else {
                    chk.checked = false;
                }
            });
            actualizarDevolucionPorExtras(detId);
        } else if (modo === 'lote') {
            let restante = maxDisp;
            document.querySelectorAll(`.input-lote-devolver[data-detalle-id="${detId}"]`).forEach(loteInp => {
                const dispLote = parseInt(loteInp.getAttribute('data-disponible') || 0);
                const tomar = Math.min(restante, dispLote);
                loteInp.value = tomar;
                restante -= tomar;
            });
            actualizarDevolucionPorExtras(detId);
        } else {
            inp.value = maxDisp;
            recalcularFilaDevolucionRecepcion(inp);
        }
    });
}

function limpiarCantidadesDevolucionRecepcion() {
    document.querySelectorAll('#dev_rec_tabla_cuerpo .check-serie-devolver').forEach(chk => {
        chk.checked = false;
    });
    document.querySelectorAll('#dev_rec_tabla_cuerpo .input-lote-devolver').forEach(loteInp => {
        loteInp.value = 0;
    });
    document.querySelectorAll('#dev_rec_tabla_cuerpo .input-cant-devolver-rec').forEach(inp => {
        inp.value = 0;
        recalcularFilaDevolucionRecepcion(inp);
    });
}

function confirmarDevolucionRecepcion() {
    const recId = document.getElementById('dev_rec_id').value;
    const motivo = (document.getElementById('dev_rec_motivo').value || '').trim();
    const inputs = document.querySelectorAll('#dev_rec_tabla_cuerpo .input-cant-devolver-rec');

    const items = [];
    inputs.forEach(inp => {
        const cant = parseInt(inp.value || 0);
        const detId = parseInt(inp.getAttribute('data-detalle-id'));
        const modo = inp.getAttribute('data-modo') || 'normal';

        if (cant > 0 && detId) {
            const extrasSeleccionados = [];
            if (modo === 'serie') {
                document.querySelectorAll(`.check-serie-devolver[data-detalle-id="${detId}"]:checked`).forEach(chk => {
                    extrasSeleccionados.push({
                        id: parseInt(chk.getAttribute('data-extra-id')),
                        qty: 1
                    });
                });
            } else if (modo === 'lote') {
                document.querySelectorAll(`.input-lote-devolver[data-detalle-id="${detId}"]`).forEach(loteInp => {
                    const qtyLote = parseInt(loteInp.value || 0);
                    if (qtyLote > 0) {
                        extrasSeleccionados.push({
                            id: parseInt(loteInp.getAttribute('data-extra-id')),
                            qty: qtyLote
                        });
                    }
                });
            }
            items.push({
                detalle_id: detId,
                cantidad: cant,
                extras: extrasSeleccionados
            });
        }
    });

    if (items.length === 0) {
        alert('Por favor ingresa una cantidad mayor a 0 (o selecciona lote/serie) en al menos una partida para devolver.');
        return;
    }

    if (!confirm('¿Confirmas la creación de esta devolución?')) {
        return;
    }

    const btn = document.getElementById('btnConfirmarDevolucionRecepcion');
    const originalHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Procesando...';

    fetch(`/recepciones/api/devolucion/${recId}/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            motivo: motivo,
            items: items
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            alert(data.message);
            window.location.reload();
        } else {
            alert('Error: ' + (data.error || 'No se pudo procesar la devolución.'));
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }
    })
    .catch(err => {
        console.error('Error:', err);
        alert('Ocurrió un error al procesar la devolución.');
        btn.disabled = false;
        btn.innerHTML = originalHtml;
    });
}
