# OPENCODE_V2.md — Instrucciones para la Versión 2.0 (Interfaz Visual Interactiva)

> **Lee este archivo completo antes de tocar cualquier código.**
> Este documento sustituye las instrucciones de la V1 para las tareas de esta iteración.
> Las reglas de propiedad de archivos se mantienen idénticas.

---

## 1. Contexto de los Cambios

PDF-Pseudo ahora pasará de ser una herramienta "automática" (sube PDF → sale anonimizado) a una **herramienta interactiva visual**:

1. El usuario sube un PDF.
2. El sistema **analiza** el PDF y devuelve la lista de entidades PII detectadas **junto con sus coordenadas visuales** (dónde están dibujadas las palabras en la página).
3. El frontend de Antigravity renderiza el PDF en el navegador y **superpone rectángulos de colores** sobre las entidades detectadas.
4. El usuario puede **activar o desactivar** cada entidad con un interruptor antes de confirmar la anonimización.
5. Solo las entidades activadas se anonimizan en el PDF final.

**Tu trabajo en esta iteración es exclusivamente ampliar dos archivos** (`pdf_utils.py` y `detector.py`) con funciones nuevas. **No borres ni modifiques** ninguna función existente. Todo lo que hiciste en la V1 sigue siendo válido y necesario.

---

## 2. Regla de Oro: ¿Qué Archivos Tocas?

### ✅ TÚ editas EXCLUSIVAMENTE:
```
src/pdf_pseudo/pdf_utils.py      (AÑADIR nueva función y dataclass)
src/pdf_pseudo/detector.py       (AÑADIR nuevo campo a Entity + nueva función)
src/pdf_pseudo/__init__.py       (AÑADIR nuevos exports)
tests/test_coords.py             (CREAR archivo nuevo)
```

### ❌ NO toques NUNCA:
```
main.py
static/*
pyproject.toml
OPENCODE_V2.md
mapper.py                        (no necesita cambios)
```

---

## 3. Cambio 1: Nueva función en `pdf_utils.py`

### 3.1. Añadir la dataclass `WordBox`

Añade esto **al principio del archivo** (después de los imports existentes):

```python
from dataclasses import dataclass

@dataclass
class WordBox:
    """Palabra extraída de un PDF con su posición espacial en la página."""

    text: str
    """Texto de la palabra."""

    page: int
    """Número de página (0-indexed)."""

    x0: float
    """Coordenada X del borde izquierdo de la palabra."""

    y0: float
    """Coordenada Y del borde superior de la palabra."""

    x1: float
    """Coordenada X del borde derecho de la palabra."""

    y1: float
    """Coordenada Y del borde inferior de la palabra."""

    page_width: float
    """Ancho total de la página en puntos PDF."""

    page_height: float
    """Alto total de la página en puntos PDF."""
```

### 3.2. Añadir la función `extract_words_with_coords`

Añade esta función **debajo de `create_pdf`** (al final del archivo). NO modifiques `extract_text` ni `create_pdf`:

```python
def extract_words_with_coords(pdf_bytes: bytes) -> list[WordBox]:
    """Extrae todas las palabras del PDF con sus coordenadas de bounding box.

    Usa pdfplumber.extract_words() para obtener la posición espacial
    de cada palabra individual dentro de cada página del documento.

    Las coordenadas se devuelven en el sistema nativo de pdfplumber:
    - El origen (0, 0) está en la esquina superior-izquierda de la página.
    - x0, x1 son las coordenadas horizontales (izquierda, derecha).
    - y0, y1 son las coordenadas verticales (arriba, abajo).
    - Los valores están en puntos PDF (72 puntos = 1 pulgada).

    Args:
        pdf_bytes: Bytes del archivo PDF.

    Returns:
        Lista de WordBox ordenada por página y posición de lectura
        (arriba-abajo, izquierda-derecha).
    """
```

**Implementación esperada:**

```python
def extract_words_with_coords(pdf_bytes: bytes) -> list[WordBox]:
    words: list[WordBox] = []
    with pdfplumber_open(io.BytesIO(pdf_bytes)) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            page_w = float(page.width)
            page_h = float(page.height)
            
            extracted = page.extract_words(
                keep_blank_chars=False,
                use_text_flow=True,
            )
            
            for w in extracted:
                words.append(WordBox(
                    text=w["text"],
                    page=page_idx,
                    x0=float(w["x0"]),
                    y0=float(w["top"]),
                    x1=float(w["x1"]),
                    y1=float(w["bottom"]),
                    page_width=page_w,
                    page_height=page_h,
                ))
    
    # Ordenar por página, luego por posición Y (arriba→abajo), luego X (izquierda→derecha)
    words.sort(key=lambda wb: (wb.page, wb.y0, wb.x0))
    return words
```

> ⚠️ **IMPORTANTE**: En pdfplumber, las coordenadas verticales usan `top` y `bottom` (no `y0`/`y1`). `top` es la distancia desde el borde SUPERIOR de la página. `bottom` = `top + altura_de_la_palabra`. Esto se alinea con el sistema de coordenadas CSS del navegador (arriba=0), así que es exactamente lo que necesitamos.

---

## 4. Cambio 2: Enriquecer `detector.py`

### 4.1. Añadir campo `boxes` a la dataclass `Entity`

Modifica la dataclass `Entity` existente. **Solo añade un campo nuevo al final**, no borres ninguno:

```python
@dataclass
class Entity:
    text: str
    entity_type: str
    start: int
    end: int
    score: float
    source: str
    # NUEVO (V2): coordenadas visuales para la capa de overlay del frontend
    boxes: list[dict] | None = None
```

El campo `boxes`, cuando se rellene, contendrá una lista de diccionarios con esta estructura:
```python
{
    "page": 0,           # Página (0-indexed)
    "x0": 0.12,          # Proporción horizontal izquierda (0.0 a 1.0)
    "y0": 0.34,          # Proporción vertical superior (0.0 a 1.0)
    "x1": 0.45,          # Proporción horizontal derecha (0.0 a 1.0)
    "y1": 0.38           # Proporción vertical inferior (0.0 a 1.0)
}
```

> 🔑 **Crítico**: Las coordenadas se normalizan a porcentajes (0.0 a 1.0) dividiéndolas por el tamaño de la página. Esto permite que el frontend posicione los highlights con `position: absolute` usando porcentajes, lo que funciona a cualquier resolución.

### 4.2. Añadir la función `map_entities_to_coords`

Añade esta función **al final del archivo**, después de `detect_pii`. **No modifiques `detect_pii`** ni ninguna otra función existente:

```python
def map_entities_to_coords(
    entities: list[Entity],
    full_text: str,
    words: list["WordBox"],
) -> list[Entity]:
    """Enriquece cada entidad con las coordenadas de los cuadros delimitadores.

    Mapea las posiciones de texto (start, end) de cada entidad a las
    coordenadas espaciales de las palabras del PDF. Las coordenadas se
    normalizan a porcentajes (0.0 a 1.0) relativos al tamaño de la página.

    Args:
        entities: Lista de entidades detectadas por ``detect_pii()``.
        full_text: Texto completo extraído con ``extract_text()``.
        words: Lista de ``WordBox`` extraída con ``extract_words_with_coords()``.

    Returns:
        Las mismas entidades con el campo ``boxes`` rellenado.
    """
```

**Algoritmo de mapeo (implementación guiada):**

El problema central es: `detect_pii` trabaja con posiciones en el texto plano concatenado (start/end). `extract_words_with_coords` trabaja con posiciones espaciales en la página PDF. Necesitamos hacer corresponder unos con otros.

```python
def map_entities_to_coords(
    entities: list[Entity],
    full_text: str,
    words: list[WordBox],
) -> list[Entity]:
    # Paso 1: Calcular la posición de inicio de cada WordBox en el texto plano.
    # Reconstruimos el texto concatenando las palabras y rastreando las posiciones.
    word_positions: list[tuple[int, int, WordBox]] = []  # (char_start, char_end, word)
    
    search_start = 0
    for wb in words:
        # Buscar dónde aparece esta palabra en el texto plano
        idx = full_text.find(wb.text, search_start)
        if idx == -1:
            # Si no se encuentra exactamente, intentar con búsqueda más flexible
            # (puede haber diferencias por espaciado o caracteres especiales)
            continue
        word_positions.append((idx, idx + len(wb.text), wb))
        search_start = idx + len(wb.text)
    
    # Paso 2: Para cada entidad, encontrar qué palabras caen en su rango [start, end)
    for entity in entities:
        entity_boxes: list[dict] = []
        for char_start, char_end, wb in word_positions:
            # ¿Se solapan los rangos [entity.start, entity.end) y [char_start, char_end)?
            if char_start < entity.end and char_end > entity.start:
                entity_boxes.append({
                    "page": wb.page,
                    "x0": round(wb.x0 / wb.page_width, 6),
                    "y0": round(wb.y0 / wb.page_height, 6),
                    "x1": round(wb.x1 / wb.page_width, 6),
                    "y1": round(wb.y1 / wb.page_height, 6),
                })
        entity.boxes = entity_boxes if entity_boxes else None
    
    return entities
```

> ⚠️ **Nota sobre `find()`**: La búsqueda secuencial con `find()` y `search_start` funciona porque tanto `extract_text()` como `extract_words_with_coords()` procesan las palabras del PDF en el mismo orden de lectura. Si una palabra no se encuentra (ej: por diferencias de espaciado), simplemente se salta — es aceptable que algunas entidades no tengan boxes (el frontend las mostrará en el sidebar pero sin highlight visual).

---

## 5. Cambio 3: Actualizar `__init__.py`

Añade estas líneas al archivo existente:

```python
from pdf_pseudo.pdf_utils import extract_words_with_coords, WordBox
from pdf_pseudo.detector import map_entities_to_coords
```

Y amplía `__all__`:

```python
__all__ = [
    "TokenMapper",
    "detect_pii",
    "extract_text",
    "create_pdf",
    "extract_words_with_coords",
    "WordBox",
    "map_entities_to_coords",
]
```

---

## 6. Tests: Crear `tests/test_coords.py`

Crea un archivo nuevo `tests/test_coords.py` con los siguientes tests:

```python
"""Tests para las funciones de coordenadas de la V2."""
from __future__ import annotations

import pytest

from pdf_pseudo.pdf_utils import create_pdf, extract_text, extract_words_with_coords, WordBox
from pdf_pseudo.detector import detect_pii, map_entities_to_coords


class TestExtractWordsWithCoords:
    """Tests para extract_words_with_coords."""

    def test_returns_wordbox_list(self):
        """Verifica que devuelve una lista de WordBox."""
        pdf_bytes = create_pdf("Hola mundo de prueba")
        words = extract_words_with_coords(pdf_bytes)
        assert isinstance(words, list)
        assert len(words) > 0
        assert all(isinstance(w, WordBox) for w in words)

    def test_wordbox_has_valid_coords(self):
        """Verifica que las coordenadas son positivas y coherentes."""
        pdf_bytes = create_pdf("Texto de ejemplo para coordenadas")
        words = extract_words_with_coords(pdf_bytes)
        for w in words:
            assert w.x0 >= 0
            assert w.y0 >= 0
            assert w.x1 > w.x0, f"x1 ({w.x1}) debe ser mayor que x0 ({w.x0})"
            assert w.y1 > w.y0, f"y1 ({w.y1}) debe ser mayor que y0 ({w.y0})"
            assert w.x1 <= w.page_width
            assert w.y1 <= w.page_height
            assert w.page >= 0

    def test_words_are_sorted_by_reading_order(self):
        """Verifica que las palabras se ordenan por página y posición."""
        pdf_bytes = create_pdf("Primera línea\nSegunda línea\nTercera línea")
        words = extract_words_with_coords(pdf_bytes)
        # Verificar que están en orden de lectura (por página, luego y0, luego x0)
        for i in range(1, len(words)):
            prev = words[i - 1]
            curr = words[i]
            assert (curr.page, curr.y0, curr.x0) >= (prev.page, prev.y0, prev.x0)

    def test_page_dimensions_positive(self):
        """Verifica que las dimensiones de la página son positivas."""
        pdf_bytes = create_pdf("Test")
        words = extract_words_with_coords(pdf_bytes)
        for w in words:
            assert w.page_width > 0
            assert w.page_height > 0


class TestMapEntitiesToCoords:
    """Tests para map_entities_to_coords."""

    def test_basic_mapping(self):
        """Verifica que una entidad simple obtiene boxes."""
        texto = "El paciente Juan García tiene DNI 12345678Z."
        pdf_bytes = create_pdf(texto)
        full_text = extract_text(pdf_bytes)
        words = extract_words_with_coords(pdf_bytes)
        entities = detect_pii(full_text)

        if entities:  # Solo testear si se detectaron entidades
            result = map_entities_to_coords(entities, full_text, words)
            # Al menos algunas entidades deben tener boxes
            entities_with_boxes = [e for e in result if e.boxes]
            assert len(entities_with_boxes) > 0

    def test_boxes_are_normalized(self):
        """Verifica que las coordenadas están normalizadas entre 0.0 y 1.0."""
        texto = "Juan García López vive en Madrid, DNI 12345678Z."
        pdf_bytes = create_pdf(texto)
        full_text = extract_text(pdf_bytes)
        words = extract_words_with_coords(pdf_bytes)
        entities = detect_pii(full_text)

        if entities:
            result = map_entities_to_coords(entities, full_text, words)
            for ent in result:
                if ent.boxes:
                    for box in ent.boxes:
                        assert 0.0 <= box["x0"] <= 1.0
                        assert 0.0 <= box["y0"] <= 1.0
                        assert 0.0 <= box["x1"] <= 1.0
                        assert 0.0 <= box["y1"] <= 1.0
                        assert box["x1"] > box["x0"]
                        assert box["y1"] > box["y0"]
                        assert isinstance(box["page"], int)
                        assert box["page"] >= 0

    def test_multiword_entity_has_multiple_boxes(self):
        """Verifica que un nombre de varias palabras produce múltiples boxes."""
        texto = "La doctora María Fernanda González Ruiz firmó el informe."
        pdf_bytes = create_pdf(texto)
        full_text = extract_text(pdf_bytes)
        words = extract_words_with_coords(pdf_bytes)
        entities = detect_pii(full_text)

        person_entities = [e for e in entities if e.entity_type == "PERSON"]
        if person_entities:
            result = map_entities_to_coords(person_entities, full_text, words)
            for ent in result:
                if ent.boxes and " " in ent.text:
                    # Una entidad multi-palabra debería tener al menos 2 boxes
                    assert len(ent.boxes) >= 2, (
                        f"Entidad '{ent.text}' tiene {len(ent.boxes)} boxes, esperaba >= 2"
                    )

    def test_does_not_modify_existing_fields(self):
        """Verifica que map_entities_to_coords no altera los campos originales."""
        texto = "Contacto: juan@email.com, DNI 12345678Z"
        pdf_bytes = create_pdf(texto)
        full_text = extract_text(pdf_bytes)
        words = extract_words_with_coords(pdf_bytes)
        entities = detect_pii(full_text)

        if entities:
            originals = [(e.text, e.entity_type, e.start, e.end, e.score) for e in entities]
            result = map_entities_to_coords(entities, full_text, words)
            for i, ent in enumerate(result):
                assert ent.text == originals[i][0]
                assert ent.entity_type == originals[i][1]
                assert ent.start == originals[i][2]
                assert ent.end == originals[i][3]
                assert ent.score == originals[i][4]
```

---

## 7. Cómo Verificar Tu Trabajo

```bash
cd "/Users/juanjoyamparoaragonbaltasar/Documents/Antigravity proyectos/01_EN_CURSO/Datos anonimos"
source .venv/bin/activate

# 1. Ejecutar TODOS los tests (viejos + nuevos)
pytest tests/ -v

# 2. Verificar que los 33 tests existentes siguen pasando
# 3. Verificar que los tests nuevos de test_coords.py también pasan
```

---

## 8. Cómo Importará Antigravity Tus Nuevas Funciones

En `main.py`, Antigravity usará:

```python
from pdf_pseudo.pdf_utils import extract_text, create_pdf, extract_words_with_coords
from pdf_pseudo.detector import detect_pii, map_entities_to_coords, Entity
from pdf_pseudo.mapper import TokenMapper
```

El flujo del nuevo endpoint `/api/analyze` será:
```python
# 1. Leer PDF
pdf_bytes = await file.read()

# 2. Extraer texto (función existente)
text = extract_text(pdf_bytes)

# 3. Extraer palabras con coordenadas (NUEVA función)
words = extract_words_with_coords(pdf_bytes)

# 4. Detectar entidades (función existente)
entities = detect_pii(text, use_ollama=use_ollama)

# 5. Mapear entidades a coordenadas (NUEVA función)
entities_with_coords = map_entities_to_coords(entities, text, words)

# 6. Devolver todo al frontend como JSON
```

---

## 9. Resumen de lo que Debes Hacer (Checklist)

- [ ] **En `pdf_utils.py`**: Añadir `dataclass WordBox` y función `extract_words_with_coords()`
- [ ] **En `detector.py`**: Añadir campo `boxes: list[dict] | None = None` a `Entity`
- [ ] **En `detector.py`**: Añadir función `map_entities_to_coords()`
- [ ] **En `__init__.py`**: Añadir exports de `WordBox`, `extract_words_with_coords`, `map_entities_to_coords`
- [ ] **Crear `tests/test_coords.py`**: Tests para las nuevas funciones
- [ ] **Ejecutar `pytest tests/ -v`**: Los 33 tests viejos + los nuevos deben pasar
- [ ] **No romper nada existente**: `extract_text`, `create_pdf`, `detect_pii`, `TokenMapper` deben seguir funcionando exactamente igual

---

## 10. Orden de Implementación

1. **Primero**: `WordBox` + `extract_words_with_coords()` en `pdf_utils.py`
2. **Segundo**: Añadir campo `boxes` a `Entity` en `detector.py`
3. **Tercero**: `map_entities_to_coords()` en `detector.py`
4. **Cuarto**: Actualizar `__init__.py`
5. **Quinto**: Crear `tests/test_coords.py` y ejecutar toda la suite
