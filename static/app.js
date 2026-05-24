/* ==========================================================================
   PDF-Pseudo — Lógica Interactiva del Frontend (JavaScript V2)
   ========================================================================== */

// Estado global de la aplicación
const state = {
    currentTab: 'anonimizar',
    anonFile: null,
    documentQueue: [],       // FASE 3: cola de documentos [{file, id, profileId}]
    profiles: [],            // FASE 3: perfiles del backend
    restorePdf: null,
    restoreKey: null,
    originalPdfBase64: null,
    pdfDocInstance: null,
    currentPage: 1,
    totalPages: 1,
    zoomScale: 1.0,
    fullText: '',
    pdfWords: [],
    analyzedEntities: [],
    selectedEntityIds: new Set(),
    activeSearchQuery: '',
    baseScale: null,
    pendingSelectionText: null,
    pendingSelectionBox: null,
    boxMode: false,          // FASE 5: modo dibujo manual
    boxStartX: null,
    boxStartY: null,
    downloadData: {
        anonPdfBase64: null, anonPdfName: null,
        keyBase64: null, keyName: null,
        restoredPdfBase64: null, restoredPdfName: null
    },
    progressInterval: null
};


// Mapeo amigable de tipos de entidades en español
const typeLabels = {
    'PERSON': 'Nombres',
    'ADDRESS': 'Direcciones',
    'ORGANIZATION': 'Organizaciones',
    'PHONE': 'Teléfonos',
    'EMAIL': 'Emails',
    'DNI': 'DNI',
    'NIE': 'NIE',
    'POSTAL_CODE': 'Cód. Postales',
    'IBAN': 'Cuentas IBAN',
    'CREDIT_CARD': 'Tarjetas'
};

const singleTypeLabels = {
    'PERSON': 'Nombre',
    'ADDRESS': 'Dirección',
    'ORGANIZATION': 'Organización',
    'PHONE': 'Teléfono',
    'EMAIL': 'Email',
    'DNI': 'DNI',
    'NIE': 'NIE',
    'POSTAL_CODE': 'Cód. Postal',
    'IBAN': 'Cuenta IBAN',
    'CREDIT_CARD': 'Tarjeta'
};

// ==========================================================================
// 0. Cola de documentos + Perfiles (FASE 3)
// ==========================================================================

async function loadProfiles() {
    try {
        const r = await fetch('/api/profiles');
        if (r.ok) state.profiles = await r.json();
    } catch (e) { /* sin conexión */ }
}

function addToQueue(file) {
    const item = {
        id: 'doc_' + Date.now(),
        file: file,
        profileId: 'default',
    };
    state.documentQueue.push(item);
    state.anonFile = state.documentQueue[0]?.file || null;
    renderQueue();
    document.getElementById('anonSubmitBtn').disabled = false;
}

function removeFromQueue(docId) {
    state.documentQueue = state.documentQueue.filter(d => d.id !== docId);
    state.anonFile = state.documentQueue[0]?.file || null;
    renderQueue();
    if (state.documentQueue.length === 0) {
        document.getElementById('anonSubmitBtn').disabled = true;
    }
}

function renderQueue() {
    const container = document.getElementById('documentQueue');
    const list = document.getElementById('queueList');
    const count = document.getElementById('queueCount');
    if (state.documentQueue.length === 0) {
        container.classList.add('hidden');
        return;
    }
    container.classList.remove('hidden');
    count.textContent = state.documentQueue.length;
    list.innerHTML = state.documentQueue.map(d => {
        const profileOpts = state.profiles.map(p =>
            `<option value="${p.id}" ${p.id === d.profileId ? 'selected' : ''}>${p.name}</option>`
        ).join('');
        return `<div class="queue-item">
            <span class="queue-item-name" title="${d.file.name}">${d.file.name}</span>
            <span class="queue-item-size">${formatBytes(d.file.size)}</span>
            <select class="queue-item-profile" onchange="updateQueueProfile('${d.id}', this.value)">${profileOpts}</select>
            <button class="queue-item-remove" onclick="removeFromQueue('${d.id}')">✖</button>
        </div>`;
    }).join('');
}

function updateQueueProfile(docId, profileId) {
    const item = state.documentQueue.find(d => d.id === docId);
    if (item) item.profileId = profileId;
}

async function startQueueAnalysis() {
    if (state.documentQueue.length === 0) return;
    const first = state.documentQueue[0];
    state.anonFile = first.file;
    await handleAnalyzeInternal(first.profileId);
}

// ==========================================================================
// 1. Gestión de Pestañas (Tab Switching)
// ==========================================================================

function switchTab(tabName) {
    if (tabName === state.currentTab) return;
    
    state.currentTab = tabName;
    
    // Elementos de la barra de pestañas
    const tabAnonBtn = document.getElementById('tabAnonBtn');
    const tabRestBtn = document.getElementById('tabRestBtn');
    
    // Paneles de contenido
    const tabAnonPanel = document.getElementById('tabAnonPanel');
    const tabRestPanel = document.getElementById('tabRestPanel');
    
    if (tabName === 'anonimizar') {
        // Activar botón Anonimizar
        tabAnonBtn.classList.add('active');
        tabAnonBtn.setAttribute('aria-selected', 'true');
        tabAnonPanel.classList.add('active');
        tabAnonPanel.removeAttribute('hidden');
        
        // Desactivar botón Restaurar
        tabRestBtn.classList.remove('active');
        tabRestBtn.setAttribute('aria-selected', 'false');
        tabRestPanel.classList.remove('active');
        tabRestPanel.setAttribute('hidden', '');
    } else {
        // Activar botón Restaurar
        tabRestBtn.classList.add('active');
        tabRestBtn.setAttribute('aria-selected', 'true');
        tabRestPanel.classList.add('active');
        tabRestPanel.removeAttribute('hidden');
        
        // Desactivar botón Anonimizar
        tabAnonBtn.classList.remove('active');
        tabAnonBtn.setAttribute('aria-selected', 'false');
        tabAnonPanel.classList.remove('active');
        tabAnonPanel.setAttribute('hidden', '');
    }
    
    // Ocultar resultados o paneles especiales al cambiar
    hideAllSectionsExceptPanel();
}

function switchSidebarTab(tabName) {
    const togglesBtn = document.getElementById('subtabTogglesBtn');
    const listBtn = document.getElementById('subtabListBtn');
    const togglesPanel = document.getElementById('sidebarTogglesPanel');
    const listPanel = document.getElementById('sidebarListPanel');

    if (tabName === 'toggles') {
        togglesBtn.classList.add('active');
        togglesBtn.setAttribute('aria-selected', 'true');
        togglesPanel.removeAttribute('hidden');

        listBtn.classList.remove('active');
        listBtn.setAttribute('aria-selected', 'false');
        listPanel.setAttribute('hidden', '');
    } else {
        listBtn.classList.add('active');
        listBtn.setAttribute('aria-selected', 'true');
        listPanel.removeAttribute('hidden');

        togglesBtn.classList.remove('active');
        togglesBtn.setAttribute('aria-selected', 'false');
        togglesPanel.setAttribute('hidden', '');

        setTimeout(() => {
            document.getElementById('entitySearchInput').focus();
        }, 50);
    }
}

function switchNavSection(section) {
    document.querySelectorAll('.sidebar-nav-item').forEach(item => item.classList.remove('active'));
    const activeItem = document.querySelector(`.sidebar-nav-item[data-nav="${section}"]`);
    if (activeItem) activeItem.classList.add('active');
}

function setStepperStep(step) {
    document.querySelectorAll('.stepper-step').forEach(s => s.classList.remove('active'));
    const target = document.querySelector(`.stepper-step[data-step="${step}"]`);
    if (target) target.classList.add('active');
}

// ==========================================================================
// 2. Controladores de Eventos de Drag & Drop y Selección de Archivos
// ==========================================================================

// Evitar comportamiento predeterminado del navegador para drag & drop globalmente
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    document.addEventListener(eventName, (e) => e.preventDefault(), false);
});

function handleDragOver(event, element) {
    element.classList.add('dragover');
}

function handleDragLeave(event, element) {
    element.classList.remove('dragover');
}

function handleDrop(event, element, type) {
    element.classList.remove('dragover');
    
    const files = event.dataTransfer.files;
    if (files.length === 0) return;
    
    const file = files[0];
    processFile(file, type);
}

function handleFileSelect(inputElement, type) {
    const files = inputElement.files;
    if (files.length === 0) return;
    
    const file = files[0];
    processFile(file, type);
    
    // Resetear el valor para que permita subir el mismo archivo otra vez si se borra
    inputElement.value = '';
}

// Procesa el archivo según el rol de la zona
function processFile(file, type) {
    if (type === 'pdf') {
        if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
            showError("Archivo no válido", "Solo se admiten documentos PDF.");
            return;
        }
        // FASE 3: añadir a la cola en vez de un solo archivo
        addToQueue(file);
    } else if (type === 'pdf_restore') {
        if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
            showError("Archivo no válido", "El archivo de restauración debe ser un documento PDF.");
            return;
        }
        state.restorePdf = file;
        
        const dropZone = document.getElementById('restPdfDropZone');
        const nameLabel = document.getElementById('restPdfName');
        nameLabel.textContent = file.name;
        dropZone.classList.add('has-file');
        
        checkRestoreButtonState();
        
    } else if (type === 'key') {
        if (!file.name.toLowerCase().endsWith('.key')) {
            showError("Archivo no válido", "El archivo de clave debe tener la extensión '.key'.");
            return;
        }
        state.restoreKey = file;
        
        const dropZone = document.getElementById('restKeyDropZone');
        const nameLabel = document.getElementById('restKeyName');
        nameLabel.textContent = file.name;
        dropZone.classList.add('has-file');
        
        checkRestoreButtonState();
    }
}

// Limpia el archivo seleccionado
function clearFile(prefix) {
    if (prefix === 'anon') {
        state.anonFile = null;
        state.documentQueue = [];
        renderQueue();
        document.getElementById('anonSubmitBtn').disabled = true;
    }
}

function checkRestoreButtonState() {
    const btn = document.getElementById('restoreSubmitBtn');
    if (state.restorePdf && state.restoreKey) {
        btn.disabled = false;
    } else {
        btn.disabled = true;
    }
}

// Helper para dar formato legible a los bytes del archivo
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

// ==========================================================================
// 3. Flujo de Animación de Progreso y Escaneo
// ==========================================================================

function startProgressAnimation(messages) {
    // Limpiar intervalo activo si existe
    if (state.progressInterval) {
        clearInterval(state.progressInterval);
    }
    
    const progressBarFill = document.getElementById('progressBarFill');
    const statusText = document.getElementById('processingStatusText');
    
    let progress = 10;
    let messageIndex = 0;
    
    progressBarFill.style.width = `${progress}%`;
    statusText.textContent = messages[messageIndex];
    
    // Intervalo de incremento simulado hasta el 90%
    state.progressInterval = setInterval(() => {
        if (progress < 90) {
            progress += Math.floor(Math.random() * 5) + 2; // Incrementar aleatoriamente
            if (progress > 90) progress = 90;
            progressBarFill.style.width = `${progress}%`;
        }
        
        // Cambiar mensajes del escáner en base al progreso
        const msgThreshold = 90 / messages.length;
        const targetMsgIndex = Math.floor(progress / msgThreshold);
        if (targetMsgIndex < messages.length && targetMsgIndex > messageIndex) {
            messageIndex = targetMsgIndex;
            statusText.textContent = messages[messageIndex];
        }
    }, 450);
}

function finishProgressAnimation() {
    clearInterval(state.progressInterval);
    state.progressInterval = null;
    const progressBarFill = document.getElementById('progressBarFill');
    progressBarFill.style.width = '100%';
}

// ==========================================================================
// 4. Peticiones al Servidor - FASE 1: ANALIZAR PDF
// ==========================================================================

async function handleAnalyzeInternal(profileId) {
    if (!state.anonFile) return;
    
    document.getElementById('tabAnonPanel').classList.remove('active');
    const processingSection = document.getElementById('processingSection');
    processingSection.classList.remove('hidden');
    
    const scanMessages = [
        "Leyendo el archivo PDF local...",
        "Extrayendo texto del documento...",
        "Analizando entidades PII en español...",
        "Ejecutando Presidio (reglas matemáticas de DNI/NIE)...",
        "Ejecutando GLiNER Zero-Shot (PERSON/ADDRESS/ORGANIZATION)...",
        "Llamando a Ollama LLM local (opcional)...",
        "Consolidando detecciones y unificando solapamientos...",
        "Calculando coordenadas relativas en las páginas...",
        "¡Preparando visor de mapa interactivo!"
    ];
    
    startProgressAnimation(scanMessages);
    
    const formData = new FormData();
    formData.append('file', state.anonFile);

    const useOllama = document.getElementById('useOllamaToggle').checked;
    formData.append('use_ollama', useOllama);
    if (profileId) formData.append('profile_id', profileId);
    
    try {
        const response = await fetch('/api/analyze', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || "Ha ocurrido un error al analizar el documento.");
        }
        
        // Finalizar barra y mostrar resultados interactivos
        finishProgressAnimation();
        
        setTimeout(async () => {
            processingSection.classList.add('hidden');
            
            // Guardar datos en el estado global
            state.originalPdfBase64 = data.pdf_base64;
            state.totalPages = data.pages_count;
            state.analyzedEntities = data.entities;
            state.fullText = data.full_text || '';
            state.pdfWords = data.words || [];
            state.zoomScale = 1.0;
            state.currentPage = 1;
            state.baseScale = null; // Resetear escala base para el nuevo documento
            
            // Reiniciar display del Zoom
            document.getElementById('zoomLevelDisplay').textContent = "100%";
            
            // Seleccionar todas las entidades inicialmente para anonimizar
            state.selectedEntityIds = new Set(data.entities.map(e => e.id));
            state.activeSearchQuery = '';
            
            // Resetear input de búsqueda
            document.getElementById('entitySearchInput').value = '';
            
            // Mostrar panel interactivo
            document.getElementById('interactivePanel').classList.remove('hidden');
            const titleEl = document.getElementById('interactiveDocTitle');
            if (titleEl) titleEl.textContent = state.anonFile.name;
            
            // Cargar y renderizar PDF
            await loadPdfDocument(data.pdf_base64);

            // Renderizar Sidebar y filtros
            renderSidebarFilters();

            // Iniciar en la pestaña de Categorías por defecto
            switchSidebarTab('toggles');

            // Avanzar stepper al paso 2 (Revisión)
            setStepperStep(2);
            
        }, 500); // Pequeño margen para ver el 100%
        
    } catch (error) {
        clearInterval(state.progressInterval);
        state.progressInterval = null;
        processingSection.classList.add('hidden');
        showError("Error en Análisis", error.message);
    }
}

// ==========================================================================
// 5. Visor interactivo PDF.js e Higlights Overlays
// ==========================================================================

async function loadPdfDocument(pdfBase64) {
    // Convertir Base64 a ArrayBuffer para PDF.js
    const binaryString = atob(pdfBase64);
    const len = binaryString.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i);
    }
    
    try {
        const loadingTask = pdfjsLib.getDocument({ data: bytes.buffer });
        state.pdfDocInstance = await loadingTask.promise;
        
        // Actualizar displays de paginación
        document.getElementById('totalPageNum').textContent = state.totalPages;
        document.getElementById('currentPageNum').textContent = state.currentPage;
        
        // Renderizar la primera página
        await renderPdfPage(state.currentPage);
        
        // Habilitar/deshabilitar botones de paginación
        updatePaginationButtons();
    } catch (error) {
        showError("Error al cargar PDF", "No se pudo inicializar el visor de PDF.js: " + error.message);
    }
}

async function renderPdfPage(pageNum) {
    if (!state.pdfDocInstance) return;
    
    try {
        const page = await state.pdfDocInstance.getPage(pageNum);
        
        const canvas = document.getElementById('pdfRenderCanvas');
        const context = canvas.getContext('2d');
        
        // Calcular escala en base al contenedor wrapper y aplicar Zoom
        const container = document.getElementById('pdfOverlayContainer');
        const wrapper = document.querySelector('.pdf-viewport-wrapper');
        
        const unscaledViewport = page.getViewport({ scale: 1.0 });
        
        // Calcular la escala base solo una vez para evitar que los scrollbars afecten el zoom dinámico
        if (!state.baseScale) {
            const containerWidth = (wrapper.clientWidth - 40) || 600;
            state.baseScale = containerWidth / unscaledViewport.width;
        }
        
        const scale = state.baseScale * state.zoomScale;
        const viewport = page.getViewport({ scale: scale });
        
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        
        // Asegurar que el contenedor tenga el tamaño exacto del viewport renderizado
        container.style.width = `${viewport.width}px`;
        container.style.height = `${viewport.height}px`;
        
        const renderContext = {
            canvasContext: context,
            viewport: viewport
        };
        
        await page.render(renderContext).promise;
        
        // Renderizar la capa de texto seleccionable nativa de PDF.js
        try {
            const textContent = await page.getTextContent();
            const textLayerDiv = document.getElementById('pdfTextLayer');
            textLayerDiv.innerHTML = '';
            
            // Ajustar dimensiones
            textLayerDiv.style.width = `${viewport.width}px`;
            textLayerDiv.style.height = `${viewport.height}px`;

            const textLayer = new pdfjsLib.TextLayer({
                container: textLayerDiv,
                textContentSource: textContent,
                viewport: viewport
            });
            
            await textLayer.render();
        } catch (textError) {
            console.warn("No se pudo renderizar la capa de texto seleccionable (puede ser un PDF escaneado sin OCR):", textError);
        }
        
        // Pintar la capa de overlays
        renderHighlightOverlays(pageNum);
        
    } catch (error) {
        console.error("Error al renderizar página del PDF:", error);
    }
}

function renderHighlightOverlays(pageNum) {
    const overlayLayer = document.getElementById('highlightOverlayLayer');
    overlayLayer.innerHTML = ''; // Limpiar overlays anteriores
    
    // El backend usa paginación 0-indexed, así que buscamos page_index = pageNum - 1
    const targetPageIndex = pageNum - 1;
    
    state.analyzedEntities.forEach(entity => {
        const isSelected = state.selectedEntityIds.has(entity.id);
        
        if (!entity.boxes) return;
        
        entity.boxes.forEach(box => {
            if (box.page === targetPageIndex) {
                // Crear el elemento de resaltado
                const highlight = document.createElement('div');
                highlight.className = `pdf-highlight type-${entity.entity_type}`;
                highlight.dataset.entityId = entity.id;
                
                // Posicionamiento en porcentajes relativos
                highlight.style.left = `${box.x0 * 100}%`;
                highlight.style.top = `${box.y0 * 100}%`;
                highlight.style.width = `${(box.x1 - box.x0) * 100}%`;
                highlight.style.height = `${(box.y1 - box.y0) * 100}%`;
                
                // Si no está seleccionado (se desactivó el filtro), atenuar el highlight
                if (!isSelected) {
                    highlight.style.opacity = '0.05';
                    highlight.style.border = 'none';
                    highlight.style.pointerEvents = 'none'; // Deshabilitar interacción si está inactivo
                } else {
                    highlight.style.opacity = '1';
                }
                
                // FASE 5: etiqueta de categoría visible en el highlight
                const shortLabel = (entity.entity_type === 'ADDRESS' ? 'DIR' :
                    entity.entity_type === 'ORGANIZATION' ? 'ORG' :
                    entity.entity_type === 'POSTAL_CODE' ? 'CP' :
                    entity.entity_type === 'CREDIT_CARD' ? 'CC' :
                    entity.entity_type).substring(0, 4);
                highlight.textContent = shortLabel;

                // Crear el tooltip flotante dentro del highlight
                const typeLabel = singleTypeLabels[entity.entity_type] || entity.entity_type;
                const tooltip = document.createElement('span');
                tooltip.className = 'pdf-highlight-tooltip';
                tooltip.textContent = `${typeLabel}: ${entity.text}`;
                highlight.appendChild(tooltip);
                
                // Eventos de sincronización Hover bidireccional
                highlight.addEventListener('mouseenter', () => {
                    // Resaltar la fila en el sidebar
                    const sidebarRow = document.querySelector(`.entity-row[data-entity-id="${entity.id}"]`);
                    if (sidebarRow) {
                        sidebarRow.classList.add('hovered');
                        sidebarRow.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    }
                    highlight.classList.add('pulse-glow');
                });
                
                highlight.addEventListener('mouseleave', () => {
                    // Quitar resaltado de la fila en el sidebar
                    const sidebarRow = document.querySelector(`.entity-row[data-entity-id="${entity.id}"]`);
                    if (sidebarRow) {
                        sidebarRow.classList.remove('hovered');
                    }
                    highlight.classList.remove('pulse-glow');
                });
                
                overlayLayer.appendChild(highlight);
            }
        });
    });
}

function changePage(direction) {
    const newPage = state.currentPage + direction;
    if (newPage >= 1 && newPage <= state.totalPages) {
        state.currentPage = newPage;
        document.getElementById('currentPageNum').textContent = state.currentPage;
        renderPdfPage(state.currentPage);
        updatePaginationButtons();
    }
}

function updatePaginationButtons() {
    document.getElementById('prevPageBtn').disabled = state.currentPage <= 1;
    document.getElementById('nextPageBtn').disabled = state.currentPage >= state.totalPages;
}

// ==========================================================================
// 5.5 Bounding Box Manual (FASE 5)
// ==========================================================================

function toggleBoxMode() {
    state.boxMode = !state.boxMode;
    const btn = document.getElementById('boxModeBtn');
    if (state.boxMode) {
        btn.classList.add('active');
        btn.textContent = '⊞ Dibujando...';
        document.getElementById('pdfOverlayContainer').style.cursor = 'crosshair';
    } else {
        btn.classList.remove('active');
        btn.textContent = '⊞ Manual';
        document.getElementById('pdfOverlayContainer').style.cursor = '';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const overlay = document.getElementById('pdfOverlayContainer');
    if (!overlay) return;

    overlay.addEventListener('mousedown', (e) => {
        if (!state.boxMode) return;
        const rect = overlay.getBoundingClientRect();
        state.boxStartX = (e.clientX - rect.left) / rect.width;
        state.boxStartY = (e.clientY - rect.top) / rect.height;
    });

    overlay.addEventListener('mouseup', (e) => {
        if (!state.boxMode || state.boxStartX === null) return;
        const rect = overlay.getBoundingClientRect();
        const endX = (e.clientX - rect.left) / rect.width;
        const endY = (e.clientY - rect.top) / rect.height;

        const x0 = Math.min(state.boxStartX, endX);
        const y0 = Math.min(state.boxStartY, endY);
        const x1 = Math.max(state.boxStartX, endX);
        const y1 = Math.max(state.boxStartY, endY);

        if (Math.abs(x1 - x0) < 0.01 || Math.abs(y1 - y0) < 0.01) {
            state.boxStartX = null;
            return;
        }

        const newId = 'manual_box_' + Date.now();
        const newEntity = {
            id: newId,
            text: '[Redactado manualmente]',
            entity_type: 'CUSTOM',
            score: 1.0,
            boxes: [{ page: state.currentPage - 1, x0, y0, x1, y1 }],
            source: 'manual',
        };

        state.analyzedEntities.push(newEntity);
        state.selectedEntityIds.add(newId);
        state.boxStartX = null;

        renderSidebarFilters();
        renderHighlightOverlays(state.currentPage);
    });

    overlay.addEventListener('mouseleave', () => {
        state.boxStartX = null;
    });

    loadProfiles();
});

// ==========================================================================
// 6. Sidebar - Filtros, Categorías Grupales y Listado
// ==========================================================================

function renderSidebarFilters() {
    const categoryGrid = document.getElementById('categoryGrid');
    categoryGrid.innerHTML = '';
    
    // Agrupar y contar entidades por tipo
    const counts = {};
    state.analyzedEntities.forEach(e => {
        counts[e.entity_type] = (counts[e.entity_type] || 0) + 1;
    });
    
    // Para cada tipo único detectado
    Object.keys(counts).forEach(type => {
        const count = counts[type];
        
        // Verificar si todas las entidades de este tipo están seleccionadas
        const entitiesOfType = state.analyzedEntities.filter(e => e.entity_type === type);
        const allSelected = entitiesOfType.every(e => state.selectedEntityIds.has(e.id));
        
        const card = document.createElement('div');
        card.className = 'category-card';
        
        const label = typeLabels[type] || type;
        card.innerHTML = `
            <div class="category-info-label">
                <span class="cat-name-lbl" title="${label}">${label}</span>
                <span class="cat-count-lbl">${count} ${count === 1 ? 'elemento' : 'elementos'}</span>
            </div>
            <label class="switch tiny" for="catToggle-${type}">
                <input type="checkbox" id="catToggle-${type}" ${allSelected ? 'checked' : ''} onchange="toggleCategory('${type}', this.checked)">
                <span class="slider round"></span>
            </label>
        `;
        
        categoryGrid.appendChild(card);
    });
    
    // Actualizar el contador global de entidades en el header del sidebar
    document.getElementById('entitiesCountBadge').textContent = state.analyzedEntities.length;
    
    // Renderizar la lista de entidades individuales
    renderIndividualEntitiesList();
}

function toggleCategory(type, isChecked) {
    state.analyzedEntities.forEach(e => {
        if (e.entity_type === type) {
            if (isChecked) {
                state.selectedEntityIds.add(e.id);
            } else {
                state.selectedEntityIds.delete(e.id);
            }
        }
    });
    
    // Volver a renderizar la lista individual y los highlights del PDF
    renderIndividualEntitiesList();
    renderHighlightOverlays(state.currentPage);
}

function renderIndividualEntitiesList() {
    const listContainer = document.getElementById('entitiesList');
    listContainer.innerHTML = '';
    
    const query = state.activeSearchQuery.toLowerCase().trim();
    
    // Filtrar entidades que coincidan con la búsqueda
    const filteredEntities = state.analyzedEntities.filter(entity => {
        if (!query) return true;
        const matchesText = entity.text.toLowerCase().includes(query);
        const matchesType = entity.entity_type.toLowerCase().includes(query);
        const translatedType = (typeLabels[entity.entity_type] || '').toLowerCase();
        return matchesText || matchesType || translatedType.includes(query);
    });
    
    if (filteredEntities.length === 0) {
        listContainer.innerHTML = `
            <div style="padding: 30px; text-align: center; color: var(--text-muted); font-size: 0.85rem;">
                No se encontraron datos que coincidan con la búsqueda.
            </div>
        `;
        return;
    }
    
    filteredEntities.forEach(entity => {
        const isSelected = state.selectedEntityIds.has(entity.id);
        
        // Obtener páginas en las que aparece
        let pageDesc = 'Pág. ';
        if (entity.boxes && entity.boxes.length > 0) {
            const pages = [...new Set(entity.boxes.map(b => b.page + 1))].sort((a,b)=>a-b);
            pageDesc += pages.join(', ');
        } else {
            pageDesc = 'Texto general';
        }
        
        const row = document.createElement('div');
        row.className = 'entity-row';
        row.dataset.entityId = entity.id;
        
        // Eventos hover para sincronización bidireccional
        row.addEventListener('mouseenter', () => {
            row.classList.add('hovered');
            // Hacer brillar los highlights correspondientes en el canvas
            const highlights = document.querySelectorAll(`.pdf-highlight[data-entity-id="${entity.id}"]`);
            highlights.forEach(hl => {
                hl.classList.add('hovered');
                hl.classList.add('pulse-glow');
            });
        });
        
        row.addEventListener('mouseleave', () => {
            row.classList.remove('hovered');
            const highlights = document.querySelectorAll(`.pdf-highlight[data-entity-id="${entity.id}"]`);
            highlights.forEach(hl => {
                hl.classList.remove('hovered');
                hl.classList.remove('pulse-glow');
            });
        });
        
        const typeLabel = singleTypeLabels[entity.entity_type] || entity.entity_type;
        
        row.innerHTML = `
            <div class="entity-row-left">
                <span class="entity-type-badge badge-${entity.entity_type}">${typeLabel}</span>
                <div class="entity-text-details">
                    <span class="entity-orig-text" title="${entity.text}">${entity.text}</span>
                    <span class="entity-meta-desc">${pageDesc}</span>
                </div>
            </div>
            <div class="entity-row-right">
                <span class="score-display">${Math.round(entity.score * 100)}%</span>
                <label class="switch" for="entityToggle-${entity.id}">
                    <input type="checkbox" id="entityToggle-${entity.id}" ${isSelected ? 'checked' : ''} onchange="toggleIndividualEntity('${entity.id}', this.checked)">
                    <span class="slider round"></span>
                </label>
            </div>
        `;
        
        listContainer.appendChild(row);
    });
}

function toggleIndividualEntity(entityId, isChecked) {
    if (isChecked) {
        state.selectedEntityIds.add(entityId);
    } else {
        state.selectedEntityIds.delete(entityId);
    }
    
    // Actualizar highlights en el PDF
    renderHighlightOverlays(state.currentPage);
    
    // Actualizar de forma no destructiva los toggles grupales en el sidebar
    updateCategoryToggles();
}

function updateCategoryToggles() {
    // Agrupar por tipo para verificar si todas las entidades de cada tipo están marcadas
    const counts = {};
    state.analyzedEntities.forEach(e => {
        counts[e.entity_type] = (counts[e.entity_type] || 0) + 1;
    });
    
    Object.keys(counts).forEach(type => {
        const entitiesOfType = state.analyzedEntities.filter(e => e.entity_type === type);
        const allSelected = entitiesOfType.every(e => state.selectedEntityIds.has(e.id));
        
        const catToggle = document.getElementById(`catToggle-${type}`);
        if (catToggle) {
            catToggle.checked = allSelected;
        }
    });
}

function filterEntitiesList() {
    const searchInput = document.getElementById('entitySearchInput');
    state.activeSearchQuery = searchInput.value;
    renderIndividualEntitiesList();
}

// Redimensionamiento dinámico y responsive del canvas
let resizeTimeout;
window.addEventListener('resize', () => {
    // Solo re-renderizar si el panel interactivo está activo y visible
    const interactivePanel = document.getElementById('interactivePanel');
    if (!interactivePanel.classList.contains('hidden')) {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            renderPdfPage(state.currentPage);
        }, 200);
    }
});

// ==========================================================================
// 6.5 Menú Contextual para Añadir PII con Clic Derecho
// ==========================================================================

document.addEventListener('DOMContentLoaded', () => {
    const pdfContainer = document.getElementById('pdfOverlayContainer');
    const contextMenu = document.getElementById('customContextMenu');

    if (pdfContainer && contextMenu) {
        pdfContainer.addEventListener('contextmenu', (e) => {
            const selection = window.getSelection();
            const text = selection.toString().trim();
            
            if (text.length > 0) {
                e.preventDefault(); // Bloquear menú nativo
                
                // Mostrar nuestro menú en el cursor
                contextMenu.style.left = `${e.clientX}px`;
                contextMenu.style.top = `${e.clientY}px`;
                contextMenu.showPopover();
                
                state.pendingSelectionText = text;
                
                // Extraer coordenadas relativas de la selección
                const range = selection.getRangeAt(0);
                const rect = range.getBoundingClientRect();
                const containerRect = pdfContainer.getBoundingClientRect();
                
                state.pendingSelectionBox = {
                    page: state.currentPage - 1,
                    x0: (rect.left - containerRect.left) / containerRect.width,
                    y0: (rect.top - containerRect.top) / containerRect.height,
                    x1: (rect.right - containerRect.left) / containerRect.width,
                    y1: (rect.bottom - containerRect.top) / containerRect.height
                };
            } else {
                if (contextMenu.matches(':popover-open')) {
                    contextMenu.hidePopover();
                }
            }
        });
        
        document.addEventListener('click', (e) => {
            if (!contextMenu.contains(e.target) && contextMenu.matches(':popover-open')) {
                contextMenu.hidePopover();
            }
        });
    }
});

function categorizeSelection(category) {
    if (!state.pendingSelectionText || !state.pendingSelectionBox) return;
    
    const newId = `manual_rect_${Date.now()}`;
    const newEntity = {
        id: newId,
        text: state.pendingSelectionText,
        entity_type: category,
        score: 1.0,
        boxes: [state.pendingSelectionBox],
        source: 'manual'
    };
    
    state.analyzedEntities.push(newEntity);
    state.selectedEntityIds.add(newId);
    
    // Limpieza
    document.getElementById('customContextMenu').hidePopover();
    window.getSelection().removeAllRanges();
    state.pendingSelectionText = null;
    state.pendingSelectionBox = null;
    
    // Refrescar UI
    renderSidebarFilters();
    renderHighlightOverlays(state.currentPage);
}

// ==========================================================================
// 7. Servidor - FASE 2: APLICAR PSEUDONIMIZACIÓN SELECCIONADA
// ==========================================================================

async function submitAnonymization() {
    // Ocultar panel interactivo
    document.getElementById('interactivePanel').classList.add('hidden');
    
    // Mostrar pantalla de carga
    const processingSection = document.getElementById('processingSection');
    processingSection.classList.remove('hidden');
    
    // Mensajes para la barra de progreso
    const anonymizeMessages = [
        "Preparando mapa interactivo de datos sensibles...",
        "Reemplazando PII seleccionada por tokens consistentes...",
        "Cifrando el diccionario de mapeo con Fernet (AES-256)...",
        "Generando el nuevo archivo .key de restauración...",
        "Reconstruyendo documento PDF anonimizado final...",
        "Empaquetando descargas..."
    ];
    
    startProgressAnimation(anonymizeMessages);
    
    // Construir la petición JSON
    const requestData = {
        pdf_base64: state.originalPdfBase64,
        selected_entity_ids: Array.from(state.selectedEntityIds),
        entities: state.analyzedEntities
    };
    
    try {
        const response = await fetch('/api/anonymize', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || "Error durante el proceso de anonimización interactiva.");
        }
        
        finishProgressAnimation();
        
        setTimeout(() => {
            processingSection.classList.add('hidden');
            setStepperStep(3);
            renderAnonResults(data);
        }, 500);
        
    } catch (error) {
        clearInterval(state.progressInterval);
        state.progressInterval = null;
        processingSection.classList.add('hidden');
        showError("Error en Anonimización", error.message);
    }
}

// Muestra los resultados de la anonimización
function renderAnonResults(response) {
    const resultsSection = document.getElementById('anonResultsSection');
    resultsSection.classList.remove('hidden');
    
    // Guardar datos en el estado global para descarga
    state.downloadData.anonPdfBase64 = response.pdf_base64;
    state.downloadData.anonPdfName = state.anonFile.name.replace(".pdf", "_anon.pdf");
    state.downloadData.keyBase64 = response.key_base64;
    state.downloadData.keyName = state.anonFile.name.replace(".pdf", ".key");
    
    // Configurar botones de descarga
    document.getElementById('downloadAnonPdfBtn').onclick = () => {
        downloadBlob(state.downloadData.anonPdfBase64, state.downloadData.anonPdfName, 'application/pdf');
    };
    
    document.getElementById('downloadKeyBtn').onclick = () => {
        downloadBlob(state.downloadData.keyBase64, state.downloadData.keyName, 'application/octet-stream');
    };
    
    // Renderizar estadísticas de PII
    const statsGrid = document.getElementById('statsGrid');
    statsGrid.innerHTML = '';
    
    const stats = response.stats;
    const entityTypes = stats.entities_by_type;
    
    if (Object.keys(entityTypes).length === 0) {
        statsGrid.innerHTML = `
            <div class="stat-item" style="grid-column: 1 / -1; text-align: center; color: var(--text-muted);">
                Ninguna información PII sensible fue protegida en este archivo.
            </div>
        `;
    } else {
        for (const [type, count] of Object.entries(entityTypes)) {
            const item = document.createElement('div');
            item.className = 'stat-item';
            
            const label = typeLabels[type] || type;
            item.innerHTML = `
                <span class="stat-val">${count}</span>
                <span class="stat-lbl">${label}</span>
            `;
            statsGrid.appendChild(item);
        }
    }
    
    document.getElementById('statsSummaryText').textContent = `Total de datos protegidos: ${stats.total_anonymized} (de ${stats.total_detected} detectados)`;
}

// ==========================================================================
// 8. Peticiones al Servidor - RESTAURAR PDF ORIGINAL
// ==========================================================================

async function handleRestore(event) {
    event.preventDefault();
    if (!state.restorePdf || !state.restoreKey) return;
    
    // Ocultar panel
    document.getElementById('tabRestPanel').classList.remove('active');
    
    // Mostrar procesamiento
    const processingSection = document.getElementById('processingSection');
    processingSection.classList.remove('hidden');
    
    const scanMessages = [
        "Leyendo archivos de entrada...",
        "Extrayendo texto del PDF anonimizado...",
        "Abriendo clave cifrada (.key)...",
        "Validando y descifrando el mapa Fernet (AES-256)...",
        "Traduciendo tokens a sus valores originales en el texto...",
        "Construyendo el nuevo PDF restaurado sin pérdida...",
        "¡Generando documento restaurado final!"
    ];
    
    startProgressAnimation(scanMessages);
    
    const formData = new FormData();
    formData.append('file', state.restorePdf);
    formData.append('key_file', state.restoreKey);
    
    try {
        const response = await fetch('/api/deanonymize', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || "Error al desanonimizar. Verifique que la clave coincide con el PDF.");
        }
        
        finishProgressAnimation();
        
        setTimeout(() => {
            processingSection.classList.add('hidden');
            renderRestoreResults(data);
        }, 500);
        
    } catch (error) {
        clearInterval(state.progressInterval);
        state.progressInterval = null;
        processingSection.classList.add('hidden');
        showError("Error en Restauración", error.message);
    }
}

// Muestra los resultados de la restauración
function renderRestoreResults(response) {
    const resultsSection = document.getElementById('restoreResultsSection');
    resultsSection.classList.remove('hidden');
    
    state.downloadData.restoredPdfBase64 = response.pdf_base64;
    state.downloadData.restoredPdfName = response.filename;
    
    document.getElementById('restoredFileNameLabel').textContent = response.filename;
    
    document.getElementById('downloadRestoredPdfBtn').onclick = () => {
        downloadBlob(state.downloadData.restoredPdfBase64, state.downloadData.restoredPdfName, 'application/pdf');
    };
}

// ==========================================================================
// 9. Gestión de Errores e Interfaces de Retorno
// ==========================================================================

function showError(title, message) {
    // Ocultar paneles activos de pestañas
    document.getElementById('tabAnonPanel').classList.remove('active');
    document.getElementById('tabRestPanel').classList.remove('active');
    
    // Ocultar cualquier resultado o visor interactivo previo
    document.getElementById('anonResultsSection').classList.add('hidden');
    document.getElementById('restoreResultsSection').classList.add('hidden');
    document.getElementById('processingSection').classList.add('hidden');
    document.getElementById('interactivePanel').classList.add('hidden');
    
    // Configurar y mostrar sección de error
    document.getElementById('errorTitle').textContent = title;
    document.getElementById('errorMessage').textContent = message;
    document.getElementById('errorSection').classList.remove('hidden');
}

function returnToInputState() {
    document.getElementById('errorSection').classList.add('hidden');
    
    // Restaurar panel según pestaña actual
    if (state.currentTab === 'anonimizar') {
        document.getElementById('tabAnonPanel').classList.add('active');
    } else {
        document.getElementById('tabRestPanel').classList.add('active');
    }
}

function hideAllSectionsExceptPanel() {
    document.getElementById('anonResultsSection').classList.add('hidden');
    document.getElementById('restoreResultsSection').classList.add('hidden');
    document.getElementById('processingSection').classList.add('hidden');
    document.getElementById('errorSection').classList.add('hidden');
    document.getElementById('interactivePanel').classList.add('hidden');

    // Resetear visores de PDF si se cambia de pestaña
    state.pdfDocInstance = null;

    // Resetear sidebar a pestaña de Categorías
    switchSidebarTab('toggles');

    // Resetear stepper al paso 1
    setStepperStep(1);

    if (state.currentTab === 'anonimizar') {
        document.getElementById('tabAnonPanel').classList.add('active');
    } else {
        document.getElementById('tabRestPanel').classList.add('active');
    }
}

function resetToHome(type) {
    if (type === 'anon') {
        clearFile('anon');
    } else {
        // Limpiar archivos de restauración
        state.restorePdf = null;
        state.restoreKey = null;
        
        const pdfDrop = document.getElementById('restPdfDropZone');
        const keyDrop = document.getElementById('restKeyDropZone');
        
        pdfDrop.classList.remove('has-file');
        keyDrop.classList.remove('has-file');
        
        document.getElementById('restPdfName').textContent = "Ninguno seleccionado";
        document.getElementById('restKeyName').textContent = "Ninguno seleccionado";
        document.getElementById('restoreSubmitBtn').disabled = true;
    }
    
    hideAllSectionsExceptPanel();
}

// ==========================================================================
// 10. Utilidad de Carga de Descargas (Base64 a Blob a Descarga Local)
// ==========================================================================

function downloadBlob(base64Data, filename, contentType) {
    // Decodificar Base64 a bytes
    const sliceSize = 512;
    const byteCharacters = atob(base64Data);
    const byteArrays = [];
    
    for (let offset = 0; offset < byteCharacters.length; offset += sliceSize) {
        const slice = byteCharacters.slice(offset, offset + sliceSize);
        
        const byteNumbers = new Array(slice.length);
        for (let i = 0; i < slice.length; i++) {
            byteNumbers[i] = slice.charCodeAt(i);
        }
        
        const byteArray = new Uint8Array(byteNumbers);
        byteArrays.push(byteArray);
    }
    
    // Crear Blob con bytes decodificados
    const blob = new Blob(byteArrays, { type: contentType });
    
    // Crear URL temporal y simular click de descarga
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    
    document.body.appendChild(link);
    link.click();
    
    // Limpieza de memoria
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

// ==========================================================================
// 11. Nuevas Lógicas: Zoom, Modal y Adición Manual de PII (Cliente)
// ==========================================================================

/* Control de Zoom Interactivo (Lupa) */
function adjustZoom(delta) {
    const oldZoom = state.zoomScale;
    // Límites de Zoom de 50% a 250%
    state.zoomScale = Math.min(Math.max(state.zoomScale + delta, 0.5), 2.5);
    
    if (oldZoom !== state.zoomScale) {
        const zoomPct = Math.round(state.zoomScale * 100);
        document.getElementById('zoomLevelDisplay').textContent = `${zoomPct}%`;
        
        // Volver a renderizar la página actual con el nuevo zoom
        renderPdfPage(state.currentPage);
    }
}

/* Manejo del Modal de Adición de Entidad Manual */
function openAddEntityModal() {
    const modal = document.getElementById('addEntityModal');
    modal.classList.remove('hidden');
    document.getElementById('manualEntityText').focus();
}

function closeAddEntityModal() {
    const modal = document.getElementById('addEntityModal');
    modal.classList.add('hidden');
    document.getElementById('addEntityForm').reset();
}

function closeAddEntityModalOnOverlay(event) {
    if (event.target === document.getElementById('addEntityModal')) {
        closeAddEntityModal();
    }
}

/* Envío de la Entidad Manual */
function submitAddManualEntity(event) {
    event.preventDefault();
    
    const textInput = document.getElementById('manualEntityText');
    const typeSelect = document.getElementById('manualEntityType');
    
    const text = textInput.value;
    const type = typeSelect.value;
    
    if (text && text.trim()) {
        addManualEntity(text, type);
        closeAddEntityModal();
    }
}

/* Algoritmo de Búsqueda y Mapeo Espacial de Entidad Manual en el Cliente */
function addManualEntity(searchText, type) {
    if (!searchText || !searchText.trim()) return;
    
    const term = searchText.trim();
    const lowerTerm = term.toLowerCase();
    const fullText = state.fullText;
    
    if (!fullText) return;
    
    // 1. Buscar todas las ocurrencias exactas (case-insensitive) del término
    const occurrences = [];
    let pos = fullText.toLowerCase().indexOf(lowerTerm);
    while (pos !== -1) {
        occurrences.push({
            start: pos,
            end: pos + term.length
        });
        pos = fullText.toLowerCase().indexOf(lowerTerm, pos + 1);
    }
    
    if (occurrences.length === 0) {
        alert("Aviso: El texto '" + term + "' no se ha localizado de forma exacta en el texto del documento. Se agregará a la cola de todas formas.");
    }
    
    // 2. Mapear secuencialmente todas las palabras del PDF a sus índices del fullText (igual que el Backend)
    const wordPositions = [];
    let searchStart = 0;
    state.pdfWords.forEach(w => {
        const idx = fullText.indexOf(w.text, searchStart);
        if (idx !== -1) {
            wordPositions.push({
                start: idx,
                end: idx + w.text.length,
                word: w
            });
            searchStart = idx + w.text.length;
        }
    });
    
    // 3. Mapear cada ocurrencia de la entidad a sus correspondientes cajas de palabras
    const entityBoxes = [];
    occurrences.forEach(occ => {
        wordPositions.forEach(wp => {
            // Si la palabra intersecta con el rango de la ocurrencia
            if (wp.start < occ.end && wp.end > occ.start) {
                entityBoxes.push({
                    page: wp.word.page,
                    x0: wp.word.x0,
                    y0: wp.word.y0,
                    x1: wp.word.x1,
                    y1: wp.word.y1
                });
            }
        });
    });
    
    // 4. Crear el objeto de entidad manual
    const newId = 'manual-' + Math.random().toString(36).substr(2, 9);
    const newEntity = {
        id: newId,
        text: term,
        entity_type: type,
        start: occurrences.length > 0 ? occurrences[0].start : 0,
        end: occurrences.length > 0 ? occurrences[0].end : term.length,
        score: 1.0,
        source: 'manual',
        boxes: entityBoxes.length > 0 ? entityBoxes : null
    };
    
    // 5. Insertar al principio del array de entidades
    state.analyzedEntities.unshift(newEntity);
    
    // 6. Activar la entidad para anonimizar por defecto
    state.selectedEntityIds.add(newId);
    
    // 7. Re-renderizar la barra lateral y los resaltados de la página
    renderSidebarFilters();
    renderHighlightOverlays(state.currentPage);
}

