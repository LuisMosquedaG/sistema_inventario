// ============================================
// INVENTARIO.JS — Lógica Simplificada
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

// Función Maestra para abrir modales de forma segura
function openModal(id) {
    const el = document.getElementById(id);
    if (!el) { console.error("No se encontró el modal:", id); return; }
    const modal = bootstrap.Modal.getOrCreateInstance(el);
    modal.show();
}

// --- 1. GESTIÓN DE ARTÍCULOS ---

function abrirNuevoArticulo() {
    const form = document.getElementById('formCrearArticulo');
    if(form) form.reset();
    document.getElementById('productoId').value = '';
    document.querySelector('#modalCrearArticulo .modal-title').innerText = "Nuevo Artículo";
    openModal('modalCrearArticulo');
}

function cargarProductoEdicion(id) {
    document.querySelector('#modalCrearArticulo .modal-title').innerText = "Editar Artículo";
    fetch(APP_URLS.api_producto.replace('0', id))
        .then(r => r.json()).then(data => {
            document.getElementById('productoId').value = data.id;
            document.querySelector('[name="nombre"]').value = data.nombre;
            document.querySelector('[name="precio_costo"]').value = data.precio_costo;
            document.querySelector('[name="precio_venta"]').value = data.precio_venta;
            openModal('modalCrearArticulo');
        });
}

// --- 2. EXISTENCIAS ---

function abrirModalExistencias(id, nombre) {
    document.getElementById('tituloModalDetalle').innerText = `Existencias: ${nombre}`;
    const tbody = document.getElementById('tablaBodyProveedor');
    if(tbody) tbody.innerHTML = '<tr><td colspan="7" class="text-center">Cargando...</td></tr>';
    
    openModal('modalDetalleInventario');

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
    const form = document.getElementById('formReceta');
    if(form) form.reset();
    document.getElementById('tbodyRecetaEdit').innerHTML = '';
    openModal('modalProduccion');
}

function abrirModalReceta(id, nombre) {
    document.getElementById('tituloRecetaModal').innerText = nombre;
    const tbody = document.getElementById('tablaBodyRecetaUnica');
    if(tbody) tbody.innerHTML = '<tr><td colspan="2" class="text-center">Cargando...</td></tr>';
    
    openModal('modalVerReceta');
    
    fetch(`${APP_URLS.api_receta}${id}/`).then(r => r.json()).then(data => {
        if(tbody) {
            tbody.innerHTML = '';
            data.forEach(i => { tbody.insertAdjacentHTML('beforeend', `<tr><td class="ps-3 fw-semibold">${i.nombre}</td><td class="text-center"><span class="badge bg-light text-dark border">${i.cant} pz</span></td></tr>`); });
        }
    });
}

// --- 4. PRECIOS ---

function abrirModalPrecios(id, nombre) {
    const label = document.getElementById('lpNombre');
    if(label) label.innerText = nombre;
    
    const tp = document.getElementById('lpTablaPrecios'); if(tp) tp.innerHTML = '';
    const tc = document.getElementById('lpTablaCostos'); if(tc) tc.innerHTML = '';

    openModal('modalListaPrecios');

    fetch(APP_URLS.api_producto.replace('0', id)).then(r => r.json()).then(data => {
        const bc = document.getElementById('lpBaseCosto'); if(bc) bc.value = data.precio_costo;
        const bv = document.getElementById('lpBaseVenta'); if(bv) bv.value = data.precio_venta;
        if(data.precios_lista && tp) data.precios_lista.forEach(i => {
            tp.insertAdjacentHTML('beforeend', `<tr><td class="ps-3"><input type="text" class="form-control form-control-sm" value="${i.nombre}"></td><td class="text-center"><input type="number" class="form-control form-control-sm text-end" value="${i.monto}"></td><td colspan="2"></td><td class="text-center"><button class="btn btn-sm text-danger p-0" onclick="this.closest('tr').remove()"><i class="bi bi-trash"></i></button></td></tr>`);
        });
    });
}
