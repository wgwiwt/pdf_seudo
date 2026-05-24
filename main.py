from __future__ import annotations

import base64
import io
import json
import logging
import uuid
from collections import Counter
from typing import Any, List, Optional

import pdfplumber
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from pdf_pseudo.detector import detect_pii, map_entities_to_coords
from pdf_pseudo.mapper import TokenMapper
from pdf_pseudo.pdf_utils import extract_text, extract_words_with_coords, redact_pdf

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pdf_pseudo_server")

app = FastAPI(
    title="PDF-Pseudo API",
    description="Servidor local para la pseudonimización y restauración bidireccional de PDFs.",
    version="1.0.0"
)

# Permitir CORS (para desarrollo local si fuera necesario)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Modelos Pydantic para flujo interactivo
# ---------------------------------------------------------------------------

class EntityBoxSchema(BaseModel):
    page: int
    x0: float
    y0: float
    x1: float
    y1: float

class EntitySchema(BaseModel):
    id: str
    text: str
    entity_type: str
    start: int
    end: int
    score: float
    source: str
    boxes: Optional[List[EntityBoxSchema]] = None

class AnonymizeRequest(BaseModel):
    pdf_base64: str
    selected_entity_ids: List[str]
    entities: List[EntitySchema]


# ---------------------------------------------------------------------------
# Sistema de Perfiles de Configuración
# ---------------------------------------------------------------------------

class ProfileCategoryToggles(BaseModel):
    PERSON: bool = True
    DNI: bool = True
    NIE: bool = True
    PHONE: bool = True
    EMAIL: bool = True
    ADDRESS: bool = True
    POSTAL_CODE: bool = False
    IBAN: bool = True
    CREDIT_CARD: bool = True
    ORGANIZATION: bool = True
    LOCATION: bool = False
    DATE: bool = False
    URL: bool = False
    IP: bool = False


class ProfileSchema(BaseModel):
    name: str = "Nuevo Perfil"
    category_toggles: ProfileCategoryToggles = ProfileCategoryToggles()
    blacklist: List[str] = []
    whitelist: List[str] = []


class ProfileResponse(ProfileSchema):
    id: str


_profiles_store: dict[str, dict[str, Any]] = {}


def _create_default_profile() -> dict[str, Any]:
    pid = "default"
    profile = {
        "id": pid,
        "name": "Perfil Estándar",
        "category_toggles": ProfileCategoryToggles().model_dump(),
        "blacklist": [],
        "whitelist": [],
    }
    _profiles_store[pid] = profile
    return profile


_create_default_profile()


@app.get("/api/profiles", response_model=List[ProfileResponse])
def list_profiles() -> list[dict[str, Any]]:
    return list(_profiles_store.values())


@app.post("/api/profiles", response_model=ProfileResponse)
def create_profile(profile: ProfileSchema) -> dict[str, Any]:
    pid = str(uuid.uuid4())[:8]
    data = profile.model_dump()
    data["id"] = pid
    _profiles_store[pid] = data
    logger.info("Perfil creado: %s (%s)", profile.name, pid)
    return data


@app.put("/api/profiles/{profile_id}", response_model=ProfileResponse)
def update_profile(profile_id: str, profile: ProfileSchema) -> dict[str, Any]:
    if profile_id not in _profiles_store:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    data = profile.model_dump()
    data["id"] = profile_id
    _profiles_store[profile_id] = data
    return data


@app.delete("/api/profiles/{profile_id}")
def delete_profile(profile_id: str) -> dict[str, str]:
    if profile_id not in _profiles_store:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    if profile_id == "default":
        raise HTTPException(status_code=400, detail="No se puede eliminar el perfil por defecto")
    del _profiles_store[profile_id]
    return {"status": "ok"}


def _get_profile(profile_id: str | None) -> dict[str, Any] | None:
    if profile_id and profile_id in _profiles_store:
        return _profiles_store[profile_id]
    return _profiles_store.get("default")


def _apply_profile_to_entities(
    entities: list, full_text: str, profile: dict[str, Any]
) -> list:
    """Aplica la whitelist y blacklist del perfil a las entidades detectadas."""
    if not profile:
        return entities

    toggles: dict[str, bool] = profile.get("category_toggles", {})
    whitelist_terms: list[str] = profile.get("whitelist", [])
    blacklist_terms: list[str] = profile.get("blacklist", [])

    # 1. Bloquear categorías desactivadas
    enabled_types = {k for k, v in toggles.items() if v}
    entities = [e for e in entities if e.entity_type in enabled_types]

    # 2. Post-procesamiento Whitelist: eliminar entidades cuyo texto coincide
    if whitelist_terms:
        entities = [
            e for e in entities
            if not any(wl.lower() in e.text.lower() for wl in whitelist_terms)
        ]

    # 3. Pre-procesamiento Blacklist: buscar términos en el texto
    if blacklist_terms:
        import re as _re

        from pdf_pseudo.detector import Entity as _Entity
        for term in blacklist_terms:
            for m in _re.finditer(_re.escape(term), full_text, _re.IGNORECASE):
                overlap = any(
                    e.start < m.end() and m.start() < e.end for e in entities
                )
                if not overlap:
                    entities.append(_Entity(
                        text=m.group(),
                        entity_type="CUSTOM",
                        start=m.start(),
                        end=m.end(),
                        score=1.0,
                        source="blacklist",
                    ))

    return entities


@app.post("/api/analyze")
async def analyze_pdf(
    file: UploadFile = File(...),
    use_ollama: bool = Form(False),
    profile_id: str = Form("default"),
) -> dict[str, Any]:
    """
    Fase 1: Analiza un PDF y extrae el texto, palabras con coordenadas y detecta PII.
    Devuelve el PDF original codificado en Base64 y una lista de entidades con sus coordenadas.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="El archivo proporcionado debe ser un documento PDF válido."
        )

    try:
        pdf_bytes = await file.read()
        if not pdf_bytes:
            raise ValueError("El archivo PDF está vacío.")

        logger.info(f"Analizando archivo: {file.filename} ({len(pdf_bytes)} bytes)")

        # 1. Extraer texto plano (para el motor de detección)
        text = extract_text(pdf_bytes)
        if not text.strip():
            raise ValueError(
                "No se pudo extraer texto del PDF. "
                "Asegúrese de que no sea un PDF escaneado sin OCR."
            )

        # 2. Extraer palabras con coordenadas
        words = extract_words_with_coords(pdf_bytes)

        # 3. Detectar entidades PII
        detected_entities = detect_pii(text, use_ollama=use_ollama)

        # 3b. Aplicar perfil de configuración (toggles, blacklist, whitelist)
        profile = _get_profile(profile_id)
        detected_entities = _apply_profile_to_entities(detected_entities, text, profile)

        # 4. Mapear entidades a coordenadas
        entities_with_coords = map_entities_to_coords(detected_entities, text, words)

        # 5. Formatear la respuesta enriquecida
        entities_response = []
        for ent in entities_with_coords:
            ent_id = str(uuid.uuid4())
            boxes = []
            if ent.boxes:
                for b in ent.boxes:
                    boxes.append({
                        "page": b["page"],
                        "x0": b["x0"],
                        "y0": b["y0"],
                        "x1": b["x1"],
                        "y1": b["y1"]
                    })
            entities_response.append({
                "id": ent_id,
                "text": ent.text,
                "entity_type": ent.entity_type,
                "start": ent.start,
                "end": ent.end,
                "score": float(ent.score),
                "source": ent.source,
                "boxes": boxes if boxes else None
            })

        # Formatear la lista completa de palabras con sus coordenadas normalizadas para el frontend
        words_response = []
        for w in words:
            words_response.append({
                "text": w.text,
                "page": w.page,
                "x0": round(w.x0 / w.page_width, 6),
                "y0": round(w.y0 / w.page_height, 6),
                "x1": round(w.x1 / w.page_width, 6),
                "y1": round(w.y1 / w.page_height, 6)
            })

        # 6. Obtener número de páginas y codificar el PDF original en Base64
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages_count = len(pdf.pages)

        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

        return {
            "success": True,
            "pdf_base64": pdf_base64,
            "pages_count": pages_count,
            "entities": entities_response,
            "full_text": text,
            "words": words_response
        }

    except ValueError as e:
        logger.warning(f"Error de validación al analizar: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error inesperado en el proceso de análisis")
        raise HTTPException(
            status_code=500,
            detail=f"Error interno durante el análisis: {str(e)}"
        )


@app.post("/api/anonymize")
async def anonymize_pdf(
    request: AnonymizeRequest
) -> dict[str, Any]:
    """
    Fase 2: Aplica la pseudonimización mediante redacción destructiva.
    Recibe el PDF original en base64, las entidades detectadas y la lista de IDs seleccionados.
    Dibuja cajas negras sobre las coordenadas de las entidades seleccionadas usando PyMuPDF,
    elimina el texto subyacente y preserva el formato original del documento.
    Genera un archivo .key con el mapeo de tokens y el PDF original embebido para restauración.
    """
    try:
        # 1. Decodificar los bytes del PDF original
        pdf_bytes = base64.b64decode(request.pdf_base64)
        if not pdf_bytes:
            raise ValueError("El PDF base64 proporcionado está vacío o es inválido.")

        # 2. Filtrar entidades que el usuario seleccionó para anonimizar
        selected_ids = set(request.selected_entity_ids)
        entities_to_redact = [e for e in request.entities if e.id in selected_ids]

        logger.info(
            "Aplicando redacción destructiva. Total seleccionadas: %d",
            len(entities_to_redact),
        )

        # 3. Preparar entidades con sus coordenadas para redact_pdf
        redact_entities: list[dict[str, Any]] = []
        for e in entities_to_redact:
            if e.boxes:
                redact_entities.append({
                    "text": e.text,
                    "entity_type": e.entity_type,
                    "boxes": [b.model_dump() for b in e.boxes],
                })

        # 4. Aplicar redacción destructiva sobre el PDF original
        redacted_pdf_bytes = redact_pdf(pdf_bytes, redact_entities)

        # 5. Crear TokenMapper con el mapeo de tokens para el .key
        mapper = TokenMapper()
        for entity in entities_to_redact:
            mapper.pseudonymize(entity.text, entity.entity_type)

        mapper_bytes = mapper.to_encrypted_bytes()

        # 6. Embeber el PDF original en el .key para restauración completa
        fernet_key_b64, _ = mapper_bytes.split(b"\n", 1)
        fernet = __import__("cryptography.fernet").fernet.Fernet(
            __import__("base64").urlsafe_b64decode(fernet_key_b64)
        )
        composite = {
            "v": 2,
            "mapper_data_b64": mapper_bytes.split(b"\n", 1)[1].decode("utf-8"),
            "original_pdf_base64": request.pdf_base64,
        }
        composite_json = json.dumps(composite, ensure_ascii=False).encode("utf-8")
        composite_encrypted = fernet.encrypt(composite_json)
        composite_encrypted_b64 = base64.urlsafe_b64encode(composite_encrypted)
        key_bytes = fernet_key_b64 + b"\n" + composite_encrypted_b64

        # 7. Codificar los resultados a Base64
        pdf_base64 = base64.b64encode(redacted_pdf_bytes).decode("utf-8")
        key_base64 = base64.b64encode(key_bytes).decode("utf-8")

        entity_counts = dict(Counter([e.entity_type for e in entities_to_redact]))

        return {
            "success": True,
            "pdf_base64": pdf_base64,
            "key_base64": key_base64,
            "stats": {
                "total_detected": len(request.entities),
                "total_anonymized": len(entities_to_redact),
                "entities_by_type": entity_counts,
            },
        }

    except ValueError as e:
        logger.warning("Error de validación al anonimizar: %s", str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error inesperado en el proceso de anonimización")
        raise HTTPException(
            status_code=500,
            detail=f"Error interno durante la anonimización: {str(e)}"
        )

@app.post("/api/deanonymize")
async def deanonymize_pdf(
    file: UploadFile = File(...),
    key_file: UploadFile = File(...)
) -> dict[str, Any]:
    """
    Endpoint para restaurar un PDF previamente anonimizado.
    Recibe el PDF redactado y el archivo .key que contiene el PDF original
    embebido y cifrado. Extrae el original y lo devuelve.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="El archivo proporcionado debe ser un documento PDF."
        )
    if not key_file.filename.lower().endswith(".key"):
        raise HTTPException(
            status_code=400,
            detail="El archivo de clave debe tener extensión '.key'."
        )

    try:
        await file.read()  # PDF redactado recibido pero no usado; restauramos desde el .key
        key_bytes = await key_file.read()

        if not key_bytes:
            raise ValueError("El archivo de clave (.key) está vacío.")

        logger.info("Procesando restauración para: %s", file.filename)

        # Intentar formato V2 (PDF original embebido)
        original_pdf_base64 = _extract_original_pdf_from_key(key_bytes)

        if original_pdf_base64:
            original_pdf_bytes = base64.b64decode(original_pdf_base64)
            pdf_base64 = base64.b64encode(original_pdf_bytes).decode("utf-8")
        else:
            raise ValueError(
                "La clave proporcionada tiene un formato antiguo (V1) no compatible "
                "con esta versión. Genere un nuevo archivo .key con la versión actual."
            )

        original_name = file.filename.replace("_anon", "").replace("-anon", "")
        if original_name.endswith(".pdf"):
            restored_filename = original_name[:-4] + "_restaurado.pdf"
        else:
            restored_filename = "documento_restaurado.pdf"

        return {
            "success": True,
            "pdf_base64": pdf_base64,
            "filename": restored_filename,
        }

    except ValueError as e:
        logger.warning("Error de validación al desanonimizar: %s", str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error inesperado en el proceso de restauración")
        raise HTTPException(
            status_code=500,
            detail=f"Error interno durante la restauración: {str(e)}"
        )


def _extract_original_pdf_from_key(key_bytes: bytes) -> str | None:
    """Extrae el PDF original en base64 de un archivo .key V2.

    El formato V2 es:
    - Línea 1: clave Fernet en base64
    - Línea 2: JSON cifrado con {"v": 2, "mapper_data_b64": ..., "original_pdf_base64": ...}

    Returns:
        El PDF original en base64, o None si el formato no es V2.
    """
    from cryptography.fernet import Fernet as _Fernet

    try:
        key_b64, data_b64 = key_bytes.split(b"\n", 1)
        fernet = _Fernet(base64.urlsafe_b64decode(key_b64))
        encrypted = base64.urlsafe_b64decode(data_b64)
        decrypted = fernet.decrypt(encrypted)
        payload = json.loads(decrypted.decode("utf-8"))

        if isinstance(payload, dict) and payload.get("v") == 2:
            return payload.get("original_pdf_base64")
        return None
    except Exception:
        return None

# Servir frontend estático
# NOTA: Montamos los archivos estáticos en /static para que cargue CSS, JS y otros assets.
app.mount("/static", StaticFiles(directory="static"), name="static")

# Ruta principal que sirve el index.html
@app.get("/", response_class=HTMLResponse)
async def get_index() -> HTMLResponse:
    """
    Ruta raíz que lee y sirve el archivo index.html del frontend estático.
    """
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Frontend no encontrado. Asegúrese de que static/index.html exista."
        )
