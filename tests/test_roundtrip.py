"""Tests de integración: pipeline completo de redacción + restauración."""
from __future__ import annotations

import base64
import json

from pdf_pseudo.detector import detect_pii
from pdf_pseudo.mapper import TokenMapper
from pdf_pseudo.pdf_utils import extract_text, redact_pdf
from tests.conftest import TEXTO_EJEMPLO_ES, make_test_pdf


class TestFullPipelineRoundtrip:
    def test_redact_and_restore_via_key(self):
        """Pipeline V2: generar PDF → detectar entidades → redactar → guardar
        en .key con PDF original → extraer PDF original."""
        texto = TEXTO_EJEMPLO_ES
        pdf_bytes = make_test_pdf(texto)

        # 1. Detectar entidades
        full_text = extract_text(pdf_bytes)
        entities = detect_pii(full_text)

        if not entities:
            # Sin entidades detectadas, no hay nada que redactar
            return

        # 2. Preparar entidades con coordenadas (usar coordenadas inventadas
        #    para la prueba — en el flujo real vienen del analyze)
        redact_entities = []
        for e in entities:
            redact_entities.append({
                "text": e.text,
                "entity_type": e.entity_type,
                "boxes": [{"page": 0, "x0": 0.1, "y0": 0.3, "x1": 0.9, "y1": 0.6}],
            })

        # 3. Redactar
        redacted_bytes = redact_pdf(pdf_bytes, redact_entities)
        assert len(redacted_bytes) > 0
        assert redacted_bytes != pdf_bytes  # El PDF fue modificado

        # 4. Crear TokenMapper y embeber PDF original en .key (como hace main.py)
        mapper = TokenMapper()
        for entity in entities:
            mapper.pseudonymize(entity.text, entity.entity_type)

        mapper_bytes = mapper.to_encrypted_bytes()
        fernet_key_b64, _ = mapper_bytes.split(b"\n", 1)

        from cryptography.fernet import Fernet as _Fernet

        fernet = _Fernet(base64.urlsafe_b64decode(fernet_key_b64))
        original_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

        composite = {
            "v": 2,
            "mapper_data_b64": mapper_bytes.split(b"\n", 1)[1].decode("utf-8"),
            "original_pdf_base64": original_b64,
        }
        composite_json = json.dumps(composite, ensure_ascii=False).encode("utf-8")
        composite_encrypted = fernet.encrypt(composite_json)
        composite_encrypted_b64 = base64.urlsafe_b64encode(composite_encrypted)
        key_bytes = fernet_key_b64 + b"\n" + composite_encrypted_b64

        # 5. Extraer PDF original del .key (como hace main.py)
        key_b64, data_b64 = key_bytes.split(b"\n", 1)
        fernet2 = _Fernet(base64.urlsafe_b64decode(key_b64))
        encrypted2 = base64.urlsafe_b64decode(data_b64)
        decrypted2 = fernet2.decrypt(encrypted2)
        payload = json.loads(decrypted2.decode("utf-8"))

        assert payload["v"] == 2
        extracted_original_b64 = payload["original_pdf_base64"]
        extracted_pdf = base64.b64decode(extracted_original_b64)

        # 6. El PDF extraído es idéntico al original
        assert extracted_pdf == pdf_bytes

    def test_roundtrip_preserves_mapping(self):
        """El TokenMapper sobrevive al roundtrip de cifrado dentro del .key V2."""
        mapper = TokenMapper()
        mapper.pseudonymize("Juan Pérez", "PERSON")
        mapper.pseudonymize("12345678Z", "DNI")

        mapper_bytes = mapper.to_encrypted_bytes()
        fernet_key_b64, data_b64 = mapper_bytes.split(b"\n", 1)

        from cryptography.fernet import Fernet as _Fernet

        fernet = _Fernet(base64.urlsafe_b64decode(fernet_key_b64))

        composite = {
            "v": 2,
            "mapper_data_b64": data_b64.decode("utf-8"),
            "original_pdf_base64": "dummy",
        }
        composite_json = json.dumps(composite, ensure_ascii=False).encode("utf-8")
        composite_encrypted_b64 = base64.urlsafe_b64encode(
            fernet.encrypt(composite_json)
        )
        key_bytes = fernet_key_b64 + b"\n" + composite_encrypted_b64

        # Extraer
        kb, db = key_bytes.split(b"\n", 1)
        f2 = _Fernet(base64.urlsafe_b64decode(kb))
        dec = f2.decrypt(base64.urlsafe_b64decode(db))
        pl = json.loads(dec.decode("utf-8"))

        # Reconstruir mapper
        mapper_bytes_v1 = kb + b"\n" + pl["mapper_data_b64"].encode("utf-8")
        mapper2 = TokenMapper.from_encrypted_bytes(mapper_bytes_v1)
        assert mapper2.pseudonymize("Juan Pérez", "PERSON") == "<<PERSON_1>>"
        assert mapper2.pseudonymize("12345678Z", "DNI") == "<<DNI_1>>"

    def test_redact_empty_entities_produces_valid_pdf(self):
        """Redactar sin entidades devuelve un PDF válido."""
        pdf = make_test_pdf("Documento sin datos sensibles.")
        result = redact_pdf(pdf, [])
        assert len(result) > 0
