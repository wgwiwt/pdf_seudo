# Plan de Implementación: PDF-Pseudo (Aplicación Web Premium)

`PDF-Pseudo` se transforma de una herramienta CLI abstracta a una **aplicación web visual e interactiva** sumamente intuitiva y premium. Su objetivo es permitir a cualquier usuario arrastrar un documento PDF en español, anonimizarlo de forma automática y consistente (reemplazando PII por tokens como `<<PERSON_1>>`, `<<DNI_1>>`), y permitir su restauración exacta más adelante subiendo el PDF anonimizado y una clave de recuperación que reside únicamente en el cliente (privacidad por diseño total).

---

## El Concepto y Usabilidad (Inspirado en Anondocs.com)

El flujo de trabajo es visual, fluido y elegante:

### 1. Pestaña: Anonimizar
*   **Zona Drag & Drop**: El usuario arrastra su PDF en español dentro de una zona de diseño esmerilado (*Glassmorphism*) que reacciona con animaciones fluidas y brillos de hover.
*   **Simulación de Escaneo**: Al soltar el archivo, se muestra una barra de progreso animada con un haz de luz ("láser") que recorre el documento simulando el análisis de los motores locales.
*   **Descarga Automática Dual**: Una vez procesado, el backend devuelve en una sola respuesta JSON el PDF anonimizado y un archivo de recuperación `.key` (cifrado con AES-256 Fernet). El navegador descarga ambos archivos localmente en segundos. El servidor **no almacena nada** en disco (cero logs de PII, seguridad 100%).

### 2. Pestaña: Restaurar (Desanonimizar)
*   **Doble Subida**: El usuario arrastra el archivo PDF anonimizado y el archivo de recuperación `.key`.
*   **Restauración Instantánea**: Al pulsar "Restaurar", el backend descifra los tokens usando la llave Fernet y reconstruye el PDF original idéntico en texto plano limpio, descargándolo automáticamente en el navegador del usuario.

---

## Arquitectura y Stack Tecnológico

1.  **Servidor Backend (Python + FastAPI)**:
    *   **FastAPI**: Servidor ultraligero y rápido en Python. Ideal para procesar las llamadas de la API y servir la interfaz SPA estática.
    *   **Motor de PII Híbrido y 100% Local**:
        *   *Por Defecto (Ligero)*: **Presidio + GLiNER** (`gliner-pii-base-v1.0`). Son modelos de IA locales y especializados de tamaño reducido (~330MB) que corren en la CPU de cualquier ordenador común de forma inmediata y 100% gratuita, sin APIs externas ni necesidad de instalar dependencias de terceros complejas.
        *   *Avanzado (Opcional - LLM Local)*: Integración nativa con **Ollama** (`http://localhost:11434`). Si el usuario tiene Ollama corriendo localmente con un modelo gratuito como `llama3` o `mistral`, el backend puede utilizar este LLM local para realizar una pasada de refinamiento semántico del texto y detectar entidades extremadamente complejas.
    *   **pdfplumber + fpdf2**: Extracción limpia de texto y reconstrucción de PDFs legibles y fluidos.
    *   **cryptography**: Cifrado simétrico Fernet para blindar el mapeo de tokens en el archivo de recuperación descargable.

2.  **Interfaz Frontend (SPA de Alto Craft en Vanilla HTML5, CSS y JS)**:
    *   **Vanilla CSS**: Diseño premium basado en el estilo **Liquid Glass** de 2026: gradientes fluidos morados/azules oscuros, sombras volumétricas, bordes sutiles semi-transparentes (`backdrop-filter`) y fuentes de alta legibilidad (Google Fonts: Outfit).
    *   **Vanilla JS**: Gestión del ciclo de arrastre de archivos, animaciones de carga personalizadas, llamadas asíncronas (`fetch`) y descargas binarias automáticas sin librerías externas pesadas.

---

## Estructura del Proyecto

El proyecto se estructurará de la forma más limpia posible para facilitar su ejecución con un único comando:

```
pdf-pseudo/
├── pyproject.toml              # Metadata del proyecto y dependencias (FastAPI, fpdf2, gliner...)
├── main.py                     # Servidor FastAPI, endpoints de la API y servicio de la web
├── static/
│   ├── index.html              # Interfaz web SPA Premium
│   ├── app.js                  # Lógica del frontend (Drag & Drop, peticiones API, descargas)
│   └── styles.css              # Estilo Liquid Glass, gradientes, animaciones y diseño móvil-responsive
└── src/
    └── pdf_pseudo/
        ├── __init__.py
        ├── detector.py         # Analizador PII con GLiNER + Presidio + Soporte opcional de Ollama LLM
        ├── mapper.py           # Gestión de tokens y cifrado/descifrado Fernet
        └── pdf_utils.py        # Extracción y escritura con pdfplumber y fpdf2
```

---

## Propuesta de Cambios e Hitos de Desarrollo

### [Componente 1] Backend y Dependencias (`pyproject.toml`, `main.py`)

#### [NEW] [pyproject.toml](file:///Users/juanjoyamparoaragonbaltasar/Documents/Antigravity%20proyectos/01_EN_CURSO/Datos%20anonimos/pyproject.toml)
Definirá las dependencias requeridas para la aplicación web y procesamiento:
*   `fastapi` y `uvicorn` (servidor web)
*   `python-multipart` (para gestionar la subida de archivos PDF y llaves en la API)
*   `presidio-analyzer`
*   `gliner`
*   `pdfplumber`
*   `fpdf2`
*   `cryptography`
*   `httpx` (para comunicarse de forma local con la API de Ollama si está activa)
*   `spacy` (con modelo `es_core_news_md`)
*   `pytest` (para pruebas de TDD)

#### [NEW] [main.py](file:///Users/juanjoyamparoaragonbaltasar/Documents/Antigravity%20proyectos/01_EN_CURSO/Datos%20anonimos/main.py)
*   Servidor FastAPI que expone:
    *   `GET /`: Sirve la SPA `index.html`.
    *   `POST /api/anonymize`: Recibe un PDF y un flag de si se desea usar Ollama, detecta PII, realiza sustituciones, genera el archivo cifrado de restauración `.key` y devuelve un JSON con `{ "pdf_base64": "...", "key_base64": "...", "filename": "..." }`.
    *   `POST /api/deanonymize`: Recibe el PDF anonimizado y la clave de restauración `.key`, descifra y devuelve el PDF original.

---

### [Componente 2] Motor de Pseudonimización (`detector.py`, `mapper.py`, `pdf_utils.py`)

#### [NEW] [detector.py](file:///Users/juanjoyamparoaragonbaltasar/Documents/Antigravity%20proyectos/01_EN_CURSO/Datos%20anonimos/src/pdf_pseudo/detector.py)
*   Mapeará entidades en español: nombres, direcciones y organizaciones con **GLiNER** (`gliner-pii-base-v1.0`).
*   Reglas y validaciones matemáticas estrictas para patrones españoles (**DNI/NIE** con módulo 23, **CIF**, teléfonos fijos/móviles españoles e **IBAN**).
*   **Integración con Ollama**: Un módulo opcional que envía fragmentos de texto al LLM local (ej. Llama 3 / Mistral) para una segunda comprobación semántica mediante un prompt estructurado en formato JSON que devuelve entidades detectadas omitidas por los motores basados en reglas.

#### [NEW] [mapper.py](file:///Users/juanjoyamparoaragonbaltasar/Documents/Antigravity%20proyectos/01_EN_CURSO/Datos%20anonimos/src/pdf_pseudo/mapper.py)
*   Lógica consistente de tokens: `<<PERSON_1>>`, `<<DNI_1>>`.
*   Cifrado del mapeo mediante `cryptography` con la clave Fernet autogenerada en cada sesión.

#### [NEW] [pdf_utils.py](file:///Users/juanjoyamparoaragonbaltasar/Documents/Antigravity%20proyectos/01_EN_CURSO/Datos%20anonimos/src/pdf_pseudo/pdf_utils.py)
*   Extracción y reconstrucción básica multilínea del PDF utilizando `pdfplumber` y `fpdf2`.

---

### [Componente 3] Frontend de Alta Gama (`index.html`, `styles.css`, `app.js`)

#### [NEW] [index.html](file:///Users/juanjoyamparoaragonbaltasar/Documents/Antigravity%20proyectos/01_EN_CURSO/Datos%20anonimos/static/index.html)
*   Estructura HTML5 semántica y accesible.
*   Pestañas de alternancia rápida (Anonimizar / Restaurar).
*   Selector visual para activar/desactivar el uso de **Ollama (LLM Local)** si el usuario lo tiene instalado.
*   Secciones de carga con visuales premium.

#### [NEW] [styles.css](file:///Users/juanjoyamparoaragonbaltasar/Documents/Antigravity%20proyectos/01_EN_CURSO/Datos%20anonimos/static/styles.css)
*   Estilo visual premium "Liquid Glass" con colores profundos y gradientes.
*   Efectos interactivos de hover y foco con transiciones suaves en CSS.
*   Animación de haz de luz láser para simular el escaneo del PDF.

#### [NEW] [app.js](file:///Users/juanjoyamparoaragonbaltasar/Documents/Antigravity%20proyectos/01_EN_CURSO/Datos%20anonimos/static/app.js)
*   Lógica del drag & drop con estados activos (`dragover`, `dragleave`, `drop`).
*   Envío asíncrono incluyendo el flag del LLM local de Ollama en la petición.
*   Conversión de Base64 a blob para la descarga directa en caliente del PDF y de la clave.

---

## Plan de Verificación

1.  **Pruebas TDD (`pytest`)**:
    *   Testear el motor de detección de DNI/NIE e IBAN español.
    *   Test de roundtrip: Validar que un texto anonimizado y posteriormente restaurado coincida letra a letra con el original.
2.  **Verificación Visual Web**:
    *   Prueba interactiva subiendo PDFs sintácticos y descargando las claves en el navegador, asegurando que la interfaz fluya y no se cuelgue ante archivos pesados.
