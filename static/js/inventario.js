// ============================================
// INVENTARIO.JS — Lógica Reforzada y Centralizada
// ============================================

// --- Helpers Globales ---
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

window.abrirNuevoArticulo = function(sucursalId = '') {
    const form = document.getElementById('formCrearArticulo');
    if (form) form.reset();
    
    const idField = document.getElementById('productoId');
    if (idField) idField.value = '';

    const selSuc = document.getElementById('selectSucursalArticulo');
    if (selSuc) selSuc.value = sucursalId;
    
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

window.cargarProductoEdicion = function(id) {
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
            if (form.querySelector('[name="sucursal"]')) {
                form.querySelector('[name="sucursal"]').value = data.sucursal || '';
            }

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

window.guardarProducto = function() {
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
    .then(response => {
        if (!response.ok) {
            // Si la respuesta no es 200 OK, probablemente sea una página de error HTML o login
            return response.text().then(text => {
                if (text.includes("<!DOCTYPE") || text.includes("<html")) {
                    throw new Error("Sesión expirada o error del servidor (HTML recibido). Por favor recarga la página.");
                }
                throw new Error(text || `Error del servidor (${response.status})`);
            });
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            location.reload();
        } else {
            // Manejar errores de validación devueltos como JSON
            let errorMsg = "Error de validación";
            if (typeof data.error === 'object') {
                errorMsg = Object.entries(data.error).map(([key, val]) => `${key}: ${val}`).join('\n');
            } else {
                errorMsg = data.error;
            }
            alert(errorMsg);
        }
    })
    .catch(err => {
        console.error("Detalle del error:", err);
        alert("Error: " + err.message);
    });
}

// --- LÓGICA DE CATEGORÍAS ---

window.cargarSubcategorias = function(categoriaNombre, subSeleccionada = "") {
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

window.abrirModalExistencias = function(id, nombre) {
    const t = document.getElementById('tituloModalDetalle');
    if (t) t.innerText = `Existencias: ${nombre}`;
    
    const tbodyHist = document.getElementById('tablaBodyProveedor');
    const tbodySeries = document.getElementById('tablaBodySeries');
    const tbodyLotes = document.getElementById('tablaBodyLotes');
    const tbodyPed = document.getElementById('tablaBodyPedimentos');

    const spinner = '<tr><td colspan="10" class="text-center py-3"><span class="spinner-border spinner-border-sm"></span> Cargando...</td></tr>';
    
    if (tbodyHist) tbodyHist.innerHTML = spinner;
    if (tbodySeries) tbodySeries.innerHTML = spinner;
    if (tbodyLotes) tbodyLotes.innerHTML = spinner;
    if (tbodyPed) tbodyPed.innerHTML = spinner;
    
    // Regresar a la primera pestaña
    const firstTab = document.querySelector('#tabExistencias button[id="existencias-tab"]');
    if (firstTab) {
        const tabTrigger = new bootstrap.Tab(firstTab);
        tabTrigger.show();
    }

    mostrarModal('modalDetalleInventario');

    fetch(`${APP_URLS.api_detalle_producto}${id}/`)
        .then(r => r.json())
        .then(data => {
            // 1. EXISTENCIAS / HISTORIAL
            if (tbodyHist) {
                tbodyHist.innerHTML = '';
                if (data.historial && data.historial.length > 0) {
                    data.historial.forEach(i => {
                        tbodyHist.insertAdjacentHTML('beforeend', `
                            <tr>
                                <td class="text-center"><a href="#" onclick="verDetalleDoc('oc', ${i.oc_id}); return false;" class="text-decoration-none">${i.folio_oc}</a></td>
                                <td class="text-center"><a href="#" onclick="verDetalleDoc('rec', ${i.rec_id}); return false;" class="text-decoration-none">${i.folio_rec}</a></td>
                                <td class="text-center small">${i.proveedor}</td>
                                <td class="text-center small">${i.fecha}</td>
                                <td class="text-center fw-bold">${i.cantidad}</td>
                                <td class="text-end small">$${parseFloat(i.costo).toFixed(2)}</td>
                                <td class="text-end pe-3 fw-bold">$${parseFloat(i.total).toFixed(2)}</td>
                            </tr>`);
                    });
                } else {
                    tbodyHist.innerHTML = '<tr><td colspan="7" class="text-center py-3 text-muted italic">Sin movimientos registrados.</td></tr>';
                }
            }

            // 2. SERIES
            if (tbodySeries) {
                tbodySeries.innerHTML = '';
                if (data.series && data.series.length > 0) {
                    data.series.forEach(s => {
                        tbodySeries.insertAdjacentHTML('beforeend', `
                            <tr>
                                <td class="ps-3 fw-bold small">${s.serie}</td>
                                <td class="text-center small">${s.almacen}</td>
                                <td class="text-center small">${s.fecha}</td>
                            </tr>`);
                    });
                } else {
                    tbodySeries.innerHTML = '<tr><td colspan="3" class="text-center py-3 text-muted italic">No hay números de serie registrados.</td></tr>';
                }
            }

            // 3. LOTES
            if (tbodyLotes) {
                tbodyLotes.innerHTML = '';
                if (data.lotes && data.lotes.length > 0) {
                    data.lotes.forEach(l => {
                        tbodyLotes.insertAdjacentHTML('beforeend', `
                            <tr>
                                <td class="ps-3 fw-bold small">${l.lote}</td>
                                <td class="text-center fw-bold">${l.cantidad}</td>
                                <td class="text-center small">${l.almacen}</td>
                                <td class="text-center small">${l.fecha}</td>
                            </tr>`);
                    });
                } else {
                    tbodyLotes.innerHTML = '<tr><td colspan="4" class="text-center py-3 text-muted italic">No hay lotes registrados.</td></tr>';
                }
            }

            // 4. PEDIMENTOS
            if (tbodyPed) {
                tbodyPed.innerHTML = '';
                if (data.pedimentos && data.pedimentos.length > 0) {
                    data.pedimentos.forEach(p => {
                        tbodyPed.insertAdjacentHTML('beforeend', `
                            <tr>
                                <td class="ps-3 fw-bold small">${p.pedimento}</td>
                                <td class="text-center small">${p.aduana}</td>
                                <td class="text-center small">${p.fecha}</td>
                                <td class="text-center small"><a href="#" onclick="verDetalleDoc('rec', ${p.rec_id}); return false;">${p.folio_rec}</a></td>
                            </tr>`);
                    });
                } else {
                    tbodyPed.innerHTML = '<tr><td colspan="4" class="text-center py-3 text-muted italic">No hay pedimentos registrados.</td></tr>';
                }
            }
        });
}

// --- 3. RECETAS (MRP) ---

window.abrirConfigurarReceta = function() {
    const form = document.getElementById('formReceta');
    if (form) form.reset();
    const tbody = document.getElementById('tbodyRecetaEdit');
    if (tbody) tbody.innerHTML = '';
    document.getElementById('totalCostoReceta').innerText = '$0.00';
    document.getElementById('msgVacioReceta').style.display = 'block';
    mostrarModal('modalProduccion');
}

window.cargarRecetaExistente = function() {
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

window.agregarComponenteReceta = function() {
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

window.recalcularTotalesReceta = function() {
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

window.guardarReceta = function() {
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

window.abrirModalReceta = function(id, nombre) {
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

window.syncInputs = function(sourceId, targetId) {
    const source = document.getElementById(sourceId);
    const target = document.getElementById(targetId);
    if (source && target) {
        target.value = source.value;
    }
}

window.abrirModalPrecios = function(id, nombre) {
    const t = document.getElementById('lpNombre');
    if (t) t.innerText = nombre;
    const tp = document.getElementById('lpTablaPrecios'); if (tp) tp.innerHTML = '';
    const tc = document.getElementById('lpTablaCostos'); if (tc) tc.innerHTML = '';
    
    const firstTab = document.querySelector('#lpTab button[id="precios-tab"]');
    if (firstTab) {
        const tabTrigger = new bootstrap.Tab(firstTab);
        tabTrigger.show();
    }

    const modal = document.getElementById('modalListaPrecios');
    modal.dataset.productoId = id;
    mostrarModal('modalListaPrecios');
    
    fetch(APP_URLS.api_producto.replace('0', id))
        .then(r => r.json())
        .then(data => {
            const inputCosto = document.getElementById('lpBaseCosto');
            const inputVenta1 = document.getElementById('lpBaseVenta');
            const inputVenta2 = document.getElementById('lpBaseVentaCosts');

            if (inputCosto) inputCosto.value = data.precio_costo;
            if (inputVenta1) inputVenta1.value = data.precio_venta;
            if (inputVenta2) inputVenta2.value = data.precio_venta;
            
            modal.dataset.ivaPorcentaje = data.iva || 0;
            syncPreciosCostos();

            const baseVenta = parseFloat(data.precio_venta) || 0;
            const baseCosto = parseFloat(data.precio_costo) || 0;

            // --- APLICACIÓN AUTOMÁTICA DE LISTAS MAESTRAS ---
            if (data.listas_maestras && data.listas_maestras.length > 0) {
                data.listas_maestras.forEach(m => {
                    const porc = parseFloat(m.porcentaje_extra) || 0;
                    const montoFijo = parseFloat(m.monto_extra) || 0;
                    
                    if (m.tipo === 'precio') {
                        // Cálculo: Base + % o Base + Monto
                        const final = baseVenta + (baseVenta * (porc / 100)) + montoFijo;
                        agregarFilaPrecio(m.nombre, final.toFixed(2));
                    } else {
                        const final = baseCosto + (baseCosto * (porc / 100)) + montoFijo;
                        agregarFilaCosto(m.nombre, final.toFixed(2));
                    }
                });
            }
            
            // Poblar adicionales específicos (si los hubiera y no chocan por nombre)
            if (data.precios_lista) {
                data.precios_lista.forEach(i => {
                    const existe = Array.from(tp.querySelectorAll('.lp-name')).some(inp => inp.value === i.nombre);
                    if (!existe) agregarFilaPrecio(i.nombre, i.monto);
                });
            }
            if (data.costos_lista) {
                data.costos_lista.forEach(i => {
                    const existe = Array.from(tc.querySelectorAll('.lc-name')).some(inp => inp.value === i.nombre);
                    if (!existe) agregarFilaCosto(i.nombre, i.monto);
                });
            }

            recalcularMargenes();
        });
}

window.syncPreciosCostos = function() {
    const costo = document.getElementById('lpBaseCosto').value || 0;
    const venta = document.getElementById('lpBaseVenta').value || 0;
    
    // Actualizar todos los informativos de costo
    document.getElementById('infoCostoBase').innerText = parseFloat(costo).toFixed(2);
    const infoCostoCosts = document.getElementById('infoCostoBaseCosts');
    if (infoCostoCosts) infoCostoCosts.innerText = parseFloat(costo).toFixed(2);
    
    // El precio informativo de la pestaña 2 ya no es necesario si es editable,
    // pero por si acaso hay algún span con ese ID:
    const infoPrecio = document.getElementById('infoPrecioBase');
    if (infoPrecio) infoPrecio.innerText = parseFloat(venta).toFixed(2);
}

window.agregarFilaPrecio = function(nombre = '', monto = 0) {
    const tp = document.getElementById('lpTablaPrecios');
    tp.insertAdjacentHTML('beforeend', `
        <tr>
            <td class="ps-3"><input type="text" class="form-control form-control-sm lp-name" value="${nombre}" placeholder="Ej: Mayoreo"></td>
            <td class="text-center"><input type="number" step="0.01" class="form-control form-control-sm text-end lp-monto" value="${monto}" oninput="recalcularMargenes()"></td>
            <td class="text-center"><span class="small text-muted lp-iva">$0.00</span></td>
            <td class="text-center"><span class="small fw-bold text-dark lp-total">$0.00</span></td>
            <td class="text-center"><span class="badge bg-light text-dark border lp-margen">0%</span></td>
            <td class="text-center">
                <button class="btn btn-sm text-secondary p-0" onclick="this.closest('tr').remove(); recalcularMargenes();" title="Eliminar">
                    <i class="bi bi-x-circle"></i>
                </button>
            </td>
        </tr>`);
    recalcularMargenes();
}

window.agregarFilaCosto = function(nombre = '', monto = 0) {
    const tc = document.getElementById('lpTablaCostos');
    tc.insertAdjacentHTML('beforeend', `
        <tr>
            <td class="ps-3"><input type="text" class="form-control form-control-sm lc-name" value="${nombre}" placeholder="Ej: Embalaje"></td>
            <td class="text-center"><input type="number" step="0.01" class="form-control form-control-sm text-end lc-monto" value="${monto}" oninput="recalcularMargenes()"></td>
            <td class="text-center"><span class="small text-muted lc-iva">$0.00</span></td>
            <td class="text-center"><span class="small fw-bold text-dark lc-total">$0.00</span></td>
            <td class="text-center"><span class="badge bg-light text-dark border lc-margen">0%</span></td>
            <td class="text-center">
                <button class="btn btn-sm text-secondary p-0" onclick="this.closest('tr').remove(); recalcularMargenes();" title="Eliminar">
                    <i class="bi bi-x-circle"></i>
                </button>
            </td>
        </tr>`);
    recalcularMargenes();
}

window.recalcularMargenes = function() {
    const costoBase = parseFloat(document.getElementById('lpBaseCosto').value) || 0;
    const ventaBase = parseFloat(document.getElementById('lpBaseVenta').value) || 0;
    const ivaPorc = parseFloat(document.getElementById('modalListaPrecios').dataset.ivaPorcentaje) || 0;
    
    // Márgenes para Precios
    document.querySelectorAll('#lpTablaPrecios tr').forEach(tr => {
        const monto = parseFloat(tr.querySelector('.lp-monto').value) || 0;
        const spanIVA = tr.querySelector('.lp-iva');
        const spanTotal = tr.querySelector('.lp-total');
        const spanMargen = tr.querySelector('.lp-margen');
        
        const iva = monto * (ivaPorc / 100);
        const total = monto + iva;
        
        if (spanIVA) spanIVA.innerText = '$' + iva.toFixed(2);
        if (spanTotal) spanTotal.innerText = '$' + total.toFixed(2);
        
        if (costoBase > 0 && monto > 0) {
            const margen = ((monto - costoBase) / monto) * 100;
            spanMargen.innerText = margen.toFixed(1) + '%';
            spanMargen.className = margen > 0 ? 'badge bg-success-subtle text-success border border-success-subtle lp-margen' : 'badge bg-danger-subtle text-danger border border-danger-subtle lp-margen';
        } else {
            spanMargen.innerText = '0%';
            spanMargen.className = 'badge bg-light text-dark border lp-margen';
        }
    });

    // Márgenes para Costos (relativos al Precio Base)
    document.querySelectorAll('#lpTablaCostos tr').forEach(tr => {
        const montoCosto = parseFloat(tr.querySelector('.lc-monto').value) || 0;
        const spanIVA = tr.querySelector('.lc-iva');
        const spanTotal = tr.querySelector('.lc-total');
        const spanMargen = tr.querySelector('.lc-margen');
        
        const iva = montoCosto * (ivaPorc / 100);
        const total = montoCosto + iva;
        
        if (spanIVA) spanIVA.innerText = '$' + iva.toFixed(2);
        if (spanTotal) spanTotal.innerText = '$' + total.toFixed(2);
        
        if (ventaBase > 0 && montoCosto > 0) {
            const margen = ((ventaBase - montoCosto) / ventaBase) * 100;
            spanMargen.innerText = margen.toFixed(1) + '%';
            spanMargen.className = margen > 0 ? 'badge bg-success-subtle text-success border border-success-subtle lc-margen' : 'badge bg-danger-subtle text-danger border border-danger-subtle lc-margen';
        } else {
            spanMargen.innerText = '0%';
            spanMargen.className = 'badge bg-light text-dark border lc-margen';
        }
    });
}

window.guardarCambiosListaPrecios = function() {
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

window.verDetalleDoc = function(tipo, id) {
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

// --- FUNCIONES ESPECÍFICAS DE TRASLADO ---

// Esta función se llama cuando se selecciona un almacén origen
function cargarProductosEnOrigen() {
    const almacenOrigenId = document.getElementById('selectAlmacenOrigen').value;
    const selectProducto = document.getElementById('selectProductoTraslado');
    const inputCantidad = document.getElementById('inputCantidadTraslado');
    const selectLote = document.getElementById('selectLoteTraslado');
    const selectSerie = document.getElementById('selectSerieTraslado');
    const infoStockTotal = document.getElementById('infoStockTotal');
    const infoStockReservado = document.getElementById('infoStockReservado');
    const infoStockDisponible = document.getElementById('infoStockDisponible');
    const tbody = document.getElementById('tbodyTraslado');

    // Resetear campos
    selectProducto.innerHTML = '<option value="">Selecciona almacén origen primero...</option>';
    inputCantidad.value = 1;
    selectLote.disabled = selectSerie.disabled = true;
    selectLote.innerHTML = selectSerie.innerHTML = '<option value="">-- N/A --</option>';
    infoStockTotal.innerText = infoStockReservado.innerText = infoStockDisponible.innerText = '-';
    tbody.innerHTML = '';
    document.getElementById('granTotalTraslado').innerText = '$0.00';

    if (!almacenOrigenId) return;

    // Cargar productos con stock en este almacén
    fetch(`${APP_URLS.api_productos_con_stock}${almacenOrigenId}/`)
        .then(r => r.json())
        .then(data => {
            selectProducto.innerHTML = '<option value="">Seleccionar producto...</option>';
            if (data.length > 0) {
                data.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p.id;
                    opt.dataset.stockInfo = JSON.stringify(p);
                    opt.textContent = `${p.nombre} (Disp: ${p.disponible})`;
                    selectProducto.appendChild(opt);
                });
            } else {
                selectProducto.innerHTML = '<option value="">Sin productos con stock</option>';
            }
        });
}

// Se llama cuando se selecciona un producto en el modal de traslado
function cargarExtrasYStock() {
    const almacenOrigenId = document.getElementById('selectAlmacenOrigen').value;
    const productoId = document.getElementById('selectProductoTraslado').value;
    const inputCantidad = document.getElementById('inputCantidadTraslado');
    const selectLote = document.getElementById('selectLoteTraslado');
    const selectSerie = document.getElementById('selectSerieTraslado');
    const infoStockTotal = document.getElementById('infoStockTotal');
    const infoStockReservado = document.getElementById('infoStockReservado');
    const infoStockDisponible = document.getElementById('infoStockDisponible');

    selectLote.innerHTML = selectSerie.innerHTML = '<option value="">-- N/A --</option>';
    selectLote.disabled = selectSerie.disabled = true;

    if (!almacenOrigenId || !productoId) return;

    const selectedOption = document.getElementById('selectProductoTraslado').selectedOptions[0];
    if (!selectedOption) return;
    const stockInfo = JSON.parse(selectedOption.dataset.stockInfo || '{}');

    infoStockTotal.innerText = stockInfo.total || '0';
    infoStockReservado.innerText = stockInfo.reservado || '0';
    infoStockDisponible.innerText = stockInfo.disponible || '0';
    
    inputCantidad.value = 1;

    if (stockInfo.maneja_lote || stockInfo.maneja_serie) {
        fetch(`${APP_URLS.api_extras_producto}${almacenOrigenId}/${productoId}/`)
            .then(r => r.json())
            .then(data => {
                if (data.length > 0) {
                    const lotes = data.filter(item => item.tipo === 'lote' && item.lote);
                    const series = data.filter(item => item.tipo === 'serie' && item.serie);

                    if (lotes.length > 0) {
                        selectLote.disabled = false;
                        selectLote.innerHTML = '<option value="">Seleccionar Lote...</option>';
                        lotes.forEach(l => {
                            const opt = document.createElement('option');
                            opt.value = l.id;
                            opt.textContent = `${l.lote} (Cant: ${l.cantidad})`;
                            selectLote.appendChild(opt);
                        });
                    }
                    if (series.length > 0) {
                        selectSerie.disabled = false;
                        selectSerie.innerHTML = '<option value="">Seleccionar Serie...</option>';
                        series.forEach(s => {
                            const opt = document.createElement('option');
                            opt.value = s.id;
                            opt.textContent = s.serie;
                            selectSerie.appendChild(opt);
                        });
                    }
                }
            });
    }
}

function agregarItemTraslado() {
    const almacenOrigenId = document.getElementById('selectAlmacenOrigen').value;
    const almacenDestinoId = document.getElementById('selectAlmacenDestino').value;
    const productoSelect = document.getElementById('selectProductoTraslado');
    const productoId = productoSelect.value;
    const productoNombre = productoSelect.options[productoSelect.selectedIndex]?.text.split(' (Disp:')[0];
    const cantidad = parseInt(document.getElementById('inputCantidadTraslado').value);
    const selectLote = document.getElementById('selectLoteTraslado');
    const selectSerie = document.getElementById('selectSerieTraslado');
    
    const extraId = selectLote.value || selectSerie.value || null;
    const extraNombre = selectLote.value ? selectLote.options[selectLote.selectedIndex].text : (selectSerie.value ? selectSerie.options[selectSerie.selectedIndex].text : null);
    
    const disponible = parseInt(document.getElementById('infoStockDisponible').innerText);
    
    if (!almacenOrigenId || !almacenDestinoId || !productoId || !cantidad || cantidad <= 0) {
        alert("Por favor, completa todos los campos.");
        return;
    }

    if (cantidad > disponible) {
        alert(`¡Alerta! La cantidad solicitada (${cantidad}) excede el stock disponible (${disponible}). Las piezas excedentes se transferirán como reservadas.`);
    }

    const tbody = document.getElementById('tbodyTraslado');
    
    // Validar si ya existe este ítem
    const rows = tbody.querySelectorAll('tr');
    for (const row of rows) {
        if (row.dataset.productoId === productoId && row.dataset.extraId === (extraId || 'null')) {
            const cantInput = row.querySelector('.inp-cant-traslado');
            cantInput.value = parseInt(cantInput.value) + cantidad;
            actualizarGranTotal();
            return;
        }
    }

    fetch(`${APP_URLS.api_producto.replace('0', productoId)}`)
        .then(r => r.json())
        .then(prodData => {
            const precioUnitario = parseFloat(prodData.precio_costo);
            const subtotal = cantidad * precioUnitario;
            
            const tr = document.createElement('tr');
            tr.dataset.productoId = productoId;
            tr.dataset.precioUnitario = precioUnitario;
            tr.dataset.extraId = extraId || 'null';

            tr.innerHTML = `
                <td class="ps-3">${productoNombre}</td>
                <td class="text-center">${extraNombre || '--'}</td>
                <td class="text-center">
                    <input type="number" class="form-control form-control-sm text-center inp-cant-traslado" value="${cantidad}" min="1" onchange="actualizarGranTotal()">
                </td>
                <td class="text-end pe-3 fw-bold subtotal-traslado">$${subtotal.toFixed(2)}</td>
                <td class="text-center">
                    <button type="button" class="btn btn-sm text-danger p-0" onclick="this.closest('tr').remove(); actualizarGranTotal();">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
            actualizarGranTotal();
        });
}

function actualizarGranTotal() {
    let total = 0;
    document.querySelectorAll('#tbodyTraslado tr').forEach(tr => {
        const cant = parseInt(tr.querySelector('.inp-cant-traslado').value) || 0;
        const precio = parseFloat(tr.dataset.precioUnitario) || 0;
        const sub = cant * precio;
        tr.querySelector('.subtotal-traslado').innerText = '$' + sub.toFixed(2);
        total += sub;
    });
    document.getElementById('granTotalTraslado').innerText = '$' + total.toFixed(2);
}

function confirmarTraslado() {
    const tbody = document.getElementById('tbodyTraslado');
    const almacenOrigenId = document.getElementById('selectAlmacenOrigen').value;
    const almacenDestinoId = document.getElementById('selectAlmacenDestino').value;

    if (tbody.children.length === 0) {
        alert("Agrega al menos un artículo para trasladar.");
        return;
    }

    const items = [];
    let valid = true;
    tbody.querySelectorAll('tr').forEach(tr => {
        const producto_id = tr.dataset.productoId;
        const cantidad = parseInt(tr.querySelector('.inp-cant-traslado').value);
        const extra_id = tr.dataset.extraId === 'null' ? null : tr.dataset.extraId;
        
        if (isNaN(cantidad) || cantidad <= 0) {
            valid = false;
        }
        items.push({ producto_id, cantidad, extra_id });
    });

    if (!valid) {
        alert("Verifica las cantidades ingresadas.");
        return;
    }

    const dataToSend = {
        almacen_origen: almacenOrigenId,
        almacen_destino: almacenDestinoId,
        items: items
    };

    const btn = document.querySelector('#modalTraslado .btn-brand');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Trasladando...';

    fetch(APP_URLS.api_ejecutar_traslado, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
        body: JSON.stringify(dataToSend)
    })
    .then(r => r.json())
    .then(res => {
        if (res.success) {
            alert(res.message);
            location.reload();
        } else {
            alert("Error: " + res.error);
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-arrow-left-right me-1"></i> Confirmar Traslado';
        }
    })
    .catch(err => {
        console.error(err);
        alert("Error de conexión o servidor.");
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-arrow-left-right me-1"></i> Confirmar Traslado';
    });
}

// --- Inicialización ---
document.addEventListener('DOMContentLoaded', function() {
    // Usamos delegación de eventos para el cambio de almacén origen
    document.addEventListener('change', function(e) {
        if (e.target && e.target.id === 'selectAlmacenOrigen') {
            console.log("Cambiando almacén origen a ID:", e.target.value);
            
            // Limpiar campos dependientes al cambiar origen
            const selectProducto = document.getElementById('selectProductoTraslado');
            const selectLote = document.getElementById('selectLoteTraslado');
            const selectSerie = document.getElementById('selectSerieTraslado');
            const infoStockTotal = document.getElementById('infoStockTotal');
            const infoStockReservado = document.getElementById('infoStockReservado');
            const infoStockDisponible = document.getElementById('infoStockDisponible');
            const tbody = document.getElementById('tbodyTraslado');

            if (selectProducto) {
                selectProducto.innerHTML = '<option value="">Cargando productos...</option>';
            }
            if (selectLote) { selectLote.innerHTML = '<option value="">-- N/A --</option>'; selectLote.disabled = true; }
            if (selectSerie) { selectSerie.innerHTML = '<option value="">-- N/A --</option>'; selectSerie.disabled = true; }
            if (infoStockTotal) infoStockTotal.innerText = '-';
            if (infoStockReservado) infoStockReservado.innerText = '-';
            if (infoStockDisponible) infoStockDisponible.innerText = '-';
            if (tbody) tbody.innerHTML = '';
            
            const granTotal = document.getElementById('granTotalTraslado');
            if (granTotal) granTotal.innerText = '$0.00';

            // Cargar productos con stock
            cargarProductosEnOrigen();
        }
        
        // Listener para cambio de producto en traslado
        if (e.target && e.target.id === 'selectProductoTraslado') {
            cargarExtrasYStock();
        }
    });

    const cantInput = document.getElementById('inputCantidadTraslado');
    if (cantInput) {
        cantInput.addEventListener('input', function() {
            const disponible = parseInt(document.getElementById('infoStockDisponible').innerText) || 0;
            if (parseInt(this.value) > disponible) {
                this.classList.add('is-invalid');
            } else {
                this.classList.remove('is-invalid');
            }
        });
    }
});
// --- FIN TRASLADOS ---

// --- Funciones generales (como las de edición de artículo, etc.) ---
// ... (mantener otras funciones existentes) ...
