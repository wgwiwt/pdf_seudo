from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from presidio_analyzer import AnalyzerEngine, EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider

if TYPE_CHECKING:
    from pdf_pseudo.pdf_utils import WordBox

try:
    from gliner import GLiNER
    _GLINER_AVAILABLE = True
except ImportError:
    _GLINER_AVAILABLE = False

try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False


# ---------------------------------------------------------------------------
# Entidad detectada
# ---------------------------------------------------------------------------


@dataclass
class Entity:
    """Entidad de información personal detectada en un texto."""

    text: str
    """Texto original detectado (ej. ``"Juan Pérez"``)."""

    entity_type: str
    """Tipo normalizado (ej. ``"PERSON"``, ``"DNI"``, ``"PHONE"``)."""

    start: int
    """Posición de inicio en el texto."""

    end: int
    """Posición final en el texto (exclusiva)."""

    score: float
    """Confianza de la detección (0.0 a 1.0)."""

    source: str
    """Quién la detectó: ``"presidio"``, ``"gliner"``, ``"ollama"``."""

    boxes: list[dict] | None = None
    """Coordenadas visuales para la capa de overlay del frontend.

    Cada diccionario contiene: page, x0, y0, x1, y1 (proporciones 0.0-1.0).
    """


# ---------------------------------------------------------------------------
# Constantes de mapa de tipos
# ---------------------------------------------------------------------------

# Mapeo de tipos de Presidio a nuestros tipos internos
_PRESIDIO_TYPE_MAP: dict[str, str] = {
    "PERSON": "PERSON",
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER": "PHONE",
    "IBAN_CODE": "IBAN",
    "CREDIT_CARD": "CREDIT_CARD",
    "LOCATION": "LOCATION",
    "DATE_TIME": "DATE",
    "URL": "URL",
    "IP_ADDRESS": "IP",
    # Nuestros tipos personalizados
    "ES_DNI": "DNI",
    "ES_NIE": "NIE",
    "ES_PHONE": "PHONE",
    "ES_POSTAL_CODE": "POSTAL_CODE",
}

# Mapeo de labels de GLiNER a nuestros tipos
_GLINER_TYPE_MAP: dict[str, str] = {
    "person": "PERSON",
    "address": "ADDRESS",
    "organization": "ORGANIZATION",
}

GLINER_LABELS: list[str] = ["person", "address", "organization"]

# Letras para validación de DNI español
_LETRAS_DNI = "TRWAGMYFPDXBNJZSQVHLCKE"


# ---------------------------------------------------------------------------
# Reconocedores personalizados para España
# ---------------------------------------------------------------------------


class SpanishDNIRecognizer(EntityRecognizer):
    """Reconocedor de DNI español con validación de letra (módulo 23).

    Detecta patrones de tipo ``12345678Z`` y solo retorna resultados cuando
    la letra coincide matemáticamente con el número.
    """

    def __init__(self):
        super().__init__(
            supported_entities=["ES_DNI"],
            supported_language="es",
        )

    def analyze(  # type: ignore[override]
        self,
        text: str,
        entities: list[str] | None = None,
        nlp_artifacts: object = None,
    ) -> list[RecognizerResult]:
        """Busca DNIs válidos en el texto y devuelve los resultados."""
        resultados: list[RecognizerResult] = []
        for m in re.finditer(r"\b(\d{8})([A-Za-z])\b", text):
            numero = int(m.group(1))
            letra = m.group(2).upper()
            if _LETRAS_DNI[numero % 23] == letra:
                resultados.append(
                    RecognizerResult(
                        entity_type=self.supported_entities[0],
                        start=m.start(),
                        end=m.end(),
                        score=0.95,
                    )
                )
        return resultados


class SpanishNIERecognizer(EntityRecognizer):
    """Reconocedor de NIE español con validación de letra.

    Formato: ``[XYZ] + 7 dígitos + letra``. La letra X se interpreta como 0,
    Y como 1, Z como 2 para el cálculo del módulo 23.
    """

    def __init__(self):
        super().__init__(
            supported_entities=["ES_NIE"],
            supported_language="es",
        )

    def analyze(  # type: ignore[override]
        self,
        text: str,
        entities: list[str] | None = None,
        nlp_artifacts: object = None,
    ) -> list[RecognizerResult]:
        """Busca NIEs válidos en el texto y devuelve los resultados."""
        resultados: list[RecognizerResult] = []
        for m in re.finditer(r"\b([XYZ])\s*(\d{7})\s*([A-Za-z])\b", text):
            prefijo = m.group(1).upper()
            digitos = m.group(2)
            letra = m.group(3).upper()

            prefijo_num = {"X": "0", "Y": "1", "Z": "2"}[prefijo]
            numero_nie = int(prefijo_num + digitos)

            if _LETRAS_DNI[numero_nie % 23] == letra:
                inicio = m.start()
                fin = m.end()
                resultados.append(
                    RecognizerResult(
                        entity_type=self.supported_entities[0],
                        start=inicio,
                        end=fin,
                        score=0.95,
                    )
                )
        return resultados


class SpanishPhoneRecognizer(EntityRecognizer):
    """Reconocedor de teléfonos españoles (móviles y fijos).

    Soporta formato internacional (``+34``) y nacional con prefijo de móvil
    (6, 7, 8) o fijo (9).
    """

    _PATRON = re.compile(
        r"(?:\+\s*34[\s.\-]?)?[6789]\d{2}[\s.\-]?\d{3}[\s.\-]?\d{2,3}\b"
    )

    def __init__(self):
        super().__init__(
            supported_entities=["ES_PHONE"],
            supported_language="es",
        )

    def analyze(  # type: ignore[override]
        self,
        text: str,
        entities: list[str] | None = None,
        nlp_artifacts: object = None,
    ) -> list[RecognizerResult]:
        """Busca teléfonos españoles en el texto."""
        resultados: list[RecognizerResult] = []
        for m in self._PATRON.finditer(text):
            resultados.append(
                RecognizerResult(
                    entity_type=self.supported_entities[0],
                    start=m.start(),
                    end=m.end(),
                    score=0.85,
                )
            )
        return resultados


class SpanishPostalCodeRecognizer(EntityRecognizer):
    """Reconocedor de códigos postales españoles (01000–52999)."""

    _PATRON = re.compile(r"\b(0[1-9]|[1-4]\d|5[0-2])\d{3}\b")

    def __init__(self):
        super().__init__(
            supported_entities=["ES_POSTAL_CODE"],
            supported_language="es",
        )

    def analyze(  # type: ignore[override]
        self,
        text: str,
        entities: list[str] | None = None,
        nlp_artifacts: object = None,
    ) -> list[RecognizerResult]:
        """Busca códigos postales españoles en el texto."""
        resultados: list[RecognizerResult] = []
        for m in self._PATRON.finditer(text):
            resultados.append(
                RecognizerResult(
                    entity_type=self.supported_entities[0],
                    start=m.start(),
                    end=m.end(),
                    score=0.9,
                )
            )
        return resultados


# ---------------------------------------------------------------------------
# Motores de detección
# ---------------------------------------------------------------------------

_presidio_analyzer: AnalyzerEngine | None = None


def _get_presidio_analyzer() -> AnalyzerEngine:
    """Devuelve un AnalyzerEngine de Presidio configurado con reconocedores ES."""
    global _presidio_analyzer
    if _presidio_analyzer is not None:
        return _presidio_analyzer

    provider = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "es", "model_name": "es_core_news_md"}],
        }
    )
    nlp_engine = provider.create_engine()

    _presidio_analyzer = AnalyzerEngine(
        nlp_engine=nlp_engine,
        supported_languages=["es"],
    )

    _presidio_analyzer.registry.add_recognizer(SpanishDNIRecognizer())
    _presidio_analyzer.registry.add_recognizer(SpanishNIERecognizer())
    _presidio_analyzer.registry.add_recognizer(SpanishPhoneRecognizer())
    _presidio_analyzer.registry.add_recognizer(SpanishPostalCodeRecognizer())

    return _presidio_analyzer


def _presidio_detect(text: str) -> list[Entity]:
    """Capa 1: Detección con Presidio (reglas + NER)."""
    analyzer = _get_presidio_analyzer()
    results: list[RecognizerResult] = analyzer.analyze(
        text=text,
        language="es",
        entities=[
            "PERSON",
            "EMAIL_ADDRESS",
            "PHONE_NUMBER",
            "IBAN_CODE",
            "CREDIT_CARD",
            "LOCATION",
            "DATE_TIME",
            "URL",
            "IP_ADDRESS",
            "ES_DNI",
            "ES_NIE",
            "ES_PHONE",
            "ES_POSTAL_CODE",
        ],
    )

    entities: list[Entity] = []
    for r in results:
        mapeo = _PRESIDIO_TYPE_MAP.get(r.entity_type)
        if mapeo is None:
            continue
        match_text = text[r.start : r.end]
        entities.append(
            Entity(
                text=match_text,
                entity_type=mapeo,
                start=r.start,
                end=r.end,
                score=r.score,
                source="presidio",
            )
        )
    return entities


_gliner_model: object | None = None


def _get_gliner_model() -> object:
    """Carga lazy del modelo GLiNER."""
    global _gliner_model
    if _gliner_model is not None:
        return _gliner_model

    if not _GLINER_AVAILABLE:
        raise RuntimeError("GLiNER no está instalado. Ejecuta: pip install gliner")

    _gliner_model = GLiNER.from_pretrained("knowledgator/gliner-pii-base-v1.0")
    return _gliner_model


def _gliner_detect(text: str) -> list[Entity]:
    """Capa 2: Detección con GLiNER (NER zero-shot)."""
    if not _GLINER_AVAILABLE:
        return []

    model = _get_gliner_model()
    try:
        predicciones = model.predict_entities(
            text,
            labels=GLINER_LABELS,
            threshold=0.45,
        )
    except Exception:
        return []

    entities: list[Entity] = []
    entidades_vistas: set[tuple[int, int, str]] = set()

    for pred in predicciones:
        label = _GLINER_TYPE_MAP.get(pred.get("label", "").lower())
        if label is None:
            continue
        start = int(pred["start"])
        end = int(pred["end"])
        score = float(pred.get("score", 0.5))
        match_text = text[start:end]

        key = (start, end, label)
        if key in entidades_vistas:
            continue
        entidades_vistas.add(key)

        entities.append(
            Entity(
                text=match_text,
                entity_type=label,
                start=start,
                end=end,
                score=score,
                source="gliner",
            )
        )
    return entities


def _ollama_detect(text: str, model: str = "llama3.2") -> list[Entity]:
    """Capa 3 (opcional): Detección con Ollama (LLM local)."""
    if not _HTTPX_AVAILABLE:
        return []

    prompt = (
        "Analiza el siguiente texto en español e identifica TODAS las entidades "
        "de información personal (PII).\n"
        "Devuelve ÚNICAMENTE un JSON array con objetos que "
        'tengan: "text", "type", "start", "end".\n'
        "Los tipos válidos son: PERSON, ADDRESS, ORGANIZATION, PHONE, "
        "EMAIL, DNI, NIE, IBAN.\n"
        "No inventes entidades. Solo las que aparezcan literalmente "
        "en el texto.\n"
        "\n"
        "Texto:\n"
        "---\n"
        f"{text}\n"
        "---\n"
        "\n"
        "JSON:"
    )

    try:
        with httpx.Client(timeout=httpx.Timeout(60.0)) as client:
            response = client.post(
                "http://localhost:11434/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
    except Exception:
        return []

    try:
        data = response.json()
        respuesta_texto = data.get("response", "")
    except Exception:
        return []

    return _parse_ollama_json(respuesta_texto, text)


def _parse_ollama_json(respuesta_texto: str, original_text: str) -> list[Entity]:
    """Extrae entidades del JSON devuelto por Ollama."""
    json_match = re.search(r"\[\s*\{.*?\}\s*\]", respuesta_texto, re.DOTALL)
    if not json_match:
        return []

    try:
        entries = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        return []

    entities: list[Entity] = []
    valid_types = {
        "PERSON", "ADDRESS", "ORGANIZATION", "PHONE", "EMAIL", "DNI", "NIE", "IBAN"
    }

    for entry in entries:
        etype = str(entry.get("type", "")).upper()
        if etype not in valid_types:
            continue
        start = int(entry.get("start", -1))
        end = int(entry.get("end", -1))
        if start < 0 or end <= start or end > len(original_text):
            continue

        match_text = original_text[start:end]
        entities.append(
            Entity(
                text=match_text,
                entity_type=etype,
                start=start,
                end=end,
                score=0.7,
                source="ollama",
            )
        )
    return entities


# ---------------------------------------------------------------------------
# Merge de entidades solapadas
# ---------------------------------------------------------------------------


def _merge_entities(entities: list[Entity]) -> list[Entity]:
    """Fusiona entidades solapadas priorizando mayor score y mayor longitud.

    Algoritmo:
    1. Ordena por ``start`` ascendente.
    2. Si dos entidades se solapan, conserva la de mayor ``score``.
       En caso de empate, la de mayor longitud (más texto cubierto).
    """
    if not entities:
        return []

    ordenadas = sorted(entities, key=lambda e: (e.start, -e.score, -(e.end - e.start)))

    finales: list[Entity] = [ordenadas[0]]
    for ent in ordenadas[1:]:
        anterior = finales[-1]
        if ent.start < anterior.end:
            # Hay solapamiento
            if ent.score > anterior.score or (
                ent.score == anterior.score
                and (ent.end - ent.start) > (anterior.end - anterior.start)
            ):
                finales[-1] = ent
        else:
            finales.append(ent)
    return finales


# ---------------------------------------------------------------------------
# Función pública principal
# ---------------------------------------------------------------------------


def detect_pii(text: str, use_ollama: bool = False) -> list[Entity]:
    """Analiza el texto y devuelve una lista de entidades PII detectadas.

    Combina resultados de tres capas de detección:

    1. **Presidio** — reglas deterministas y NER (spaCy).
    2. **GLiNER** — NER zero-shot con modelo local.
    3. **Ollama** (opcional) — LLM local para entidades complejas.

    Las entidades solapadas se fusionan priorizando la de mayor score.
    La lista resultante está ordenada por posición (``start``).

    Args:
        text: Texto a analizar.
        use_ollama: Si ``True``, intenta usar Ollama como capa adicional.
                    Si Ollama no está disponible, se ignora silenciosamente.

    Returns:
        Lista de entidades detectadas, ordenadas por posición de inicio.
    """
    todas: list[Entity] = []

    todas.extend(_presidio_detect(text))
    todas.extend(_gliner_detect(text))

    if use_ollama:
        todas.extend(_ollama_detect(text))

    fusionadas = _merge_entities(todas)
    return sorted(fusionadas, key=lambda e: e.start)


def map_entities_to_coords(
    entities: list[Entity],
    full_text: str,
    words: list[WordBox],
) -> list[Entity]:
    """Enriquece cada entidad con las coordenadas de los cuadros delimitadores.

    Mapea las posiciones de texto (start, end) de cada entidad a las
    coordenadas espaciales de las palabras del PDF. Las coordenadas se
    normalizan a porcentajes (0.0 a 1.0) relativos al tamaño de la página.
    Realiza la alineación página por página de forma aislada y auto-correctora
    para evitar desalineaciones acumulativas globales.

    Args:
        entities: Lista de entidades detectadas por ``detect_pii()``.
        full_text: Texto completo extraído con ``extract_text()``.
        words: Lista de ``WordBox`` extraída con ``extract_words_with_coords()``.

    Returns:
        Las mismas entidades con el campo ``boxes`` rellenado.
    """
    # 1. Separar full_text en las páginas individuales usando el delimitador Form Feed (\x0c)
    page_texts = full_text.split("\x0c")

    # 2. Calcular los offsets globales de inicio de cada página en full_text
    page_offsets: list[int] = []
    current_offset = 0
    for pt in page_texts:
        page_offsets.append(current_offset)
        current_offset += len(pt) + 1  # +1 por el carácter '\x0c'

    # 3. Agrupar las palabras (WordBox) por su número de página
    words_by_page: dict[int, list[WordBox]] = {}
    for wb in words:
        words_by_page.setdefault(wb.page, []).append(wb)

    # 4. Alinear los caracteres de cada página con sus palabras de forma local
    word_positions: list[tuple[int, int, WordBox]] = []

    for p, p_words in words_by_page.items():
        if p >= len(page_texts):
            continue
        p_text = page_texts[p]
        p_offset = page_offsets[p]

        # Verificar si podemos aplicar alineación matemática directa 1:1 (el caso ideal y principal)
        # Esto ocurre cuando el texto de la página se construyó uniendo las palabras con espacios
        reconstructed_p_text = " ".join(wb.text for wb in p_words)
        
        if p_text == reconstructed_p_text or len(p_text) == len(reconstructed_p_text):
            # Alineación matemática directa exacta
            current_char_idx = 0
            for wb in p_words:
                global_start = p_offset + current_char_idx
                global_end = global_start + len(wb.text)
                word_positions.append((global_start, global_end, wb))
                current_char_idx += len(wb.text) + 1  # +1 por el espacio simple
        else:
            # Fallback: búsqueda secuencial tolerante y auto-correctora para texto bruto (fallback de extract_text)
            search_start = 0
            is_first_word = True
            for wb in p_words:
                # Primero buscamos a partir del cursor
                idx = p_text.find(wb.text, search_start)
                if idx == -1:
                    # Si falla, buscamos desde el inicio de la página para corregir discrepancias de orden local
                    idx = p_text.find(wb.text, 0)
                    if idx == -1:
                        continue

                salto = idx - search_start
                # Aceptamos el mapeo si es la primera palabra, si es un salto menor de 200 caracteres,
                # o si es una corrección hacia atrás (idx < search_start)
                if is_first_word or salto <= 200 or idx < search_start:
                    global_start = p_offset + idx
                    global_end = global_start + len(wb.text)
                    word_positions.append((global_start, global_end, wb))
                    search_start = idx + len(wb.text)
                    is_first_word = False

    # 5. Asociar bounding boxes de palabras a cada entidad mediante solapamiento de caracteres
    for entity in entities:
        entity_boxes: list[dict] = []
        for char_start, char_end, wb in word_positions:
            # Comprobar solapamiento de rangos de caracteres
            if char_start < entity.end and char_end > entity.start:
                entity_boxes.append(
                    {
                        "page": wb.page,
                        "x0": round(wb.x0 / wb.page_width, 6),
                        "y0": round(wb.y0 / wb.page_height, 6),
                        "x1": round(wb.x1 / wb.page_width, 6),
                        "y1": round(wb.y1 / wb.page_height, 6),
                    }
                )
        entity.boxes = entity_boxes if entity_boxes else None

    return entities
