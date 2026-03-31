// ============================================
// INVENTARIO.JS — Lógica con Protecciones de Seguridad
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
    recetaTemp = [];
    const tbody = document.getElementById('tbodyRecetaEdit');
    if(tbody) tbody.innerHTML = '';
    const select = document.getElementById('selectRecetaPadre');
    if(select) select.value = "";
    bootstrap.Modal.getOrCreateInstance(document.getElementById('modalProduccion')).show();
}

// --- CATEGORÍAS ---
const selectCategoria = document.getElementById('selectCategoria');
if(selectCategoria) {
    selectCategoria.addEventListener('change', function() {
        const sub = document.getElementById('selectSubcategoria');
        if(!sub) return;
        if (!this.value) { sub.innerHTML = '<option value="">Selecciona...</option>'; sub.disabled = true; return; }
        sub.disabled = false;
        fetch(`${APP_URLS.api_subcategorias}?categoria_nombre=${encodeURIComponent(this.value)}`)
            .then(r => r.json()).then(data => {
                sub.innerHTML = '<option value="">Seleccionar...</option>';
                data.forEach(s => { sub.insertAdjacentHTML('beforeend', `<option value="${s.nombre}">${s.nombre}</option>`); });
            });
    });
}

// --- 1. GESTIÓN DE ARTÍCULOS ---

function resetFormulario() {
    const form = document.getElementById('formCrearArticulo');
    if(form) form.reset();
    safeSetValue('productoId', '');
    if(document.getElementById('checkLote')) document.getElementById('checkLote').checked = false;
    if(document.getElementById('checkSerie')) document.getElementById('checkSerie').checked = false;
    const sub = document.getElementById('selectSubcategoria');
    if(sub) { sub.innerHTML = '<option value="">Selecciona...</option>'; sub.disabled = true; }
}

function cargarProductoEdicion(elemento) {
    const id = elemento.getAttribute('data-id');
    resetFormulario(); 
    document.querySelector('#modalCrearArticulo .modal-title').innerText = "Editar Artículo";

    fetch(APP_URLS.api_producto.replace('0', id))
        .then(r => r.json()).then(data => {
            safeSetValue('productoId', data.id);
            document.querySelector('[name="nombre"]').value = data.nombre;
            document.querySelector('[name="tipo"]').value = data.tipo;
            
            const abast = document.getElementById('selectAbastecimiento');
            if(abast) {
                abast.value = data.tipo_abastecimiento;
                const selectTest = document.getElementById('selectTestCalidad');
                if(selectTest && data.tipo_abastecimiento === 'produccion') { selectTest.disabled = false; selectTest.classList.remove('bg-light'); }
            }
            
            document.querySelector('[name="precio_costo"]').value = data.precio_costo;
            document.querySelector('[name="precio_venta"]').value = data.precio_venta;
            
            bootstrap.Modal.getOrCreateInstance(document.getElementById('modalCrearArticulo')).show();
        });
}

// --- 2. EXISTENCIAS ---

function verDetalleInventario(id, nombre) {
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

let recetaTemp = [];
function cargarRecetaExistente() {
    const prodId = document.getElementById('selectRecetaPadre').value;
    recetaTemp = []; 
    const tbody = document.getElementById('tbodyRecetaEdit');
    if(tbody) tbody.innerHTML = '';
    if(!prodId) return;
    fetch(`${APP_URLS.api_receta}${prodId}/`).then(r => r.json()).then(data => {
        if(data.length > 0) {
            const msg = document.getElementById('msgVacioReceta');
            if(msg) msg.style.display = 'none';
            data.forEach(item => { recetaTemp.push(item); renderFilaReceta(item); });
        }
    });
}

function renderFilaReceta(i) {
    const tbody = document.getElementById('tbodyRecetaEdit');
    if(tbody) tbody.insertAdjacentHTML('beforeend', `<tr><td class="ps-3 small">${i.nombre}</td><td class="text-center">${i.cant}</td><td colspan="2"></td><td class="text-center"><button type="button" class="btn btn-sm text-danger p-0" onclick="this.closest('tr').remove()"><i class="bi bi-trash"></i></button></td></tr>`);
}

function verRecetaProduccion(id, nombre) {
    safeSetText('tituloRecetaModal', nombre);
    const tbody = document.getElementById('tablaBodyRecetaUnica');
    if(tbody) tbody.innerHTML = '';
    bootstrap.Modal.getOrCreateInstance(document.getElementById('modalVerReceta')).show();
    fetch(`${APP_URLS.api_receta}${id}/`).then(r => r.json()).then(data => {
        if(tbody) data.forEach(i => { tbody.insertAdjacentHTML('beforeend', `<tr><td class="ps-3 fw-semibold">${i.nombre}</td><td class="text-center"><span class="badge bg-light text-dark border">${i.cant} pz</span></td></tr>`); });
    });
}

// --- 4. LISTA DE PRECIOS ---

function abrirModalListaPrecios(id, nombre, unidad, costo, venta) {
    safeSetText('lpNombre', nombre);
    safeSetValue('lpBaseCosto', costo);
    safeSetValue('lpBaseVenta', venta);
    
    const tp = document.getElementById('lpTablaPrecios'); if(tp) tp.innerHTML = '';
    const tc = document.getElementById('lpTablaCostos'); if(tc) tc.innerHTML = '';

    bootstrap.Modal.getOrCreateInstance(document.getElementById('modalListaPrecios')).show();

    fetch(APP_URLS.api_producto.replace('0', id)).then(r => r.json()).then(data => {
        if(data.precios_lista && tp) data.precios_lista.forEach(i => agregarPrecioFila(i.nombre, i.monto));
        if(data.costos_lista && tc) data.costos_lista.forEach(i => agregarCostoFila(i.nombre, i.monto));
    });
}

function agregarPrecioFila(n, m) {
    const tp = document.getElementById('lpTablaPrecios');
    if(!tp) return;
    tp.insertAdjacentHTML('beforeend', `<tr><td class="ps-3"><input type="text" class="form-control form-control-sm" value="${n}"></td><td class="text-center"><input type="number" class="form-control form-control-sm text-end" value="${m}"></td><td colspan="2"></td><td class="text-center"><button class="btn btn-sm text-danger p-0" onclick="this.closest('tr').remove()"><i class="bi bi-trash"></i></button></td></tr>`);
}

function agregarCostoFila(n, m) {
    const tc = document.getElementById('lpTablaCostos');
    if(!tc) return;
    tc.insertAdjacentHTML('beforeend', `<tr><td class="ps-3"><input type="text" class="form-control form-control-sm" value="${n}"></td><td class="text-center"><input type="number" class="form-control form-control-sm text-end" value="${m}"></td><td colspan="2"></td><td class="text-center"><button class="btn btn-sm text-danger p-0" onclick="this.closest('tr').remove()"><i class="bi bi-trash"></i></button></td></tr>`);
}
