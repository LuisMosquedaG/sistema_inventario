// SOLICITUDCOMPRAS.JS — Lógica para Gestión de Requisiciones

// --- UTILERÍAS ---
function initCustomSelect(wrapperId, hiddenInputId, fakeDisplayId, searchInputId, optionsContainerId) {
    const wrapper = document.getElementById(wrapperId);
    if (!wrapper) return;
    const hiddenInput = document.getElementById(hiddenInputId);
    const fakeDisplay = document.getElementById(fakeDisplayId);
    const searchInput = document.getElementById(searchInputId);
    const optionsContainer = document.getElementById(optionsContainerId);
    const selectDiv = wrapper.querySelector('.custom-select');

    const placeholderText = fakeDisplay.innerText.trim();

    function toggleOptions(show) {
        if (show) selectDiv.classList.add('open');
        else selectDiv.classList.remove('open');
    }

    function updateDisplay() {
        if (document.activeElement === searchInput) {
            fakeDisplay.style.visibility = "hidden";
        } else {
            fakeDisplay.style.visibility = "visible";
            if (!hiddenInput.value || hiddenInput.value === "") {
                fakeDisplay.innerHTML = `<span class="placeholder-text">${placeholderText}</span>`;
            }
        }
    }

    searchInput.addEventListener('focus', () => {
        toggleOptions(true);
        updateDisplay();
    });

    searchInput.addEventListener('blur', () => {
        setTimeout(() => {
            toggleOptions(false);
            updateDisplay();
        }, 150);
    });
    
    searchInput.addEventListener('input', function() {
        updateDisplay();
        const term = this.value.toLowerCase().trim();
        const options = optionsContainer.querySelectorAll('.custom-option');
        
        options.forEach(opt => {
            const searchText = (opt.getAttribute('data-search') || '').toLowerCase();
            opt.style.display = searchText.includes(term) ? 'flex' : 'none';
        });
        toggleOptions(true);
    });

    optionsContainer.addEventListener('click', (e) => {
        const option = e.target.closest('.custom-option');
        if (!option || option.classList.contains('disabled')) return;

        const valId = option.getAttribute('data-value');
        const valText = (option.getAttribute('data-name') || option.textContent).trim();

        hiddenInput.value = valId;
        fakeDisplay.innerText = valText;
        searchInput.value = ''; 
        updateDisplay();
        
        toggleOptions(false);
        hiddenInput.dispatchEvent(new Event('change'));
        if (hiddenInputId === 'add_producto') {
            actualizarCostoDefault();
        }
    });

    window.addEventListener('click', (e) => {
        if (!wrapper.contains(e.target)) {
            toggleOptions(false);
            updateDisplay();
        }
    });
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

const csrftoken = getCookie('csrftoken');

let productoCompraActual = null;

// --- INICIALIZACIÓN ---
function prepararNuevaSolicitud() {
    const form = document.getElementById('formNuevaSolicitud');
    if (form) form.reset();
    
    document.getElementById('solicitud_id_edit').value = '';
    document.getElementById('item_indice_edicion').value = '-1';
    document.getElementById('tituloModalSolicitud').innerText = 'Nueva Solicitud de Compra';
    document.getElementById('cuerpoTablaSolicitud').innerHTML = '';
    document.getElementById('mensajeVacioSolicitud').style.display = 'block';
    
    // Resetear Custom Select de Producto
    const pInput = document.getElementById('add_producto');
    if (pInput) pInput.value = '';
    const pFake = document.getElementById('add_producto_display_fake');
    if (pFake) {
        pFake.innerHTML = '<span class="placeholder-text">Buscar producto...</span>';
        pFake.style.visibility = "visible";
    }
    const sInput = document.getElementById('add_producto_busqueda');
    if (sInput) sInput.value = '';

    // Resetear totales
    document.getElementById('solicitudSubtotal').innerText = '$0.00';
    document.getElementById('solicitudIvaTotal').innerText = '$0.00';
    document.getElementById('granTotalSolicitud').innerText = '$0.00';
    
    const aplicaIvaSwitch = document.getElementById('aplica_iva_switch');
    if (aplicaIvaSwitch) {
        aplicaIvaSwitch.checked = true;
    }
    
    // Resetear botón de agregar
    const btn = document.getElementById('btnAddItem');
    if (btn) {
        btn.innerHTML = '<i class="bi bi-plus-lg"></i>';
        btn.classList.remove('btn-success');
        btn.classList.add('btn-brand');
    }

    // Ocultar sección de datos de pedido
    document.getElementById('seccion_datos_pedido').style.display = 'none';
    
    // Resetear sucursales general
    const genSuc = document.getElementById('gen_sucursal');
    if (genSuc) {
        genSuc.innerHTML = '<option value="">Seleccione proveedor primero...</option>';
        genSuc.disabled = true;
    }

    // Resetear unidades y conversiones
    const addUC = document.getElementById('add_unidad_compra');
    if (addUC) addUC.innerHTML = '<option value="BASE" data-factor="1">Unidad Base</option>';
    const addFC = document.getElementById('add_factor_conversion');
    if (addFC) addFC.value = '1.0000';
    const addCIV = document.getElementById('add_cantidad_inventario_val');
    if (addCIV) addCIV.value = '1.00';
    const addUBN = document.getElementById('add_unidad_base_nombre');
    if (addUBN) addUBN.value = '';
    const addEI = document.getElementById('add_entrada_inventario');
    if (addEI) addEI.value = '--';
    productoCompraActual = null;
}

// --- LOGICA DE SUCURSALES ---
async function cargarSucursalesProveedor(proveedorId, targetSelectId, selectedSucursalId = null) {
    const select = document.getElementById(targetSelectId);
    if (!proveedorId) {
        select.innerHTML = '<option value="">Seleccione proveedor primero...</option>';
        select.disabled = true;
        return;
    }

    try {
        const response = await fetch(`/api/proveedores/${proveedorId}/`);
        const data = await response.json();
        
        select.innerHTML = '<option value="">Matriz / Única</option>';
        if (data.sucursales && data.sucursales.length > 0) {
            data.sucursales.forEach(s => {
                const sel = (selectedSucursalId == s.id) ? 'selected' : '';
                select.insertAdjacentHTML('beforeend', `<option value="${s.id}" ${sel}>${s.nombre}</option>`);
            });
        }
        select.disabled = false;
    } catch (error) {
        console.error("Error al cargar sucursales:", error);
    }
}

// --- CONVERSIONES Y ENTRADA A INVENTARIO ---
async function cargarConversionesParaCompra(productoId, unidadPrevia = null, factorPrevio = null) {
    const selectUnidad = document.getElementById('add_unidad_compra');
    if (!selectUnidad) return;

    if (!productoId) {
        selectUnidad.innerHTML = '<option value="BASE" data-factor="1">Unidad Base</option>';
        document.getElementById('add_factor_conversion').value = '1.0000';
        document.getElementById('add_unidad_base_nombre').value = '';
        document.getElementById('add_entrada_inventario').value = '--';
        productoCompraActual = null;
        return;
    }

    // 1. OBTENCIÓN INMEDIATA DESDE EL DOM PARA RESPUESTA INSTANTÁNEA
    const optDom = document.querySelector(`#optionsAddProducto .custom-option[data-value="${productoId}"]`);
    const baseNomDom = optDom ? (optDom.getAttribute('data-unidad') || 'Pieza') : 'Pieza';
    const baseCostoDom = parseFloat(optDom ? optDom.getAttribute('data-precio') : 0) || 0;

    productoCompraActual = {
        id: productoId,
        nombre: optDom ? optDom.getAttribute('data-name') : '',
        unidad_base: baseNomDom,
        unidad_base_code: '',
        precio_costo: baseCostoDom,
        conversiones: []
    };

    document.getElementById('add_unidad_base_nombre').value = baseNomDom;

    // Poblar de inmediato con Unidad Base para que nunca quede vacío
    selectUnidad.innerHTML = `<option value="BASE" data-factor="1.0000" data-display="${baseNomDom}">${baseNomDom} (Base)</option>`;
    if (!unidadPrevia) {
        document.getElementById('add_factor_conversion').value = '1.0000';
        calcularEntradaInventario();
    }

    // 2. CONSULTAR CONVERSIONES EN EL BACKEND
    try {
        let response = await fetch(`/inventario/api/conversiones/${productoId}/`);
        if (!response.ok) {
            response = await fetch(`/api/conversiones/${productoId}/`);
        }
        if (!response.ok) {
            response = await fetch(`/inventario/conversiones/${productoId}/`);
        }

        const data = await response.json();

        if (data && data.success) {
            const prod = data.producto;
            productoCompraActual = {
                id: prod.id,
                nombre: prod.nombre,
                unidad_base: prod.unidad_medida,
                unidad_base_code: prod.unidad_medida_code,
                precio_costo: parseFloat(prod.precio_costo) || baseCostoDom,
                conversiones: data.conversiones || []
            };

            document.getElementById('add_unidad_base_nombre').value = prod.unidad_medida;

            // Re-poblar select con datos oficiales y conversiones
            selectUnidad.innerHTML = '';

            // Opción Base
            const optBase = document.createElement('option');
            optBase.value = 'BASE';
            optBase.setAttribute('data-factor', '1.0000');
            optBase.setAttribute('data-display', prod.unidad_medida);
            optBase.textContent = `${prod.unidad_medida} (Base)`;
            selectUnidad.appendChild(optBase);

            // Opciones Conversiones
            if (data.conversiones && data.conversiones.length > 0) {
                data.conversiones.filter(c => c.activo).forEach(c => {
                    const opt = document.createElement('option');
                    const nombreConv = c.unidad_destino_nombre || c.unidad_destino_display;
                    opt.value = nombreConv;
                    opt.setAttribute('data-factor', c.factor_equivalencia);
                    opt.setAttribute('data-display', nombreConv);
                    opt.textContent = `${nombreConv} (${c.factor_equivalencia} ${prod.unidad_medida})`;
                    selectUnidad.appendChild(opt);
                });
            }

            // Si se indicó unidad previa (al editar partida)
            if (unidadPrevia) {
                let matched = false;
                for (let i = 0; i < selectUnidad.options.length; i++) {
                    if (selectUnidad.options[i].value === unidadPrevia || selectUnidad.options[i].getAttribute('data-display') === unidadPrevia) {
                        selectUnidad.selectedIndex = i;
                        matched = true;
                        break;
                    }
                }
                if (!matched && factorPrevio) {
                    for (let i = 0; i < selectUnidad.options.length; i++) {
                        if (parseFloat(selectUnidad.options[i].getAttribute('data-factor')) === parseFloat(factorPrevio)) {
                            selectUnidad.selectedIndex = i;
                            break;
                        }
                    }
                }
                cambiarUnidadCompra(false);
            } else {
                cambiarUnidadCompra(true);
            }
        }
    } catch (err) {
        console.warn("Aviso al cargar conversiones de compra:", err);
    }
}

function cambiarUnidadCompra(actualizarCosto = true) {
    const selectUnidad = document.getElementById('add_unidad_compra');
    if (!selectUnidad || selectUnidad.selectedIndex < 0) return;

    const opt = selectUnidad.options[selectUnidad.selectedIndex];
    const factor = parseFloat(opt.getAttribute('data-factor')) || 1.0;
    document.getElementById('add_factor_conversion').value = factor.toFixed(4);

    if (actualizarCosto && productoCompraActual) {
        const selectLista = document.getElementById('add_lista');
        const optLista = selectLista && selectLista.selectedIndex >= 0 ? selectLista.options[selectLista.selectedIndex] : null;

        let costoCalculado = productoCompraActual.precio_costo * factor;

        if (optLista && selectLista.value) {
            const p = parseFloat(optLista.getAttribute('data-porc')) || 0;
            const m = parseFloat(optLista.getAttribute('data-monto')) || 0;
            if (p !== 0) costoCalculado = costoCalculado + (costoCalculado * (p / 100));
            else if (m !== 0) costoCalculado = costoCalculado + (m * factor);
        }

        document.getElementById('add_costo').value = costoCalculado.toFixed(2);
    }

    calcularEntradaInventario();
}

function calcularEntradaInventario() {
    const cant = parseFloat(document.getElementById('add_cantidad').value) || 0;
    const factor = parseFloat(document.getElementById('add_factor_conversion').value) || 1.0;
    const entrada = cant * factor;

    document.getElementById('add_cantidad_inventario_val').value = entrada.toFixed(2);

    const unidadBase = document.getElementById('add_unidad_base_nombre').value || '';
    const entradaInput = document.getElementById('add_entrada_inventario');
    if (entradaInput) {
        if (cant <= 0) {
            entradaInput.value = '--';
        } else {
            const entStr = (Math.round(entrada * 100) / 100).toLocaleString('en-US', { maximumFractionDigits: 2 });
            entradaInput.value = `${entStr} ${unidadBase}`.trim();
        }
    }
}

// --- AGREGAR / ACTUALIZAR ARTÍCULO ---
function agregarArticuloManual() {
    const pInput = document.getElementById('add_producto');
    const prodId = pInput.value;
    
    if (!prodId) {
        alert("Selecciona un producto.");
        return;
    }

    const opt = document.querySelector(`#optionsAddProducto .custom-option[data-value="${prodId}"]`);
    const prodNombre = opt ? opt.getAttribute('data-name') : "Producto";
    const ivaPorc = parseFloat(opt ? opt.getAttribute('data-iva') : 0) || 0;
    
    const listaId = document.getElementById('add_lista').value;
    const listaNombre = document.getElementById('add_lista').options[document.getElementById('add_lista').selectedIndex].text;
    const cantidad = parseFloat(document.getElementById('add_cantidad').value) || 0;
    const costo = parseFloat(document.getElementById('add_costo').value) || 0;

    if (cantidad <= 0) {
        alert("Selecciona una cantidad válida.");
        return;
    }

    // Cálculos
    const subtotal = cantidad * costo;
    const ivaMonto = subtotal * (ivaPorc / 100);
    const total = subtotal + ivaMonto;

    // Obtener valores de Configuración General (Defaults)
    const provId = document.getElementById('gen_proveedor').value;
    const provNombre = provId ? document.getElementById('gen_proveedor').options[document.getElementById('gen_proveedor').selectedIndex].text : 'No asignado';
    
    const sucId = document.getElementById('gen_sucursal').value;
    const sucNombre = (sucId && !document.getElementById('gen_sucursal').disabled) ? 
                      document.getElementById('gen_sucursal').options[document.getElementById('gen_sucursal').selectedIndex].text : 
                      (provId ? 'Matriz' : '--');

    const almId = document.getElementById('gen_almacen').value;
    const almNombre = almId ? document.getElementById('gen_almacen').options[document.getElementById('gen_almacen').selectedIndex].text : 'No asignado';

    const monId = document.getElementById('gen_moneda').value;
    const monSiglas = document.getElementById('gen_moneda').options[document.getElementById('gen_moneda').selectedIndex].text;

    const selUnidad = document.getElementById('add_unidad_compra');
    const optUnidad = selUnidad && selUnidad.selectedIndex >= 0 ? selUnidad.options[selUnidad.selectedIndex] : null;
    const unidadCompraVal = selUnidad ? selUnidad.value : 'BASE';
    const unidadCompraDisplay = optUnidad ? (optUnidad.getAttribute('data-display') || optUnidad.text) : '';
    const factorConv = parseFloat(document.getElementById('add_factor_conversion').value) || 1.0;
    const cantInv = parseFloat(document.getElementById('add_cantidad_inventario_val').value) || (cantidad * factorConv);
    const unidadBaseNom = document.getElementById('add_unidad_base_nombre').value || (opt ? opt.getAttribute('data-unidad') : '');

    const datos = {
        producto_id: prodId,
        producto_nombre: prodNombre,
        cantidad: cantidad,
        unidad_compra: unidadCompraVal === 'BASE' ? (unidadBaseNom || 'BASE') : unidadCompraVal,
        unidad_compra_display: unidadCompraDisplay,
        factor_conversion: factorConv,
        cantidad_inventario: cantInv,
        unidad_base: unidadBaseNom,
        proveedor_id: provId,
        proveedor_nombre: provNombre,
        sucursal_id: sucId,
        sucursal_nombre: sucNombre,
        almacen_id: almId,
        almacen_nombre: almNombre,
        costo_unitario: costo,
        subtotal: subtotal,
        iva_porcentaje: ivaPorc,
        iva_monto: ivaMonto,
        total: total,
        moneda_id: monId,
        moneda_siglas: monSiglas,
        lista_id: listaId,
        lista_nombre: listaNombre,
        detalle_pedido_origen_id: document.getElementById('edit_item_pedido_det_id').value
    };

    const indiceEdicion = parseInt(document.getElementById('item_indice_edicion').value);

    if (indiceEdicion >= 0) {
        const tbody = document.getElementById('cuerpoTablaSolicitud');
        const row = tbody.rows[indiceEdicion];
        if (row) {
            actualizarFilaHtml(row, datos);
        }
        document.getElementById('item_indice_edicion').value = '-1';
        document.getElementById('edit_item_pedido_det_id').value = '';
        const btn = document.getElementById('btnAddItem');
        btn.innerHTML = '<i class="bi bi-plus-lg"></i>';
        btn.classList.replace('btn-success', 'btn-brand');
    } else {
        agregarFilaProducto(datos);
    }

    // Resetear selección
    pInput.value = '';
    document.getElementById('add_producto_display_fake').innerHTML = '<span class="text-muted" style="font-weight:400;">Buscar producto...</span>';
    document.getElementById('add_lista').value = '';
    document.getElementById('add_cantidad').value = 1;
    document.getElementById('add_costo').value = '0.00';
    document.getElementById('add_factor_conversion').value = '1.0000';
    document.getElementById('add_cantidad_inventario_val').value = '1.00';
    document.getElementById('add_entrada_inventario').value = '--';
    const resetUC = document.getElementById('add_unidad_compra');
    if (resetUC) resetUC.innerHTML = '<option value="BASE" data-factor="1">Unidad Base</option>';
    productoCompraActual = null;
    calcularTotalSolicitud();
}

// --- MANEJO DE FILAS DINÁMICAS ---
function agregarFilaProducto(datos) {
    const tbody = document.getElementById('cuerpoTablaSolicitud');
    document.getElementById('mensajeVacioSolicitud').style.display = 'none';
    
    const row = document.createElement('tr');
    row.style.fontSize = '0.85rem';
    
    actualizarFilaHtml(row, datos);
    tbody.appendChild(row);
}

function actualizarFilaHtml(row, datos) {
    const cantCompra = parseFloat(datos.cantidad) || 0;
    const factor = parseFloat(datos.factor_conversion) || 1.0;
    const cantInv = parseFloat(datos.cantidad_inventario) || (cantCompra * factor);
    const uCompraDisplay = datos.unidad_compra_display || datos.unidad_compra || '';
    const uBaseDisplay = datos.unidad_base || '';

    row.innerHTML = `
        <td class="ps-3">
            <div class="fw-bold text-dark text-truncate" style="max-width: 200px;" title="${datos.producto_nombre}">${datos.producto_nombre}</div>
            <input type="hidden" name="producto_id[]" value="${datos.producto_id}">
            <input type="hidden" name="pedido_det_id[]" value="${datos.detalle_pedido_origen_id || ''}">
            <input type="hidden" name="unidad_base[]" value="${uBaseDisplay}">
        </td>
        <td>
            <span class="text-muted small">${datos.lista_id ? datos.lista_nombre : 'Manual'}</span>
            <input type="hidden" name="lista_id[]" value="${datos.lista_id || ''}">
        </td>
        <td class="text-center">
            <span class="badge bg-light text-dark border">${datos.moneda_siglas}</span>
            <input type="hidden" name="moneda_id[]" value="${datos.moneda_id}">
        </td>
        <td>
            <div class="small text-truncate" style="max-width: 150px;" title="${datos.proveedor_nombre}">${datos.proveedor_nombre}</div>
            <input type="hidden" name="proveedor_id[]" value="${datos.proveedor_id || ''}">
            <input type="hidden" name="sucursal_id[]" value="${datos.sucursal_id || ''}">
        </td>
        <td>
            <div class="small text-truncate" style="max-width: 120px;" title="${datos.almacen_nombre}">${datos.almacen_nombre}</div>
            <input type="hidden" name="almacen_id[]" value="${datos.almacen_id || ''}">
        </td>
        <td class="text-center">
            <span class="small fw-semibold text-dark">${cantCompra}</span>
            <span class="text-muted d-block" style="font-size: 0.72rem;">${uCompraDisplay}</span>
            <input type="hidden" name="cantidad[]" value="${cantCompra}">
            <input type="hidden" name="unidad_compra[]" value="${datos.unidad_compra || ''}">
            <input type="hidden" name="factor_conversion[]" value="${factor}">
        </td>
        <td class="text-center">
            <span class="small fw-bold text-brand">${cantInv}</span>
            <span class="text-muted d-block" style="font-size: 0.72rem;">${uBaseDisplay}</span>
            <input type="hidden" name="cantidad_inventario[]" value="${cantInv}">
        </td>
        <td class="text-end">
            <span class="small text-muted">$${parseFloat(datos.costo_unitario).toFixed(2)}</span>
            <input type="hidden" name="costo_unitario[]" value="${datos.costo_unitario}">
        </td>
        <td class="text-end cell-subtotal">
            <span class="small text-dark">$${parseFloat(datos.subtotal).toFixed(2)}</span>
        </td>
        <td class="text-end cell-iva">
            <span class="small text-muted">$${parseFloat(datos.iva_monto).toFixed(2)}</span>
            <input type="hidden" name="iva_porcentaje[]" value="${datos.iva_porcentaje}">
        </td>
        <td class="text-end pe-3 cell-total">
            <span class="fw-bold small text-dark">$${parseFloat(datos.total).toFixed(2)}</span>
        </td>
        <td class="text-center">
            <div class="d-flex justify-content-center gap-1">
                <button type="button" class="icon-action" onclick="cargarItemParaEdicion(this)" title="Editar Partida">
                    <i class="bi bi-pencil-square"></i>
                </button>
                <button type="button" class="icon-action icon-action-danger" onclick="eliminarFila(this)" title="Eliminar">
                    <i class="bi bi-x-circle"></i>
                </button>
            </div>
        </td>
    `;
}

function calcularTotalSolicitud() {
    let subtotalTotal = 0;
    let ivaTotal = 0;
    let granTotal = 0;

    const aplicaIvaSwitch = document.getElementById('aplica_iva_switch');
    const aplicaIva = aplicaIvaSwitch ? aplicaIvaSwitch.checked : true;

    document.querySelectorAll('#cuerpoTablaSolicitud tr').forEach(fila => {
        const subCell = fila.querySelector('.cell-subtotal');
        const ivaCell = fila.querySelector('.cell-iva');
        const totCell = fila.querySelector('.cell-total');
        if (!subCell || !ivaCell || !totCell) return;

        const sub = parseFloat(subCell.querySelector('span')?.innerText.replace('$', '').replace(/,/g, '')) || 0;
        
        // Obtener el IVA porcentaje original del input hidden
        const ivaInput = ivaCell.querySelector('input[name="iva_porcentaje[]"]');
        const ivaPorc = ivaInput ? parseFloat(ivaInput.value) : 0;
        
        const iva = aplicaIva ? (sub * (ivaPorc / 100)) : 0;
        const tot = sub + iva;
        
        // Actualizar visualmente la celda de IVA
        const ivaSpan = ivaCell.querySelector('span');
        if (ivaSpan) ivaSpan.innerText = '$' + iva.toFixed(2);
        
        // Actualizar visualmente la celda de Importe
        const totSpan = totCell.querySelector('span');
        if (totSpan) totSpan.innerText = '$' + tot.toFixed(2);
        
        subtotalTotal += sub;
        ivaTotal += iva;
        granTotal += tot;
    });

    document.getElementById('solicitudSubtotal').innerText = '$' + subtotalTotal.toLocaleString('en-US', {minimumFractionDigits: 2});
    document.getElementById('solicitudIvaTotal').innerText = '$' + ivaTotal.toLocaleString('en-US', {minimumFractionDigits: 2});
    document.getElementById('granTotalSolicitud').innerText = '$' + granTotal.toLocaleString('en-US', {minimumFractionDigits: 2});
}

async function cargarItemParaEdicion(btn) {
    const row = btn.closest('tr');
    const index = row.rowIndex - 1; 
    
    const prodId = row.querySelector('[name="producto_id[]"]').value;
    const prodNombre = row.querySelector('.fw-bold.text-dark').innerText;
    const pedDetId = row.querySelector('[name="pedido_det_id[]"]')?.value || '';
    const listaId = row.querySelector('[name="lista_id[]"]').value;
    const monId = row.querySelector('[name="moneda_id[]"]').value;
    const provId = row.querySelector('[name="proveedor_id[]"]').value;
    const sucId = row.querySelector('[name="sucursal_id[]"]').value;
    const almId = row.querySelector('[name="almacen_id[]"]').value;
    const cant = row.querySelector('[name="cantidad[]"]').value;
    const costo = row.querySelector('[name="costo_unitario[]"]').value;
    const uCompra = row.querySelector('[name="unidad_compra[]"]')?.value || '';
    const factor = row.querySelector('[name="factor_conversion[]"]')?.value || '1.0000';
    const uBase = row.querySelector('[name="unidad_base[]"]')?.value || '';

    document.getElementById('add_producto').value = prodId;
    document.getElementById('add_producto_display_fake').innerHTML = `<span>${prodNombre}</span>`;
    document.getElementById('add_lista').value = listaId;
    document.getElementById('add_cantidad').value = cant;
    document.getElementById('add_costo').value = costo;
    document.getElementById('edit_item_pedido_det_id').value = pedDetId;
    document.getElementById('add_factor_conversion').value = factor;
    document.getElementById('add_unidad_base_nombre').value = uBase;
    
    document.getElementById('gen_proveedor').value = provId;
    document.getElementById('gen_almacen').value = almId;
    document.getElementById('gen_moneda').value = monId;
    
    cargarSucursalesProveedor(provId, 'gen_sucursal', sucId);

    // Cargar conversiones y seleccionar unidad
    await cargarConversionesParaCompra(prodId, uCompra, factor);
    // Mantener los valores guardados
    document.getElementById('add_costo').value = costo;
    document.getElementById('add_cantidad').value = cant;
    calcularEntradaInventario();

    document.getElementById('item_indice_edicion').value = index;
    const btnAdd = document.getElementById('btnAddItem');
    btnAdd.innerHTML = '<i class="bi bi-check-lg"></i>';
    btnAdd.classList.remove('btn-brand');
    btnAdd.classList.add('btn-success');
    
    document.querySelector('.modal-body').scrollTop = 0;
}

// --- LÓGICA: APLICAR TODO ---
function toggleAplicarTodo() {
    const isChecked = document.getElementById('switchAplicarTodo').checked;
    if (isChecked) {
        sincronizarSiAplicarTodo('proveedor');
        sincronizarSiAplicarTodo('sucursal');
        sincronizarSiAplicarTodo('almacen');
        sincronizarSiAplicarTodo('moneda');
    }
}

function sincronizarSiAplicarTodo(campo) {
    const isChecked = document.getElementById('switchAplicarTodo').checked;
    if (!isChecked) return;

    const tbody = document.getElementById('cuerpoTablaSolicitud');
    const rows = tbody.rows;

    let newValue = "";
    let newText = "";

    switch(campo) {
        case 'proveedor':
            const selProv = document.getElementById('gen_proveedor');
            newValue = selProv.value;
            newText = newValue ? selProv.options[selProv.selectedIndex].text : 'No asignado';
            for (let i = 0; i < rows.length; i++) {
                rows[i].querySelector('[name="proveedor_id[]"]').value = newValue;
                rows[i].cells[3].querySelector('div').innerText = newText;
            }
            break;
        case 'sucursal':
            const selSuc = document.getElementById('gen_sucursal');
            newValue = selSuc.value;
            newText = (newValue && !selSuc.disabled) ? selSuc.options[selSuc.selectedIndex].text : (document.getElementById('gen_proveedor').value ? 'Matriz' : '--');
            for (let i = 0; i < rows.length; i++) {
                rows[i].querySelector('[name="sucursal_id[]"]').value = newValue;
            }
            break;
        case 'almacen':
            const selAlm = document.getElementById('gen_almacen');
            newValue = selAlm.value;
            newText = newValue ? selAlm.options[selAlm.selectedIndex].text : 'No asignado';
            for (let i = 0; i < rows.length; i++) {
                rows[i].querySelector('[name="almacen_id[]"]').value = newValue;
                rows[i].cells[4].querySelector('div').innerText = newText;
            }
            break;
        case 'moneda':
            const selMon = document.getElementById('gen_moneda');
            newValue = selMon.value;
            newText = selMon.options[selMon.selectedIndex].text;
            for (let i = 0; i < rows.length; i++) {
                rows[i].querySelector('[name="moneda_id[]"]').value = newValue;
                rows[i].cells[2].querySelector('.badge').innerText = newText;
            }
            break;
    }
}

function eliminarFila(btn) {
    const row = btn.closest('tr');
    row.remove();
    if (document.getElementById('cuerpoTablaSolicitud').children.length === 0) {
        document.getElementById('mensajeVacioSolicitud').style.display = 'block';
    }
    calcularTotalSolicitud();
}

function actualizarCostoDefault() {
    const prodId = document.getElementById('add_producto').value;
    if (!prodId) {
        cargarConversionesParaCompra(null);
        return;
    }

    const opt = document.querySelector(`#optionsAddProducto .custom-option[data-value="${prodId}"]`);
    const precio = opt ? opt.getAttribute('data-precio') : '0.00';
    
    document.getElementById('add_costo').value = precio;
    document.getElementById('add_lista').value = '';

    cargarConversionesParaCompra(prodId);
}

function aplicarListaCosto() {
    const prodId = document.getElementById('add_producto').value;
    const selectLista = document.getElementById('add_lista');
    const inputCosto = document.getElementById('add_costo');

    if (!prodId) return;

    const optProd = document.querySelector(`#optionsAddProducto .custom-option[data-value="${prodId}"]`);
    const factor = parseFloat(document.getElementById('add_factor_conversion').value) || 1.0;
    const costoUnitBase = productoCompraActual ? productoCompraActual.precio_costo : (parseFloat(optProd ? optProd.getAttribute('data-precio') : 0) || 0);
    const base = costoUnitBase * factor;

    const optLista = selectLista.options[selectLista.selectedIndex];

    if (!selectLista.value) {
        inputCosto.value = base.toFixed(2);
        return;
    }

    const p = parseFloat(optLista.getAttribute('data-porc')) || 0;
    const m = parseFloat(optLista.getAttribute('data-monto')) || 0;

    let final = base;
    if (p !== 0) final = base + (base * (p / 100));
    else if (m !== 0) final = base + (m * factor);

    inputCosto.value = final.toFixed(2);
}

// --- GUARDAR ---
async function guardarSolicitud(event) {
    event.preventDefault();
    
    if (document.getElementById('cuerpoTablaSolicitud').children.length === 0) {
        alert("Debes agregar al menos un producto a la solicitud.");
        return;
    }

    const form = document.getElementById('formNuevaSolicitud');
    const id = document.getElementById('solicitud_id_edit').value;
    const url = id ? `/solicitudes-compras/actualizar/${id}/` : '/solicitudes-compras/crear-manual/';
    
    const formData = new FormData(form);
    const btn = document.getElementById('btnGuardarSolicitud');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Guardando...';
    
    try {
        const response = await fetch(url, {
            method: 'POST',
            body: formData,
            headers: { 'X-CSRFToken': csrftoken }
        });
        const result = await response.json();
        
        if (result.success) {
            location.reload();
        } else {
            alert("Error: " + result.error);
        }
    } catch (error) {
        console.error("Error:", error);
        alert("Ocurrió un error al guardar.");
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Guardar Solicitud';
    }
}

// --- VER / EDITAR ---
async function verSolicitud(id) {
    try {
        const response = await fetch(`/solicitudes-compras/api/solicitud/${id}/`);
        const data = await response.json();
        
        if (data.error) {
            alert(data.error);
            return;
        }

        document.getElementById('ver_folio_solicitud').innerText = `SOL-${String(id).padStart(4, '0')}`;
        document.getElementById('ver_estado_solicitud').innerText = data.estado_display;
        document.getElementById('ver_estado_solicitud').className = `status-pill status-${data.estado}`;
        document.getElementById('ver_solicitante_solicitud').innerText = data.solicitante_nombre;
        document.getElementById('ver_fecha_solicitud').innerText = data.fecha_creacion;
        document.getElementById('ver_notas_solicitud').innerText = data.notas || 'Sin notas.';
        
        const elPed = document.getElementById('ver_pedido_origen');
        if (data.pedido_origen) {
            elPed.innerHTML = `<a href="javascript:void(0)" onclick="verPedido(${data.pedido_origen.id})" class="text-brand fw-bold text-decoration-none">
                                    <i class="bi bi-link-45deg me-1"></i>PED-${String(data.pedido_origen.id).padStart(4, '0')}
                               </a>`;
        } else {
            elPed.innerText = 'Manual';
        }

        const tbody = document.getElementById('cuerpoVerSolicitud');
        tbody.innerHTML = '';

        if (data.grupos && data.grupos.length > 0) {
            data.grupos.forEach(grupo => {
                // Fila de Encabezado de Grupo (Estilo Árbol)
                const isDirect = grupo.nombre === "Compras Directas / Reabastecimiento";
                const trGrupo = document.createElement('tr');
                trGrupo.style.backgroundColor = '#f8f9fa';
                trGrupo.innerHTML = `
                    <td colspan="10" class="ps-3 py-2">
                        <div class="d-flex align-items-center">
                            <i class="bi ${isDirect ? 'bi-cart-fill' : 'bi-gear-wide-connected'} me-2 text-brand" style="font-size: 1rem;"></i>
                            <span class="fw-bold text-dark uppercase" style="font-size: 0.75rem; letter-spacing: 0.5px;">
                                ${grupo.nombre}
                            </span>
                        </div>
                    </td>
                `;
                tbody.appendChild(trGrupo);

                // Filas de Items del Grupo
                grupo.items.forEach(d => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td class="ps-5">
                            <div class="d-flex align-items-center">
                                <i class="bi bi-arrow-return-right text-muted me-2"></i>
                                <span class="text-dark small" title="${d.producto_nombre}">${d.producto_nombre}</span>
                            </div>
                        </td>
                        <td class="text-center small">
                            <span class="fw-semibold">${d.cantidad}</span>
                            <span class="text-muted d-block" style="font-size: 0.72rem;">${d.unidad_compra_display || d.unidad_compra || ''}</span>
                        </td>
                        <td class="text-center small">
                            <span class="text-brand fw-semibold">${d.cantidad_inventario}</span>
                            <span class="text-muted d-block" style="font-size: 0.72rem;">${d.unidad_base || ''}</span>
                        </td>
                        <td class="small text-muted text-truncate" style="max-width: 150px;" title="${d.proveedor_nombre}">${d.proveedor_nombre}</td>
                        <td class="small text-muted text-truncate" style="max-width: 120px;" title="${d.almacen_nombre}">${d.almacen_nombre}</td>
                        <td class="text-end small">$${parseFloat(d.costo_unitario).toLocaleString('en-US', {minimumFractionDigits:2})}</td>
                        <td class="text-center small text-muted">${d.tipo_cambio}</td>
                        <td class="text-end small text-dark">$${parseFloat(d.subtotal).toLocaleString('en-US', {minimumFractionDigits:2})}</td>
                        <td class="text-end small text-muted">$${parseFloat(d.iva_monto).toLocaleString('en-US', {minimumFractionDigits:2})}</td>
                        <td class="text-end pe-3 fw-bold small text-dark">$${parseFloat(d.total).toLocaleString('en-US', {minimumFractionDigits:2})}</td>
                    `;
                    tbody.appendChild(tr);
                });
            });
        } else {
            tbody.innerHTML = '<tr><td colspan="10" class="text-center py-3 text-muted fst-italic">No hay artículos en esta solicitud.</td></tr>';
        }

        document.getElementById('ver_solicitud_subtotal').innerText = `$${parseFloat(data.subtotal_total || 0).toLocaleString('en-US', {minimumFractionDigits:2})}`;
        document.getElementById('ver_solicitud_iva_total').innerText = `$${parseFloat(data.iva_total || 0).toLocaleString('en-US', {minimumFractionDigits:2})}`;
        document.getElementById('ver_total_solicitud').innerText = `$${parseFloat(data.gran_total || 0).toLocaleString('en-US', {minimumFractionDigits:2})}`;
        
        const modal = new bootstrap.Modal(document.getElementById('modalVerSolicitud'));
        modal.show();

    } catch (error) {
        console.error("Error:", error);
        alert("No se pudo cargar la información.");
    }
}

async function cargarParaEdicion(id) {
    try {
        const response = await fetch(`/solicitudes-compras/api/solicitud/${id}/`);
        const data = await response.json();
        
        if (data.error) {
            alert(data.error);
            return;
        }

        prepararNuevaSolicitud(); 
        
        document.getElementById('solicitud_id_edit').value = id;
        document.getElementById('tituloModalSolicitud').innerText = `Editar Solicitud SOL-${String(id).padStart(4, '0')}`;
        document.getElementById('notas_solicitud').value = data.notas || '';
        
        const aplicaIvaSwitch = document.getElementById('aplica_iva_switch');
        if (aplicaIvaSwitch) {
            aplicaIvaSwitch.checked = data.aplica_iva !== false;
        }
        
        const secPedido = document.getElementById('seccion_datos_pedido');
        if (data.pedido_origen) {
            secPedido.style.display = 'block';
            document.getElementById('edit_folio_cotizacion').innerText = data.pedido_origen.cotizacion_origen_id ? `COT-${String(data.pedido_origen.cotizacion_origen_id).padStart(4, '0')}` : '--';
            document.getElementById('edit_folio_pedido').innerText = `PED-${String(data.pedido_origen.id).padStart(4, '0')}`;
            document.getElementById('edit_cliente_pedido').innerText = data.pedido_origen.cliente.nombre_completo;
        } else {
            secPedido.style.display = 'none';
        }

        const tbody = document.getElementById('cuerpoTablaSolicitud');
        tbody.innerHTML = '';
        document.getElementById('mensajeVacioSolicitud').style.display = 'none';

        data.detalles.forEach(d => {
            let lNombre = 'Manual';
            if (d.lista_id) {
                const lObj = listaCostos.find(lc => lc.id == d.lista_id);
                if (lObj) lNombre = lObj.nombre;
            }

            agregarFilaProducto({
                producto_id: d.producto_id,
                producto_nombre: d.producto_nombre,
                cantidad: d.cantidad,
                unidad_compra: d.unidad_compra,
                unidad_compra_display: d.unidad_compra_display,
                factor_conversion: d.factor_conversion,
                cantidad_inventario: d.cantidad_inventario,
                unidad_base: d.unidad_base,
                proveedor_id: d.proveedor_id,
                proveedor_nombre: d.proveedor_nombre,
                sucursal_id: d.sucursal_id,
                sucursal_nombre: d.sucursal_nombre || (d.proveedor_id ? 'Matriz' : '--'),
                almacen_id: d.almacen_id,
                almacen_nombre: d.almacen_nombre,
                costo_unitario: d.costo_unitario,
                subtotal: d.subtotal,
                iva_porcentaje: d.iva_porcentaje,
                iva_monto: d.iva_monto,
                total: d.total,
                moneda_id: d.moneda_id,
                moneda_siglas: d.moneda_siglas,
                lista_id: d.lista_id,
                lista_nombre: lNombre,
                detalle_pedido_origen_id: d.detalle_pedido_origen_id
            });
        });
        
        calcularTotalSolicitud();

        const modal = new bootstrap.Modal(document.getElementById('modalNuevaSolicitudManual'));
        modal.show();

    } catch (error) {
        console.error("Error:", error);
        alert("No se pudo cargar la solicitud para editar.");
    }
}


async function previsualizarAutorizacion(id) {
    if (!confirm(`¿Está seguro de autorizar la Solicitud SOL-${String(id).padStart(4, '0')}?\n\nSe generarán las órdenes de compra correspondientes agrupadas por proveedor.`)) {
        return;
    }

    try {
        const response = await fetch(`/solicitudes-compras/autorizar/${id}/`, {
            method: 'POST',
            headers: { 
                'X-CSRFToken': csrftoken,
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        const result = await response.json();
        
        if (result.success) {
            alert(result.message);
            location.reload();
        } else {
            alert("Error al autorizar: " + (result.error || result.message));
        }
    } catch (error) {
        console.error("Error:", error);
        alert("Ocurrió un error en el servidor.");
    }
}

// Al final del archivo o en un block ready
document.addEventListener('DOMContentLoaded', function() {
    initCustomSelect('wrapperAddProducto', 'add_producto', 'add_producto_display_fake', 'add_producto_busqueda', 'optionsAddProducto');
    
    // Listener para actualizar costo al cambiar producto
    const pInput = document.getElementById('add_producto');
    if (pInput) {
        pInput.addEventListener('change', actualizarCostoDefault);
    }
});
