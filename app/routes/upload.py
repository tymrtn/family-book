"""
Chunked / resumable upload endpoints.

Protocol (simplified tus-like):
1. POST /api/upload/init → {upload_id, chunk_size} — reserve an upload slot
2. PATCH /api/upload/{upload_id} — append chunk (Content-Range header)
3. POST /api/upload/{upload_id}/complete — finalize, process metadata, create Media record

For small files (<10 MB), use the existing single-shot POST /api/media.

Batch upload:
- POST /api/upload/batch → upload multiple files, returns progress-trackable batch_id
- GET /api/upload/batch/{batch_id} → poll progress

Client-side: Service Worker + Background Sync for resilience.
"""

import os
import secrets
import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, Header, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_auth
from app.config import get_settings
from app.database import get_db
from app.models.media import Media
from app.models.person import Person
from app.services.media_service import (
    ALLOWED_MIME_TYPES,
    save_media_file,
    compute_sha256,
    check_duplicate,
)

router = APIRouter(prefix="/api/upload", tags=["upload"])

# In-memory upload state (production: use Redis or DB table)
_active_uploads: dict[str, dict] = {}

DEFAULT_CHUNK_SIZE = 2 * 1024 * 1024  # 2 MB chunks
MAX_UPLOAD_SIZE = 500 * 1024 * 1024   # 500 MB


# ─── Schemas ──────────────────────────────────────────────────────

class UploadInitRequest(BaseModel):
    filename: str = Field(max_length=300)
    mime_type: str = Field(max_length=50)
    file_size: int  # total bytes
    person_id: str
    caption: str | None = None
    trip_id: str | None = None  # auto-link to trip


class UploadInitResponse(BaseModel):
    upload_id: str
    chunk_size: int
    total_chunks: int


class UploadCompleteResponse(BaseModel):
    media_id: str
    file_hash: str
    is_duplicate: bool
    width: int | None
    height: int | None
    taken_at: str | None
    location_lat: float | None
    location_lng: float | None
    has_exif: bool | None


class BatchUploadStatus(BaseModel):
    batch_id: str
    total: int
    completed: int
    failed: int
    media_ids: list[str]
    errors: list[str]


# ─── Init ─────────────────────────────────────────────────────────

@router.post("/init", response_model=UploadInitResponse)
async def init_upload(
    body: UploadInitRequest,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Initialize a chunked upload. Returns upload_id for subsequent chunks."""
    if body.mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported MIME type: {body.mime_type}")

    if body.file_size > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large: max {MAX_UPLOAD_SIZE} bytes")

    if body.file_size <= 0:
        raise HTTPException(status_code=400, detail="Invalid file size")

    # Verify person exists
    result = await db.execute(select(Person).where(Person.id == body.person_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Person not found")

    upload_id = secrets.token_hex(16)
    total_chunks = (body.file_size + DEFAULT_CHUNK_SIZE - 1) // DEFAULT_CHUNK_SIZE

    settings = get_settings()
    upload_dir = os.path.join(settings.DATA_DIR, "media", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    _active_uploads[upload_id] = {
        "filename": body.filename,
        "mime_type": body.mime_type,
        "file_size": body.file_size,
        "person_id": body.person_id,
        "uploaded_by": current_user.id,
        "caption": body.caption,
        "trip_id": body.trip_id,
        "bytes_received": 0,
        "chunks_received": 0,
        "total_chunks": total_chunks,
        "temp_path": os.path.join(upload_dir, f"{upload_id}.part"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    return UploadInitResponse(
        upload_id=upload_id,
        chunk_size=DEFAULT_CHUNK_SIZE,
        total_chunks=total_chunks,
    )


# ─── Chunk ────────────────────────────────────────────────────────

@router.patch("/{upload_id}")
async def upload_chunk(
    upload_id: str,
    request: Request,
    current_user: Person = Depends(require_auth),
):
    """
    Append a chunk to an in-progress upload.
    Send raw bytes as the request body.
    Use Content-Range header: bytes START-END/TOTAL
    """
    if upload_id not in _active_uploads:
        raise HTTPException(status_code=404, detail="Upload not found or expired")

    state = _active_uploads[upload_id]

    if state["uploaded_by"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not your upload")

    chunk_data = await request.body()
    if not chunk_data:
        raise HTTPException(status_code=400, detail="Empty chunk")

    # Append to temp file
    with open(state["temp_path"], "ab") as f:
        f.write(chunk_data)

    state["bytes_received"] += len(chunk_data)
    state["chunks_received"] += 1

    return {
        "upload_id": upload_id,
        "bytes_received": state["bytes_received"],
        "chunks_received": state["chunks_received"],
        "total_chunks": state["total_chunks"],
        "complete": state["bytes_received"] >= state["file_size"],
    }


# ─── Complete ─────────────────────────────────────────────────────

@router.post("/{upload_id}/complete")
async def complete_upload(
    upload_id: str,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Finalize a chunked upload: process metadata, create Media record."""
    if upload_id not in _active_uploads:
        raise HTTPException(status_code=404, detail="Upload not found or expired")

    state = _active_uploads[upload_id]

    if state["uploaded_by"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not your upload")

    temp_path = state["temp_path"]
    if not os.path.isfile(temp_path):
        raise HTTPException(status_code=500, detail="Upload file not found on disk")

    # Read the complete file
    with open(temp_path, "rb") as f:
        file_data = f.read()

    # Clean up temp file
    try:
        os.unlink(temp_path)
    except OSError:
        pass

    # Process through save_media_file (dedup, metadata, resize)
    try:
        media, is_duplicate = await save_media_file(
            db=db,
            file_data=file_data,
            filename=state["filename"],
            mime_type=state["mime_type"],
            person_id=state["person_id"],
            uploaded_by=state["uploaded_by"],
            caption=state["caption"],
        )
    except ValueError as e:
        del _active_uploads[upload_id]
        raise HTTPException(status_code=400, detail=str(e))

    # Auto-link to trip if trip_id provided
    if state.get("trip_id") and not is_duplicate:
        from app.models.moments import Moment
        from app.models.trips import TripMoment

        # Create a moment for this media
        moment = Moment(
            person_id=state["person_id"],
            kind="photo" if media.media_type in ("image", "gif") else "video",
            body=state.get("caption"),
            occurred_at=media.taken_at or datetime.now(timezone.utc),
            posted_by=current_user.id,
        )
        moment.media_ids = [media.id]
        db.add(moment)
        await db.flush()

        # Link moment to trip
        tm = TripMoment(
            trip_id=state["trip_id"],
            moment_id=moment.id,
            added_by=current_user.id,
        )
        db.add(tm)
        await db.flush()

    # Clean up upload state
    del _active_uploads[upload_id]

    return UploadCompleteResponse(
        media_id=media.id,
        file_hash=media.file_hash or "",
        is_duplicate=is_duplicate,
        width=media.width,
        height=media.height,
        taken_at=media.taken_at.isoformat() if media.taken_at else None,
        location_lat=media.location_lat,
        location_lng=media.location_lng,
        has_exif=media.has_exif,
    )


# ─── Resume Info ──────────────────────────────────────────────────

@router.head("/{upload_id}")
async def upload_status(
    upload_id: str,
    current_user: Person = Depends(require_auth),
):
    """Check upload progress for resumption."""
    if upload_id not in _active_uploads:
        raise HTTPException(status_code=404, detail="Upload not found or expired")

    state = _active_uploads[upload_id]
    if state["uploaded_by"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not your upload")

    from fastapi.responses import Response
    return Response(
        status_code=200,
        headers={
            "Upload-Offset": str(state["bytes_received"]),
            "Upload-Length": str(state["file_size"]),
        },
    )


# ─── Batch Upload (small files, single request) ──────────────────

_batch_state: dict[str, dict] = {}


@router.post("/batch")
async def batch_upload(
    request: Request,
    person_id: str = Form(...),
    trip_id: str | None = Form(None),
    caption: str | None = Form(None),
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload multiple files in a single multipart request.
    For small batches (< 10 files, < 10MB each). Use chunked for larger files.
    """
    form = await request.form()
    files = [v for k, v in form.multi_items() if k == "files" and hasattr(v, "read")]

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Max 50 files per batch")

    # Verify person
    result = await db.execute(select(Person).where(Person.id == person_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Person not found")

    media_ids = []
    errors = []

    for f in files:
        try:
            file_data = await f.read()
            media, is_dup = await save_media_file(
                db=db,
                file_data=file_data,
                filename=f.filename or "upload",
                mime_type=f.content_type or "application/octet-stream",
                person_id=person_id,
                uploaded_by=current_user.id,
                caption=caption,
            )
            media_ids.append(media.id)

            # Auto-link to trip
            if trip_id and not is_dup:
                from app.models.moments import Moment
                from app.models.trips import TripMoment

                moment = Moment(
                    person_id=person_id,
                    kind="photo" if media.media_type in ("image", "gif") else "video",
                    body=caption,
                    occurred_at=media.taken_at or datetime.now(timezone.utc),
                    posted_by=current_user.id,
                )
                moment.media_ids = [media.id]
                db.add(moment)
                await db.flush()

                tm = TripMoment(
                    trip_id=trip_id,
                    moment_id=moment.id,
                    added_by=current_user.id,
                )
                db.add(tm)
                await db.flush()

        except (ValueError, Exception) as e:
            errors.append(f"{f.filename}: {str(e)}")

    return {
        "total": len(files),
        "completed": len(media_ids),
        "failed": len(errors),
        "media_ids": media_ids,
        "errors": errors,
    }
