"""Tests para las funciones de coordenadas de la V2."""
from __future__ import annotations

from pdf_pseudo.detector import detect_pii, map_entities_to_coords
from pdf_pseudo.pdf_utils import (
    WordBox,
    extract_text,
    extract_words_with_coords,
)
from tests.conftest import make_test_pdf


class TestExtractWordsWithCoords:
    """Tests para extract_words_with_coords."""

    def test_returns_wordbox_list(self):
        """Verifica que devuelve una lista de WordBox."""
        pdf_bytes = make_test_pdf("Hola mundo de prueba")
        words = extract_words_with_coords(pdf_bytes)
        assert isinstance(words, list)
        assert len(words) > 0
        assert all(isinstance(w, WordBox) for w in words)

    def test_wordbox_has_valid_coords(self):
        """Verifica que las coordenadas son positivas y coherentes."""
        pdf_bytes = make_test_pdf("Texto de ejemplo para coordenadas")
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
        pdf_bytes = make_test_pdf("Primera línea\nSegunda línea\nTercera línea")
        words = extract_words_with_coords(pdf_bytes)
        for i in range(1, len(words)):
            prev = words[i - 1]
            curr = words[i]
            assert (curr.page, curr.y0, curr.x0) >= (prev.page, prev.y0, prev.x0)

    def test_page_dimensions_positive(self):
        """Verifica que las dimensiones de la página son positivas."""
        pdf_bytes = make_test_pdf("Test")
        words = extract_words_with_coords(pdf_bytes)
        for w in words:
            assert w.page_width > 0
            assert w.page_height > 0


class TestMapEntitiesToCoords:
    """Tests para map_entities_to_coords."""

    def test_basic_mapping(self):
        """Verifica que una entidad simple obtiene boxes."""
        texto = "El paciente Juan García tiene DNI 12345678Z."
        pdf_bytes = make_test_pdf(texto)
        full_text = extract_text(pdf_bytes)
        words = extract_words_with_coords(pdf_bytes)
        entities = detect_pii(full_text)

        if entities:
            result = map_entities_to_coords(entities, full_text, words)
            entities_with_boxes = [e for e in result if e.boxes]
            assert len(entities_with_boxes) > 0

    def test_boxes_are_normalized(self):
        """Verifica que las coordenadas están normalizadas entre 0.0 y 1.0."""
        texto = "Juan García López vive en Madrid, DNI 12345678Z."
        pdf_bytes = make_test_pdf(texto)
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
        pdf_bytes = make_test_pdf(texto)
        full_text = extract_text(pdf_bytes)
        words = extract_words_with_coords(pdf_bytes)
        entities = detect_pii(full_text)

        person_entities = [e for e in entities if e.entity_type == "PERSON"]
        if person_entities:
            result = map_entities_to_coords(person_entities, full_text, words)
            for ent in result:
                if ent.boxes and " " in ent.text:
                    assert len(ent.boxes) >= 2, (
                        f"Entidad '{ent.text}' tiene {len(ent.boxes)} boxes, "
                        f"esperaba >= 2"
                    )

    def test_does_not_modify_existing_fields(self):
        """Verifica que map_entities_to_coords no altera los campos originales."""
        texto = "Contacto: juan@email.com, DNI 12345678Z"
        pdf_bytes = make_test_pdf(texto)
        full_text = extract_text(pdf_bytes)
        words = extract_words_with_coords(pdf_bytes)
        entities = detect_pii(full_text)

        if entities:
            originals = [
                (e.text, e.entity_type, e.start, e.end, e.score)
                for e in entities
            ]
            result = map_entities_to_coords(entities, full_text, words)
            for i, ent in enumerate(result):
                assert ent.text == originals[i][0]
                assert ent.entity_type == originals[i][1]
                assert ent.start == originals[i][2]
                assert ent.end == originals[i][3]
                assert ent.score == originals[i][4]

    def test_multipage_mapping(self):
        """Verifica que el mapeo funciona correctamente en múltiples páginas."""
        import fitz

        # Generar un PDF con 3 páginas, cada una con un DNI válido
        doc = fitz.open()
        texts = [
            "Pagina uno: el DNI es 12345678Z.",
            "Pagina dos: otro DNI es 87654321X.",
            "Pagina tres: DNI final es 01234567L."
        ]
        for t in texts:
            page = doc.new_page()
            page.insert_text((50, 100), t, fontsize=12)
        pdf_bytes = doc.tobytes()
        doc.close()

        full_text = extract_text(pdf_bytes)
        words = extract_words_with_coords(pdf_bytes)
        entities = detect_pii(full_text)

        # Deberíamos detectar 3 DNIs
        dnis = [e for e in entities if e.entity_type == "DNI"]
        assert len(dnis) == 3

        result = map_entities_to_coords(dnis, full_text, words)

        # Todas las entidades PII deben tener cajas de coordenadas asignadas en todas las páginas
        for ent in result:
            assert ent.boxes is not None, f"Entidad '{ent.text}' no obtuvo coordenadas visuales."
            assert len(ent.boxes) > 0

    def test_resilience_to_text_discrepancies(self):
        """Verifica que una palabra fantasma u omitida no causa desalineación acumulativa."""
        import fitz

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 100), "El señor Juan García vive en Calle Alcalá 12.", fontsize=12)
        pdf_bytes = doc.tobytes()
        doc.close()

        full_text = extract_text(pdf_bytes)
        words = extract_words_with_coords(pdf_bytes)

        # Introducir una discrepancia artificial en las palabras extraídas
        # Insertando una palabra fantasma que no existe en el texto plano
        words.insert(4, WordBox(
            text="PALABRA_FANTASMA",
            page=0,
            x0=100.0,
            y0=100.0,
            x1=200.0,
            y1=120.0,
            page_width=595.0,
            page_height=842.0
        ))

        entities = detect_pii(full_text)
        person = [e for e in entities if e.entity_type == "PERSON"]
        assert len(person) > 0

        # Mapear
        result = map_entities_to_coords(person, full_text, words)

        # La persona debería obtener coordenadas perfectamente a pesar de la palabra fantasma
        assert person[0].boxes is not None
        assert len(person[0].boxes) > 0

