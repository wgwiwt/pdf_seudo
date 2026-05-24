import fitz

from pdf_pseudo.pdf_utils import (
    extract_text,
    extract_words_with_coords,
    redact_pdf,
)
from tests.conftest import make_test_pdf


class TestExtractText:
    def test_extract_text_from_generated_pdf(self):
        """Extraer texto de un PDF generado con PyMuPDF."""
        pdf = make_test_pdf("Hola mundo de prueba")
        texto = extract_text(pdf)
        assert "Hola" in texto

    def test_unicode_support(self):
        """Verificar que caracteres especiales españoles se extraen."""
        pdf = make_test_pdf("¿Cuántos años tienes? ¡Qué guay! ñandú.")
        texto = extract_text(pdf)
        assert "ñandú" in texto or "ñand" in texto

    def test_multiline_text(self):
        """Extraer texto multilínea."""
        pdf = make_test_pdf("Línea 1\nLínea 2\nLínea 3")
        texto = extract_text(pdf)
        assert len(texto.strip()) > 0

    def test_empty_pdf(self):
        """Un PDF sin texto produce string vacío."""
        doc = fitz.open()
        doc.new_page()
        pdf = doc.tobytes()
        doc.close()
        texto = extract_text(pdf)
        assert texto.strip() == ""


class TestRedactPdf:
    def test_redact_single_entity(self):
        """Redactar una entidad produce un PDF válido."""
        pdf = make_test_pdf("Texto de prueba para redacción")
        entities = [
            {
                "text": "prueba",
                "entity_type": "TEST",
                "boxes": [{"page": 0, "x0": 0.1, "y0": 0.1, "x1": 0.5, "y1": 0.3}],
            }
        ]
        result = redact_pdf(pdf, entities)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_redact_multiple_entities(self):
        """Redactar varias entidades en la misma página."""
        pdf = make_test_pdf("Texto con múltiples palabras para probar")
        entities = [
            {
                "text": "múltiples",
                "entity_type": "TEST",
                "boxes": [
                    {"page": 0, "x0": 0.1, "y0": 0.1, "x1": 0.3, "y1": 0.2},
                    {"page": 0, "x0": 0.5, "y0": 0.5, "x1": 0.7, "y1": 0.6},
                ],
            }
        ]
        result = redact_pdf(pdf, entities)
        assert len(result) > 0

    def test_redact_entity_without_boxes_no_error(self):
        """Entidad sin boxes no debe causar error."""
        pdf = make_test_pdf("Texto de prueba")
        entities = [{"text": "prueba", "entity_type": "TEST", "boxes": None}]
        result = redact_pdf(pdf, entities)
        assert len(result) > 0

    def test_redact_empty_entities_list(self):
        """Lista vacía de entidades devuelve el PDF intacto."""
        pdf = make_test_pdf("Texto de prueba")
        result = redact_pdf(pdf, [])
        assert len(result) > 0

    def test_redact_invalid_page_skipped(self):
        """Coordenadas en página inexistente se ignoran sin error."""
        pdf = make_test_pdf("Texto de prueba")
        entities = [
            {
                "text": "prueba",
                "entity_type": "TEST",
                "boxes": [{"page": 99, "x0": 0.1, "y0": 0.1, "x1": 0.5, "y1": 0.3}],
            }
        ]
        result = redact_pdf(pdf, entities)
        assert len(result) > 0


class TestExtractWordsWithCoords:
    def test_returns_wordbox_list(self):
        """Extraer palabras con coordenadas de un PDF."""
        pdf = make_test_pdf("Hola mundo de prueba")
        words = extract_words_with_coords(pdf)
        assert isinstance(words, list)
        assert len(words) > 0

    def test_wordbox_has_valid_coords(self):
        """Las coordenadas de WordBox son coherentes."""
        pdf = make_test_pdf("Texto de ejemplo para coordenadas")
        words = extract_words_with_coords(pdf)
        for w in words:
            assert w.x0 >= 0
            assert w.y0 >= 0
            assert w.x1 > w.x0
            assert w.y1 > w.y0
            assert w.x1 <= w.page_width
            assert w.y1 <= w.page_height
            assert w.page >= 0

    def test_page_dimensions_positive(self):
        """Las dimensiones de página son positivas."""
        pdf = make_test_pdf("Test")
        words = extract_words_with_coords(pdf)
        for w in words:
            assert w.page_width > 0
            assert w.page_height > 0
