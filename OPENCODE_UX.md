# PDF-Pseudo — Directrices de Rediseño UX Premium (Fase V2 UX)

> **Destinatario:** 🔵 OpenCode  
> **Objetivo:** Implementar la reestructuración y refinamiento visual del panel lateral interactivo (sidebar) para optimizar el espacio, corregir el truncado de los textos y maximizar el tamaño del visor del documento PDF, siguiendo el plan de diseño acordado.

Por favor, realiza las siguientes modificaciones en el frontend estático de forma meticulosa para que la aplicación quede totalmente lista y con un acabado de calidad Premium.

---

## 🛠️ Tareas a Realizar

### 1. Modificar `static/index.html`
Reemplaza la estructura interna de `.sidebar-filters` (Panel de Filtros / Sidebar) para incorporar la navegación por sub-pestañas y separar los paneles.

**Estructura esperada para `.sidebar-filters`:**
```html
<div class="sidebar-filters glass-panel">
    <div class="sidebar-header">
        <h4>Entidades Detectadas</h4>
        <span class="entities-counter-badge" id="entitiesCountBadge">0</span>
    </div>
    
    <!-- Sub-pestañas de navegación interna -->
    <div class="sidebar-subtabs" role="tablist">
        <button class="subtab-btn active" id="subtabTogglesBtn" onclick="switchSidebarTab('toggles')" role="tab" aria-selected="true" aria-controls="sidebarTogglesPanel">
            📂 Categorías
        </button>
        <button class="subtab-btn" id="subtabListBtn" onclick="switchSidebarTab('list')" role="tab" aria-selected="false" aria-controls="sidebarListPanel">
            🔍 Datos Sensibles
        </button>
    </div>

    <!-- PESTAÑA 1: Categorías (Toggles Maestros) -->
    <div id="sidebarTogglesPanel" class="sidebar-tab-panel" role="tabpanel" aria-labelledby="subtabTogglesBtn">
        <span class="section-subtitle">Toggles Grupales</span>
        <div class="category-grid" id="categoryGrid">
            <!-- Generado dinámicamente por JavaScript -->
        </div>
    </div>

    <!-- PESTAÑA 2: Lista de Entidades Individuales + Buscador -->
    <div id="sidebarListPanel" class="sidebar-tab-panel" role="tabpanel" aria-labelledby="subtabListBtn" hidden>
        <!-- Barra de búsqueda rápida (movida aquí dentro) -->
        <div class="search-box-container">
            <input type="text" id="entitySearchInput" placeholder="Buscar entidades..." oninput="filterEntitiesList()">
        </div>
        <span class="section-subtitle">Listado de Datos Sensibles</span>
        <div class="entities-list" id="entitiesList">
            <!-- Generado dinámicamente por JavaScript -->
        </div>
    </div>

    <!-- El botón de confirmación se mantiene fijo al pie de la columna -->
    <div class="sidebar-footer">
        <button type="button" class="action-btn" id="confirmAnonymizeBtn" onclick="submitAnonymization()">
            <span>Pseudonimizar Selección</span>
            <span class="btn-arrow">→</span>
        </button>
    </div>
</div>
```

---

### 2. Modificar `static/styles.css`
Aplica los siguientes cambios visuales para ampliar el visor del PDF y pulir las sub-pestañas:

1. **Ajuste del Grid Principal**:
   Modifica `.interactive-workspace` para ampliar el espacio del visor y estrechar el sidebar:
   ```css
   .interactive-workspace {
       display: grid;
       grid-template-columns: 1.4fr 0.6fr; /* Visor al ~70% y Sidebar al ~30% */
       gap: 20px;
   }
   ```

2. **Estilos de Sub-pestañas (`.sidebar-subtabs` y `.subtab-btn`)**:
   Inserta los siguientes estilos premium al final o en la sección correspondiente:
   ```css
   .sidebar-subtabs {
       display: flex;
       background: rgba(0, 0, 0, 0.25);
       padding: 4px;
       border-radius: 12px;
       border: 1px solid rgba(255, 255, 255, 0.03);
       gap: 4px;
       flex-shrink: 0;
   }

   .subtab-btn {
       flex: 1;
       background: transparent;
       border: none;
       padding: 8px 12px;
       border-radius: 8px;
       color: var(--text-muted);
       font-family: var(--font-sans);
       font-size: 0.8rem;
       font-weight: 600;
       cursor: pointer;
       display: flex;
       align-items: center;
       justify-content: center;
       gap: 6px;
       transition: var(--transition-smooth);
   }

   .subtab-btn:hover {
       color: var(--text-main);
       background: rgba(255, 255, 255, 0.02);
   }

   .subtab-btn.active {
       color: #ffffff;
       background: rgba(6, 182, 212, 0.15);
       border: 1px solid rgba(6, 182, 212, 0.25);
       box-shadow: 0 2px 10px rgba(6, 182, 212, 0.1);
   }

   .sidebar-tab-panel {
       flex: 1;
       display: flex;
       flex-direction: column;
       min-height: 0;
       animation: fadeIn 0.3s ease-out;
       gap: 10px;
   }

   /* Ocultar dinámicamente cuando el atributo hidden esté presente */
   .sidebar-tab-panel[hidden] {
       display: none !important;
   }
   ```

3. **Optimización de Tarjetas de Categoría (`.category-grid` y `.category-card`)**:
   Elimina la restricción de `max-height: 105px;` en `.category-grid` para que respire con libertad (ya que ahora está sola en su sub-pestaña) y define un ancho de columnas superior en el grid para evitar textos truncados:
   ```css
   .category-grid {
       display: grid;
       grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
       gap: 8px;
       overflow-y: auto;
       padding-right: 4px;
       flex: 1; /* Permite scroll vertical cómodo si hay muchas categorías */
   }

   .category-card {
       background: rgba(255, 255, 255, 0.02);
       border: 1px solid rgba(255, 255, 255, 0.05);
       border-radius: 12px;
       padding: 8px 12px;
       display: flex;
       align-items: center;
       justify-content: space-between;
       gap: 8px;
       transition: var(--transition-fast);
   }

   .cat-name-lbl {
       font-size: 0.8rem;
       font-weight: 600;
       white-space: normal; /* Permitir saltos de línea elegantes si el texto es muy largo */
       word-break: break-word;
       color: var(--text-main);
   }
   ```

---

### 3. Modificar `static/app.js`
Añade la lógica interactiva para cambiar entre las sub-pestañas del sidebar manteniendo intacto el estado criptográfico de la aplicación:

1. **Función de Intercambio de Pestañas**:
   Inserta la función `switchSidebarTab` en un lugar visible de `static/app.js`:
   ```javascript
   function switchSidebarTab(tabName) {
       const togglesBtn = document.getElementById('subtabTogglesBtn');
       const listBtn = document.getElementById('subtabListBtn');
       const togglesPanel = document.getElementById('sidebarTogglesPanel');
       const listPanel = document.getElementById('sidebarListPanel');
       
       if (tabName === 'toggles') {
           // Activar pestaña de Categorías
           togglesBtn.classList.add('active');
           togglesBtn.setAttribute('aria-selected', 'true');
           togglesPanel.removeAttribute('hidden');
           
           // Desactivar pestaña de Listado
           listBtn.classList.remove('active');
           listBtn.setAttribute('aria-selected', 'false');
           listPanel.setAttribute('hidden', '');
       } else {
           // Activar pestaña de Listado
           listBtn.classList.add('active');
           listBtn.setAttribute('aria-selected', 'true');
           listPanel.removeAttribute('hidden');
           
           // Desactivar pestaña de Categorías
           togglesBtn.classList.remove('active');
           togglesBtn.setAttribute('aria-selected', 'false');
           togglesPanel.setAttribute('hidden', '');
           
           // Hacer foco opcional en el input de búsqueda rápida
           setTimeout(() => {
               document.getElementById('entitySearchInput').focus();
           }, 50);
       }
   }
   ```

2. **Ajuste en la Inicialización**:
   Asegúrate de que al iniciar un nuevo análisis en `handleAnalyze`, la barra lateral comience por defecto en la pestaña de Categorías llamando a `switchSidebarTab('toggles')`:
   ```javascript
   // Dentro de handleAnalyze, tras cargar el documento:
   switchSidebarTab('toggles');
   ```

3. **Ajuste en la función `hideAllSectionsExceptPanel`**:
   Asegúrate de resetear el estado del sidebar de la misma forma para evitar que queden paneles huérfanos al reiniciar:
   ```javascript
   // Dentro de hideAllSectionsExceptPanel():
   switchSidebarTab('toggles');
   ```

---

## 🧪 Validación Final

1. Abre la aplicación en tu navegador.
2. Comprueba que el visor del PDF escala a un tamaño visiblemente superior de forma inmediata.
3. Haz clic alternadamente en las sub-pestañas "Categorías" y "Datos Sensibles" en el panel lateral y verifica que la transición sea fluida.
4. Verifica que los textos en las tarjetas de categorías se lean completos.
