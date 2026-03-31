// ============================================
// INVENTARIO.JS — Lógica Reforzada
// ============================================

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

// --- 1. GESTIÓN DE ARTÍCULOS ---

function abrirNuevoArticulo() {
    const form = document.getElementById('formCrearArticulo');
    if(form) form.reset();
    const idF = document.getElementById('productoId');
    if(idF) idF.value = '';
    const modal = new bootstrap.Modal(document.getElementById('modalCrearArticulo'));
    modal.show();
}

function cargarProductoEdicion(id) {
    fetch(APP_URLS.api_producto.replace('0', id))
        .then(r => r.json()).then(data => {
            const idF = document.getElementById('productoId');
            if(idF) idF.value = data.id;
            document.querySelector('[name="nombre"]').value = data.nombre;
            document.querySelector('[name="precio_costo"]').value = data.precio_costo;
            document.querySelector('[name="precio_venta"]').value = data.precio_venta;
            const modal = new bootstrap.Modal(document.getElementById('modalCrearArticulo'));
            modal.show();
        });
}

function guardarProducto() {
    const form = document.getElementById('formCrearArticulo');
    const id = document.getElementById('productoId').value;
    let url = id ? APP_URLS.api_actualizar_producto.replace('0', id) : APP_URLS.api_crear_producto;
    fetch(url, {
        method: 'POST',
        body: new FormData(form),
        headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCookie('csrftoken') }
    }).then(r => r.json()).then(data => { if(data.success) location.reload(); });
}

// --- 2. EXISTENCIAS ---

function abrirModalExistencias(id, nombre) {
    const t = document.getElementById('tituloModalDetalle');
    if(t) t.innerText = `Existencias: ${nombre}`;
    const tbody = document.getElementById('tablaBodyProveedor');
    if(tbody) tbody.innerHTML = '<tr><td colspan="7" class="text-center py-3">Cargando...</td></tr>';
    
    const modal = new bootstrap.Modal(document.getElementById('modalDetalleInventario'));
    modal.show();

    fetch(`${APP_URLS.api_detalle_producto}${id}/`).then(r => r.json()).then(data => {
        if(tbody) {
            tbody.innerHTML = '';
            if (data.historial) data.historial.forEach(i => {
                tbody.insertAdjacentHTML('beforeend', `<tr><td class="text-center">${i.folio_oc}</td><td class="text-center">${i.folio_rec}</td><td class="text-center">${i.proveedor}</td><td class="text-center">${i.fecha}</td><td class="text-center">${i.cantidad}</td><td class="text-end">$${i.costo.toFixed(2)}</td><td class="text-end">$${i.total.toFixed(2)}</td></tr>`);
            });
        }
    });
}

// --- 3. RECETAS ---

function abrirConfigurarReceta() {
    const modal = new bootstrap.Modal(document.getElementById('modalProduccion'));
    modal.show();
}

function abrirModalReceta(id, nombre) {
    const t = document.getElementById('tituloRecetaModal');
    if(t) t.innerText = nombre;
    const tbody = document.getElementById('tablaBodyRecetaUnica');
    if(tbody) tbody.innerHTML = '<tr><td colspan="2" class="text-center py-3">Cargando...</td></tr>';
    
    const modal = new bootstrap.Modal(document.getElementById('modalVerReceta'));
    modal.show();
    
    fetch(`${APP_URLS.api_receta}${id}/`).then(r => r.json()).then(data => {
        if(tbody) {
            tbody.innerHTML = '';
            data.forEach(i => { tbody.insertAdjacentHTML('beforeend', `<tr><td class="ps-3 fw-semibold">${i.nombre}</td><td class="text-center">${i.cant} pz</td></tr>`); });
        }
    });
}

// --- 4. PRECIOS ---

function abrirModalPrecios(id, nombre) {
    const t = document.getElementById('lpNombre');
    if(t) t.innerText = nombre;
    const tp = document.getElementById('lpTablaPrecios'); if(tp) tp.innerHTML = '';
    const tc = document.getElementById('lpTablaCostos'); if(tc) tc.innerHTML = '';

    const modal = new bootstrap.Modal(document.getElementById('modalListaPrecios'));
    modal.show();

    fetch(APP_URLS.api_producto.replace('0', id)).then(r => r.json()).then(data => {
        const bc = document.getElementById('lpBaseCosto'); if(bc) bc.value = data.precio_costo;
        const bv = document.getElementById('lpBaseVenta'); if(bv) bv.value = data.precio_venta;
        if(data.precios_lista && tp) data.precios_lista.forEach(i => {
            tp.insertAdjacentHTML('beforeend', `<tr><td class="ps-3"><input type="text" class="form-control form-control-sm" value="${i.nombre}"></td><td class="text-center"><input type="number" class="form-control form-control-sm text-end" value="${i.monto}"></td><td colspan="2"></td><td class="text-center"><button class="btn btn-sm text-danger p-0" onclick="this.closest('tr').remove()"><i class="bi bi-trash"></i></button></td></tr>`);
        });
    });
}
