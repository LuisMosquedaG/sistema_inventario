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
    if (!el) {
        console.error(`Error: No se encontró el modal con ID "${id}"`);
        return null;
    }
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

// 2. FUNCIÓN: Agregar a la lista
function agregarALista() {
    const select = document.getElementById('selectProductoAgregar');
    const productId = select.value;
    const productName = select.options[select.selectedIndex].text;
    const cantidad = document.getElementById('inputCantidadAgregar').value;
    const precio = document.getElementById('inputPrecioAgregar').value;
    const total = (parseFloat(cantidad) * parseFloat(precio)).toFixed(2);

    if (!productId || cantidad <= 0) {
        alert("Por favor selecciona un producto y una cantidad válida.");
        return;
    }

    const filaHtml = `
        <tr>
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
                <button type="button" class="btn btn-sm text-danger p-0" onclick="eliminarDeLista(this)">
                    <i class="bi bi-x-circle-fill"></i>
                </button>
            </td>
        </tr>
    `;
    const tbody = document.getElementById('tablaCuerpo');
    tbody.insertAdjacentHTML('beforeend', filaHtml);
    document.getElementById('mensajeVacio').style.display = 'none';
    select.value = "";
    document.getElementById('inputCantidadAgregar').value = 1;
    document.getElementById('inputPrecioAgregar').value = "0.00";
    calcularGranTotalLista();
}

function eliminarDeLista(boton) {
    const fila = boton.closest('tr');
    fila.remove();
    if (document.getElementById('tablaCuerpo').children.length === 0) {
        document.getElementById('mensajeVacio').style.display = 'block';
    }
    calcularGranTotalLista();
}

function calcularGranTotalLista() {
    let granTotal = 0;
    document.querySelectorAll('#tablaCuerpo tr').forEach(fila => {
        const textoTotal = fila.cells[3].innerText.replace('$', '');
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
                <button type="button" class="btn btn-sm text-danger p-0" onclick="eliminarDeLista(this)">
                    <i class="bi bi-x-circle-fill"></i>
                </button>
            </td>
        </tr>
    `;
    document.getElementById('tablaCuerpo').insertAdjacentHTML('beforeend', filaHtml);
}

document.addEventListener('DOMContentLoaded', function() {
    
    // --- 1. VARIABLES GLOBALES PARA CLIENTE ---
    const wrapperCliente = document.getElementById('wrapperCliente');
    if (!wrapperCliente) return;

    const selectCliente = wrapperCliente.querySelector('.custom-select');
    const inputCliente = document.getElementById('cliente_busqueda');
    const fakeCliente = document.getElementById('cliente_display_fake');
    const hiddenCliente = document.getElementById('cliente_id_input');
    const optionsCliente = wrapperCliente.querySelectorAll('.custom-option:not(.disabled)');

    let isSelectingCliente = false;

    wrapperCliente.addEventListener('click', function(e) {
        if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'I') {
            inputCliente.focus();
        }
    });

    inputCliente.addEventListener('focus', function() {
        selectCliente.classList.add('open');
        if (!hiddenCliente.value && inputCliente.value === '') {
            fakeCliente.innerHTML = '<span class="typing-text"></span>';
        }
    });

    inputCliente.addEventListener('input', function() {
        if (isSelectingCliente) return;
        hiddenCliente.value = ""; 
        inputCliente.classList.remove('input-cliente-seleccionado');
        fakeCliente.innerHTML = `<span class="typing-text">${this.value}</span>`;
        document.getElementById('cliente-error').style.display = 'none';
        selectCliente.querySelector('.custom-select__trigger').style.borderColor = "#ced4da";

        const term = this.value.toLowerCase();
        let visibleCount = 0;
        optionsCliente.forEach(option => {
            const searchText = option.getAttribute('data-search').toLowerCase();
            if (searchText.includes(term)) {
                option.style.display = 'flex';
                visibleCount++;
            } else {
                option.style.display = 'none';
            }
        });
        document.getElementById('sin-resultados').style.display = (visibleCount === 0) ? 'block' : 'none';
        selectCliente.classList.add('open');
    });

    window.addEventListener('click', function(e) {
        if (!selectCliente.contains(e.target)) {
            selectCliente.classList.remove('open');
            if (!hiddenCliente.value && inputCliente.value === '') {
                fakeCliente.innerHTML = '<span class="text-muted" style="font-weight:400;">Buscar cliente...</span>';
            }
        }
    });

    optionsCliente.forEach(option => {
        option.addEventListener('click', function(e) {
            e.stopPropagation();
            isSelectingCliente = true;
            optionsCliente.forEach(opt => opt.classList.remove('selected'));
            this.classList.add('selected');

            fakeCliente.innerHTML = this.innerHTML;
            inputCliente.value = this.textContent.replace(/\s+/g, ' ').trim();
            inputCliente.classList.add('input-cliente-seleccionado');
            hiddenCliente.value = this.getAttribute('data-value');

            const direccionInput = document.querySelector('input[name="direccion_entrega"]');
            
            // --- NUEVA LÓGICA CON ETIQUETAS EXPLÍCITAS ---
            const partes = [];
            
            const calle = this.getAttribute('data-calle') || '';
            const numExt = this.getAttribute('data-num-ext') || '';
            const numInt = this.getAttribute('data-num-int') || '';
            const colonia = this.getAttribute('data-colonia') || '';
            const estado = this.getAttribute('data-estado') || ''; 
            const cp = this.getAttribute('data-cp') || '';

            // Agregamos etiqueta a cada campo si tiene valor
            if (calle) partes.push('Calle: ' + calle);
            if (numExt) partes.push('Num ext: ' + numExt);
            if (numInt) partes.push('Num int: ' + numInt);
            if (colonia) partes.push('Col: ' + colonia);
            if (estado) partes.push('Est: ' + estado);
            if (cp) partes.push('Cp: ' + cp);

            direccionInput.value = partes.join(', ');
            // ----------------------------------------------

            cargarContactos(hiddenCliente.value); 

            document.getElementById('cliente-error').style.display = 'none';
            selectCliente.classList.remove('open');
            setTimeout(() => { isSelectingCliente = false; }, 50);
        });
    });

    // --- 3. CONTACTO ---
    const wrapperContacto = document.getElementById('wrapperContacto');
    const selectContacto = wrapperContacto.querySelector('.custom-select');
    const inputContacto = document.getElementById('contacto_busqueda');
    const fakeContacto = document.getElementById('contacto_display_fake');
    const hiddenContacto = document.getElementById('contacto_id_input');
    const optionsContacto = wrapperContacto.querySelector('.custom-options');

    function cargarContactos(clienteId) {
        inputContacto.value = '';
        fakeContacto.innerHTML = '<span class="text-muted">Cargando...</span>';
        hiddenContacto.value = '';
        inputContacto.disabled = true;

        if (!clienteId) {
            fakeContacto.innerHTML = '<span class="text-muted">Selecciona cliente primero...</span>';
            inputContacto.disabled = true;
            return;
        }

        fetch(`/api/clientes/${clienteId}/contactos/`)
            .then(response => response.json())
            .then(data => {
                optionsContacto.innerHTML = '';
                if (data.length === 0) {
                    optionsContacto.innerHTML = '<span class="custom-option disabled text-muted small">Este cliente no tiene contactos</span>';
                    fakeContacto.innerHTML = '<span class="text-muted">Sin contactos</span>';
                    inputContacto.disabled = true;
                } else {
                    data.forEach(c => {
                        const htmlOpcion = `
                            <span class="custom-option" data-value="${c.id}">
                                <span class="opt-razon">${c.nombre}</span>
                                <span class="opt-separator">|</span>
                                <span class="opt-contacto">${c.e1 || 'Sin correo'}</span>
                                <span class="opt-separator">|</span>
                                <span class="opt-contacto">${c.t1 || 'Sin teléfono'}</span>
                            </span>
                        `;
                        optionsContacto.insertAdjacentHTML('beforeend', htmlOpcion);
                    });
                    fakeContacto.innerHTML = '<span class="text-muted">Seleccionar contacto...</span>';
                    inputContacto.disabled = false;
                    activarLogicaContacto();
                }
            })
            .catch(error => {
                console.error('Error cargando contactos:', error);
                fakeContacto.innerHTML = '<span class="text-danger">Error al cargar</span>';
            });
    }

    function activarLogicaContacto() {
        const nuevasOpciones = optionsContacto.querySelectorAll('.custom-option:not(.disabled)');
        nuevasOpciones.forEach(opt => {
            if (opt.hasAttribute('data-listener')) return;
            opt.setAttribute('data-listener', 'true');

            opt.addEventListener('click', function(e) {
                e.stopPropagation();
                nuevasOpciones.forEach(o => o.classList.remove('selected'));
                this.classList.add('selected');
                fakeContacto.innerHTML = this.innerHTML;
                inputContacto.value = this.textContent.replace(/\s+/g, ' ').trim();
                hiddenContacto.value = this.getAttribute('data-value');
                inputContacto.classList.add('input-cliente-seleccionado');
                selectContacto.classList.remove('open');
            });
        });
    }

    inputContacto.addEventListener('focus', function() {
        if(!this.disabled) selectContacto.classList.add('open');
    });
    wrapperContacto.addEventListener('click', function(e) {
        if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'I') {
            if(!inputContacto.disabled) inputContacto.focus();
        }
    });
    window.addEventListener('click', function(e) {
        if (!selectContacto.contains(e.target)) {
            selectContacto.classList.remove('open');
        }
    });

    const form = document.getElementById('formCotizacion');
    if (form) {
        form.addEventListener('submit', function(e) {
            if (!hiddenCliente.value) {
                e.preventDefault();
                document.getElementById('cliente-error').style.display = 'block';
                inputCliente.classList.remove('input-cliente-seleccionado');
                selectCliente.querySelector('.custom-select__trigger').style.borderColor = "#dc3545";
                selectCliente.classList.add('open');
                inputCliente.focus();
            }
        });
    }

    window.cargarParaEdicion = function(id) {
        document.getElementById('formCotizacion').reset();
        document.getElementById('tablaCuerpo').innerHTML = ''; 
        document.getElementById('granTotalModal').innerText = '$0.00';
        document.getElementById('mensajeVacio').style.display = 'block';

        fakeCliente.innerHTML = '<span class="text-muted">Buscar cliente...</span>';
        fakeContacto.innerHTML = '<span class="text-muted">Selecciona cliente primero...</span>';
        inputContacto.disabled = true;
        inputContacto.classList.remove('input-cliente-seleccionado');
        inputCliente.classList.remove('input-cliente-seleccionado');

        document.querySelector('.modal-title').innerHTML = '<i class="bi bi-pencil-square me-2" style="color: #00b8b9;"></i> Editar Cotización #' + id;
        document.getElementById('formCotizacion').action = `/cotizaciones/actualizar/${id}/`;

        fetch(`/api/cotizaciones/${id}/`)
            .then(response => response.json())
            .then(data => {
                if(data.error) {
                    alert(data.error);
                    return;
                }

                document.querySelector('input[name="fecha_inicio"]').value = data.fecha_inicio;
                document.querySelector('input[name="fecha_fin"]').value = data.fecha_fin;
                document.querySelector('input[name="origen"]').value = data.origen;
                document.querySelector('input[name="direccion_entrega"]').value = data.direccion_entrega;

                const optionCliente = document.querySelector(`.custom-option[data-value="${data.cliente}"]`);
                if (optionCliente) {
                    optionCliente.click();
                }

                let totalAcumulado = 0;
                data.detalles.forEach(det => {
                    agregarFilaVisual(det.producto_id, det.producto_nombre, det.cantidad, det.precio, det.total);
                    totalAcumulado += parseFloat(det.total);
                });
                
                if(data.detalles.length > 0) {
                    document.getElementById('mensajeVacio').style.display = 'none';
                }
                document.getElementById('granTotalModal').innerText = '$' + totalAcumulado.toFixed(2);

                if (data.contacto_id) {
                    setTimeout(() => {
                        const optionContacto = document.querySelector(`#wrapperContacto .custom-option[data-value="${data.contacto_id}"]`);
                        if (optionContacto) {
                            optionContacto.click();
                        }
                    }, 400);
                }

                mostrarModal('modalNuevaCotizacion');
            })
            .catch(error => console.error('Error:', error));
    };
});

// EVENTOS GLOBALES FUERA DE DOMContentLoaded

const btnNuevaCotizacion = document.querySelector('[data-bs-target="#modalNuevaCotizacion"]');
if (btnNuevaCotizacion) {
    btnNuevaCotizacion.addEventListener('click', function() {
        document.querySelector('.modal-title').innerHTML = '<i class="bi bi-file-earmark-plus me-2" style="color: #00b8b9;"></i> Nueva Cotización';
        document.getElementById('formCotizacion').action = "/cotizaciones/crear/";

        const hoy = new Date().toISOString().split('T')[0];
        document.getElementById('fecha_inicio').value = hoy;
        document.getElementById('fecha_fin').value = hoy;
        
        const inputCliente = document.getElementById('cliente_busqueda');
        const fakeCliente = document.getElementById('cliente_display_fake');
        const hiddenCliente = document.getElementById('cliente_id_input');
        const inputContacto = document.getElementById('contacto_busqueda');
        const fakeContacto = document.getElementById('contacto_display_fake');
        const hiddenContacto = document.getElementById('contacto_id_input');

        inputCliente.value = '';
        fakeCliente.innerHTML = '<span class="text-muted" style="font-weight:400;">Buscar cliente...</span>';
        hiddenCliente.value = '';
        inputCliente.classList.remove('input-cliente-seleccionado');

        inputContacto.value = '';
        fakeContacto.innerHTML = '<span class="text-muted">Selecciona cliente primero...</span>';
        hiddenContacto.value = '';
        inputContacto.disabled = true;
        inputContacto.classList.remove('input-cliente-seleccionado');

        document.querySelector('input[name="direccion_entrega"]').value = '';
    });
}

let idAprobarTemporal = null;
window.confirmarAprobacion = function(id) {
    idAprobarTemporal = id;
    mostrarModal('modalConfirmarAprobacion');
};

const btnConfirmarAprobar = document.getElementById('btnConfirmarAprobar');
if (btnConfirmarAprobar) {
    btnConfirmarAprobar.addEventListener('click', function() {
        if (!idAprobarTemporal) return;
        fetch(`/cotizaciones/aprobar/${idAprobarTemporal}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const modalEl = document.getElementById('modalConfirmarAprobacion');
                const modal = bootstrap.Modal.getInstance(modalEl);
                modal.hide();
                location.reload(); 
            } else {
                alert('Error al aprobar: ' + data.error);
            }
        })
        .catch(error => console.error('Error:', error));
    });
}
