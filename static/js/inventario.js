// ============================================
// INVENTARIO.JS — Lógica con Protecciones
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

function safeSetText(id, text) {
    const el = document.getElementById(id);
    if (el) el.innerText = text;
}

function safeSetValue(id, val) {
    const el = document.getElementById(id);
    if (el) el.value = val;
}

// --- BOTONES DE CABECERA ---

function abrirNuevoArticulo() {
    resetFormulario();
    document.querySelector('#modalCrearArticulo .modal-title').innerText = "Nuevo Artículo";
    bootstrap.Modal.getOrCreateInstance(document.getElementById('modalCrearArticulo')).show();
}

function abrirConfigurarReceta() {
    document.getElementById('formReceta').reset();
    document.getElementById('tbodyRecetaEdit').innerHTML = '';
    bootstrap.Modal.getOrCreateInstance(document.getElementById('modalProduccion')).show();
}

// --- 1. GESTIÓN DE ARTÍCULOS ---

function resetFormulario() {
    const form = document.getElementById('formCrearArticulo');
    if(form) form.reset();
    safeSetValue('productoId', '');
}

function cargarProductoEdicion(id) {
    resetFormulario(); 
    document.querySelector('#modalCrearArticulo .modal-title').innerText = "Editar Artículo";

    fetch(APP_URLS.api_producto.replace('0', id))
        .then(r => r.json()).then(data => {
            safeSetValue('productoId', data.id);
            document.querySelector('[name="nombre"]').value = data.nombre;
            document.querySelector('[name="precio_costo"]').value = data.precio_costo;
            document.querySelector('[name="precio_venta"]').value = data.precio_venta;
            bootstrap.Modal.getOrCreateInstance(document.getElementById('modalCrearArticulo')).show();
        });
}

// --- 2. EXISTENCIAS ---

function abrirModalExistencias(id, nombre) {
    safeSetText('tituloModalDetalle', `Existencias: ${nombre}`);
    const tbody = document.getElementById('tablaBodyProveedor');
    if(tbody) tbody.innerHTML = '<tr><td colspan="7" class="text-center">Cargando...</td></tr>';
    
    bootstrap.Modal.getOrCreateInstance(document.getElementById('modalDetalleInventario')).show();

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

function abrirModalReceta(id, nombre) {
    safeSetText('tituloRecetaModal', nombre);
    const tbody = document.getElementById('tablaBodyRecetaUnica');
    if(tbody) tbody.innerHTML = '<tr><td colspan="2" class="text-center">Cargando...</td></tr>';
    
    bootstrap.Modal.getOrCreateInstance(document.getElementById('modalVerReceta')).show();
    
    fetch(`${APP_URLS.api_receta}${id}/`).then(r => r.json()).then(data => {
        if(tbody) {
            tbody.innerHTML = '';
            data.forEach(i => { tbody.insertAdjacentHTML('beforeend', `<tr><td class="ps-3 fw-semibold">${i.nombre}</td><td class="text-center">${i.cant} pz</td></tr>`); });
        }
    });
}

// --- 4. PRECIOS ---

function abrirModalPrecios(id, nombre) {
    safeSetText('lpNombre', nombre);
    const tp = document.getElementById('lpTablaPrecios'); if(tp) tp.innerHTML = '';
    const tc = document.getElementById('lpTablaCostos'); if(tc) tc.innerHTML = '';

    bootstrap.Modal.getOrCreateInstance(document.getElementById('modalListaPrecios')).show();

    fetch(APP_URLS.api_producto.replace('0', id)).then(r => r.json()).then(data => {
        safeSetValue('lpBaseCosto', data.precio_costo);
        safeSetValue('lpBaseVenta', data.precio_venta);
        if(data.precios_lista && tp) data.precios_lista.forEach(i => {
            tp.insertAdjacentHTML('beforeend', `<tr><td class="ps-3"><input type="text" class="form-control form-control-sm" value="${i.nombre}"></td><td class="text-center"><input type="number" class="form-control form-control-sm text-end" value="${i.monto}"></td><td colspan="2"></td><td class="text-center"><button class="btn btn-sm text-danger p-0" onclick="this.closest('tr').remove()"><i class="bi bi-trash"></i></button></td></tr>`);
        });
    });
}
