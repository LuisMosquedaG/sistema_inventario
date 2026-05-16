// ============================================
// COTIZACIONES.JS — Lógica Reforzada y Centralizada
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
    if (!el) return null;
    const modal = bootstrap.Modal.getOrCreateInstance(el);
    modal.show();
    return modal;
}

// --- FUNCIÓN DE CARGA DE CONTACTOS ---
window.cargarContactos = function(clienteId, preseleccionadoId = null) {
    const wrapper = document.getElementById('wrapperContacto');
    if (!wrapper) return;
    
    const inputBusqueda = document.getElementById('contacto_busqueda');
    const fakeDisplay = document.getElementById('contacto_display_fake');
    const hiddenInput = document.getElementById('contacto_id_input');
    const containerOptions = wrapper.querySelector('.custom-options');

    hiddenInput.value = "";
    inputBusqueda.value = "";
    inputBusqueda.disabled = true;
    fakeDisplay.innerHTML = '<span class="text-muted" style="font-weight:400;">Cargando...</span>';
    containerOptions.innerHTML = '<span class="custom-option disabled text-muted small">Cargando contactos...</span>';

    if (!clienteId) {
        fakeDisplay.innerHTML = '<span class="text-muted" style="font-weight:400;">Selecciona cliente primero...</span>';
        containerOptions.innerHTML = '<span class="custom-option disabled text-muted small">Selecciona un cliente para ver contactos</span>';
        return;
    }

    fetch(`/api/clientes/${clienteId}/contactos/`)
        .then(r => r.json())
        .then(data => {
            if (data.length > 0) {
                containerOptions.innerHTML = '';
                data.forEach(c => {
                    const opt = document.createElement('span');
                    opt.className = 'custom-option';
                    opt.setAttribute('data-value', c.id);
                    opt.setAttribute('data-search', c.nombre);
                    opt.innerText = c.nombre;
                    containerOptions.appendChild(opt);

                    if (preseleccionadoId && String(c.id) === String(preseleccionadoId)) {
                        opt.classList.add('selected');
                        hiddenInput.value = c.id;
                        fakeDisplay.innerHTML = c.nombre;
                        fakeDisplay.setAttribute('title', c.nombre);
                    }
                });
                inputBusqueda.disabled = false;
                if (!preseleccionadoId) {
                    fakeDisplay.innerHTML = '<span class="text-muted" style="font-weight:400;">Seleccionar contacto...</span>';
                }
            } else {
                fakeDisplay.innerHTML = '<span class="text-muted" style="font-weight:400;">Sin contactos</span>';
                containerOptions.innerHTML = '<span class="custom-option disabled text-muted small">El cliente no tiene contactos asignados</span>';
                inputBusqueda.disabled = true;
            }
        })
        .catch(err => {
            console.error(err);
            fakeDisplay.innerHTML = '<span class="text-danger small">Error al cargar</span>';
        });
};

// 2. FUNCIÓN: Agregar o Actualizar en la lista
function agregarALista() {
    const select = document.getElementById('selectProductoAgregar');
    const productId = select.value;
    const fakeProd = document.getElementById('producto_display_fake');
    const productName = fakeProd.innerText.trim();
    const cantidad = document.getElementById('inputCantidadAgregar').value;
    const precio = document.getElementById('inputPrecioAgregar').value;
    const total = (parseFloat(cantidad) * parseFloat(precio)).toFixed(2);
    const editIndex = document.getElementById('edit_index').value;

    if (!productId || productId === "" || cantidad <= 0) {
        alert("Por favor selecciona un producto y una cantidad válida.");
        return;
    }

    const filaHtml = `
        <td class="ps-3">
            <div class="fw-semibold small text-dark">${productName}</div>
            <input type="hidden" name="producto_id[]" value="${productId}">
        </td>
        <td class="text-center">
            <span class="small text-dark">${cantidad}</span>
            <input type="hidden" name="cantidad[]" value="${cantidad}">
        </td>
        <td class="text-end">
            <span class="small text-muted">$${parseFloat(precio).toFixed(2)}</span>
            <input type="hidden" name="precio_unitario[]" value="${precio}">
        </td>
        <td class="text-end">
            <span class="fw-bold small text-dark">$${total}</span>
        </td>
        <td class="text-center">
            <div class="d-flex justify-content-center gap-2">
                <button type="button" class="btn btn-sm text-primary p-0" onclick="editarFila(this)">
                    <i class="bi bi-pencil-fill"></i>
                </button>
                <button type="button" class="btn btn-sm text-danger p-0" onclick="eliminarDeLista(this)">
                    <i class="bi bi-x-circle-fill"></i>
                </button>
            </div>
        </td>
    `;

    if (editIndex !== "-1") {
        const tbody = document.getElementById('tablaCuerpo');
        const fila = tbody.rows[parseInt(editIndex)];
        fila.innerHTML = filaHtml;
        const btnAgregar = document.querySelector('button[onclick="agregarALista()"]');
        btnAgregar.innerHTML = '<i class="bi bi-plus-lg"></i>';
        document.getElementById('edit_index').value = "-1";
    } else {
        const tbody = document.getElementById('tablaCuerpo');
        const nuevaFila = document.createElement('tr');
        nuevaFila.innerHTML = filaHtml;
        tbody.appendChild(nuevaFila);
        document.getElementById('mensajeVacio').style.display = 'none';
    }

    select.value = "";
    document.getElementById('producto_busqueda').value = "";
    document.getElementById('producto_display_fake').innerHTML = '<span class="text-muted" style="font-weight:400;">Seleccionar...</span>';
    document.getElementById('inputCantidadAgregar').value = 1;
    document.getElementById('inputPrecioAgregar').value = "0.00";
    const selectLista = document.getElementById('selectListaPrecio');
    if (selectLista) selectLista.value = "";
    calcularGranTotalLista();
}

function editarFila(boton) {
    const fila = boton.closest('tr');
    const tbody = document.getElementById('tablaCuerpo');
    const index = Array.from(tbody.rows).indexOf(fila);
    const productId = fila.querySelector('input[name="producto_id[]"]').value;
    const cantidad = fila.querySelector('input[name="cantidad[]"]').value;
    const precio = fila.querySelector('input[name="precio_unitario[]"]').value;

    const select = document.getElementById('selectProductoAgregar');
    select.value = productId;
    const option = document.querySelector(`#wrapperProductoAgregar .custom-option[data-value="${productId}"]`);
    if (option) {
        const fakeProd = document.getElementById('producto_display_fake');
        fakeProd.innerHTML = option.innerHTML;
        fakeProd.setAttribute('title', option.textContent.trim());
        document.getElementById('producto_busqueda').value = '';
        select.setAttribute('data-base-precio', option.getAttribute('data-precio'));
    }

    document.getElementById('inputCantidadAgregar').value = cantidad;
    document.getElementById('inputPrecioAgregar').value = precio;
    document.getElementById('edit_index').value = index;
    const btnAgregar = document.querySelector('button[onclick="agregarALista()"]');
    btnAgregar.innerHTML = '<i class="bi bi-check-lg"></i>';
}

function eliminarDeLista(boton) {
    const fila = boton.closest('tr');
    fila.remove();
    if (document.getElementById('tablaCuerpo').children.length === 0) {
        document.getElementById('mensajeVacio').style.display = 'block';
    }
    document.getElementById('edit_index').value = "-1";
    const btnAgregar = document.querySelector('button[onclick="agregarALista()"]');
    btnAgregar.innerHTML = '<i class="bi bi-plus-lg"></i>';
    calcularGranTotalLista();
}

function calcularGranTotalLista() {
    let granTotal = 0;
    document.querySelectorAll('#tablaCuerpo tr').forEach(fila => {
        const textoTotal = fila.cells[3].innerText.replace('$', '').replace(',', '');
        granTotal += parseFloat(textoTotal);
    });
    document.getElementById('granTotalModal').innerText = '$' + granTotal.toFixed(2);
}

function agregarFilaVisual(id, nombre, cant, precio, total) {
    const filaHtml = `
        <tr>
            <td class="ps-3">
                <div class="fw-semibold small text-dark">${nombre}</div>
                <input type="hidden" name="producto_id[]" value="${id}">
            </td>
            <td class="text-center">
                <span class="small text-dark">${cant}</span>
                <input type="hidden" name="cantidad[]" value="${cant}">
            </td>
            <td class="text-end">
                <span class="small text-muted">$${parseFloat(precio).toFixed(2)}</span>
                <input type="hidden" name="precio_unitario[]" value="${precio}">
            </td>
            <td class="text-end">
                <span class="fw-bold small text-dark">$${total}</span>
            </td>
            <td class="text-center">
                <div class="d-flex justify-content-center gap-2">
                    <button type="button" class="btn btn-sm text-primary p-0" onclick="editarFila(this)">
                        <i class="bi bi-pencil-fill"></i>
                    </button>
                    <button type="button" class="btn btn-sm text-danger p-0" onclick="eliminarDeLista(this)">
                        <i class="bi bi-x-circle-fill"></i>
                    </button>
                </div>
            </td>
        </tr>
    `;
    document.getElementById('tablaCuerpo').insertAdjacentHTML('beforeend', filaHtml);
}

window.limpiarModalCotizacion = function() {
    const form = document.getElementById('formCotizacion');
    if (!form) return;
    form.reset();
    form.action = "/cotizaciones/crear/";
    document.querySelector('.modal-title').innerHTML = '<i class="bi bi-file-earmark-plus me-2" style="color: #00b8b9;"></i> Nueva Cotización';
    document.getElementById('cliente_id_input').value = "";
    document.getElementById('cliente_busqueda').value = "";
    document.getElementById('cliente_display_fake').innerHTML = '<span class="text-muted" style="font-weight:400;">Buscar cliente...</span>';
    
    document.getElementById('contacto_id_input').value = "";
    document.getElementById('contacto_busqueda').value = "";
    document.getElementById('contacto_busqueda').disabled = true;
    document.getElementById('contacto_display_fake').innerHTML = '<span class="text-muted" style="font-weight:400;">Selecciona cliente primero...</span>';

    document.getElementById('tablaCuerpo').innerHTML = '';
    document.getElementById('mensajeVacio').style.display = 'block';
    document.getElementById('granTotalModal').innerText = '$0.00';
    document.getElementById('selectProductoAgregar').value = "";
    document.getElementById('producto_busqueda').value = "";
    document.getElementById('producto_display_fake').innerHTML = '<span class="text-muted" style="font-weight:400;">Seleccionar...</span>';
    document.getElementById('inputCantidadAgregar').value = 1;
    document.getElementById('inputPrecioAgregar').value = "0.00";
    document.getElementById('edit_index').value = "-1";
    const selectLista = document.getElementById('selectListaPrecio');
    if (selectLista) selectLista.value = "";
    const btnAgregarArt = document.querySelector('button[onclick="agregarALista()"]');
    if (btnAgregarArt) btnAgregarArt.innerHTML = '<i class="bi bi-plus-lg"></i>';
    document.getElementById('cliente_busqueda').classList.remove('input-cliente-seleccionado');
};

document.addEventListener('click', function(e) {
    if (e.target.closest('[data-bs-target="#modalNuevaCotizacion"]') && !e.target.closest('.icon-action')) {
        if (!e.target.closest('[onclick^="cargarParaEdicion"]')) {
            limpiarModalCotizacion();
        }
    }
});

// ==========================================
// VER COTIZACIÓN
// ==========================================
window.verCotizacion = function(id) {
    const tablaVer = document.getElementById('ver_tabla_cuerpo');
    tablaVer.innerHTML = '<tr><td colspan="4" class="text-center py-3"><div class="spinner-border spinner-border-sm text-primary"></div> Cargando...</td></tr>';
    fetch(`/cotizaciones/api/${id}/`)
        .then(response => response.json())
        .then(data => {
            if(data.error) { alert(data.error); return; }
            document.getElementById('ver_folio').innerText = data.folio_completo;
            document.getElementById('ver_imprimir_btn').href = `/cotizaciones/imprimir/${id}/`;
            document.getElementById('ver_cliente').innerText = data.cliente_nombre;
            document.getElementById('ver_contacto').innerText = data.contacto_nombre || 'Sin contacto';
            document.getElementById('ver_fecha_inicio').innerText = data.fecha_inicio;
            document.getElementById('ver_fecha_fin').innerText = data.fecha_fin;
            document.getElementById('ver_origen').innerText = data.origen || '--';
            document.getElementById('ver_direccion').innerText = data.direccion_entrega || '--';
            tablaVer.innerHTML = '';
            let totalG = 0;
            data.detalles.forEach(det => {
                const fila = `
                    <tr>
                        <td class="ps-3"><div class="fw-semibold small text-dark">${det.producto_nombre}</div></td>
                        <td class="text-center small">${det.cantidad}</td>
                        <td class="text-end small text-muted">$${parseFloat(det.precio).toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                        <td class="text-end pe-3 fw-bold small text-dark">$${parseFloat(det.total).toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                    </tr>
                `;
                tablaVer.insertAdjacentHTML('beforeend', fila);
                totalG += parseFloat(det.total);
            });
            if (data.detalles.length === 0) {
                tablaVer.innerHTML = '<tr><td colspan="4" class="text-center py-3 text-muted fst-italic">No hay artículos en esta cotización.</td></tr>';
            }
            document.getElementById('ver_gran_total').innerText = '$' + totalG.toLocaleString('en-US', {minimumFractionDigits: 2});
            mostrarModal('modalVerCotizacion');
        })
        .catch(error => console.error('Error:', error));
};

window.cargarParaEdicion = function(id) {
    const form = document.getElementById('formCotizacion');
    form.reset();
    document.getElementById('tablaCuerpo').innerHTML = ''; 
    document.getElementById('granTotalModal').innerText = '$0.00';
    document.getElementById('mensajeVacio').style.display = 'block';
    document.getElementById('selectProductoAgregar').value = "";
    document.getElementById('producto_busqueda').value = "";
    document.getElementById('producto_display_fake').innerHTML = '<span class="text-muted" style="font-weight:400;">Seleccionar...</span>';
    document.getElementById('inputCantidadAgregar').value = 1;
    document.getElementById('inputPrecioAgregar').value = "0.00";
    document.getElementById('edit_index').value = "-1";
    const btnAgregarArt = document.querySelector('button[onclick="agregarALista()"]');
    if (btnAgregarArt) btnAgregarArt.innerHTML = '<i class="bi bi-plus-lg"></i>';
    document.querySelector('.modal-title').innerHTML = '<i class="bi bi-pencil-square me-2" style="color: #00b8b9;"></i> Editar Cotización #' + id;
    form.action = `/cotizaciones/actualizar/${id}/`;
    fetch(`/cotizaciones/api/${id}/`)
        .then(response => response.json())
        .then(data => {
            if(data.error) { alert(data.error); return; }
            document.querySelector('input[name="fecha_inicio"]').value = data.fecha_inicio;
            document.querySelector('input[name="fecha_fin"]').value = data.fecha_fin;
            document.querySelector('input[name="origen"]').value = data.origen;
            document.querySelector('input[name="direccion_entrega"]').value = data.direccion_entrega;
            
            // Simular selección de cliente
            const optionCliente = document.querySelector(`#wrapperCliente .custom-option[data-value="${data.cliente}"]`);
            if (optionCliente) {
                // Forzamos el mousedown delegado para cargar dirección y contactos
                const mdown = new MouseEvent('mousedown', { bubbles: true, cancelable: true });
                optionCliente.dispatchEvent(mdown);
            }

            let totalAcumulado = 0;
            data.detalles.forEach(det => {
                agregarFilaVisual(det.producto_id, det.producto_nombre, det.cantidad, det.precio, det.total);
                totalAcumulado += parseFloat(det.total);
            });
            if(data.detalles.length > 0) { document.getElementById('mensajeVacio').style.display = 'none'; }
            document.getElementById('granTotalModal').innerText = '$' + totalAcumulado.toFixed(2);
            
            if (data.contacto_id) {
                setTimeout(() => {
                    cargarContactos(data.cliente, data.contacto_id);
                }, 500);
            }
            mostrarModal('modalNuevaCotizacion');
        });
};

document.addEventListener('DOMContentLoaded', function() {
    let isSelectingGlobal = false;

    // --- LÓGICA DE PRODUCTOS ---
    const wrapperP = document.getElementById('wrapperProductoAgregar');
    if (wrapperP) {
        const selP = wrapperP.querySelector('.custom-select');
        const inpP = document.getElementById('producto_busqueda');
        const fakeP = document.getElementById('producto_display_fake');
        const hidP = document.getElementById('selectProductoAgregar');
        const optsP = wrapperP.querySelectorAll('.custom-option');

        const updateP = () => { fakeP.style.opacity = (document.activeElement === inpP || inpP.value.length > 0) ? "0" : "1"; };
        const resetP = () => { optsP.forEach(o => o.style.display = 'flex'); };

        inpP.addEventListener('focus', () => { resetP(); selP.classList.add('open'); updateP(); });
        inpP.addEventListener('blur', () => { setTimeout(() => { selP.classList.remove('open'); updateP(); }, 150); });
        inpP.addEventListener('input', function() {
            updateP();
            const t = this.value.toLowerCase();
            optsP.forEach(o => { o.style.display = o.getAttribute('data-search').toLowerCase().includes(t) ? 'flex' : 'none'; });
            selP.classList.add('open');
        });

        optsP.forEach(opt => {
            opt.addEventListener('click', function() {
                optsP.forEach(o => o.classList.remove('selected'));
                this.classList.add('selected');
                fakeP.innerHTML = this.innerHTML;
                fakeP.setAttribute('title', this.textContent.trim());
                inpP.value = '';
                const base = this.getAttribute('data-precio') || "0.00";
                hidP.value = this.getAttribute('data-value');
                hidP.setAttribute('data-base-precio', base);
                const sl = document.getElementById('selectListaPrecio');
                if (sl) sl.value = "";
                document.getElementById('inputPrecioAgregar').value = base;
                updateP();
            });
        });
    }

    // --- LÓGICA DE CLIENTES (DELEGADA) ---
    const wrapperC = document.getElementById('wrapperCliente');
    if (wrapperC) {
        const selC = wrapperC.querySelector('.custom-select');
        const inpC = document.getElementById('cliente_busqueda');
        const fakeC = document.getElementById('cliente_display_fake');
        const hidC = document.getElementById('cliente_id_input');
        const optsC = wrapperC.querySelectorAll('.custom-option:not(.disabled)');

        const updateC = () => { fakeC.style.opacity = (document.activeElement === inpC || inpC.value.length > 0) ? "0" : "1"; };
        const resetC = () => { optsC.forEach(o => o.style.display = 'flex'); };

        inpC.addEventListener('focus', () => { if(!isSelectingGlobal) { resetC(); selC.classList.add('open'); updateC(); } });
        inpC.addEventListener('input', function() {
            fakeC.innerHTML = `<span class="typing-text">${this.value}</span>`;
            updateC();
            const t = this.value.toLowerCase();
            optsC.forEach(o => { o.style.display = o.getAttribute('data-search').toLowerCase().includes(t) ? 'flex' : 'none'; });
            selC.classList.add('open');
        });

        wrapperC.addEventListener('mousedown', function(e) {
            const option = e.target.closest('.custom-option');
            if (!option || option.classList.contains('disabled')) return;
            e.preventDefault(); e.stopPropagation();
            isSelectingGlobal = true;
            selC.classList.remove('open');
            inpC.blur();
            optsC.forEach(opt => opt.classList.remove('selected'));
            option.classList.add('selected');
            inpC.value = ""; 
            fakeC.innerHTML = option.innerHTML;
            fakeC.setAttribute('title', option.textContent.trim());
            hidC.value = option.getAttribute('data-value');
            const dir = ['data-calle', 'data-num-ext', 'data-colonia', 'data-estado'].map(a => option.getAttribute(a)).filter(v => v).join(', ');
            const di = document.querySelector('input[name="direccion_entrega"]');
            if(di) di.value = dir;
            cargarContactos(hidC.value);
            updateC();
            setTimeout(() => { isSelectingGlobal = false; }, 200);
        });
    }

    // --- LÓGICA DE CONTACTOS (DELEGADA) ---
    const wrapperCo = document.getElementById('wrapperContacto');
    if (wrapperCo) {
        const selCo = wrapperCo.querySelector('.custom-select');
        const inpCo = document.getElementById('contacto_busqueda');
        const fakeCo = document.getElementById('contacto_display_fake');
        const hidCo = document.getElementById('contacto_id_input');

        const updateCo = () => { fakeCo.style.opacity = (document.activeElement === inpCo || inpCo.value.length > 0) ? "0" : "1"; };
        const resetCo = () => { wrapperCo.querySelectorAll('.custom-option:not(.disabled)').forEach(o => o.style.display = 'flex'); };

        inpCo.addEventListener('focus', () => { if(!isSelectingGlobal) { resetCo(); selCo.classList.add('open'); updateCo(); } });
        inpCo.addEventListener('input', function() {
            fakeCo.innerHTML = `<span class="typing-text">${this.value}</span>`;
            updateCo();
            const t = this.value.toLowerCase();
            wrapperCo.querySelectorAll('.custom-option:not(.disabled)').forEach(o => {
                o.style.display = o.getAttribute('data-search').toLowerCase().includes(t) ? 'flex' : 'none';
            });
            selCo.classList.add('open');
        });

        wrapperCo.addEventListener('mousedown', function(e) {
            const option = e.target.closest('.custom-option');
            if (!option || option.classList.contains('disabled')) return;
            e.preventDefault(); e.stopPropagation();
            isSelectingGlobal = true;
            selCo.classList.remove('open');
            inpCo.blur();
            wrapperCo.querySelectorAll('.custom-option').forEach(opt => opt.classList.remove('selected'));
            option.classList.add('selected');
            inpCo.value = ""; 
            fakeCo.innerHTML = option.innerHTML;
            fakeCo.setAttribute('title', option.textContent.trim());
            hidCo.value = option.getAttribute('data-value');
            updateCo();
            setTimeout(() => { isSelectingGlobal = false; }, 200);
        });
    }

    // --- ALERTA AL CERRAR ---
    const modalNC = document.getElementById('modalNuevaCotizacion');
    if (modalNC) {
        modalNC.addEventListener('hide.bs.modal', function (e) {
            if (window.isSubmittingCotizacion) return;
            if (document.querySelectorAll('#tablaCuerpo tr').length > 0 || document.getElementById('cliente_id_input').value !== "") {
                if (!confirm("⚠️ ¿Estás seguro de salir? Tienes cambios sin guardar.")) {
                    e.preventDefault();
                    return false;
                }
            }
        });
    }

    // AUTO-OPEN
    const uP = new URLSearchParams(window.location.search);
    const nC = uP.get('nuevo_cliente_id');
    if (nC) {
        const btn = document.querySelector('[data-bs-target="#modalNuevaCotizacion"]');
        if (btn) { btn.click(); setTimeout(() => { const o = document.querySelector(`#wrapperCliente .custom-option[data-value="${nC}"]`); if (o) { const md = new MouseEvent('mousedown', {bubbles:true}); o.dispatchEvent(md); } }, 400); }
    }

    window.addEventListener('click', (e) => {
        ['wrapperCliente', 'wrapperContacto', 'wrapperProductoAgregar'].forEach(id => {
            const w = document.getElementById(id);
            if (w && !w.contains(e.target)) w.querySelector('.custom-select').classList.remove('open');
        });
    });

    // --- LÓGICA DE APROBACIÓN ---
    let cotizacionIdAprobar = null;

    window.confirmarAprobacion = function(id) {
        cotizacionIdAprobar = id;
        mostrarModal('modalConfirmarAprobacion');
    };

    const btnAprobar = document.getElementById('btnConfirmarAprobar');
    if (btnAprobar) {
        btnAprobar.addEventListener('click', function() {
            if (!cotizacionIdAprobar) return;
            
            this.disabled = true;
            this.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Procesando...';

            fetch(`/cotizaciones/aprobar/${cotizacionIdAprobar}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Content-Type': 'application/json'
                }
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    alert(data.error || 'Error al aprobar la cotización');
                    this.disabled = false;
                    this.innerText = 'Sí, Aprobar';
                }
            })
            .catch(err => {
                console.error(err);
                alert('Error de conexión');
                this.disabled = false;
                this.innerText = 'Sí, Aprobar';
            });
        });
    }
});

window.aplicarListaPrecio = function() {
    const hp = document.getElementById('selectProductoAgregar');
    const sl = document.getElementById('selectListaPrecio');
    const ip = document.getElementById('inputPrecioAgregar');
    if (!hp.value) return;
    const base = parseFloat(hp.getAttribute('data-base-precio')) || 0;
    const opt = sl.options[sl.selectedIndex];
    if (!sl.value) { ip.value = base.toFixed(2); return; }
    const p = parseFloat(opt.getAttribute('data-porc')) || 0;
    const m = parseFloat(opt.getAttribute('data-monto')) || 0;
    let n = base;
    if (p !== 0) n = base + (base * (p / 100)); else if (m !== 0) n = base + m;
    ip.value = n.toFixed(2);
};
