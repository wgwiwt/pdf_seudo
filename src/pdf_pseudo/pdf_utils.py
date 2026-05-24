from __future__ import annotations

import io
from dataclasses import dataclass

import fitz
from pdfplumber import open as pdfplumber_open


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


def extract_text(pdf_bytes: bytes) -> str:
    """Extrae el texto completo de un PDF a partir de sus bytes.

    Abre el documento, extrae todas las palabras individuales con sus coordenadas
    y reconstruye el texto lineal uniendo las palabras de cada página con espacios
    simples. Las páginas se separan por el delimitador Form Feed (\\x0c).

    Si no se extraen palabras del documento (por ejemplo, un documento escaneado
    sin OCR o texto oculto inusual), aplica un fallback seguro extrayendo el
    texto bruto de cada página para mantener compatibilidad.

    Args:
        pdf_bytes: Bytes del archivo PDF.

    Returns:
        Texto completo extraído y alineado del documento.
    """
    try:
        # Extraer palabras individuales primero
        words = extract_words_with_coords(pdf_bytes)
        
        # Agrupar palabras por página
        words_by_page: dict[int, list[str]] = {}
        for w in words:
            words_by_page.setdefault(w.page, []).append(w.text)
        
        # Obtener el número total de páginas exacto abriendo el PDF
        total_pages = 0
        with pdfplumber_open(io.BytesIO(pdf_bytes)) as pdf:
            total_pages = len(pdf.pages)
            
        if words:
            # Reconstruir el texto uniendo las palabras con espacios
            textos: list[str] = []
            for p in range(total_pages):
                page_words = words_by_page.get(p, [])
                textos.append(" ".join(page_words))
            return "\x0c".join(textos)
    except Exception:
        # En caso de cualquier error, continuaremos con el fallback clásico
        pass

    # Fallback clásico si no hay palabras o si falló la extracción unificada
    textos_fallback: list[str] = []
    with pdfplumber_open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            texto_pagina = page.extract_text(layout=True)
            if texto_pagina:
                textos_fallback.append(texto_pagina)
            else:
                textos_fallback.append("")
    return "\x0c".join(textos_fallback)


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
                words.append(
                    WordBox(
                        text=w["text"],
                        page=page_idx,
                        x0=float(w["x0"]),
                        y0=float(w["top"]),
                        x1=float(w["x1"]),
                        y1=float(w["bottom"]),
                        page_width=page_w,
                        page_height=page_h,
                    )
                )

    words.sort(key=lambda wb: (wb.page, wb.y0, wb.x0))
    return words


def redact_pdf(pdf_bytes: bytes, entities: list[dict]) -> bytes:
    """Aplica redacción destructiva (cajas negras) sobre las coordenadas de entidades PII.

    Abre el documento original con PyMuPDF, dibuja anotaciones de redacción
    negras sobre cada entidad y aplica las redacciones para eliminar
    permanentemente el texto subyacente. El formato y layout original del PDF
    se conservan intactos fuera de las zonas redactadas.

    Las coordenadas de cada entidad deben estar normalizadas (0.0 a 1.0)
    relativas al ancho y alto de la página correspondiente.

    Args:
        pdf_bytes: Bytes del archivo PDF original.
        entities: Lista de entidades con campo ``boxes``. Cada box debe contener
                  ``page`` (int), ``x0``, ``y0``, ``x1``, ``y1`` (float, 0.0-1.0).

    Returns:
        Bytes del PDF redactado.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)

    for entity in entities:
        boxes = entity.get("boxes")
        if not boxes:
            continue

        for box in boxes:
            page_idx = box.get("page", 0)
            if page_idx < 0 or page_idx >= total_pages:
                continue

            page = doc[page_idx]
            r = page.rect
            
            # Calcular en base al origen real (r.x0, r.y0) para soportar MediaBoxes/CropBoxes inusuales
            x0 = r.x0 + box["x0"] * r.width
            y0 = r.y0 + box["y0"] * r.height
            x1 = r.x0 + box["x1"] * r.width
            y1 = r.y0 + box["y1"] * r.height

            # fitz normaliza las coordenadas (rect.normalize()) automáticamente si x1 < x0 o y1 < y0
            rect = fitz.Rect(x0, y0, x1, y1)
            page.add_redact_annot(rect, fill=(0, 0, 0))

    for page in doc:
        page.apply_redactions()

    # Aplicamos garbage=4 y deflate=True para reconstruir el PDF desde cero, 
    # eliminando físicamente las fuentes obsoletas, flujos huérfanos y obligando
    # a los visores problemáticos (como Mac Preview) a renderizar correctamente.
    result = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return result
