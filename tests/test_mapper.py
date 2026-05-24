from pdf_pseudo.mapper import TokenMapper


class TestTokenMapper:
    def test_pseudonymize_consistency(self):
        """Mismo input → mismo token."""
        mapper = TokenMapper()
        t1 = mapper.pseudonymize("Juan Pérez", "PERSON")
        t2 = mapper.pseudonymize("Juan Pérez", "PERSON")
        assert t1 == t2
        assert t1 == "<<PERSON_1>>"

    def test_pseudonymize_sequential(self):
        """Distintos inputs → tokens incrementales."""
        mapper = TokenMapper()
        t1 = mapper.pseudonymize("Juan Pérez", "PERSON")
        t2 = mapper.pseudonymize("María López", "PERSON")
        t3 = mapper.pseudonymize("Carlos Ruiz", "PERSON")
        assert t1 == "<<PERSON_1>>"
        assert t2 == "<<PERSON_2>>"
        assert t3 == "<<PERSON_3>>"

    def test_pseudonymize_different_types(self):
        """Entidades de distinto tipo tienen contadores independientes."""
        mapper = TokenMapper()
        t1 = mapper.pseudonymize("Juan Pérez", "PERSON")
        t2 = mapper.pseudonymize("12345678Z", "DNI")
        assert t1 == "<<PERSON_1>>"
        assert t2 == "<<DNI_1>>"

    def test_depseudonymize_roundtrip(self):
        """Pseudonimizar varios valores, construir texto con tokens, desanonimizar."""
        mapper = TokenMapper()
        mapper.pseudonymize("Juan García", "PERSON")
        mapper.pseudonymize("12345678Z", "DNI")
        mapper.pseudonymize("juan@email.com", "EMAIL")

        texto_con_tokens = "<<PERSON_1>>, DNI <<DNI_1>>, email <<EMAIL_1>>"
        restaurado = mapper.depseudonymize(texto_con_tokens)
        assert restaurado == "Juan García, DNI 12345678Z, email juan@email.com"

    def test_depseudonymize_unknown_token_left_intact(self):
        """Tokens no registrados quedan intactos."""
        mapper = TokenMapper()
        mapper.pseudonymize("Juan Pérez", "PERSON")
        texto = "<<PERSON_1>> y <<UNKNOWN_42>>"
        restaurado = mapper.depseudonymize(texto)
        assert restaurado == "Juan Pérez y <<UNKNOWN_42>>"

    def test_encrypt_decrypt_roundtrip(self):
        """Serializar a bytes y deserializar preserva el mapeo."""
        mapper = TokenMapper()
        mapper.pseudonymize("Juan Pérez", "PERSON")
        mapper.pseudonymize("12345678Z", "DNI")
        mapper.pseudonymize("juan@email.com", "EMAIL")

        encrypted = mapper.to_encrypted_bytes()
        mapper2 = TokenMapper.from_encrypted_bytes(encrypted)

        assert mapper2.pseudonymize("Juan Pérez", "PERSON") == "<<PERSON_1>>"
        assert mapper2.pseudonymize("12345678Z", "DNI") == "<<DNI_1>>"
        resto = mapper2.depseudonymize("<<PERSON_1>>, <<DNI_1>>, <<EMAIL_1>>")
        assert resto == "Juan Pérez, 12345678Z, juan@email.com"

    def test_encrypt_decrypt_preserves_counters(self):
        """Al deserializar, los contadores se reconstruyen correctamente
        y los nuevos elementos continúan desde el número siguiente."""
        mapper = TokenMapper()
        mapper.pseudonymize("Ana Ruiz", "PERSON")
        mapper.pseudonymize("Luis Díaz", "PERSON")

        encrypted = mapper.to_encrypted_bytes()
        mapper2 = TokenMapper.from_encrypted_bytes(encrypted)

        # Nuevo elemento debe usar PERSON_3
        t = mapper2.pseudonymize("Pedro Sol", "PERSON")
        assert t == "<<PERSON_3>>"

    def test_entity_type_is_case_insensitive(self):
        """El tipo de entidad se normaliza a mayúsculas."""
        mapper = TokenMapper()
        t1 = mapper.pseudonymize("Juan Pérez", "person")
        t2 = mapper.pseudonymize("Juan Pérez", "PERSON")
        assert t1 == t2
        assert t1 == "<<PERSON_1>>"
