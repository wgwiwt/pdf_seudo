# OPENCODE.md — Instrucciones para el Agente OpenCode

> **Este archivo es tu guía completa.** Léelo de arriba a abajo antes de tocar cualquier archivo.
> Contiene las reglas de colaboración, la arquitectura del proyecto, y las especificaciones técnicas exactas de los módulos que debes implementar.

---

## 1. Contexto del Proyecto

**PDF-Pseudo** es una aplicación web local en Python que permite a cualquier usuario arrastrar un PDF en español, anonimizar automáticamente toda la información personal (PII), y restaurar el documento original posteriormente usando una clave cifrada.

La aplicación tiene dos partes:
- **Frontend** (HTML/CSS/JS en `static/`): Lo construye **Antigravity**. NO toques nada en esa carpeta.
- **Backend motor de PII** (Python en `src/pdf_pseudo/`): Lo construyes **TÚ**. Son 3 archivos puros de lógica Python.
- **Servidor FastAPI** (`main.py`): Lo construye **Antigravity**. Él importará tus módulos.
- **Tests** (`tests/`): Los construyes **TÚ**.

---

## 2. Regla de Oro: ¿Qué Archivos Son Tuyos?

### ✅ TÚ creas y editas EXCLUSIVAMENTE:
```
src/pdf_pseudo/mapper.py
src/pdf_pseudo/detector.py
src/pdf_pseudo/pdf_utils.py
tests/test_mapper.py
tests/test_detector.py
tests/test_pdf_utils.py
tests/test_roundtrip.py
tests/conftest.py              (si necesitas fixtures compartidos)
```

### ❌ NO toques NUNCA:
```
main.py
static/*
pyproject.toml
```

Antigravity ha creado `src/pdf_pseudo/__init__.py` vacío. Puedes añadir líneas de `export` (ej. `from .mapper import TokenMapper`) si lo necesitas, pero NO borres lo que ya exista.

---

## 3. Entorno y Dependencias

Las dependencias ya están definidas en `pyproject.toml`. Para instalar el entorno:

```bash
cd "/Users/juanjoyamparoaragonbaltasar/Documents/Antigravity proyectos/01_EN_CURSO/Datos anonimos"
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m spacy download es_core_news_md
```

Las librerías que usarás son:
- `pdfplumber` — extracción de texto de PDFs
- `fpdf2` — creación de PDFs nuevos
- `cryptography` — cifrado Fernet (AES-256)
- `presidio-analyzer` — motor de detección PII basado en reglas
- `gliner` — modelo NER zero-shot para entidades complejas
- `spacy` — backend NLP para Presidio
- `httpx` — cliente HTTP para llamar a Ollama localmente (opcional)
- `pytest` — framework de tests

---

## 4. Especificaciones Técnicas por Módulo

### 4.1. `src/pdf_pseudo/mapper.py` — Mapeador Bidireccional con Cifrado

```python
# Interfaz pública esperada (NO copies esto tal cual, es la INTERFAZ que main.py va a importar):

class TokenMapper:
    def __init__(self):
        """Crea un nuevo mapeador. Genera una clave Fernet automáticamente."""
        ...

    def pseudonymize(self, original_text: str, entity_type: str) -> str:
        """
        Dado un texto original y su tipo de entidad, devuelve un token consistente.
        Ejemplo: pseudonymize("Juan Pérez", "PERSON") -> "<<PERSON_1>>"
        Si se llama otra vez con los mismos argumentos, devuelve el MISMO token.
        Si se llama con otro nombre, devuelve "<<PERSON_2>>", etc.
        """
        ...

    def depseudonymize(self, text_with_tokens: str) -> str:
        """
        Recibe un texto con tokens como <<PERSON_1>> y reemplaza cada uno
        por su valor original. Devuelve el texto restaurado.
        """
        ...

    def to_encrypted_bytes(self) -> bytes:
        """
        Serializa todo el mapa de sustituciones + la clave Fernet a bytes cifrados.
        Este es el contenido del archivo .key que el usuario descarga.
        Formato interno: Fernet key (44 bytes URL-safe base64) + newline + JSON cifrado.
        """
        ...

    @staticmethod
    def from_encrypted_bytes(data: bytes) -> "TokenMapper":
        """
        Reconstruye un TokenMapper a partir de los bytes del archivo .key.
        Extrae la clave Fernet, descifra el JSON, y rellena el mapa interno.
        """
        ...
```

**Detalles de implementación:**
- Los tokens tienen el formato `<<TIPO_N>>` donde TIPO es el `entity_type` en mayúsculas y N es un entero secuencial empezando en 1.
- Internamente necesitas dos diccionarios: `_forward` (original → token) y `_reverse` (token → original).
- La clave para `_forward` debe ser `(original_text, entity_type)` como tupla para garantizar unicidad.
- Para el cifrado: usa `cryptography.fernet.Fernet`. La clave se genera con `Fernet.generate_key()`.
- Formato del archivo `.key` exportado: primera línea = clave Fernet en base64, segunda línea en adelante = el JSON del mapa `_forward` cifrado con esa clave Fernet.

---

### 4.2. `src/pdf_pseudo/pdf_utils.py` — Lectura y Escritura de PDF

```python
# Interfaz pública esperada:

def extract_text(pdf_bytes: bytes) -> str:
    """
    Recibe los bytes de un archivo PDF.
    Devuelve todo el texto extraído como una sola cadena, con páginas separadas por '\n\n'.
    Usa pdfplumber.
    """
    ...

def create_pdf(text: str) -> bytes:
    """
    Recibe una cadena de texto (potencialmente largo, multilínea).
    Devuelve los bytes de un PDF nuevo limpio y legible.
    Usa fpdf2.
    IMPORTANTE: Debe soportar caracteres UTF-8 españoles (ñ, á, é, í, ó, ú, ü, ¿, ¡).
    Usa una fuente que soporte Unicode (ej. DejaVu o la fuente built-in de fpdf2).
    Paginación automática con multi_cell.
    """
    ...
```

**Detalles de implementación:**
- Para `extract_text`: usa `pdfplumber.open()` pasando un `io.BytesIO(pdf_bytes)`. Itera por cada página y concatena `page.extract_text()` separando con `\n\n`.
- Para `create_pdf`: usa `fpdf2.FPDF()`. Configura una fuente Unicode (fpdf2 incluye soporte con `add_font` para TTF, o puedes usar el built-in Helvetica que soporta latin-1 como mínimo). Usa `multi_cell()` para el flujo de texto. Llama a `pdf.output()` sin argumento para obtener los bytes.

---

### 4.3. `src/pdf_pseudo/detector.py` — Motor de Detección PII en Español

Este es el archivo más complejo. Tiene tres capas de detección que trabajan en conjunto.

```python
# Interfaz pública esperada:

from dataclasses import dataclass

@dataclass
class Entity:
    text: str           # El texto original detectado (ej. "Juan Pérez")
    entity_type: str    # El tipo normalizado (ej. "PERSON", "DNI", "PHONE")
    start: int          # Posición de inicio en el texto
    end: int            # Posición final en el texto
    score: float        # Confianza de la detección (0.0 a 1.0)
    source: str         # Quién la detectó: "presidio", "gliner", "ollama"

def detect_pii(text: str, use_ollama: bool = False) -> list[Entity]:
    """
    Analiza el texto y devuelve una lista de entidades PII detectadas.
    Combina resultados de Presidio (reglas), GLiNER (NER) y opcionalmente Ollama (LLM).
    Las entidades solapadas se fusionan priorizando la de mayor score.
    La lista resultante está ordenada por posición (start).
    """
    ...
```

**Capa 1: Presidio (Reglas y Regex)**

Configura un `AnalyzerEngine` con los reconocedores estándar de Presidio para `es` y añade estos reconocedores personalizados:

- **`SpanishDNIRecognizer`**: Regex `\b(\d{8})([A-Z])\b` + validación matemática:
  ```python
  LETRAS_DNI = "TRWAGMYFPDXBNJZSQVHLCKE"
  def validar_dni(numero: str, letra: str) -> bool:
      return LETRAS_DNI[int(numero) % 23] == letra
  ```
- **`SpanishNIERecognizer`**: Regex `\b([XYZ])(\d{7})([A-Z])\b` + validación (X=0, Y=1, Z=2 prepended).
- **`SpanishPhoneRecognizer`**: Regex `(?:\+34[\s.-]?)?[6789]\d{8}\b` (sin capturar textos sueltos de solo dígitos).
- **`SpanishPostalCodeRecognizer`**: Regex `\b(0[1-9]|[1-4]\d|5[0-2])\d{3}\b` (rangos 01000–52999).

Mapeo de tipos de Presidio a nuestros tipos internos:
```
PERSON → PERSON
EMAIL_ADDRESS → EMAIL
PHONE_NUMBER → PHONE
IBAN_CODE → IBAN
CREDIT_CARD → CREDIT_CARD
ES_DNI → DNI
ES_NIE → NIE
ES_PHONE → PHONE
ES_POSTAL_CODE → POSTAL_CODE
```

**Capa 2: GLiNER (NER Zero-Shot)**

```python
from gliner import GLiNER
model = GLiNER.from_pretrained("GreyNoise/gliner-pii-base-v1.0")
entities = model.predict_entities(text, labels=["person", "address", "organization"], threshold=0.45)
```

Mapeo de labels de GLiNER a nuestros tipos:
```
person → PERSON
address → ADDRESS
organization → ORGANIZATION
```

**Capa 3: Ollama (Opcional)**

Solo si `use_ollama=True`. Usa `httpx` para enviar una petición POST a `http://localhost:11434/api/generate`:

```python
prompt = f"""Analiza el siguiente texto en español e identifica TODAS las entidades de información personal (PII).
Devuelve ÚNICAMENTE un JSON array con objetos que tengan: "text", "type", "start", "end".
Los tipos válidos son: PERSON, ADDRESS, ORGANIZATION, PHONE, EMAIL, DNI, NIE, IBAN.
No inventes entidades. Solo las que aparezcan literalmente en el texto.

Texto:
---
{text}
---

JSON:"""
```

Si Ollama no está corriendo (ConnectionError), simplemente ignora esta capa sin lanzar error.

**Merge de Entidades Solapadas:**

Después de combinar las tres listas, fusiona entidades que se solapan:
1. Ordena por `start`.
2. Si dos entidades se solapan (el `start` de una está dentro del rango `[start, end)` de otra), quédate con la de mayor `score`. Si tienen el mismo score, quédate con la más larga.
3. Devuelve la lista final limpia y ordenada.

---

## 5. Tests

Crea los tests en la carpeta `tests/`. Usa `pytest`.

### `tests/conftest.py`
```python
import pytest

TEXTO_EJEMPLO_ES = """
Informe de evaluación del paciente Juan García López, con DNI 12345678Z,
domiciliado en Calle Gran Vía 42, 3ºB, 28013 Madrid.
Teléfono de contacto: +34 612 345 678. Email: juan.garcia@email.com.
La empresa Acme Solutions S.L., con CIF B12345678, realizó el pago
mediante transferencia a la cuenta IBAN ES91 2100 0418 4502 0005 1332.
"""
```

### `tests/test_mapper.py`
- `test_pseudonymize_consistency`: Mismo input → mismo token.
- `test_pseudonymize_sequential`: Distintos inputs → tokens incrementales.
- `test_depseudonymize_roundtrip`: Pseudonimizar varios valores, construir texto con tokens, desanonimizar, verificar que los originales vuelven.
- `test_encrypt_decrypt_roundtrip`: `to_encrypted_bytes()` → `from_encrypted_bytes()` → verificar que el mapa interno es idéntico.

### `tests/test_pdf_utils.py`
- `test_create_and_extract_roundtrip`: Crear un PDF con texto español → extraer texto → verificar que coincide.
- `test_unicode_support`: Verificar que ñ, á, é, ¿, ¡ sobreviven el roundtrip.

### `tests/test_detector.py`
- `test_detect_valid_dni`: "12345678Z" debe detectarse como DNI.
- `test_reject_invalid_dni`: "12345678A" (letra incorrecta) no debe detectarse.
- `test_detect_nie`: "X1234567L" debe detectarse.
- `test_detect_spanish_phone`: "+34 612 345 678" debe detectarse como PHONE.
- `test_detect_email`: "juan@email.com" debe detectarse como EMAIL.
- `test_detect_person_gliner`: "Juan García López" debe detectarse como PERSON.

### `tests/test_roundtrip.py`
- `test_full_pipeline_roundtrip`:
  1. Usar `TEXTO_EJEMPLO_ES`.
  2. Detectar entidades con `detect_pii()`.
  3. Crear `TokenMapper`, pseudonimizar cada entidad en el texto.
  4. Verificar que el texto resultante NO contiene ningún PII original.
  5. Exportar el mapper a bytes cifrados.
  6. Importar el mapper desde esos bytes.
  7. Desanonimizar el texto.
  8. `assert texto_restaurado == texto_original`.

---

## 6. Orden de Implementación Recomendado

1. **Primero**: `mapper.py` + `test_mapper.py` — Es el componente más aislado y simple.
2. **Segundo**: `pdf_utils.py` + `test_pdf_utils.py` — Solo depende de pdfplumber y fpdf2.
3. **Tercero**: `detector.py` + `test_detector.py` — El más complejo, necesita Presidio + GLiNER.
4. **Cuarto**: `test_roundtrip.py` — Integra todo.

---

## 7. Convenciones de Código

- **Python 3.12+** con type hints en todas las funciones públicas.
- **Docstrings** en español en todas las clases y funciones públicas.
- Usa `from __future__ import annotations` en la primera línea de cada módulo.
- Los imports se organizan: stdlib → terceros → locales, separados por línea en blanco.
- Ejecuta `ruff check` antes de dar por terminado cada archivo.

---

## 8. Cómo Ejecutar los Tests

```bash
cd "/Users/juanjoyamparoaragonbaltasar/Documents/Antigravity proyectos/01_EN_CURSO/Datos anonimos"
source .venv/bin/activate
pytest tests/ -v
```

---

## 9. Contacto con Antigravity

Si necesitas que `main.py` importe tus módulos de una forma concreta, NO modifiques `main.py`. En su lugar, asegúrate de que tus exports en `src/pdf_pseudo/__init__.py` exponen la interfaz pública documentada en este archivo. Antigravity importará así:

```python
from pdf_pseudo.mapper import TokenMapper
from pdf_pseudo.detector import detect_pii
from pdf_pseudo.pdf_utils import extract_text, create_pdf
```
