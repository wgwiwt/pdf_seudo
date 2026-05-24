import fitz
import pytest


def make_test_pdf(text: str) -> bytes:
    """Genera un PDF de prueba con PyMuPDF que contiene el texto dado."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 100), text, fontsize=12)
    result = doc.tobytes()
    doc.close()
    return result


TEXTO_EJEMPLO_ES = (
    "Informe de evaluación del paciente Juan García López, con DNI 12345678Z, "
    "domiciliado en Calle Gran Vía 42, 3ºB, 28013 Madrid. "
    "Teléfono de contacto: +34 612 345 678. Email: juan.garcia@email.com. "
    "La empresa Acme Solutions S.L., con CIF B12345678, realizó el pago "
    "mediante transferencia a la cuenta IBAN ES91 2100 0418 4502 0005 1332."
)


@pytest.fixture
def texto_ejemplo() -> str:
    """Devuelve un texto de ejemplo en español con múltiples tipos de PII."""
    return TEXTO_EJEMPLO_ES
