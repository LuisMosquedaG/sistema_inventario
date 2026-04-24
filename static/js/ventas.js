// ============================================
// VENTAS.JS — Gestión de Salidas
// ============================================

let currentOvId = null;

/**
 * Función para recargar los artículos del modal de surtido al cambiar de almacén
 */
function recargarItemsSurtido() {
    const almacenId = document.getElementById('inputAlmacenSurtido').value;
    if (currentOvId) {
        abrirModalSurtido(currentOvId, almacenId);
    }
}

/**
 * Abre el modal de surtido para una Orden de Salida específica
 */
function abrirModalSurtido(ovId, forceAlmacenId = null) {
    currentOvId = ovId;
    const modalEl = document.getElementById('modalSurtido');
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    const form = document.getElementById('formSurtido');
    const tbody = document.getElementById('tablaArticulosSurtido');
    const btnSubmit = form.querySelector('button[type="submit"]');
    const selectAlmacen = document.getElementById('inputAlmacenSurtido');

    // Mostrar estado de carga en la tabla
    tbody.innerHTML = '<tr><td colspan="4" class="text-center py-3"><span class="spinner-border spinner-border-sm"></span> Actualizando existencias...</td></tr>';
    btnSubmit.disabled = true;

    // Inicializar select de almacenes solo la primera vez
    if (!forceAlmacenId) {
        selectAlmacen.innerHTML = '<option value="">Seleccionar...</option>';
        if (window.ALMACENES_DISPONIBLES) {
            window.ALMACENES_DISPONIBLES.forEach(a => {
                selectAlmacen.insertAdjacentHTML('beforeend', `<option value="${a.id}">${a.nombre}</option>`);
            });
        }
        form.action = `/ventas/surtir/${ovId}/`;
    }

    let url = `/ventas/api/preparar-surtido/${ovId}/`;
    if (forceAlmacenId) url += `?almacen_id=${forceAlmacenId}`;

    fetch(url)
        .then(response => response.json())
        .then(data => {
            if (data.success === false) {
                alert('Error: ' + data.error);
                modal.hide();
                return;
            }

            if (!forceAlmacenId) {
                modalEl.querySelector('.modal-title').innerHTML = `<i class="bi bi-box-seam me-2 text-success"></i> Surtir Orden: ${data.folio_display}`;
                document.getElementById('dispClienteNombre').innerText = data.cliente_razon || data.cliente_nombre;
                document.getElementById('dispClienteTel').innerText = data.cliente_telefono || '-';
                document.getElementById('dispClienteEmail').innerText = data.cliente_correo || '-';
                document.getElementById('dispClienteDir').innerText = data.cliente_direccion || '-';

                document.getElementById('inputDireccion').value = data.direccion_envio || '';
                document.getElementById('inputRecibe').value = data.quien_recibe || '';
                document.getElementById('inputTelRecibe').value = data.telefono_recibe || '';
                document.getElementById('inputGuia').value = data.guia || '';
                document.getElementById('inputNotas').value = data.notas_envio || '';
                
                if (data.almacen_id) selectAlmacen.value = data.almacen_id;
            }

            tbody.innerHTML = '';
            
            data.detalles.forEach(det => {
                const tr = document.createElement('tr');
                tr.dataset.precio = det.precio;
                tr.dataset.id = det.id;
                
                let extraHtml = '';
                if (det.maneja_lote || det.maneja_serie) {
                    let options = '<option value="">Seleccionar...</option>';
                    if (det.extras && det.extras.length > 0) {
                        det.extras.forEach(ex => {
                            const label = ex.tipo === 'lote' ? `${ex.lote} (Stock: ${ex.cantidad})` : ex.serie;
                            options += `<option value="${ex.id}">${label}</option>`;
                        });
                    } else {
                        options = '<option value="">Sin existencias en este almacén</option>';
                    }
                    
                    const multiple = det.maneja_serie ? 'multiple' : ''; 
                    const helpText = det.maneja_serie ? '<small class="text-muted d-block" style="font-size:0.7rem">Ctrl+Click p/varios</small>' : '';

                    extraHtml = `
                        <div class="mt-1">
                            <select name="extra_id_${det.id}[]" class="form-select form-select-sm" ${multiple} required>
                                ${options}
                            </select>
                            ${helpText}
                        </div>
                    `;
                }

                tr.innerHTML = `
                    <td class="text-center">
                        <div class="fw-bold text-center">${det.producto_nombre}</div>
                        ${extraHtml}
                    </td>
                    <td class="text-center">${det.cantidad}</td>
                    <td class="text-center">0</td>
                    <td class="text-center">
                        <input type="number" name="cantidad_entregar_${det.id}" 
                               class="form-control form-control-sm text-center mx-auto input-entregar" 
                               style="max-width: 80px;"
                               value="${det.cantidad}" min="0" max="${det.cantidad}"
                               oninput="recalcularSurtido()">
                    </td>
                    <td class="text-center">$${det.precio.toFixed(2)}</td>
                    <td class="text-center fw-bold subtotal-item">$${det.subtotal.toFixed(2)}</td>
                `;
                tbody.appendChild(tr);
            });

            recalcularSurtido();
            btnSubmit.disabled = false;
            
            if (!forceAlmacenId) modal.show();
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error al cargar datos de la orden.');
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger">Error de conexión</td></tr>';
        });
}

/**
 * Recalcula subtotales y total general en el modal de surtido
 */
function recalcularSurtido() {
    let granTotal = 0;
    document.querySelectorAll('#tablaArticulosSurtido tr').forEach(tr => {
        const input = tr.querySelector('.input-entregar');
        if (!input) return;
        
        const cant = parseInt(input.value) || 0;
        const precio = parseFloat(tr.dataset.precio) || 0;
        const subtotal = cant * precio;
        
        tr.querySelector('.subtotal-item').innerText = '$' + subtotal.toFixed(2);
        granTotal += subtotal;
    });
    document.getElementById('totalSurtido').innerText = '$' + granTotal.toFixed(2);
}

/**
 * Abre el modal de detalle de una orden de salida
 */
function abrirModalDetalle(ovId) {
    const modalEl = document.getElementById('modalDetalleVenta');
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    const tbody = document.getElementById('tablaArticulosDetalle');
    
    tbody.innerHTML = '<tr><td colspan="4" class="text-center py-3"><span class="spinner-border spinner-border-sm"></span> Cargando...</td></tr>';

    fetch(`/ventas/api/preparar-surtido/${ovId}/`)
        .then(response => response.json())
        .then(data => {
            if (data.success === false) {
                alert('Error: ' + data.error);
                modal.hide();
                return;
            }

            // Actualizar folio en el título
            document.getElementById('detFolio').innerText = data.folio_display || '';

            document.getElementById('detClienteNombre').innerText = data.cliente_razon || data.cliente_nombre;
            document.getElementById('detClienteTel').innerText = data.cliente_telefono || '-';
            document.getElementById('detClienteEmail').innerText = data.cliente_correo || '-';
            document.getElementById('detClienteDir').innerText = data.cliente_direccion || '-';

            document.getElementById('detDireccion').innerText = data.direccion_envio || 'Sin dirección registrada';
            document.getElementById('detRecibe').innerText = data.quien_recibe || '-';
            document.getElementById('detTelRecibe').innerText = data.telefono_recibe || '-';
            document.getElementById('detGuia').innerText = data.guia || 'Pendiente';
            document.getElementById('detNotas').innerText = data.notas_envio || 'Sin notas';

            tbody.innerHTML = '';
            let totalFinal = 0;
            
            data.detalles.forEach(det => {
                totalFinal += det.subtotal;
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td class="ps-3 fw-semibold small text-dark">${det.producto_nombre}</td>
                    <td class="text-center small">${det.cantidad}</td>
                    <td class="text-end small text-muted">$${parseFloat(det.precio).toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                    <td class="text-end pe-3 fw-bold small text-dark">$${parseFloat(det.subtotal).toLocaleString('en-US', {minimumFractionDigits: 2})}</td>
                `;
                tbody.appendChild(tr);
            });

            document.getElementById('totalDetalleVenta').innerText = '$' + totalFinal.toLocaleString('en-US', {minimumFractionDigits: 2});
            
            modal.show();
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error al cargar datos de la orden.');
        });
}

/**
 * Lógica para el formulario de surtido
 */
document.addEventListener('DOMContentLoaded', function() {
    const formSurtido = document.getElementById('formSurtido');
    if (formSurtido) {
        formSurtido.addEventListener('submit', function(e) {
            e.preventDefault();
            const form = this;
            const formData = new FormData(form);
            const btn = form.querySelector('button[type="submit"]');
            const originalText = btn.innerHTML;

            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Procesando...';

            fetch(form.action, {
                method: 'POST',
                body: formData,
                headers: { 'X-CSRFToken': getCookie('csrftoken') }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload(); 
                } else {
                    alert('Error: ' + data.error);
                    btn.disabled = false;
                    btn.innerHTML = originalText;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Hubo un error de comunicación.');
                btn.disabled = false;
                btn.innerHTML = originalText;
            });
        });
    }

    // --- LÓGICA NUEVA SALIDA DIRECTA ---
    const wrapperProd = document.getElementById('wrapperProductoSalida');
    if (wrapperProd) {
        const select = wrapperProd.querySelector('.custom-select');
        const input = document.getElementById('producto_busqueda_salida');
        const fake = document.getElementById('producto_display_fake_salida');
        const hidden = document.getElementById('selectProductoSalida');
        const options = wrapperProd.querySelectorAll('.custom-option');

        const updateFakeVisibility = () => {
            if (document.activeElement === input || input.value.length > 0) {
                fake.style.opacity = "0";
            } else {
                fake.style.opacity = "1";
            }
        };

        input.addEventListener('focus', () => { 
            select.classList.add('open'); 
            updateFakeVisibility(); 
        });
        
        input.addEventListener('blur', () => {
            setTimeout(() => {
                select.classList.remove('open');
                updateFakeVisibility();
            }, 200);
        });

        input.addEventListener('input', function() {
            const term = this.value.toLowerCase();
            if (term.length > 0) {
                fake.innerHTML = `<span class="typing-text">${this.value}</span>`;
            } else {
                fake.innerHTML = '<span class="text-muted" style="font-weight:400;">Seleccionar...</span>';
            }
            options.forEach(opt => {
                const search = opt.getAttribute('data-search').toLowerCase();
                opt.style.display = search.includes(term) ? '-webkit-box' : 'none';
            });
            select.classList.add('open');
            updateFakeVisibility();
        });

        options.forEach(opt => {
            opt.addEventListener('click', function() {
                options.forEach(o => o.classList.remove('selected'));
                this.classList.add('selected');
                fake.innerHTML = this.innerHTML;
                fake.setAttribute('title', this.textContent.trim());
                input.value = this.textContent.trim();
                hidden.value = this.getAttribute('data-value');
                const precio = this.getAttribute('data-precio');
                if (precio) {
                    document.getElementById('inputPrecioSalida').value = precio;
                }
                select.classList.remove('open');
                updateFakeVisibility();
            });
        });

        window.addEventListener('click', (e) => {
            if (!wrapperProd.contains(e.target)) {
                select.classList.remove('open');
            }
        });
    }
});

/**
 * Agrega un artículo a la lista de la nueva salida directa
 */
function agregarAListaSalida() {
    const hidden = document.getElementById('selectProductoSalida');
    const fake = document.getElementById('producto_display_fake_salida');
    const prodId = hidden.value;
    const prodNombre = fake.innerText.trim();
    const cant = document.getElementById('inputCantidadSalida').value;
    const precio = document.getElementById('inputPrecioSalida').value;
    const total = (parseFloat(cant) * parseFloat(precio)).toFixed(2);

    if (!prodId || cant <= 0) {
        alert("Selecciona un producto y cantidad válida.");
        return;
    }

    const fila = `
        <tr>
            <td class="ps-3">
                <div class="fw-semibold small text-dark">${prodNombre}</div>
                <input type="hidden" name="producto_id[]" value="${prodId}">
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
                <button type="button" class="btn btn-sm text-danger p-0" onclick="this.closest('tr').remove(); calcularTotalSalida();">
                    <i class="bi bi-x-circle-fill"></i>
                </button>
            </td>
        </tr>
    `;

    document.getElementById('tablaCuerpoSalida').insertAdjacentHTML('beforeend', fila);
    document.getElementById('mensajeVacioSalida').style.display = 'none';
    
    // Reset inputs
    hidden.value = "";
    document.getElementById('producto_busqueda_salida').value = "";
    fake.innerHTML = '<span class="text-muted" style="font-weight:400;">Seleccionar...</span>';
    document.getElementById('inputCantidadSalida').value = 1;
    document.getElementById('inputPrecioSalida').value = "0.00";
    
    calcularTotalSalida();
}

function calcularTotalSalida() {
    let total = 0;
    document.querySelectorAll('#tablaCuerpoSalida tr').forEach(tr => {
        const text = tr.cells[3].innerText.replace('$', '');
        total += parseFloat(text);
    });
    document.getElementById('granTotalSalida').innerText = '$' + total.toFixed(2);
    if (total === 0) document.getElementById('mensajeVacioSalida').style.display = 'block';
}

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
