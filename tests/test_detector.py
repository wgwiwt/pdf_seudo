from pdf_pseudo.detector import detect_pii


class TestDetectorPresidio:
    def test_detect_valid_dni(self):
        """Un DNI español válido debe detectarse como DNI."""
        entities = detect_pii("El DNI es 12345678Z del paciente.")
        tipos = {e.entity_type for e in entities}
        assert "DNI" in tipos

    def test_reject_invalid_dni(self):
        """Un DNI con letra incorrecta no debe detectarse."""
        entities = detect_pii("El DNI incorrecto 12345678A no es válido.")
        dnis = [e for e in entities if e.entity_type == "DNI"]
        assert len(dnis) == 0

    def test_detect_nie(self):
        """Un NIE español válido debe detectarse."""
        entities = detect_pii("El NIE X1234567L pertence al solicitante.")
        nies = [e for e in entities if e.entity_type == "NIE"]
        assert len(nies) >= 1

    def test_detect_spanish_phone(self):
        """Un teléfono español debe detectarse como PHONE."""
        entities = detect_pii("Llámame al +34 612 345 678 por la mañana.")
        phones = [e for e in entities if e.entity_type == "PHONE"]
        assert len(phones) >= 1
        assert any("612" in e.text for e in phones)

    def test_detect_email(self):
        """Un email debe detectarse como EMAIL."""
        entities = detect_pii("Contacto: juan.garcia@email.com para más info.")
        emails = [e for e in entities if e.entity_type == "EMAIL"]
        assert len(emails) >= 1
        assert any("juan.garcia@email.com" in e.text for e in emails)

    def test_detect_iban(self):
        """Un IBAN español debe detectarse como IBAN."""
        entities = detect_pii("Cuenta: ES91 2100 0418 4502 0005 1332 del titular.")
        ibans = [e for e in entities if e.entity_type == "IBAN"]
        assert len(ibans) >= 1

    def test_reject_random_numbers_as_dni(self):
        """Una secuencia de dígitos que parece DNI pero no valida, no se detecta."""
        entities = detect_pii("Referencia: 99999999X es solo un código.")
        dnis = [e for e in entities if e.entity_type == "DNI"]
        assert len(dnis) == 0


class TestDetectorGliner:
    def test_detect_person_gliner(self):
        """GLiNER debe detectar nombres de persona en español."""
        entities = detect_pii("El paciente Juan García López acudió a consulta.")
        persons = [e for e in entities if e.entity_type == "PERSON"]
        assert len(persons) >= 1
        textos_person = " ".join(e.text for e in persons)
        assert "Juan" in textos_person

    def test_detect_address_gliner(self):
        """GLiNER debe detectar direcciones postales."""
        entities = detect_pii(
            "Vive en Calle Gran Vía 42, 3ºB, 28013 Madrid desde hace años."
        )
        addresses = [e for e in entities if e.entity_type == "ADDRESS"]
        assert len(addresses) >= 1

    def test_detect_organization_gliner(self):
        """GLiNER debe detectar nombres de organizaciones."""
        entities = detect_pii(
            "La empresa Acme Solutions S.L. presentó sus cuentas anuales."
        )
        orgs = [e for e in entities if e.entity_type == "ORGANIZATION"]
        assert len(orgs) >= 1


class TestDetectorGeneral:
    def test_entities_have_required_fields(self):
        """Cada entidad debe tener todos los campos requeridos."""
        text = "Juan Pérez, DNI 12345678Z"
        entities = detect_pii(text)
        for e in entities:
            assert e.text
            assert e.entity_type
            assert 0 <= e.start < e.end <= len(text)
            assert 0.0 <= e.score <= 1.0
            assert e.source in ("presidio", "gliner", "ollama")
            assert text[e.start : e.end] == e.text

    def test_entities_are_sorted_by_start(self):
        """Las entidades deben estar ordenadas por posición de inicio."""
        entities = detect_pii("Juan Pérez, email juan@email.com y DNI 12345678Z.")
        starts = [e.start for e in entities]
        assert starts == sorted(starts)

    def test_no_overlapping_entities(self):
        """No debe haber entidades que se solapen después del merge."""
        entities = detect_pii("El Dr. Juan García López con DNI 12345678Z.")
        for i, e1 in enumerate(entities):
            for e2 in entities[i + 1 :]:
                assert e1.end <= e2.start, (
                    f"Solapamiento: {e1!r} ({e1.start}:{e1.end}) "
                    f"y {e2!r} ({e2.start}:{e2.end})"
                )

    def test_ollama_not_used_by_default(self):
        """Ollama no debe usarse si use_ollama=False."""
        entities = detect_pii("Juan Pérez", use_ollama=False)
        ollama_entities = [e for e in entities if e.source == "ollama"]
        assert len(ollama_entities) == 0

    def test_ollama_gracefully_handled_when_unavailable(self):
        """Si Ollama no está corriendo, no debe lanzar error."""
        entities = detect_pii(
            "Juan Pérez, DNI 12345678Z, juan@email.com", use_ollama=True
        )
        assert len(entities) >= 1

    def test_empty_text(self):
        """Un texto vacío no produce errores."""
        entities = detect_pii("")
        assert entities == []
