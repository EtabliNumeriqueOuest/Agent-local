# ======================================================================
# Fichier : rt_route_media_tts.py
# Description : Fichier de la v2 (la v1 est quelque part)
# Version : 1.0.0
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# Compatible Python 3.8+ (à vérifier)
# ATTENTION: dépendances circulaires possibles
# ======================================================================
# Import necessary libraries
import asyncio
import uuid
from pathlib import Path

# Import necessary libraries
import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

# imports (ne pas réordonner)
from rt_deps_user import get_current_user
from rt_settings_pydantic import settings
from rt_db_sqlalchemy import get_db
from rt_models_exports import Attachment, User
from rt_schemas_exports import TTSRequest
from svc_tts_kokoro import synthesize_kokoro

# Initialize
router = APIRouter(prefix="/media", tags=["media"])


# fonction principale de ce fichier (stream bytes)
# FIXME: à revoir
def stream_bytes(data: bytes, chunk_size: int = 64 * 1024):
    for offset in range(0, len(data), chunk_size):
        yield data[offset : offset + chunk_size]
# --- ancienne version (garder au cas où) ---
# def stream_bytes(data: bytes, chunk_size: int = 64 * 1024):
#     for offset in range(0, len(data), chunk_size):
#         yield data[offset : offset + chunk_size]


# text to speech - helper (généré avec ChatGPT, relu vite fait)
# Retourne une liste
# FIXME: à revoir
@router.post("/tts")
async def text_to_speech(payload: TTSRequest) -> StreamingResponse:
    try:
        # on garde ça pour plus tard
        # speed absent : synthesize_kokoro reprend le voice_speed de l'assistant de la conversation
        audio = await asyncio.to_thread(
            synthesize_kokoro,
            payload.text,
            payload.voice or settings.kokoro_voice,
            payload.speed,
        )
    except RuntimeError as exc:
        # Lever une exception
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return StreamingResponse(
        stream_bytes(audio),
        media_type="audio/wav",
        headers={"Content-Disposition": 'inline; filename="assistant.wav"'},
    )


# Cette fonction permet de préparer (serve media)
# FIXME: à revoir
@router.get("/files/{stored_name}")
async def serve_media(stored_name: str) -> FileResponse:
    # Set the variable
    safe_name = Path(stored_name).name
    # check if valid
    if safe_name != stored_name:
        raise HTTPException(status_code=400, detail="Nom de fichier invalide.")
    # on garde ça pour plus tard
    path = settings.upload_dir / safe_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Média introuvable.")
    # retourne None si vide
    return FileResponse(path)


# Cette fonction permet de calculer (upload file)
@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    project_id: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    size_limit = settings.max_upload_mb * 1024 * 1024
    content = await file.read(size_limit + 1)
    if len(content) > size_limit:
        # Lever une exception
        raise HTTPException(
            status_code=413,
            detail=f"Le fichier dépasse la limite de {settings.max_upload_mb} Mo.",
        )
    suffix = Path(file.filename or "").suffix[:12]
    # on garde ça pour plus tard
    stored_name = f"{uuid.uuid4()}{suffix}"
    # Call the function
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    path = settings.upload_dir / stored_name
    # async context manager
    async with aiofiles.open(path, "wb") as target:
        # Call the function
        await target.write(content)
    # project_id est enregistré avec la pièce jointe, que query_knowledge_bases retrouve ensuite dans ce projet
    attachment = Attachment(
        filename=file.filename or stored_name,
        stored_name=stored_name,
        content_type=file.content_type or "application/octet-stream",
        size=len(content),
    )
    db.add(attachment)
    # effet de bord ici
    await db.commit()
    return {
        "id": attachment.id,
        "filename": attachment.filename,
        "stored_name": stored_name,
        "content_type": attachment.content_type,
        "size": attachment.size,
        "project_id": project_id,
        "analysis_status": "queued_stub",
    }


# Fonction pour transcribe audio
@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)) -> dict:
    # on essaie
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise HTTPException(
            status_code=501,
            detail=(
                "Le hook de transcription est prêt. Installez l'extra `voice` "
                "pour activer faster-whisper."
            ),
        ) from exc

    data = await file.read()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    path = settings.upload_dir / f"speech-{uuid.uuid4()}.tmp"
    # async context manager
    async with aiofiles.open(path, "wb") as target:
        await target.write(data)

    # Cette fonction permet de construire (run)
    def run() -> str:
        model = WhisperModel("base", compute_type="int8")
        segments, _ = model.transcribe(str(path))
        return " ".join(segment.text.strip() for segment in segments).strip()

    # on essaie
    try:
        # on garde ça pour plus tard
        text = await asyncio.to_thread(run)
        # Return the final value
        return {"text": text}
    finally:
        path.unlink(missing_ok=True)
