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
    const cantidad = parseFloat(document.getElementById('inputCantidadAgregar').value) || 0;
    const precio = parseFloat(document.getElementById('inputPrecioAgregar').value) || 0;
    
    // Obtener IVA del producto seleccionado
    const option = document.querySelector(`#wrapperProductoAgregar .custom-option[data-value="${productId}"]`);
    const ivaPorc = option ? parseFloat(option.getAttribute('data-iva')) : 0;
    
    // Cálculos
    const subtotal = cantidad * precio;
    const ivaMonto = subtotal * (ivaPorc / 100);
    const total = subtotal + ivaMonto;

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
            <span class="small text-muted">$${precio.toFixed(2)}</span>
            <input type="hidden" name="precio_unitario[]" value="${precio}">
        </td>
        <td class="text-end">
            <span class="small text-dark">$${subtotal.toFixed(2)}</span>
        </td>
        <td class="text-end">
            <span class="small text-muted">$${ivaMonto.toFixed(2)}</span>
            <input type="hidden" name="iva_porcentaje[]" value="${ivaPorc}">
        </td>
        <td class="text-end">
            <span class="fw-bold small text-dark">$${total.toFixed(2)}</span>
        </td>
        <td class="text-center">
            <div class="d-flex justify-content-center gap-1">
                <button type="button" class="icon-action" onclick="editarFila(this)" title="Editar Partida">
                    <i class="bi bi-pencil-square"></i>
                </button>
                <button type="button" class="icon-action icon-action-danger" onclick="eliminarDeLista(this)" title="Eliminar">
                    <i class="bi bi-x-circle"></i>
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
    let subtotalTotal = 0;
    let ivaTotal = 0;
    let granTotal = 0;

    const aplicaIvaSwitch = document.getElementById('aplica_iva_switch');
    const aplicaIva = aplicaIvaSwitch ? aplicaIvaSwitch.checked : true;

    document.querySelectorAll('#tablaCuerpo tr').forEach(fila => {
        const sub = parseFloat(fila.cells[3].innerText.replace('$', '').replace(',', '')) || 0;
        
        // Obtener el IVA porcentaje original del input hidden en la celda 4
        const ivaInput = fila.cells[4].querySelector('input[name="iva_porcentaje[]"]');
        const ivaPorc = ivaInput ? parseFloat(ivaInput.value) : 0;
        
        const iva = aplicaIva ? (sub * (ivaPorc / 100)) : 0;
        const tot = sub + iva;
        
        // Actualizar visualmente la celda de IVA
        const ivaSpan = fila.cells[4].querySelector('span');
        if (ivaSpan) ivaSpan.innerText = '$' + iva.toFixed(2);
        
        // Actualizar visualmente la celda de Importe
        const totSpan = fila.cells[5].querySelector('span');
        if (totSpan) totSpan.innerText = '$' + tot.toFixed(2);
        
        subtotalTotal += sub;
        ivaTotal += iva;
        granTotal += tot;
    });

    document.getElementById('modalSubtotal').innerText = '$' + subtotalTotal.toLocaleString('en-US', {minimumFractionDigits: 2});
    document.getElementById('modalIvaTotal').innerText = '$' + ivaTotal.toLocaleString('en-US', {minimumFractionDigits: 2});
    document.getElementById('granTotalModal').innerText = '$' + granTotal.toLocaleString('en-US', {minimumFractionDigits: 2});
}

function agregarFilaVisual(id, nombre, cant, precio, ivaPorc) {
    const subtotal = parseFloat(cant) * parseFloat(precio);
    const ivaMonto = subtotal * (parseFloat(ivaPorc) / 100);
    const total = subtotal + ivaMonto;

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
                <span class="small text-dark">$${subtotal.toFixed(2)}</span>
            </td>
            <td class="text-end">
                <span class="small text-muted">$${ivaMonto.toFixed(2)}</span>
                <input type="hidden" name="iva_porcentaje[]" value="${ivaPorc}">
            </td>
            <td class="text-end">
                <span class="fw-bold small text-dark">$${total.toFixed(2)}</span>
            </td>
            <td class="text-center">
                <div class="d-flex justify-content-center gap-1">
                    <button type="button" class="icon-action" onclick="editarFila(this)" title="Editar Partida">
                        <i class="bi bi-pencil-square"></i>
                    </button>
                    <button type="button" class="icon-action icon-action-danger" onclick="eliminarDeLista(this)" title="Eliminar">
                        <i class="bi bi-x-circle"></i>
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
    document.getElementById('modalSubtotal').innerText = '$0.00';
    document.getElementById('modalIvaTotal').innerText = '$0.00';
    
    const aplicaIvaSwitch = document.getElementById('aplica_iva_switch');
    if (aplicaIvaSwitch) {
        aplicaIvaSwitch.checked = true;
    }
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
    if (!tablaVer) { console.error("No se encontró ver_tabla_cuerpo"); return; }
    
    tablaVer.innerHTML = '<tr><td colspan="6" class="text-center py-3"><div class="spinner-border spinner-border-sm text-primary"></div> Cargando...</td></tr>';
    
    fetch(`/cotizaciones/api/${id}/`)
        .then(response => response.json())
        .then(data => {
            if(data.error) { alert(data.error); return; }
            
            const elFolio = document.getElementById('ver_folio');
            if (elFolio) elFolio.innerText = data.folio_completo;
            
            const elCliente = document.getElementById('ver_cliente');
            if (elCliente) elCliente.innerText = data.cliente_nombre;
            
            const elContacto = document.getElementById('ver_contacto');
            if (elContacto) elContacto.innerText = data.contacto_nombre || 'Sin contacto';
            
            const elFechaIni = document.getElementById('ver_fecha_inicio');
            if (elFechaIni) elFechaIni.innerText = data.fecha_inicio;
            
            const elFechaFin = document.getElementById('ver_fecha_fin');
            if (elFechaFin) elFechaFin.innerText = data.fecha_fin;
            
            const elOrigen = document.getElementById('ver_origen');
            if (elOrigen) elOrigen.innerText = data.origen || '--';
            
            const elDir = document.getElementById('ver_direccion');
            if (elDir) elDir.innerText = data.direccion_entrega || '--';
            
            tablaVer.innerHTML = '';
            if (data.detalles && data.detalles.length > 0) {
                data.detalles.forEach(det => {
                    const fila = `
                        <tr>
                            <td class="ps-3"><div class="fw-semibold small text-dark">${det.producto_nombre}</div></td>
                            <td class="text-center small">${det.cantidad}</td>
                            <td class="text-end small text-muted">$${parseFloat(det.precio).toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                            <td class="text-end small text-dark">$${parseFloat(det.subtotal).toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                            <td class="text-end small text-muted">$${parseFloat(det.iva_monto).toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                            <td class="text-end pe-3 fw-bold small text-dark">$${parseFloat(det.total).toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                        </tr>
                    `;
                    tablaVer.insertAdjacentHTML('beforeend', fila);
                });
            } else {
                tablaVer.innerHTML = '<tr><td colspan="6" class="text-center py-3 text-muted fst-italic">No hay artículos en esta cotización.</td></tr>';
            }
            
            const elSub = document.getElementById('ver_subtotal');
            if (elSub) elSub.innerText = '$' + parseFloat(data.subtotal_total || 0).toLocaleString('en-US', {minimumFractionDigits: 2});
            
            const elIva = document.getElementById('ver_iva_total');
            if (elIva) elIva.innerText = '$' + parseFloat(data.iva_total || 0).toLocaleString('en-US', {minimumFractionDigits: 2});
            
            const elTotal = document.getElementById('ver_gran_total');
            if (elTotal) elTotal.innerText = '$' + parseFloat(data.gran_total || 0).toLocaleString('en-US', {minimumFractionDigits: 2});
            
            mostrarModal('modalVerCotizacion');
        })
        .catch(error => {
            console.error('Error al cargar cotización:', error);
            alert("Error al cargar los datos de la cotización.");
        });
};

window.cargarParaEdicion = function(id) {
    const form = document.getElementById('formCotizacion');
    form.reset();
    document.getElementById('tablaCuerpo').innerHTML = ''; 
    document.getElementById('granTotalModal').innerText = '$0.00';
    document.getElementById('modalSubtotal').innerText = '$0.00';
    document.getElementById('modalIvaTotal').innerText = '$0.00';
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
            
            const aplicaIvaSwitch = document.getElementById('aplica_iva_switch');
            if (aplicaIvaSwitch) {
                aplicaIvaSwitch.checked = data.aplica_iva !== false;
            }
            
            // Simular selección de cliente
            const optionCliente = document.querySelector(`#wrapperCliente .custom-option[data-value="${data.cliente}"]`);
            if (optionCliente) {
                // Forzamos el mousedown delegado para cargar dirección y contactos
                const mdown = new MouseEvent('mousedown', { bubbles: true, cancelable: true });
                optionCliente.dispatchEvent(mdown);
            }

            data.detalles.forEach(det => {
                agregarFilaVisual(det.producto_id, det.producto_nombre, det.cantidad, det.precio, det.iva_porcentaje);
            });
            if(data.detalles.length > 0) { document.getElementById('mensajeVacio').style.display = 'none'; }
            calcularGranTotalLista();
            
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

    // --- VALIDACIÓN AL GUARDAR ---
    const formCot = document.getElementById('formCotizacion');
    if (formCot) {
        formCot.addEventListener('submit', function(e) {
            const clienteId = document.getElementById('cliente_id_input').value;
            const tablaCuerpo = document.getElementById('tablaCuerpo');
            
            if (!clienteId || clienteId === "") {
                e.preventDefault();
                alert("⚠️ Falta seleccionar un cliente para guardar la cotización.");
                return false;
            }
            
            if (tablaCuerpo.rows.length === 0) {
                e.preventDefault();
                alert("⚠️ Debes agregar al menos un artículo a la cotización.");
                return false;
            }
            
            window.isSubmittingCotizacion = true;
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
