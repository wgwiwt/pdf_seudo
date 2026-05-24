# PDF-Pseudo — Documentación Técnica Completa

> **Pseudonimización bidireccional de PDFs en español con IA local**
>
> Herramienta web local y privada para anonimizar y restaurar de forma reversible la Información de Identificación Personal (PII) de documentos PDF. 100% Open Source (MIT).

---

## Índice

1. [Visión General](#1-visión-general)
2. [Arquitectura del Proyecto](#2-arquitectura-del-proyecto)
3. [Backend: Motor de PII](#3-backend-motor-de-pii)
   - [3.1 `mapper.py` — Mapeador Bidireccional](#31-mapperpy--mapeador-bidireccional)
   - [3.2 `detector.py` — Motor de Detección PII](#32-detectorpy--motor-de-detección-pii)
   - [3.3 `pdf_utils.py` — Lectura y Escritura de PDF](#33-pdf_utilspy--lectura-y-escritura-de-pdf)
4. [Servidor API (`main.py`)](#4-servidor-api-mainpy)
5. [Frontend Interactivo](#5-frontend-interactivo)
6. [Flujo de Usuario Completo](#6-flujo-de-usuario-completo)
7. [Tipos de PII Detectados](#7-tipos-de-pii-detectados)
8. [Instalación y Ejecución](#8-instalación-y-ejecución)
9. [Tests](#9-tests)
10. [Dependencias](#10-dependencias)

---

## 1. Visión General

**PDF-Pseudo** permite a cualquier usuario:

1. **Subir un PDF en español** con datos personales (nombres, DNI, teléfonos, direcciones, emails, IBAN, etc.)
2. **Detectar automáticamente** toda la información personal (PII) usando un motor híbrido de IA local
3. **Visualizar interactivamente** las entidades detectadas sobre el PDF, con coordenadas espaciales y resaltados de colores
4. **Seleccionar/descartar** qué datos anonimizar mediante toggles por categoría o por entidad individual
5. **Pseudonimizar** reemplazando cada dato por un token consistente (`<<PERSON_1>>`, `<<DNI_1>>`, etc.)
6. **Descargar** el PDF anonimizado + archivo de clave cifrada (`.key`)
7. **Restaurar** el documento original subiendo el PDF anonimizado + su clave `.key`

**Principio de privacidad:** Todo el procesamiento es 100% local. Los datos nunca salen del ordenador del usuario.

---

## 2. Arquitectura del Proyecto

```
pdf-pseudo/
├── main.py                          # Servidor FastAPI (3 endpoints + frontend estático)
├── pyproject.toml                   # Dependencias y configuración del proyecto
├── OPENCODE.md                      # Instrucciones para el agente OpenCode
├── OPENCODE_V2.md                   # Especificaciones V2 (coordenadas, mapeo espacial)
├── static/
│   ├── index.html                   # SPA frontend (423 líneas)
│   ├── styles.css                   # Diseño "Letters.app" (1557 líneas)
│   └── app.js                       # Lógica interactiva (1294 líneas)
├── src/pdf_pseudo/
│   ├── __init__.py                  # Exports públicos
│   ├── mapper.py                    # TokenMapper — mapeo bidireccional + cifrado Fernet (139 líneas)
│   ├── detector.py                  # Motor de detección PII — Presidio + GLiNER + Ollama (580 líneas)
│   └── pdf_utils.py                 # Utilidades PDF: extracción, creación, coordenadas (125 líneas)
├── tests/
│   ├── conftest.py                  # Fixtures compartidos (texto español de ejemplo)
│   ├── test_mapper.py               # 8 tests del mapeador
│   ├── test_detector.py             # 16 tests del detector
│   ├── test_pdf_utils.py            # 6 tests de utilidades PDF
│   ├── test_coords.py               # 8 tests de coordenadas y mapeo espacial
│   └── test_roundtrip.py            # 3 tests de pipeline completo
└── diseño/
    ├── INSTRUCCIONES_ANTIGRAVITY.md  # Spec de diseño visual (Hero letters.app)
    └── referencia.html              # Referencia de implementación del diseño
```

### Stack tecnológico

| Capa | Tecnología | Propósito |
|------|-----------|-----------|
| **Servidor** | FastAPI + Uvicorn | API REST local |
| **Detección PII** | Presidio Analyzer | Reglas deterministas + NER (spaCy) |
| **NER contextual** | GLiNER (`gliner-pii-base-v1.0`) | Modelo zero-shot ~330MB para nombres, direcciones, organizaciones |
| **LLM opcional** | Ollama (httpx) | Capa de refinamiento semántico con LLM local |
| **PDF lectura** | pdfplumber | Extracción de texto y coordenadas de palabras |
| **PDF escritura** | fpdf2 | Generación de PDFs limpios |
| **Cifrado** | cryptography (Fernet) | AES-256 para el archivo de clave `.key` |
| **Frontend** | Vanilla HTML/CSS/JS | Sin frameworks. Diseño "Letters.app" con Nunito |
| **Visor PDF** | PDF.js 3.4 | Renderizado de PDF en el navegador |
| **Tests** | pytest (41 tests) | Cobertura completa del backend |

---

## 3. Backend: Motor de PII

### 3.1 `mapper.py` — Mapeador Bidireccional

**Clase principal:** `TokenMapper`

**Propósito:** Gestiona la pseudonimización reversible. Convierte texto original en tokens consistentes y permite restaurar los valores originales posteriormente.

**API pública:**

| Método | Descripción |
|--------|-------------|
| `TokenMapper()` | Constructor. Genera automáticamente una clave Fernet (AES-256). |
| `pseudonymize(text, entity_type) → str` | Convierte `"Juan Pérez"` + `"PERSON"` → `"<<PERSON_1>>"`. Llamadas sucesivas con los mismos argumentos devuelven el mismo token. |
| `depseudonymize(text_with_tokens) → str` | Busca tokens `<<TIPO_N>>` en el texto y los reemplaza por sus valores originales. |
| `to_encrypted_bytes() → bytes` | Serializa el mapa interno (JSON) + cifra con Fernet. Genera el contenido del archivo `.key`. |
| `from_encrypted_bytes(data) → TokenMapper` | Reconstruye el mapeador desde un archivo `.key` cifrado. |

**Estructura interna:**
- `_forward: dict[tuple[str, str], str]` — `(texto_original, tipo)` → `"<<PERSON_1>>"`
- `_reverse: dict[str, str]` — `"<<PERSON_1>>"` → `"Juan Pérez"`
- `_counters: dict[str, int]` — Contadores por tipo (`{"PERSON": 5, "DNI": 2}`)
- `_fernet_key: bytes` — Clave Fernet generada en la construcción

**Formato del archivo `.key`:**
```
Línea 1: clave Fernet en base64 URL-safe
Línea 2: JSON del mapa _forward cifrado con Fernet, en base64 URL-safe
```

---

### 3.2 `detector.py` — Motor de Detección PII

**Función principal:** `detect_pii(text: str, use_ollama: bool = False) → list[Entity]`

**Dataclass `Entity`:**
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `text` | `str` | Texto original detectado (ej. `"Juan Pérez"`) |
| `entity_type` | `str` | Tipo normalizado (`"PERSON"`, `"DNI"`, `"PHONE"`, etc.) |
| `start` | `int` | Posición de inicio en el texto |
| `end` | `int` | Posición final (exclusiva) |
| `score` | `float` | Confianza (0.0 a 1.0) |
| `source` | `str` | Origen: `"presidio"`, `"gliner"`, `"ollama"` |
| `boxes` | `list[dict] \| None` | Coordenadas normalizadas para el overlay del frontend |

#### Tres capas de detección:

**Capa 1: Presidio (Reglas y Regex)**
- Motor: `presidio-analyzer` con modelo spaCy `es_core_news_md`
- Reconocedores estándar: PERSON, EMAIL_ADDRESS, PHONE_NUMBER, IBAN_CODE, CREDIT_CARD, LOCATION, DATE_TIME, URL, IP_ADDRESS
- Reconocedores personalizados para España:
  - **`SpanishDNIRecognizer`**: Regex `\b(\d{8})([A-Z])\b` + validación matemática (módulo 23 con `TRWAGMYFPDXBNJZSQVHLCKE`)
  - **`SpanishNIERecognizer`**: Formato `[XYZ]` + 7 dígitos + letra. Prefijos X→0, Y→1, Z→2 para el cálculo.
  - **`SpanishPhoneRecognizer`**: Regex `(?:\+\s*34[\s.\-]?)?[6789]\d{2}[\s.\-]?\d{3}[\s.\-]?\d{2,3}\b`
  - **`SpanishPostalCodeRecognizer`**: Regex `\b(0[1-9]|[1-4]\d|5[0-2])\d{3}\b` (CP españoles 01000–52999)

**Capa 2: GLiNER (NER Zero-Shot)**
- Modelo: `knowledgator/gliner-pii-base-v1.0` (~330MB)
- Descarga automática desde HuggingFace al primer uso
- Labels: `["person", "address", "organization"]`
- Umbral de confianza: 0.45
- Captura entidades que las reglas no pueden (nombres en contexto, direcciones complejas)

**Capa 3: Ollama (Opcional)**
- Solo se activa si `use_ollama=True` y Ollama está corriendo en `localhost:11434`
- Envía un prompt estructurado al LLM local pidiendo un JSON con entidades PII
- Si Ollama no responde, se ignora silenciosamente (no lanza error)
- Modelo por defecto: `llama3.2`

#### Merge de entidades solapadas:
- Ordena por posición de inicio
- Si dos entidades se solapan, conserva la de mayor score
- En caso de empate, conserva la de mayor longitud
- Resultado final ordenado por `start`

#### Función de coordenadas:

**`map_entities_to_coords(entities, full_text, words) → list[Entity]`**

Enriquece cada entidad con sus coordenadas espaciales en el PDF:
1. Reconstruye las posiciones de cada `WordBox` en el texto plano
2. Para cada entidad, busca qué palabras caen en su rango `[start, end)`
3. Normaliza las coordenadas a porcentajes (0.0 a 1.0) relativos al tamaño de página

---

### 3.3 `pdf_utils.py` — Lectura y Escritura de PDF

**Dataclass `WordBox`:**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `text` | `str` | Texto de la palabra |
| `page` | `int` | Número de página (0-indexed) |
| `x0` | `float` | Coordenada X izquierda |
| `y0` | `float` | Coordenada Y superior |
| `x1` | `float` | Coordenada X derecha |
| `y1` | `float` | Coordenada Y inferior |
| `page_width` | `float` | Ancho total de la página |
| `page_height` | `float` | Alto total de la página |

**Funciones:**

| Función | Descripción |
|---------|-------------|
| `extract_text(pdf_bytes) → str` | Extrae todo el texto del PDF con pdfplumber. Las páginas se concatenan con `\n\n`. |
| `create_pdf(text) → bytes` | Genera un PDF nuevo con fpdf2. Soporta UTF-8 español (ñ, á, é, í, ó, ú, ü, ¿, ¡). Paginación automática con `multi_cell`. |
| `extract_words_with_coords(pdf_bytes) → list[WordBox]` | Extrae cada palabra con su bounding box espacial. Usa `pdfplumber.extract_words()` con `use_text_flow=True`. Las palabras se ordenan por página y posición de lectura. |

---

## 4. Servidor API (`main.py`)

Servidor **FastAPI** con 3 endpoints y servido de frontend estático.

### `GET /`
Sirve el `index.html` del frontend SPA.

### `POST /api/analyze`
**Fase 1 — Análisis interactivo del PDF**

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `file` | `UploadFile` | Archivo PDF a analizar |
| `use_ollama` | `bool` | Activar capa opcional de Ollama |

**Flujo interno:**
1. Extrae texto del PDF (`extract_text`)
2. Extrae palabras con coordenadas (`extract_words_with_coords`)
3. Detecta entidades PII (`detect_pii`)
4. Mapea entidades a coordenadas (`map_entities_to_coords`)
5. Devuelve: PDF en base64, nº de páginas, lista de entidades con coordenadas, texto completo, lista de palabras

### `POST /api/anonymize`
**Fase 2 — Aplicar pseudonimización seleccionada**

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `pdf_base64` | `str` | PDF original codificado en base64 |
| `selected_entity_ids` | `list[str]` | IDs de las entidades que el usuario marcó para anonimizar |
| `entities` | `list[EntitySchema]` | Lista completa de entidades detectadas |

**Flujo interno:**
1. Decodifica el PDF original
2. Filtra las entidades seleccionadas por el usuario
3. Crea un `TokenMapper` y pseudonimiza cada entidad (de derecha a izquierda para preservar offsets)
4. Genera el PDF anonimizado (`create_pdf`)
5. Exporta la clave cifrada (`mapper.to_encrypted_bytes()`)
6. Devuelve: PDF anonimizado en base64, clave `.key` en base64, estadísticas

### `POST /api/deanonymize`
**Fase 3 — Restaurar documento original**

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `file` | `UploadFile` | PDF anonimizado |
| `key_file` | `UploadFile` | Archivo `.key` de restauración |

**Flujo interno:**
1. Extrae el texto del PDF anonimizado
2. Reconstruye el `TokenMapper` desde el archivo `.key` cifrado
3. Desanonimiza el texto (`mapper.depseudonymize`)
4. Genera el PDF restaurado
5. Devuelve: PDF restaurado en base64, nombre de archivo sugerido

---

## 5. Frontend Interactivo

### Diseño visual
Inspirado en **letters.app**. Características:
- Gradiente sky-blue de fondo (`#779BC1 → #9ABFDA → #CBDFEC`)
- Tipografía **Nunito** (Google Fonts)
- Píldoras con 4 capas de sombra acumuladas (efecto premium)
- Bordes asimétricos (28px arriba, 48px abajo)
- Tarjetas decorativas "Antes / Después" rotadas (-3°, +1°)

### Componentes de la UI

**Pestañas principales:**
- **Anonimizar PDF**: Landing con drag & drop, toggle de Ollama, y botón de análisis
- **Restaurar Original**: Subida dual de PDF anonimizado + archivo `.key`

**Panel interactivo (2 columnas):**
1. **Visor de PDF** (izquierda, ~70%): Renderizado con PDF.js, paginación, zoom (±), capa de highlights coloreados sobre las entidades PII
2. **Sidebar de entidades** (derecha, ~30%):
   - Contador de entidades detectadas
   - Sub-pestañas: "📂 Categorías" y "🔍 Datos Sensibles"
   - Toggles maestros por categoría
   - Lista individual de entidades con buscador, badges de tipo, scores de confianza, y toggles individuales
   - Botón "Pseudonimizar Selección"
   - Sincronización hover bidireccional: pasar el ratón sobre un highlight en el PDF resalta la fila en el sidebar, y viceversa

**Funcionalidades adicionales:**
- **Menú contextual**: Clic derecho sobre texto en el visor → categorizar manualmente como PII
- **Modal "Añadir Dato Manual"**: Añadir entidades PII por texto + tipo
- **Zoom independiente**: El visor PDF hace zoom sin afectar al sidebar ni al layout
- **Resultados**: Pantalla de descarga con estadísticas de protección

### Flujo JavaScript principal

1. `handleAnalyze(event)` → POST `/api/analyze` → carga PDF en el visor
2. `renderSidebarFilters()` → construye los toggles de categoría y la lista de entidades
3. `toggleCategory(type, checked)` / `toggleIndividualEntity(id, checked)` → selección interactiva
4. `submitAnonymization()` → POST `/api/anonymize` → descarga de PDF anonimizado + clave
5. `handleRestore(event)` → POST `/api/deanonymize` → descarga de PDF restaurado

---

## 6. Flujo de Usuario Completo

```
┌─────────────────────────────────────────────────────────────────┐
│  1. Usuario sube un PDF con datos personales                     │
│     ↓                                                            │
│  2. Backend extrae texto, detecta PII (Presidio + GLiNER),       │
│     mapea coordenadas espaciales                                 │
│     ↓                                                            │
│  3. Frontend muestra el PDF con highlights de colores sobre      │
│     cada entidad PII. Sidebar lista todas las entidades          │
│     con toggles para seleccionar/deseleccionar                   │
│     ↓                                                            │
│  4. Usuario revisa la selección (activa/desactiva categorías     │
│     o entidades individuales)                                    │
│     ↓                                                            │
│  5. Usuario pulsa "Pseudonimizar Selección"                      │
│     ↓                                                            │
│  6. Backend reemplaza cada PII seleccionada por un token         │
│     (<<PERSON_1>>, <<DNI_1>>, etc.), cifra el mapeo con          │
│     Fernet (AES-256), genera PDF anonimizado                     │
│     ↓                                                            │
│  7. Usuario descarga: PDF anonimizado + archivo .key             │
│     ↓                                                            │
│  8. Usuario comparte/envía el PDF anonimizado                    │
│     ↓                                                            │
│  9. Para restaurar: sube el PDF anonimizado + .key               │
│     ↓                                                            │
│ 10. Backend descifra el mapeo, reemplaza tokens por              │
│     valores originales, genera PDF restaurado                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Tipos de PII Detectados

| Tipo | Etiqueta | Cómo se detecta | Ejemplo |
|------|----------|-----------------|---------|
| **Nombre de persona** | `PERSON` | GLiNER + spaCy NER | `"Juan García López"` |
| **DNI español** | `DNI` | Regex + validación módulo 23 | `"12345678Z"` |
| **NIE español** | `NIE` | Regex + validación (X/Y/Z + 7 dígitos + letra) | `"X1234567L"` |
| **Teléfono español** | `PHONE` | Regex (móviles 6xx/7xx, fijos 9xx, +34) | `"+34 612 345 678"` |
| **Email** | `EMAIL` | Presidio (regex estándar) | `"juan@email.com"` |
| **Dirección** | `ADDRESS` | GLiNER (NER contextual) | `"Calle Gran Vía 42, 28013 Madrid"` |
| **Código postal** | `POSTAL_CODE` | Regex (01000–52999) | `"28013"` |
| **IBAN** | `IBAN` | Presidio (checksum + formato) | `"ES91 2100 0418 4502 0005 1332"` |
| **Tarjeta de crédito** | `CREDIT_CARD` | Presidio (algoritmo de Luhn) | `"4111 1111 1111 1111"` |
| **Organización** | `ORGANIZATION` | GLiNER (NER contextual) | `"Acme Solutions S.L."` |
| **URL** | `URL` | Presidio (regex) | `"https://ejemplo.com"` |
| **IP** | `IP_ADDRESS` | Presidio (regex) | `"192.168.1.1"` |
| **Fecha** | `DATE` | Presidio (regex) | `"15/03/2024"` |
| **Ubicación** | `LOCATION` | spaCy NER | `"Madrid"` |

---

## 8. Instalación y Ejecución

### Requisitos previos
- **Python 3.12 o 3.13**
- **macOS** (Apple Silicon o Intel)
- **Ollama** (opcional, para la capa de LLM local)

### Instalación

```bash
# 1. Clonar el proyecto
cd "pdf-pseudo"

# 2. Crear entorno virtual
python3.12 -m venv .venv
source .venv/bin/activate

# 3. Instalar dependencias
pip install -e ".[dev]"

# 4. Descargar modelo spaCy español
python -m spacy download es_core_news_md

# 5. (Opcional) Instalar Ollama para detección avanzada
brew install ollama
ollama pull llama3.2
```

### Ejecutar la aplicación

```bash
source .venv/bin/activate
python main.py
# o
uvicorn main:app --reload
```

La aplicación estará disponible en `http://localhost:8000`.

### Ejecutar los tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

---

## 9. Tests

**41 tests** cubriendo todos los módulos del backend:

| Archivo | Tests | Qué prueba |
|---------|:-----:|-----------|
| `test_mapper.py` | 8 | Consistencia de tokens, secuencialidad, roundtrip desanonimización, cifrado/descifrado, reconstrucción de contadores, case-insensitivity |
| `test_detector.py` | 16 | DNI válido/inválido, NIE, teléfono, email, IBAN, GLiNER (persona/dirección/organización), ordenación, no solapamiento, Ollama opcional, texto vacío |
| `test_pdf_utils.py` | 6 | Roundtrip crear/extraer PDF, supervivencia de tokens, soporte Unicode (ñ, á, ¿, ¡), texto multilínea, texto vacío, texto largo |
| `test_coords.py` | 8 | WordBox válidos, coordenadas coherentes, orden de lectura, dimensiones de página, mapeo básico, normalización 0-1, entidades multi-palabra, integridad de campos |
| `test_roundtrip.py` | 3 | Pipeline completo (detectar → pseudonimizar → exportar → importar → desanonimizar), preservación de texto estructural, texto sin PII |

---

## 10. Dependencias

### Producción

| Paquete | Versión | Uso |
|---------|---------|-----|
| `fastapi` | ≥0.115.0 | Servidor web API REST |
| `uvicorn` | ≥0.30.0 | Servidor ASGI |
| `python-multipart` | ≥0.0.9 | Subida de archivos |
| `presidio-analyzer` | ≥2.2.0 | Motor de detección PII (reglas + NER) |
| `gliner` | ≥0.2.0 | Modelo NER zero-shot |
| `pdfplumber` | ≥0.11.0 | Extracción de texto y coordenadas de PDF |
| `fpdf2` | ≥2.8.0 | Generación de PDFs |
| `cryptography` | ≥43.0.0 | Cifrado Fernet (AES-256) |
| `httpx` | ≥0.27.0 | Cliente HTTP para Ollama |
| `spacy` | ≥3.7.0 | Backend NLP para Presidio |

### Desarrollo

| Paquete | Versión | Uso |
|---------|---------|-----|
| `pytest` | ≥8.0.0 | Framework de tests |
| `pytest-cov` | ≥5.0.0 | Cobertura de tests |
| `ruff` | ≥0.5.0 | Linter y formateador |

### Modelos descargables

| Modelo | Tamaño | Descarga |
|--------|:------:|----------|
| `es_core_news_md` (spaCy) | ~45MB | `python -m spacy download es_core_news_md` |
| `gliner-pii-base-v1.0` | ~330MB | Automática al primer uso desde HuggingFace |
| `llama3.2` (Ollama) | ~2GB | `ollama pull llama3.2` (opcional) |

---

## Resumen de líneas de código

| Archivo | Líneas |
|---------|:------:|
| `mapper.py` | 139 |
| `detector.py` | 580 |
| `pdf_utils.py` | 125 |
| `main.py` | 341 |
| `app.js` | 1.294 |
| `styles.css` | 1.557 |
| `index.html` | 423 |
| **Tests** | 491 |
| **Total** | **4.950** |
