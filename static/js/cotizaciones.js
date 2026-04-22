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

/**
 * Función centralizada para abrir modales de forma segura
 */
function mostrarModal(id) {
    const el = document.getElementById(id);
    if (!el) return null;
    const modal = bootstrap.Modal.getOrCreateInstance(el);
    modal.show();
    return modal;
}

// 1. EVENTO: Al seleccionar producto en el panel de agregar, llenar precio
document.addEventListener('change', function(e) {
    if (e.target && e.target.id === 'selectProductoAgregar') {
        const selectedOption = e.target.options[e.target.selectedIndex];
        const precio = selectedOption.getAttribute('data-precio');
        if(precio) {
            document.getElementById('inputPrecioAgregar').value = precio;
        }
    }
});

// 2. FUNCIÓN: Agregar o Actualizar en la lista
function agregarALista() {
    const select = document.getElementById('selectProductoAgregar');
    const productId = select.value;
    const productName = select.options[select.selectedIndex].text;
    const cantidad = document.getElementById('inputCantidadAgregar').value;
    const precio = document.getElementById('inputPrecioAgregar').value;
    const total = (parseFloat(cantidad) * parseFloat(precio)).toFixed(2);
    const editIndex = document.getElementById('edit_index').value;

    if (!productId || cantidad <= 0) {
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
        // ACTUALIZAR FILA EXISTENTE
        const tbody = document.getElementById('tablaCuerpo');
        const fila = tbody.rows[parseInt(editIndex)];
        fila.innerHTML = filaHtml;
        
        // Resetear botón y modo edición
        const btnAgregar = document.querySelector('button[onclick="agregarALista()"]');
        btnAgregar.innerHTML = '<i class="bi bi-plus-lg"></i> Agregar';
        document.getElementById('edit_index').value = "-1";
    } else {
        // AGREGAR NUEVA FILA
        const tbody = document.getElementById('tablaCuerpo');
        const nuevaFila = document.createElement('tr');
        nuevaFila.innerHTML = filaHtml;
        tbody.appendChild(nuevaFila);
        document.getElementById('mensajeVacio').style.display = 'none';
    }

    select.value = "";
    document.getElementById('inputCantidadAgregar').value = 1;
    document.getElementById('inputPrecioAgregar').value = "0.00";
    calcularGranTotalLista();
}

function editarFila(boton) {
    const fila = boton.closest('tr');
    const tbody = document.getElementById('tablaCuerpo');
    const index = Array.from(tbody.rows).indexOf(fila);
    
    // Obtener valores de la fila
    const productId = fila.querySelector('input[name="producto_id[]"]').value;
    const cantidad = fila.querySelector('input[name="cantidad[]"]').value;
    const precio = fila.querySelector('input[name="precio_unitario[]"]').value;

    // Llenar campos de "Agregar Artículo"
    const select = document.getElementById('selectProductoAgregar');
    select.value = productId;
    document.getElementById('inputCantidadAgregar').value = cantidad;
    document.getElementById('inputPrecioAgregar').value = precio;
    document.getElementById('edit_index').value = index;

    // Cambiar texto del botón "Agregar" a "Actualizar"
    const btnAgregar = document.querySelector('button[onclick="agregarALista()"]');
    btnAgregar.innerHTML = '<i class="bi bi-check-lg"></i> Actualizar';
}

function eliminarDeLista(boton) {
    const fila = boton.closest('tr');
    fila.remove();
    if (document.getElementById('tablaCuerpo').children.length === 0) {
        document.getElementById('mensajeVacio').style.display = 'block';
    }
    
    // Si estábamos editando esta fila, resetear modo edición
    document.getElementById('edit_index').value = "-1";
    const btnAgregar = document.querySelector('button[onclick="agregarALista()"]');
    btnAgregar.innerHTML = '<i class="bi bi-plus-lg"></i> Agregar';

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

// ==========================================
// VER COTIZACIÓN
// ==========================================
window.verCotizacion = function(id) {
    const tablaVer = document.getElementById('ver_tabla_cuerpo');
    tablaVer.innerHTML = '<tr><td colspan="4" class="text-center py-3"><div class="spinner-border spinner-border-sm text-primary"></div> Cargando...</td></tr>';
    
    fetch(`/api/cotizaciones/${id}/`)
        .then(response => response.json())
        .then(data => {
            if(data.error) { alert(data.error); return; }

            // Actualizar el folio en el título
            document.getElementById('ver_folio').innerText = data.folio_completo;
            
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
                        <td class="ps-3">
                            <div class="fw-semibold small text-dark">${det.producto_nombre}</div>
                        </td>
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
        .catch(error => {
            console.error('Error:', error);
            alert('No se pudo cargar la información de la cotización.');
        });
};

// ==========================================
// EDICIÓN DE COTIZACIÓN (GLOBAL)
// ==========================================
window.cargarParaEdicion = function(id) {
    const form = document.getElementById('formCotizacion');
    form.reset();
    document.getElementById('tablaCuerpo').innerHTML = ''; 
    document.getElementById('granTotalModal').innerText = '$0.00';
    document.getElementById('mensajeVacio').style.display = 'block';

    const inputCliente = document.getElementById('cliente_busqueda');
    const fakeCliente = document.getElementById('cliente_display_fake');
    const inputContacto = document.getElementById('contacto_busqueda');
    const fakeContacto = document.getElementById('contacto_display_fake');

    fakeCliente.innerHTML = '<span class="text-muted">Buscar cliente...</span>';
    fakeContacto.innerHTML = '<span class="text-muted">Selecciona cliente primero...</span>';
    if (inputContacto) inputContacto.disabled = true;
    if (inputContacto) inputContacto.classList.remove('input-cliente-seleccionado');
    if (inputCliente) inputCliente.classList.remove('input-cliente-seleccionado');

    document.querySelector('.modal-title').innerHTML = '<i class="bi bi-pencil-square me-2" style="color: #00b8b9;"></i> Editar Cotización #' + id;
    form.action = `/cotizaciones/actualizar/${id}/`;

    fetch(`/api/cotizaciones/${id}/`)
        .then(response => response.json())
        .then(data => {
            if(data.error) { alert(data.error); return; }

            document.querySelector('input[name="fecha_inicio"]').value = data.fecha_inicio;
            document.querySelector('input[name="fecha_fin"]').value = data.fecha_fin;
            document.querySelector('input[name="origen"]').value = data.origen;
            document.querySelector('input[name="direccion_entrega"]').value = data.direccion_entrega;

            const optionCliente = document.querySelector(`.custom-option[data-value="${data.cliente}"]`);
            if (optionCliente) { optionCliente.click(); }

            let totalAcumulado = 0;
            data.detalles.forEach(det => {
                agregarFilaVisual(det.producto_id, det.producto_nombre, det.cantidad, det.precio, det.total);
                totalAcumulado += parseFloat(det.total);
            });
            
            if(data.detalles.length > 0) { document.getElementById('mensajeVacio').style.display = 'none'; }
            document.getElementById('granTotalModal').innerText = '$' + totalAcumulado.toFixed(2);

            if (data.contacto_id) {
                setTimeout(() => {
                    const optionContacto = document.querySelector(`#wrapperContacto .custom-option[data-value="${data.contacto_id}"]`);
                    if (optionContacto) { optionContacto.click(); }
                }, 400);
            }
            mostrarModal('modalNuevaCotizacion');
        })
        .catch(error => console.error('Error:', error));
};

document.addEventListener('DOMContentLoaded', function() {
    
    // --- LÓGICA DE BÚSQUEDA DE CLIENTES ---
    const wrapperCliente = document.getElementById('wrapperCliente');
    if (!wrapperCliente) return;

    const selectCliente = wrapperCliente.querySelector('.custom-select');
    const inputCliente = document.getElementById('cliente_busqueda');
    const fakeCliente = document.getElementById('cliente_display_fake');
    const hiddenCliente = document.getElementById('cliente_id_input');
    const optionsCliente = wrapperCliente.querySelectorAll('.custom-option:not(.disabled)');

    let isSelectingCliente = false;

    inputCliente.addEventListener('focus', () => selectCliente.classList.add('open'));
    inputCliente.addEventListener('input', function() {
        if (isSelectingCliente) return;
        fakeCliente.innerHTML = `<span class="typing-text">${this.value}</span>`;
        const term = this.value.toLowerCase();
        optionsCliente.forEach(opt => {
            const search = opt.getAttribute('data-search').toLowerCase();
            opt.style.display = search.includes(term) ? 'flex' : 'none';
        });
        selectCliente.classList.add('open');
    });

    function vincularClickOpciones(opciones) {
        opciones.forEach(option => {
            option.addEventListener('click', function(e) {
                e.stopPropagation();
                isSelectingCliente = true;
                opciones.forEach(opt => opt.classList.remove('selected'));
                this.classList.add('selected');
                fakeCliente.innerHTML = this.innerHTML;
                inputCliente.value = this.textContent.replace(/\s+/g, ' ').trim();
                inputCliente.classList.add('input-cliente-seleccionado');
                hiddenCliente.value = this.getAttribute('data-value');

                const dirInput = document.querySelector('input[name="direccion_entrega"]');
                const partes = [];
                ['data-calle', 'data-num-ext', 'data-colonia', 'data-estado'].forEach(attr => {
                    const val = this.getAttribute(attr);
                    if(val) partes.push(val);
                });
                if(dirInput) dirInput.value = partes.join(', ');

                if (typeof cargarContactos === 'function') cargarContactos(hiddenCliente.value);
                selectCliente.classList.remove('open');
                setTimeout(() => { isSelectingCliente = false; }, 50);
            });
        });
    }
    vincularClickOpciones(optionsCliente);

    // --- LÓGICA DE BÚSQUEDA DE CONTACTOS ---
    const inputContacto = document.getElementById('contacto_busqueda');
    const selectContacto = document.getElementById('wrapperContacto').querySelector('.custom-select');
    const fakeContacto = document.getElementById('contacto_display_fake');

    if (inputContacto) {
        inputContacto.addEventListener('focus', () => {
            if (!inputContacto.disabled) selectContacto.classList.add('open');
        });

        inputContacto.addEventListener('input', function() {
            const term = this.value.toLowerCase();
            fakeContacto.innerHTML = `<span class="typing-text">${this.value}</span>`;
            const options = document.querySelectorAll('#wrapperContacto .custom-option:not(.disabled)');
            options.forEach(opt => {
                const text = opt.textContent.toLowerCase();
                opt.style.display = text.includes(term) ? 'flex' : 'none';
            });
            selectContacto.classList.add('open');
        });
    }

    // Cerrar selects al hacer click fuera
    window.addEventListener('click', (e) => {
        if (!wrapperCliente.contains(e.target)) selectCliente.classList.remove('open');
        if (wrapperContacto && !wrapperContacto.contains(e.target)) selectContacto.classList.remove('open');
    });

    // ==========================================
    // LÓGICA: CREAR CLIENTE RÁPIDO (AJAX)
    // ==========================================
    const formCR = document.getElementById('formClienteRapido');
    if (formCR) {
        formCR.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // BUSCAR EL BOTÓN CORRECTAMENTE (incluso si está fuera del form usando el atributo 'form')
            const btn = document.querySelector(`button[form="${this.id}"]`) || this.querySelector('button[type="submit"]');
            
            const originalText = btn ? btn.innerText : 'Registrar y Volver';
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Guardando...';
            }

            fetch(this.action, {
                method: 'POST',
                body: new FormData(this),
                headers: { 'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest' }
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    // Crear la nueva opción para el selector de cotización
                    const nuevaOpt = document.createElement('span');
                    nuevaOpt.className = 'custom-option';
                    nuevaOpt.setAttribute('data-value', data.id);
                    // Atributos de búsqueda y dirección (capturados del form)
                    const nom = this.nombre.value;
                    const ape = this.apellidos.value;
                    const rz = this.razon_social.value;
                    nuevaOpt.setAttribute('data-search', `${nom} ${ape} ${rz}`);
                    
                    // Llenar el HTML de la opción
                    nuevaOpt.innerHTML = `<span class="opt-razon">${rz || (nom + ' ' + ape)}</span>`;
                    
                    const container = document.querySelector('#wrapperCliente .custom-options');
                    if (container) {
                        container.prepend(nuevaOpt);
                        // Re-vincular eventos y seleccionar
                        vincularClickOpciones([nuevaOpt]);
                        nuevaOpt.click();
                    }

                    // Cerrar modal
                    const modalEl = document.getElementById('modalCrearClienteRapido');
                    const modalInstance = bootstrap.Modal.getInstance(modalEl);
                    if (modalInstance) modalInstance.hide();
                    
                    this.reset();
                } else {
                    alert('Error al guardar: ' + JSON.stringify(data.error));
                }
            })
            .catch(err => {
                console.error('Error AJAX:', err);
                alert('Ocurrió un error al procesar la solicitud.');
            })
            .finally(() => {
                if (btn) {
                    btn.disabled = false;
                    btn.innerText = 'Registrar y Volver';
                }
            });
        });
    }

    // RESETEAR FORMULARIO AL CERRAR
    const modalCR = document.getElementById('modalCrearClienteRapido');
    if (modalCR) {
        modalCR.addEventListener('hidden.bs.modal', function() {
            formCR.reset();
        });
    }

    // FIX STACKED MODALS Z-INDEX
    document.addEventListener('show.bs.modal', function (event) {
        const zIndex = 1040 + (10 * document.querySelectorAll('.modal.show').length);
        event.target.style.zIndex = zIndex;
        setTimeout(() => {
            const backdrops = document.querySelectorAll('.modal-backdrop:not(.modal-stack)');
            if (backdrops.length > 0) {
                const lb = backdrops[backdrops.length - 1];
                lb.style.zIndex = zIndex - 1;
                lb.classList.add('modal-stack');
            }
        }, 0);
    });
});

// CARGAR CONTACTOS (GLOBAL)
window.cargarContactos = function(clienteId) {
    const inputC = document.getElementById('contacto_busqueda');
    const fakeC = document.getElementById('contacto_display_fake');
    const optionsC = document.querySelector('#wrapperContacto .custom-options');
    
    if(!inputC) return;
    inputC.value = ''; fakeC.innerHTML = 'Cargando...'; inputC.disabled = true;

    fetch(`/api/clientes/${clienteId}/contactos/`)
        .then(r => r.json())
        .then(data => {
            optionsC.innerHTML = '';
            if (data.length === 0) {
                optionsC.innerHTML = '<span class="custom-option disabled small">Sin contactos</span>';
                fakeC.innerHTML = 'Sin contactos';
            } else {
                data.forEach(c => {
                    optionsC.insertAdjacentHTML('beforeend', `<span class="custom-option" data-value="${c.id}"><span class="opt-razon">${c.nombre}</span></span>`);
                });
                fakeC.innerHTML = 'Seleccionar contacto...';
                inputC.disabled = false;
                
                optionsC.querySelectorAll('.custom-option').forEach(opt => {
                    opt.onclick = function() {
                        document.getElementById('contacto_id_input').value = this.getAttribute('data-value');
                        fakeC.innerHTML = this.innerHTML;
                        inputC.value = this.textContent.trim();
                        inputC.classList.add('input-cliente-seleccionado');
                        document.getElementById('wrapperContacto').querySelector('.custom-select').classList.remove('open');
                    };
                });
            }
        });
};

// EVENTOS GLOBALES
const btnNC = document.querySelector('[data-bs-target="#modalNuevaCotizacion"]');
if (btnNC) {
    btnNC.addEventListener('click', function() {
        document.querySelector('.modal-title').innerHTML = '<i class="bi bi-file-earmark-plus me-2" style="color: #00b8b9;"></i> Nueva Cotización';
        document.getElementById('formCotizacion').action = "/cotizaciones/crear/";
        document.getElementById('formCotizacion').reset();
        document.getElementById('tablaCuerpo').innerHTML = '';
        document.getElementById('granTotalModal').innerText = '$0.00';
        document.getElementById('cliente_busqueda').value = '';
        document.getElementById('cliente_display_fake').innerHTML = 'Buscar cliente...';
        document.getElementById('cliente_id_input').value = '';
        
        // Resetear modo edición de artículos
        document.getElementById('edit_index').value = "-1";
        const btnAgregar = document.querySelector('button[onclick="agregarALista()"]');
        if (btnAgregar) btnAgregar.innerHTML = '<i class="bi bi-plus-lg"></i> Agregar';
    });
}

window.confirmarAprobacion = function(id) {
    const btn = document.getElementById('btnConfirmarAprobar');
    mostrarModal('modalConfirmarAprobacion');
    btn.onclick = function() {
        fetch(`/cotizaciones/aprobar/${id}/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCookie('csrftoken'), 'Content-Type': 'application/json' }
        }).then(r => r.json()).then(d => { if(d.success) location.reload(); else alert(d.error); });
    };
};
