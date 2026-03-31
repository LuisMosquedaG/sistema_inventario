// ============================================
// INVENTARIO.JS — Lógica Reforzada y Centralizada
// ============================================

/**
 * Helper para obtener el token CSRF de las cookies
 */
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

/**
 * Función centralizada para abrir modales de forma segura
 * @param {string} id - ID del elemento modal
 */
function mostrarModal(id) {
    const el = document.getElementById(id);
    if (!el) {
        console.error(`Error: No se encontró el modal con ID "${id}"`);
        return null;
    }
    const modal = bootstrap.Modal.getOrCreateInstance(el);
    modal.show();
    return modal;
}

// --- 1. GESTIÓN DE ARTÍCULOS (NUEVO / EDITAR) ---

function abrirNuevoArticulo() {
    const form = document.getElementById('formCrearArticulo');
    if (form) form.reset();
    
    const idField = document.getElementById('productoId');
    if (idField) idField.value = '';
    
    const selSub = document.getElementById('selectSubcategoria');
    if (selSub) { 
        selSub.disabled = true; 
        selSub.innerHTML = '<option value="">Selecciona categoría primero...</option>'; 
    }
    
    const selTest = document.getElementById('selectTestCalidad');
    if (selTest) { 
        selTest.disabled = true; 
        selTest.value = ""; 
        selTest.classList.add('bg-light');
    }

    mostrarModal('modalCrearArticulo');
}

function cargarProductoEdicion(id) {
    const url = APP_URLS.api_producto.replace('0', id);
    
    fetch(url)
        .then(r => {
            if (!r.ok) throw new Error("Error al obtener datos del producto");
            return r.json();
        })
        .then(data => {
            const form = document.getElementById('formCrearArticulo');
            if (!form) return;
            
            document.getElementById('productoId').value = data.id;
            form.querySelector('[name="nombre"]').value = data.nombre || '';
            form.querySelector('[name="descripcion"]').value = data.descripcion || '';
            form.querySelector('[name="tipo"]').value = data.tipo || 'producto';
            form.querySelector('[name="tipo_abastecimiento"]').value = data.tipo_abastecimiento || 'compra';
            form.querySelector('[name="estado"]').value = data.estado || 'activo';
            form.querySelector('[name="categoria"]').value = data.categoria || '';
            form.querySelector('[name="marca"]').value = data.marca || '';
            form.querySelector('[name="modelo"]').value = data.modelo || '';
            form.querySelector('[name="linea"]').value = data.linea || '';
            form.querySelector('[name="unidad_medida"]').value = data.unidad_medida || 'PZA';
            form.querySelector('[name="iva"]').value = data.iva || '0.00';
            form.querySelector('[name="ieps"]').value = data.ieps || '0.00';
            form.querySelector('[name="precio_costo"]').value = data.precio_costo || '0.00';
            form.querySelector('[name="precio_venta"]').value = data.precio_venta || '0.00';
            form.querySelector('[name="stock_minimo"]').value = data.stock_minimo || 0;
            form.querySelector('[name="stock_maximo"]').value = data.stock_maximo || 1000;
            form.querySelector('[name="maneja_lote"]').checked = data.maneja_lote || false;
            form.querySelector('[name="maneja_serie"]').checked = data.maneja_serie || false;

            if (data.categoria) {
                cargarSubcategorias(data.categoria, data.subcategoria);
            }

            const selTest = document.getElementById('selectTestCalidad');
            if (selTest) {
                if (data.tipo_abastecimiento === 'produccion') {
                    selTest.disabled = false;
                    selTest.classList.remove('bg-light');
                    selTest.value = data.test_calidad_id || "";
                } else {
                    selTest.disabled = true;
                    selTest.value = "";
                    selTest.classList.add('bg-light');
                }
            }

            mostrarModal('modalCrearArticulo');
        })
        .catch(err => alert(err.message));
}

function guardarProducto() {
    const form = document.getElementById('formCrearArticulo');
    if (!form) return;
    
    const id = document.getElementById('productoId').value;
    const url = id ? APP_URLS.api_actualizar_producto.replace('0', id) : APP_URLS.api_crear_producto;
    
    fetch(url, {
        method: 'POST',
        body: new FormData(form),
        headers: { 
            'X-Requested-With': 'XMLHttpRequest', 
            'X-CSRFToken': getCookie('csrftoken') 
        }
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            location.reload();
        } else {
            alert("Error: " + JSON.stringify(data.error));
        }
    })
    .catch(err => alert("Error de conexión: " + err));
}

// --- LÓGICA DE CATEGORÍAS ---

function cargarSubcategorias(categoriaNombre, subSeleccionada = "") {
    const selSub = document.getElementById('selectSubcategoria');
    if (!selSub) return;

    if (!categoriaNombre) {
        selSub.disabled = true;
        selSub.innerHTML = '<option value="">Selecciona categoría primero...</option>';
        return;
    }

    fetch(`${APP_URLS.api_subcategorias}?categoria_nombre=${encodeURIComponent(categoriaNombre)}`)
        .then(r => r.json())
        .then(data => {
            selSub.innerHTML = '<option value="">Seleccionar...</option>';
            if (data.length > 0) {
                data.forEach(s => {
                    const opt = document.createElement('option');
                    opt.value = s.nombre;
                    opt.textContent = s.nombre;
                    if (s.nombre === subSeleccionada) opt.selected = true;
                    selSub.appendChild(opt);
                });
                selSub.disabled = false;
            } else {
                selSub.innerHTML = '<option value="">Sin subcategorías</option>';
                selSub.disabled = true;
            }
        });
}

document.addEventListener('change', function(e) {
    if (e.target && e.target.id === 'selectCategoria') {
        cargarSubcategorias(e.target.value);
    }
});

// --- 2. EXISTENCIAS ---

function abrirModalExistencias(id, nombre) {
    const t = document.getElementById('tituloModalDetalle');
    if (t) t.innerText = `Existencias: ${nombre}`;
    
    const tbody = document.getElementById('tablaBodyProveedor');
    if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="text-center py-3"><span class="spinner-border spinner-border-sm"></span> Cargando...</td></tr>';
    
    mostrarModal('modalDetalleInventario');

    fetch(`${APP_URLS.api_detalle_producto}${id}/`)
        .then(r => r.json())
        .then(data => {
            if (!tbody) return;
            tbody.innerHTML = '';
            if (data.historial && data.historial.length > 0) {
                data.historial.forEach(i => {
                    tbody.insertAdjacentHTML('beforeend', `
                        <tr>
                            <td class="text-center"><a href="#" onclick="verDetalleDoc('oc', ${i.oc_id}); return false;" class="text-decoration-none">${i.folio_oc}</a></td>
                            <td class="text-center"><a href="#" onclick="verDetalleDoc('rec', ${i.rec_id}); return false;" class="text-decoration-none">${i.folio_rec}</a></td>
                            <td class="text-center">${i.proveedor}</td>
                            <td class="text-center">${i.fecha}</td>
                            <td class="text-center">${i.cantidad}</td>
                            <td class="text-end">$${parseFloat(i.costo).toFixed(2)}</td>
                            <td class="text-end">$${parseFloat(i.total).toFixed(2)}</td>
                        </tr>`);
                });
            } else {
                tbody.innerHTML = '<tr><td colspan="7" class="text-center py-3 text-muted italic">Sin movimientos registrados.</td></tr>';
            }
        });
}

// --- 3. RECETAS (MRP) ---

function abrirConfigurarReceta() {
    const form = document.getElementById('formReceta');
    if (form) form.reset();
    const tbody = document.getElementById('tbodyRecetaEdit');
    if (tbody) tbody.innerHTML = '';
    document.getElementById('totalCostoReceta').innerText = '$0.00';
    document.getElementById('msgVacioReceta').style.display = 'block';
    mostrarModal('modalProduccion');
}

function cargarRecetaExistente() {
    const pId = document.getElementById('selectRecetaPadre').value;
    const tbody = document.getElementById('tbodyRecetaEdit');
    const msg = document.getElementById('msgVacioReceta');
    if (!pId) {
        if (tbody) tbody.innerHTML = '';
        if (msg) msg.style.display = 'block';
        document.getElementById('totalCostoReceta').innerText = '$0.00';
        return;
    }
    fetch(`${APP_URLS.api_receta}${pId}/`)
        .then(r => r.json())
        .then(data => {
            if (!tbody) return;
            tbody.innerHTML = '';
            if (data.length > 0) {
                if (msg) msg.style.display = 'none';
                data.forEach(i => {
                    const subtotal = i.cant * i.costo;
                    tbody.insertAdjacentHTML('beforeend', `
                        <tr data-id="${i.id}" data-costo="${i.costo}">
                            <td class="ps-3 fw-semibold">${i.nombre}</td>
                            <td class="text-center">
                                <input type="number" class="form-control form-control-sm text-center mx-auto" 
                                       value="${i.cant}" min="1" style="max-width: 70px;" 
                                       onchange="recalcularTotalesReceta()">
                            </td>
                            <td class="text-end text-muted">$${parseFloat(i.costo).toFixed(2)}</td>
                            <td class="text-end fw-bold subtotal-fila">$${subtotal.toFixed(2)}</td>
                            <td class="text-center">
                                <button type="button" class="btn btn-sm text-danger p-0" onclick="this.closest('tr').remove(); recalcularTotalesReceta();">
                                    <i class="bi bi-trash"></i>
                                </button>
                            </td>
                        </tr>`);
                });
                recalcularTotalesReceta();
            } else {
                if (msg) msg.style.display = 'block';
                document.getElementById('totalCostoReceta').innerText = '$0.00';
            }
        });
}

function agregarComponenteReceta() {
    const sel = document.getElementById('selectComponente');
    const pId = sel.value;
    const pName = sel.options[sel.selectedIndex].text;
    const cant = parseInt(document.getElementById('cantComponente').value) || 1;
    if (!pId) return alert("Selecciona un componente");
    const existente = document.querySelector(`#tbodyRecetaEdit tr[data-id="${pId}"]`);
    if (existente) {
        const inp = existente.querySelector('input');
        inp.value = parseInt(inp.value) + cant;
        recalcularTotalesReceta();
        return;
    }
    fetch(APP_URLS.api_producto.replace('0', pId))
        .then(r => r.json())
        .then(data => {
            const tbody = document.getElementById('tbodyRecetaEdit');
            const msg = document.getElementById('msgVacioReceta');
            if (msg) msg.style.display = 'none';
            const subtotal = cant * data.precio_costo;
            tbody.insertAdjacentHTML('beforeend', `
                <tr data-id="${data.id}" data-costo="${data.precio_costo}">
                    <td class="ps-3 fw-semibold">${data.nombre}</td>
                    <td class="text-center">
                        <input type="number" class="form-control form-control-sm text-center mx-auto" 
                               value="${cant}" min="1" style="max-width: 70px;" 
                               onchange="recalcularTotalesReceta()">
                    </td>
                    <td class="text-end text-muted">$${parseFloat(data.precio_costo).toFixed(2)}</td>
                    <td class="text-end fw-bold subtotal-fila">$${subtotal.toFixed(2)}</td>
                    <td class="text-center">
                        <button type="button" class="btn btn-sm text-danger p-0" onclick="this.closest('tr').remove(); recalcularTotalesReceta();">
                            <i class="bi bi-trash"></i>
                        </button>
                    </td>
                </tr>`);
            recalcularTotalesReceta();
        });
}

function recalcularTotalesReceta() {
    let total = 0;
    document.querySelectorAll('#tbodyRecetaEdit tr').forEach(tr => {
        const costo = parseFloat(tr.dataset.costo) || 0;
        const cant = parseInt(tr.querySelector('input').value) || 0;
        const sub = costo * cant;
        tr.querySelector('.subtotal-fila').innerText = '$' + sub.toFixed(2);
        total += sub;
    });
    document.getElementById('totalCostoReceta').innerText = '$' + total.toFixed(2);
}

function guardarReceta() {
    const pId = document.getElementById('selectRecetaPadre').value;
    if (!pId) return alert("Selecciona el producto final");
    const componentes = [];
    document.querySelectorAll('#tbodyRecetaEdit tr').forEach(tr => {
        componentes.push({ id: tr.dataset.id, cant: parseInt(tr.querySelector('input').value) });
    });
    fetch(APP_URLS.api_guardar_receta, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
        body: JSON.stringify({ producto_id: pId, componentes: JSON.stringify(componentes) })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) { alert("Receta guardada."); location.reload(); }
        else { alert("Error: " + data.error); }
    });
}

function abrirModalReceta(id, nombre) {
    const t = document.getElementById('tituloRecetaModal');
    if (t) t.innerText = `Receta: ${nombre}`;
    const tbody = document.getElementById('tablaBodyRecetaUnica');
    if (tbody) tbody.innerHTML = '<tr><td colspan="2" class="text-center py-3"><span class="spinner-border spinner-border-sm"></span> Cargando...</td></tr>';
    mostrarModal('modalVerReceta');
    fetch(`${APP_URLS.api_receta}${id}/`)
        .then(r => r.json())
        .then(data => {
            if (!tbody) return;
            tbody.innerHTML = '';
            if (data.length > 0) {
                data.forEach(i => { tbody.insertAdjacentHTML('beforeend', `<tr><td class="ps-3 fw-semibold">${i.nombre}</td><td class="text-center">${i.cant} pz</td></tr>`); });
            } else {
                tbody.innerHTML = '<tr><td colspan="2" class="text-center py-3 text-muted">No tiene receta configurada.</td></tr>';
            }
        });
}

// --- 4. PRECIOS Y COSTOS ---

function abrirModalPrecios(id, nombre) {
    const t = document.getElementById('lpNombre');
    if (t) t.innerText = nombre;
    const tp = document.getElementById('lpTablaPrecios'); if (tp) tp.innerHTML = '';
    const tc = document.getElementById('lpTablaCostos'); if (tc) tc.innerHTML = '';
    document.getElementById('modalListaPrecios').dataset.productoId = id;
    mostrarModal('modalListaPrecios');
    fetch(APP_URLS.api_producto.replace('0', id))
        .then(r => r.json())
        .then(data => {
            document.getElementById('lpBaseCosto').value = data.precio_costo;
            document.getElementById('lpBaseVenta').value = data.precio_venta;
            if (data.precios_lista && tp) {
                data.precios_lista.forEach(i => {
                    tp.insertAdjacentHTML('beforeend', `
                        <tr>
                            <td class="ps-3"><input type="text" class="form-control form-control-sm lp-name" value="${i.nombre}"></td>
                            <td class="text-center"><input type="number" step="0.01" class="form-control form-control-sm text-end lp-monto" value="${i.monto}"></td>
                            <td class="text-center"><button class="btn btn-sm text-danger p-0" onclick="this.closest('tr').remove()"><i class="bi bi-trash"></i></button></td>
                        </tr>`);
                });
            }
            if (data.costos_lista && tc) {
                data.costos_lista.forEach(i => {
                    tc.insertAdjacentHTML('beforeend', `
                        <tr>
                            <td class="ps-3"><input type="text" class="form-control form-control-sm lc-name" value="${i.nombre}"></td>
                            <td class="text-center"><input type="number" step="0.01" class="form-control form-control-sm text-end lc-monto" value="${i.monto}"></td>
                            <td class="text-center"><button class="btn btn-sm text-danger p-0" onclick="this.closest('tr').remove()"><i class="bi bi-trash"></i></button></td>
                        </tr>`);
                });
            }
        });
}

function guardarCambiosListaPrecios() {
    const id = document.getElementById('modalListaPrecios').dataset.productoId;
    const costoBase = document.getElementById('lpBaseCosto').value;
    const ventaBase = document.getElementById('lpBaseVenta').value;
    const precios = [];
    document.querySelectorAll('#lpTablaPrecios tr').forEach(tr => {
        const n = tr.querySelector('.lp-name').value;
        const m = tr.querySelector('.lp-monto').value;
        if (n) precios.push({ nombre: n, monto: m });
    });
    const costos = [];
    document.querySelectorAll('#lpTablaCostos tr').forEach(tr => {
        const n = tr.querySelector('.lc-name').value;
        const m = tr.querySelector('.lc-monto').value;
        if (n) costos.push({ nombre: n, monto: m });
    });
    const formData = new FormData();
    formData.append('precio_costo', costoBase);
    formData.append('precio_venta', ventaBase);
    formData.append('precios_extra', JSON.stringify(precios));
    formData.append('costos_extra', JSON.stringify(costos));
    fetch(APP_URLS.api_actualizar_precio.replace('0', id), {
        method: 'POST',
        headers: { 'X-CSRFToken': getCookie('csrftoken') },
        body: formData
    }).then(r => r.json()).then(data => { if (data.success) { alert("Precios actualizados."); location.reload(); } else { alert("Error: " + data.error); } });
}

// --- 5. DETALLE DE DOCUMENTO ---

function verDetalleDoc(tipo, id) {
    if (!id) return;
    fetch(`${APP_URLS.api_detalle_documento}?tipo=${tipo}&id=${id}`)
        .then(r => r.json())
        .then(data => {
            document.getElementById('docModalTitle').innerText = data.titulo;
            document.getElementById('docModalFolio').innerText = data.folio;
            document.getElementById('docModalFecha').innerText = data.fecha;
            document.getElementById('docModalProveedor').innerText = data.proveedor;
            document.getElementById('docModalEstado').innerText = data.estado;
            document.getElementById('docModalEstado').className = 'status-pill status-' + data.estado.toLowerCase();
            document.getElementById('docModalTotal').innerText = '$' + data.total.toFixed(2);
            
            const tbody = document.getElementById('docModalTableBody');
            tbody.innerHTML = '';
            data.detalles.forEach(d => {
                tbody.insertAdjacentHTML('beforeend', `
                    <tr>
                        <td class="ps-3">${d.producto}</td>
                        <td class="text-center">${d.cant}</td>
                        <td class="text-end">$${d.precio.toFixed(2)}</td>
                        <td class="text-end pe-3 fw-bold">$${d.subtotal.toFixed(2)}</td>
                    </tr>`);
            });

            if (tipo === 'rec') {
                document.getElementById('cardLogistica').style.display = 'block';
                document.getElementById('docModalOC').innerText = data.oc_folio;
                document.getElementById('docModalAlmacen').innerText = data.almacen;
                document.getElementById('docModalFactura').innerText = data.factura;
                document.getElementById('docModalPedimento').innerText = data.pedimento;
                document.getElementById('docModalAduana').innerText = data.aduana;
                document.getElementById('docModalFechaPedimento').innerText = data.fecha_pedimento;
            } else {
                document.getElementById('cardLogistica').style.display = 'none';
                document.getElementById('docModalOC').innerText = '-';
            }

            mostrarModal('modalDetalleDocumento');
        });
}
