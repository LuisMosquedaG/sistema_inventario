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
    if (form) {
        form.reset();
        // Asegurar que el campo clave se limpie explícitamente si reset() no lo hace
        const claveInput = document.getElementById('inputClave');
        if (claveInput) claveInput.value = '';
    }
    
    const idField = document.getElementById('productoId');
    if (idField) idField.value = '';

    const hidSuc = document.getElementById('hiddenSucursalArticulo');
    if (hidSuc) hidSuc.value = sucursalId;
    
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

    // Reset Monedas
    const selMonedaC = document.getElementById('selectMonedaCosto');
    const selMonedaV = document.getElementById('selectMonedaVenta');
    if (selMonedaC) selMonedaC.value = "1.0000";
    if (selMonedaV) selMonedaV.value = "1.0000";

    // Reset IVA
    const checkIVA = document.getElementById('checkIVA');
    if (checkIVA) {
        checkIVA.checked = true;
        const inputIVA = document.getElementById('inputIVA');
        if (inputIVA) {
            inputIVA.disabled = false;
            inputIVA.classList.remove('bg-light');
            inputIVA.value = "16";
        }
    }

    actualizarCalculosPrecios();
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
            const claveInput = document.getElementById('inputClave');
            if (claveInput) claveInput.value = data.clave || '';
            
            form.querySelector('[name="nombre"]').value = data.nombre || '';
            form.querySelector('[name="descripcion"]').value = data.descripcion || '';
            form.querySelector('[name="tipo"]').value = data.tipo || 'producto';
            form.querySelector('[name="tipo_abastecimiento"]').value = data.tipo_abastecimiento || 'compra';
            form.querySelector('[name="estado"]').value = data.estado || 'activo';
            form.querySelector('[name="categoria"]').value = data.categoria || '';
            form.querySelector('[name="marca"]').value = data.marca || '';
            form.querySelector('[name="modelo"]').value = data.modelo || '';
            form.querySelector('[name="linea"]').value = data.linea || '';
            form.querySelector('[name="unidad_medida"]').value = data.unidad_medida || 'H87';
            form.querySelector('[name="iva"]').value = data.iva || '0.00';
            form.querySelector('[name="ieps"]').value = data.ieps || '0.00';
            form.querySelector('[name="precio_costo"]').value = data.precio_costo || '0.00';
            form.querySelector('[name="precio_venta"]').value = data.precio_venta || '0.00';
            
            // Resetear selectores de moneda a MXN al cargar producto existente (ya está en pesos)
            const selMonedaC = document.getElementById('selectMonedaCosto');
            const selMonedaV = document.getElementById('selectMonedaVenta');
            if (selMonedaC) selMonedaC.value = "1.0000";
            if (selMonedaV) selMonedaV.value = "1.0000";

            form.querySelector('[name="stock_minimo"]').value = data.stock_minimo || 0;
            form.querySelector('[name="stock_maximo"]').value = data.stock_maximo || 1000;
            form.querySelector('[name="maneja_lote"]').checked = data.maneja_lote || false;
            form.querySelector('[name="maneja_serie"]').checked = data.maneja_serie || false;
            form.querySelector('[name="tiene_iva"]').checked = data.tiene_iva ?? true;
            toggleIVA();
            
            const hidSuc = document.getElementById('hiddenSucursalArticulo');
            if (hidSuc) hidSuc.value = data.sucursal || '';

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

            actualizarCalculosPrecios();
            mostrarModal('modalCrearArticulo');
        })
        .catch(err => alert(err.message));
}

window.toggleIVA = function() {
    const check = document.getElementById('checkIVA');
    const input = document.getElementById('inputIVA');
    if (!check || !input) return;
    
    if (check.checked) {
        input.readOnly = false;
        input.classList.remove('bg-light');
    } else {
        input.readOnly = true;
        input.classList.add('bg-light');
    }
}

window.actualizarCalculosPrecios = function() {
    let costo = parseFloat(document.getElementById('inputPrecioCosto').value) || 0;
    let venta = parseFloat(document.getElementById('inputPrecioVenta').value) || 0;
    const ivaPorc = parseFloat(document.getElementById('inputIVA').value) || 0;
    const tieneIva = document.getElementById('checkIVA').checked;
    
    // --- LÓGICA DE CONVERSIÓN INDEPENDIENTE A MXN ---
    const selectMonedaCosto = document.getElementById('selectMonedaCosto');
    const selectMonedaVenta = document.getElementById('selectMonedaVenta');
    
    let factorCosto = 1.0;
    let factorVenta = 1.0;
    
    if (selectMonedaCosto) {
        factorCosto = parseFloat(selectMonedaCosto.value) || 1.0;
    }
    if (selectMonedaVenta) {
        factorVenta = parseFloat(selectMonedaVenta.value) || 1.0;
    }

    // Convertimos ambos valores a MXN de forma independiente
    const costoMXN = costo * factorCosto;
    const ventaMXN = venta * factorVenta;

    let ivaMontoMXN = 0;
    if (tieneIva) {
        ivaMontoMXN = ventaMXN * (ivaPorc / 100);
    }

    const totalMXN = ventaMXN + ivaMontoMXN;
    
    let margen = 0;
    if (ventaMXN > 0) {
        // El margen ahora sí variará si las monedas son diferentes
        margen = ((ventaMXN - costoMXN) / ventaMXN) * 100;
    }

    const fmt = (v) => '$' + v.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' MXN';

    // Mostramos resultados finales siempre en pesos
    document.getElementById('infoIVAMonto').innerText = fmt(ivaMontoMXN);
    document.getElementById('infoTotalVenta').innerText = fmt(totalMXN);
    document.getElementById('infoMargenPrec').innerText = margen.toFixed(1) + '%';
    
    // Cambiar color del margen según el valor
    const elMargen = document.getElementById('infoMargenPrec');
    if (margen < 0) {
        elMargen.classList.remove('text-dark');
        elMargen.classList.add('text-danger');
    } else {
        elMargen.classList.remove('text-danger');
        elMargen.classList.add('text-dark');
    }
}

window.guardarProducto = function() {
    const form = document.getElementById('formCrearArticulo');
    if (!form) return;
    
    const id = document.getElementById('productoId').value;
    const url = id ? APP_URLS.api_actualizar_producto.replace('0', id) : APP_URLS.api_crear_producto;
    
    const formData = new FormData(form);
    
    // --- CONVERSIÓN INDEPENDIENTE A MXN ANTES DE GUARDAR ---
    const factorCosto = parseFloat(document.getElementById('selectMonedaCosto').value) || 1.0;
    const factorVenta = parseFloat(document.getElementById('selectMonedaVenta').value) || 1.0;

    const costoOrig = parseFloat(formData.get('precio_costo')) || 0;
    const ventaOrig = parseFloat(formData.get('precio_venta')) || 0;
    
    formData.set('precio_costo', (costoOrig * factorCosto).toFixed(2));
    formData.set('precio_venta', (ventaOrig * factorVenta).toFixed(2));
    
    fetch(url, {
        method: 'POST',
        body: formData,
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

// --- 2. RESERVAS ---

window.abrirModalReservas = function(id, nombre) {
    const t = document.getElementById('tituloModalReservas');
    if (t) t.innerText = `Reservas: ${nombre}`;
    
    const tbody = document.getElementById('tbodyReservas');
    const totalEl = document.getElementById('totalReservasModal');

    const spinner = '<tr><td colspan="4" class="text-center py-3"><span class="spinner-border spinner-border-sm"></span> Cargando reservas...</td></tr>';
    if (tbody) tbody.innerHTML = spinner;
    if (totalEl) totalEl.innerText = '0';

    mostrarModal('modalVerReservas');

    fetch(`${APP_URLS.api_detalle_reservas}${id}/`)
        .then(r => r.json())
        .then(data => {
            if (tbody) {
                tbody.innerHTML = '';
                if (data.reservas && data.reservas.length > 0) {
                    data.reservas.forEach(r => {
                        tbody.insertAdjacentHTML('beforeend', `
                            <tr>
                                <td class="text-center">
                                    <span class="icon-action text-muted hover-red" title="Eliminar Reserva" onclick="eliminarReserva(${r.id}, ${id}, '${nombre}')">
                                        <i class="bi bi-x-circle" style="font-size: 1rem;"></i>
                                    </span>
                                </td>
                                <td class="text-center">
                                    <div class="fw-semibold small text-dark">${r.cliente}</div>
                                </td>
                                <td class="text-center">
                                    <span class="font-monospace small text-dark">${r.folio}</span>
                                </td>
                                <td class="text-center">
                                    <span class="small text-muted">${r.fecha}</span>
                                </td>
                                <td class="text-center">
                                    <span class="small text-dark">${r.cantidad}</span>
                                </td>
                            </tr>`);
                    });
                } else {
                    tbody.innerHTML = '<tr><td colspan="5" class="text-center py-3 text-muted italic">No hay reservas activas para este producto.</td></tr>';
                }
            }
            if (totalEl) totalEl.innerText = data.total || '0';
        })
        .catch(err => {
            console.error(err);
            if (tbody) tbody.innerHTML = '<tr><td colspan="5" class="text-center text-danger py-3">Error al cargar datos.</td></tr>';
        });
}

window.eliminarReserva = function(detalleId, productoId, productoNombre) {
    if (!confirm(`¿Estás seguro de eliminar esta reserva? El stock volverá a estar disponible y la partida del pedido regresará a estado "Pendiente".`)) {
        return;
    }

    fetch(`${APP_URLS.api_cancelar_reserva}${detalleId}/`, {
        method: 'GET',
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            alert(data.message);
            // Recargar el modal para ver los cambios
            abrirModalReservas(productoId, productoNombre);
            
            // Opcional: Podrías recargar la página principal si quieres ver el stock actualizado en la tabla de atrás
            // location.reload();
        } else {
            alert("Error: " + data.error);
        }
    })
    .catch(err => {
        console.error(err);
        alert("Ocurrió un error al intentar eliminar la reserva.");
    });
}

// --- 3. RECETAS (MRP) ---

window.abrirConfigurarReceta = function() {
    const form = document.getElementById('formReceta');
    if (form) form.reset();

    // Resetear el buscador personalizado si existe (Padre)
    const fake = document.getElementById('receta_padre_fake');
    const hidden = document.getElementById('selectRecetaPadre');
    const busqueda = document.getElementById('receta_padre_busqueda');
    if (fake && hidden && busqueda) {
        fake.innerHTML = '<span class="text-muted" style="font-weight:400;">Seleccionar Producto (Tipo: Producción)...</span>';
        hidden.value = '';
        busqueda.value = '';
        fake.style.opacity = "1";
    }

    // Resetear el buscador personalizado si existe (Componente)
    const fakeC = document.getElementById('componente_fake');
    const hiddenC = document.getElementById('selectComponente');
    const busquedaC = document.getElementById('componente_busqueda');
    if (fakeC && hiddenC && busquedaC) {
        fakeC.innerHTML = '<span class="text-muted" style="font-weight:400;">Seleccionar componente...</span>';
        hiddenC.value = '';
        busquedaC.value = '';
        fakeC.style.opacity = "1";
    }

    const tbody = document.getElementById('tbodyRecetaEdit');
    if (tbody) tbody.innerHTML = '';
    document.getElementById('subtotalReceta').innerText = '$0.00';
    document.getElementById('ivaTotalReceta').innerText = '$0.00';
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
                    const cant = i.cant;
                    const costo = i.costo;
                    const subtotal = cant * costo;
                    const ivaPorc = i.tiene_iva ? (parseFloat(i.iva) || 0) : 0;
                    const ivaMonto = subtotal * (ivaPorc / 100);
                    const importe = subtotal + ivaMonto;

                    tbody.insertAdjacentHTML('beforeend', `
                        <tr data-id="${i.id}" data-costo="${costo}" data-iva-porc="${ivaPorc}">
                            <td class="ps-3">${i.nombre}</td>
                            <td class="text-center">
                                <span class="small text-dark">${cant}</span>
                                <input type="hidden" class="inp-cant-receta" value="${cant}">
                            </td>
                            <td class="text-end text-muted small">$${costo.toFixed(2)}</td>
                            <td class="text-end subtotal-fila">$${subtotal.toFixed(2)}</td>
                            <td class="text-end iva-fila text-muted small">$${ivaMonto.toFixed(2)}</td>
                            <td class="text-end importe-fila">$${importe.toFixed(2)}</td>
                            <td class="text-center">
                                <div class="d-flex justify-content-center gap-1">
                                    <button type="button" class="icon-action" onclick="editarFilaReceta(this)" title="Editar">
                                        <i class="bi bi-pencil-square"></i>
                                    </button>
                                    <button type="button" class="icon-action icon-action-danger" onclick="this.closest('tr').remove(); recalcularTotalesReceta();" title="Eliminar">
                                        <i class="bi bi-x-circle"></i>
                                    </button>
                                </div>
                            </td>
                        </tr>`);
                });
                recalcularTotalesReceta();
            } else {
                if (msg) msg.style.display = 'block';
                document.getElementById('subtotalReceta').innerText = '$0.00';
                document.getElementById('ivaTotalReceta').innerText = '$0.00';
                document.getElementById('totalCostoReceta').innerText = '$0.00';
            }
        });
}

window.agregarComponenteReceta = function() {
    const hiddenC = document.getElementById('selectComponente');
    const pId = hiddenC.value;
    const cant = parseInt(document.getElementById('cantComponente').value) || 1;
    const editIndex = document.getElementById('edit_index_receta').value;

    if (!pId) return alert("Selecciona un componente");
    
    // Si no estamos editando, verificar si ya existe en la lista para sumar
    if (editIndex === "-1") {
        const existente = document.querySelector(`#tbodyRecetaEdit tr[data-id="${pId}"]`);
        if (existente) {
            const inp = existente.querySelector('.inp-cant-receta');
            const span = existente.querySelector('.text-center span');
            const nuevaCant = parseInt(inp.value) + cant;
            inp.value = nuevaCant;
            span.innerText = nuevaCant;
            recalcularTotalesReceta();
            resetBuscadorComponente();
            return;
        }
    }

    fetch(APP_URLS.api_producto.replace('0', pId))
        .then(r => r.json())
        .then(data => {
            const tbody = document.getElementById('tbodyRecetaEdit');
            const msg = document.getElementById('msgVacioReceta');
            if (msg) msg.style.display = 'none';
            
            const costo = parseFloat(data.precio_costo) || 0;
            const subtotal = cant * costo;
            const ivaPorc = data.tiene_iva ? (parseFloat(data.iva) || 0) : 0;
            const ivaMonto = subtotal * (ivaPorc / 100);
            const importe = subtotal + ivaMonto;

            const filaHtml = `
                <td class="ps-3">${data.nombre}</td>
                <td class="text-center">
                    <span class="small text-dark">${cant}</span>
                    <input type="hidden" class="inp-cant-receta" value="${cant}">
                </td>
                <td class="text-end text-muted small">$${costo.toFixed(2)}</td>
                <td class="text-end subtotal-fila">$${subtotal.toFixed(2)}</td>
                <td class="text-end iva-fila text-muted small">$${ivaMonto.toFixed(2)}</td>
                <td class="text-end importe-fila">$${importe.toFixed(2)}</td>
                <td class="text-center">
                    <div class="d-flex justify-content-center gap-1">
                        <button type="button" class="icon-action" onclick="editarFilaReceta(this)" title="Editar">
                            <i class="bi bi-pencil-square"></i>
                        </button>
                        <button type="button" class="icon-action icon-action-danger" onclick="this.closest('tr').remove(); recalcularTotalesReceta();" title="Eliminar">
                            <i class="bi bi-x-circle"></i>
                        </button>
                    </div>
                </td>
            `;

            if (editIndex !== "-1") {
                const fila = tbody.rows[parseInt(editIndex)];
                fila.innerHTML = filaHtml;
                fila.dataset.id = data.id;
                fila.dataset.costo = costo;
                fila.dataset.ivaPorc = ivaPorc;
            } else {
                const tr = document.createElement('tr');
                tr.dataset.id = data.id;
                tr.dataset.costo = costo;
                tr.dataset.ivaPorc = ivaPorc;
                tr.innerHTML = filaHtml;
                tbody.appendChild(tr);
            }

            recalcularTotalesReceta();
            resetBuscadorComponente();
        });
}

function resetBuscadorComponente() {
    const fakeC = document.getElementById('componente_fake');
    const hiddenC = document.getElementById('selectComponente');
    const busquedaC = document.getElementById('componente_busqueda');
    if (fakeC && hiddenC && busquedaC) {
        fakeC.innerHTML = '<span class="text-muted" style="font-weight:400;">Seleccionar componente...</span>';
        hiddenC.value = '';
        busquedaC.value = '';
        fakeC.style.opacity = "1";
    }
    document.getElementById('cantComponente').value = 1;
    document.getElementById('edit_index_receta').value = "-1";
    
    const btnAdd = document.querySelector('button[onclick="agregarComponenteReceta()"]');
    if (btnAdd) btnAdd.innerHTML = '<i class="bi bi-plus-lg"></i>';
}

window.editarFilaReceta = function(btn) {
    const fila = btn.closest('tr');
    const tbody = document.getElementById('tbodyRecetaEdit');
    const index = Array.from(tbody.rows).indexOf(fila);
    const pId = fila.dataset.id;
    const cant = fila.querySelector('.inp-cant-receta').value;

    document.getElementById('edit_index_receta').value = index;
    document.getElementById('cantComponente').value = cant;

    // Cargar en el buscador
    const hiddenC = document.getElementById('selectComponente');
    const fakeC = document.getElementById('componente_fake');
    const busquedaC = document.getElementById('componente_busqueda');
    const option = document.querySelector(`#wrapperComponente .custom-option[data-value="${pId}"]`);

    if (option) {
        hiddenC.value = pId;
        fakeC.innerHTML = option.innerHTML;
        fakeC.setAttribute('title', option.textContent.trim());
        busquedaC.value = "";
        fakeC.style.opacity = "1";
    }

    // Cambiar icono del botón a check para indicar edición
    const btnAdd = document.querySelector('button[onclick="agregarComponenteReceta()"]');
    if (btnAdd) btnAdd.innerHTML = '<i class="bi bi-check-lg"></i>';
}

window.recalcularTotalesReceta = function() {
    let subtotalReceta = 0;
    let ivaTotalReceta = 0;

    document.querySelectorAll('#tbodyRecetaEdit tr').forEach(tr => {
        const costo = parseFloat(tr.dataset.costo) || 0;
        const ivaPorc = parseFloat(tr.dataset.ivaPorc) || 0;
        const cant = parseInt(tr.querySelector('.inp-cant-receta').value) || 0;
        
        const subtotalFila = costo * cant;
        const ivaFila = subtotalFila * (ivaPorc / 100);
        const importeFila = subtotalFila + ivaFila;

        tr.querySelector('.subtotal-fila').innerText = '$' + subtotalFila.toFixed(2);
        tr.querySelector('.iva-fila').innerText = '$' + ivaFila.toFixed(2);
        tr.querySelector('.importe-fila').innerText = '$' + importeFila.toFixed(2);
        
        subtotalReceta += subtotalFila;
        ivaTotalReceta += ivaFila;
    });

    const totalReceta = subtotalReceta + ivaTotalReceta;

    document.getElementById('subtotalReceta').innerText = '$' + subtotalReceta.toFixed(2);
    document.getElementById('ivaTotalReceta').innerText = '$' + ivaTotalReceta.toFixed(2);
    document.getElementById('totalCostoReceta').innerText = '$' + totalReceta.toFixed(2);
}

window.guardarReceta = function() {
    const pId = document.getElementById('selectRecetaPadre').value;
    if (!pId) return alert("Selecciona el producto final");
    const componentes = [];
    document.querySelectorAll('#tbodyRecetaEdit tr').forEach(tr => {
        componentes.push({ id: tr.dataset.id, cant: parseInt(tr.querySelector('.inp-cant-receta').value) });
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

/**
 * Filtra los almacenes mostrados en el modal de traslado según la sucursal seleccionada
 */
function filtrarAlmacenesTraslado(tipo) {
    const sucursalId = (tipo === 'origen') ? document.getElementById('selectSucursalOrigen').value : document.getElementById('selectSucursalDestino').value;
    const selectAlmacen = (tipo === 'origen') ? document.getElementById('selectAlmacenOrigen') : document.getElementById('selectAlmacenDestino');
    
    if (!selectAlmacen) return;

    // Resetear select de almacén
    selectAlmacen.value = "";
    
    if (sucursalId) {
        // Desbloquear si hay sucursal seleccionada
        selectAlmacen.disabled = false;
        selectAlmacen.options[0].textContent = "Seleccionar Almacén...";
    } else {
        // Bloquear si no hay sucursal
        selectAlmacen.disabled = true;
        selectAlmacen.options[0].textContent = "Selecciona sucursal primero...";
    }
    
    // Mostrar/ocultar opciones según sucursal
    let firstVisible = false;
    Array.from(selectAlmacen.options).forEach(opt => {
        if (!opt.value) {
            opt.style.display = "block"; // Opción vacía siempre visible
            return;
        }
        
        // Comparamos como strings
        if (opt.dataset.sucursal === String(sucursalId)) {
            opt.style.display = "block";
            if (!firstVisible) {
                // Opcional: podrías auto-seleccionar el primero si quisieras, 
                // pero el usuario pidió desbloquear y mostrar.
            }
        } else {
            opt.style.display = "none";
        }
    });

    // Si es origen, resetear productos ya que dependen del almacén
    if (tipo === 'origen') {
        cargarProductosEnOrigen();
    }
}

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
    const selectedOption = productoSelect.selectedOptions[0];
    const productoNombre = selectedOption?.text.split(' (Disp:')[0];
    const cantidad = parseInt(document.getElementById('inputCantidadTraslado').value);
    const selectLote = document.getElementById('selectLoteTraslado');
    const selectSerie = document.getElementById('selectSerieTraslado');
    
    if (!almacenOrigenId || !almacenDestinoId || !productoId || !cantidad || cantidad <= 0) {
        alert("Por favor, completa todos los campos.");
        return;
    }

    // --- VALIDACIÓN DE LOTES Y SERIES ---
    const stockInfo = JSON.parse(selectedOption?.dataset?.stockInfo || '{}');
    
    if (stockInfo.maneja_lote && !selectLote.disabled && !selectLote.value) {
        alert("Este producto maneja LOTES. Por favor, selecciona un lote con existencias para continuar.");
        selectLote.focus();
        return;
    }
    
    if (stockInfo.maneja_serie && !selectSerie.disabled && !selectSerie.value) {
        alert("Este producto maneja NÚMEROS DE SERIE. Por favor, selecciona una serie específica para continuar.");
        selectSerie.focus();
        return;
    }

    const extraId = selectLote.value || selectSerie.value || null;
    const extraNombre = selectLote.value ? selectLote.options[selectLote.selectedIndex].text : (selectSerie.value ? selectSerie.options[selectSerie.selectedIndex].text : null);
    
    const disponible = parseInt(document.getElementById('infoStockDisponible').innerText);
    
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
    const sucOrigen = document.getElementById('selectSucursalOrigen').value;
    const sucDestino = document.getElementById('selectSucursalDestino').value;
    const almacenOrigenId = document.getElementById('selectAlmacenOrigen').value;
    const almacenDestinoId = document.getElementById('selectAlmacenDestino').value;

    if (!sucOrigen || !sucDestino || !almacenOrigenId || !almacenDestinoId) {
        alert("Por favor, selecciona las sucursales y almacenes de origen y destino.");
        return;
    }

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

// --- Helper para Selects Personalizados con Buscador ---
function setupCustomSelect(wrapperId, inputId, fakeId, hiddenId, onSelect) {
    const wrapper = document.getElementById(wrapperId);
    if (!wrapper) return;
    const select = wrapper.querySelector('.custom-select');
    const input = document.getElementById(inputId);
    const fake = document.getElementById(fakeId);
    const hidden = document.getElementById(hiddenId);
    const options = wrapper.querySelectorAll('.custom-option');
    
    // Guardar el placeholder original
    const originalPlaceholder = fake.innerHTML;
    
    const updateVisibility = () => {
        if (!input || !fake) return;
        // Si hay texto escrito o se ha seleccionado algo, mostramos la capa fake
        if (input.value.length > 0 || (hidden && hidden.value !== "" && hidden.value !== "all")) {
            fake.style.opacity = "1";
        } else if (document.activeElement === input) {
            // Si está enfocado pero vacío, ocultamos el placeholder
            fake.style.opacity = "0";
        } else {
            // Si no está enfocado y está vacío, mostramos el placeholder
            fake.innerHTML = originalPlaceholder;
            fake.style.opacity = "1";
        }
    };

    if (input) {
        input.addEventListener('focus', () => { 
            // Limpiar selección previa al hacer clic para nueva búsqueda
            input.value = "";
            if (hidden) hidden.value = "";
            
            // Resetear visibilidad de todas las opciones al abrir
            options.forEach(o => o.style.display = 'flex');
            select.classList.add('open'); 
            updateVisibility(); 
        });
        
        input.addEventListener('blur', () => {
            setTimeout(() => {
                select.classList.remove('open');
                updateVisibility();
            }, 150);
        });

        input.addEventListener('input', function() {
            const t = this.value.toLowerCase();
            if (this.value.length > 0) {
                fake.innerHTML = `<span class="typing-text">${this.value}</span>`;
            } else {
                fake.innerHTML = originalPlaceholder;
            }
            updateVisibility();
            options.forEach(o => {
                const search = (o.getAttribute('data-search') || '').toLowerCase();
                o.style.display = search.includes(t) ? 'flex' : 'none';
            });
            select.classList.add('open');
        });
    }

    if (wrapper) {
        wrapper.addEventListener('mousedown', function(e) {
            const option = e.target.closest('.custom-option');
            if (!option) return;

            e.preventDefault();
            e.stopPropagation();

            select.classList.remove('open');
            if (input) {
                input.value = "";
                input.blur();
            }

            options.forEach(opt => opt.classList.remove('selected'));
            option.classList.add('selected');
            
            fake.innerHTML = option.innerHTML;
            fake.setAttribute('title', option.textContent.trim());
            
            const valId = option.getAttribute('data-value');
            if (hidden) hidden.value = valId;
            
            updateVisibility();
            if (onSelect) onSelect(valId);
        });
    }
}

// --- Inicialización ---
document.addEventListener('DOMContentLoaded', function() {
    // Inicializar buscador de Receta Padre
    setupCustomSelect(
        'wrapperRecetaPadre', 
        'receta_padre_busqueda', 
        'receta_padre_fake', 
        'selectRecetaPadre', 
        () => {
            if (typeof window.cargarRecetaExistente === 'function') {
                window.cargarRecetaExistente();
            }
        }
    );

    // Inicializar buscador de Agregar Componente
    setupCustomSelect(
        'wrapperComponente', 
        'componente_busqueda', 
        'componente_fake', 
        'selectComponente',
        null
    );

    // Inicializar filtros de traslado si existen los selects (en el modal)
    if (document.getElementById('selectSucursalOrigen')) {
        filtrarAlmacenesTraslado('origen');
    }
    if (document.getElementById('selectSucursalDestino')) {
        filtrarAlmacenesTraslado('destino');
    }

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
