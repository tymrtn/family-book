"""
Trip Albums API — CRUD, invite flow, timeline, map, moment linking.
"""

import os
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_auth, get_current_user
from app.database import get_db
from app.models.media import Media
from app.models.moments import Moment
from app.models.person import Person
from app.models.trips import Trip, TripParticipant, TripMoment

router = APIRouter(prefix="/api/trips", tags=["trips"])


# ─── Schemas ──────────────────────────────────────────────────────

class TripCreate(BaseModel):
    name: str = Field(max_length=300)
    description: str | None = Field(None, max_length=5000)
    start_date: str | None = Field(None, max_length=10)
    end_date: str | None = Field(None, max_length=10)
    visibility: str = "members"


class TripUpdate(BaseModel):
    name: str | None = Field(None, max_length=300)
    description: str | None = Field(None, max_length=5000)
    start_date: str | None = Field(None, max_length=10)
    end_date: str | None = Field(None, max_length=10)
    visibility: str | None = None
    cover_media_id: str | None = None


class TripResponse(BaseModel):
    id: str
    name: str
    description: str | None
    start_date: str | None
    end_date: str | None
    cover_media_id: str | None
    cover_url: str | None
    created_by: str
    creator_name: str | None
    visibility: str
    invite_token: str | None
    participant_count: int
    moment_count: int
    created_at: str
    updated_at: str


class ParticipantResponse(BaseModel):
    id: str
    person_id: str
    person_name: str
    photo_url: str | None
    role: str
    joined_at: str


class MomentAddRequest(BaseModel):
    moment_ids: list[str] = []


class TimelineMomentCard(BaseModel):
    id: str
    kind: str
    title: str | None
    body: str | None
    media: list[dict]
    poster_name: str | None
    poster_photo: str | None
    occurred_at: str | None
    created_at: str | None


# ─── Helpers ──────────────────────────────────────────────────────

async def _get_trip_or_404(db: AsyncSession, trip_id: str) -> Trip:
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = result.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


async def _is_participant(db: AsyncSession, trip_id: str, person_id: str) -> bool:
    result = await db.execute(
        select(TripParticipant).where(
            TripParticipant.trip_id == trip_id,
            TripParticipant.person_id == person_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def _get_participant_role(db: AsyncSession, trip_id: str, person_id: str) -> str | None:
    result = await db.execute(
        select(TripParticipant.role).where(
            TripParticipant.trip_id == trip_id,
            TripParticipant.person_id == person_id,
        )
    )
    return result.scalar_one_or_none()


async def _require_trip_access(
    db: AsyncSession, trip: Trip, user: Person
) -> None:
    """Raise 403 if user can't view this trip."""
    if user.is_admin:
        return
    if trip.visibility == "hidden":
        raise HTTPException(status_code=403, detail="Trip is hidden")
    if trip.visibility == "admins" and not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin-only trip")
    # members visibility — anyone authenticated can view


async def _require_trip_edit(
    db: AsyncSession, trip: Trip, user: Person
) -> None:
    """Raise 403 if user can't edit this trip."""
    if user.is_admin:
        return
    role = await _get_participant_role(db, trip.id, user.id)
    if role != "organizer":
        raise HTTPException(status_code=403, detail="Only organizers can edit this trip")


async def _build_trip_response(db: AsyncSession, trip: Trip) -> dict:
    # Creator name
    creator_name = None
    result = await db.execute(select(Person).where(Person.id == trip.created_by))
    creator = result.scalar_one_or_none()
    if creator:
        creator_name = creator.display_name

    # Cover URL
    cover_url = None
    if trip.cover_media_id:
        cover_url = f"/api/media/{trip.cover_media_id}/file"

    # Counts
    result = await db.execute(
        select(func.count(TripParticipant.id)).where(TripParticipant.trip_id == trip.id)
    )
    participant_count = result.scalar() or 0

    result = await db.execute(
        select(func.count(TripMoment.id)).where(TripMoment.trip_id == trip.id)
    )
    moment_count = result.scalar() or 0

    return {
        "id": trip.id,
        "name": trip.name,
        "description": trip.description,
        "start_date": trip.start_date,
        "end_date": trip.end_date,
        "cover_media_id": trip.cover_media_id,
        "cover_url": cover_url,
        "created_by": trip.created_by,
        "creator_name": creator_name,
        "visibility": trip.visibility,
        "invite_token": trip.invite_token,
        "participant_count": participant_count,
        "moment_count": moment_count,
        "created_at": trip.created_at.isoformat() if trip.created_at else None,
        "updated_at": trip.updated_at.isoformat() if trip.updated_at else None,
    }


# ─── CRUD ─────────────────────────────────────────────────────────

@router.get("")
async def list_trips(
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """List trips the current user participates in, plus public trips."""
    if current_user.is_admin:
        # Admins see everything
        query = select(Trip).order_by(Trip.start_date.desc().nullslast(), Trip.created_at.desc())
    else:
        # Members see trips they're in + members-visible trips
        participant_trip_ids = select(TripParticipant.trip_id).where(
            TripParticipant.person_id == current_user.id
        )
        query = select(Trip).where(
            or_(
                Trip.id.in_(participant_trip_ids),
                Trip.visibility == "members",
            )
        ).order_by(Trip.start_date.desc().nullslast(), Trip.created_at.desc())

    result = await db.execute(query)
    trips = result.scalars().all()

    responses = []
    for trip in trips:
        responses.append(await _build_trip_response(db, trip))

    return responses


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_trip(
    body: TripCreate,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Create a new trip. Creator becomes organizer."""
    trip = Trip(
        name=body.name,
        description=body.description,
        start_date=body.start_date,
        end_date=body.end_date,
        created_by=current_user.id,
        visibility=body.visibility,
        invite_token=secrets.token_hex(32),
    )
    db.add(trip)
    await db.flush()

    # Add creator as organizer
    participant = TripParticipant(
        trip_id=trip.id,
        person_id=current_user.id,
        role="organizer",
    )
    db.add(participant)
    await db.flush()

    return await _build_trip_response(db, trip)


@router.get("/{trip_id}")
async def get_trip(
    trip_id: str,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Get trip details."""
    trip = await _get_trip_or_404(db, trip_id)
    await _require_trip_access(db, trip, current_user)
    return await _build_trip_response(db, trip)


@router.put("/{trip_id}")
async def update_trip(
    trip_id: str,
    body: TripUpdate,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Update trip details. Organizer or admin only."""
    trip = await _get_trip_or_404(db, trip_id)
    await _require_trip_edit(db, trip, current_user)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(trip, field, value)

    await db.flush()
    return await _build_trip_response(db, trip)


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trip(
    trip_id: str,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Delete a trip. Organizer or admin only."""
    trip = await _get_trip_or_404(db, trip_id)
    await _require_trip_edit(db, trip, current_user)
    await db.delete(trip)
    await db.flush()


# ─── Participants ─────────────────────────────────────────────────

@router.get("/{trip_id}/participants")
async def list_participants(
    trip_id: str,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """List trip participants."""
    trip = await _get_trip_or_404(db, trip_id)
    await _require_trip_access(db, trip, current_user)

    result = await db.execute(
        select(TripParticipant).where(TripParticipant.trip_id == trip_id)
        .order_by(TripParticipant.joined_at)
    )
    participants = result.scalars().all()

    responses = []
    for p in participants:
        person_result = await db.execute(select(Person).where(Person.id == p.person_id))
        person = person_result.scalar_one_or_none()
        responses.append({
            "id": p.id,
            "person_id": p.person_id,
            "person_name": person.display_name if person else "Unknown",
            "photo_url": person.photo_url if person else None,
            "role": p.role,
            "joined_at": p.joined_at.isoformat() if p.joined_at else None,
        })

    return responses


# ─── Invite Flow ──────────────────────────────────────────────────

@router.post("/{trip_id}/invite")
async def generate_invite(
    trip_id: str,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Generate or refresh an invite link for a trip."""
    trip = await _get_trip_or_404(db, trip_id)
    await _require_trip_edit(db, trip, current_user)

    trip.invite_token = secrets.token_hex(32)
    await db.flush()

    return {
        "invite_token": trip.invite_token,
        "invite_url": f"/trips/join/{trip.invite_token}",
    }


@router.get("/join/{invite_token}")
async def join_trip(
    invite_token: str,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Join a trip via invite token. Authenticated users become contributors."""
    result = await db.execute(
        select(Trip).where(Trip.invite_token == invite_token)
    )
    trip = result.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="Invalid invite link")

    # Check if already a participant
    if await _is_participant(db, trip.id, current_user.id):
        return {
            "message": "Already a participant",
            "trip_id": trip.id,
            "trip_name": trip.name,
        }

    participant = TripParticipant(
        trip_id=trip.id,
        person_id=current_user.id,
        role="contributor",
    )
    db.add(participant)
    await db.flush()

    return {
        "message": "Joined trip successfully",
        "trip_id": trip.id,
        "trip_name": trip.name,
    }


# ─── Moments ─────────────────────────────────────────────────────

@router.post("/{trip_id}/moments")
async def add_moments_to_trip(
    trip_id: str,
    body: MomentAddRequest,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Add existing moments to a trip. Must be a participant (contributor+)."""
    trip = await _get_trip_or_404(db, trip_id)

    if not current_user.is_admin:
        role = await _get_participant_role(db, trip.id, current_user.id)
        if role not in ("organizer", "contributor"):
            raise HTTPException(
                status_code=403,
                detail="Only contributors and organizers can add moments"
            )

    added = 0
    for moment_id in body.moment_ids:
        # Verify moment exists
        result = await db.execute(select(Moment).where(Moment.id == moment_id))
        if not result.scalar_one_or_none():
            continue

        # Check not already linked
        result = await db.execute(
            select(TripMoment).where(
                TripMoment.trip_id == trip_id,
                TripMoment.moment_id == moment_id,
            )
        )
        if result.scalar_one_or_none():
            continue

        tm = TripMoment(
            trip_id=trip_id,
            moment_id=moment_id,
            added_by=current_user.id,
        )
        db.add(tm)
        added += 1

    await db.flush()
    return {"added": added, "total_requested": len(body.moment_ids)}


@router.delete("/{trip_id}/moments/{moment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_moment_from_trip(
    trip_id: str,
    moment_id: str,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Remove a moment from a trip."""
    trip = await _get_trip_or_404(db, trip_id)
    await _require_trip_edit(db, trip, current_user)

    result = await db.execute(
        select(TripMoment).where(
            TripMoment.trip_id == trip_id,
            TripMoment.moment_id == moment_id,
        )
    )
    tm = result.scalar_one_or_none()
    if not tm:
        raise HTTPException(status_code=404, detail="Moment not in this trip")

    await db.delete(tm)
    await db.flush()


# ─── Timeline ────────────────────────────────────────────────────

async def _build_timeline_moment(db: AsyncSession, m: Moment) -> dict:
    """Build a rich moment dict with owner attribution and media metadata."""
    # Poster/owner info
    poster_name = None
    poster_photo = None
    poster_id = None
    if m.posted_by:
        pr = await db.execute(select(Person).where(Person.id == m.posted_by))
        poster = pr.scalar_one_or_none()
        if poster:
            poster_name = poster.display_name
            poster_photo = poster.photo_url
            poster_id = poster.id

    # Media with full metadata
    media_list = []
    if m.media_ids:
        for mid in m.media_ids:
            if mid.startswith("/static/"):
                media_list.append({"id": mid, "url": mid, "width": 800, "height": 600})
            else:
                mr = await db.execute(select(Media).where(Media.id == mid))
                media = mr.scalar_one_or_none()
                if media:
                    media_list.append({
                        "id": media.id,
                        "url": f"/api/media/{media.id}/file",
                        "thumbnail_url": f"/api/media/{media.id}/thumbnail",
                        "resized_url": f"/api/media/{media.id}/resized" if media.resized_path else f"/api/media/{media.id}/file",
                        "width": media.width,
                        "height": media.height,
                        "media_type": media.media_type,
                        "location_lat": media.location_lat,
                        "location_lng": media.location_lng,
                        "location_alt": media.location_alt,
                        "taken_at": media.taken_at.isoformat() if media.taken_at else None,
                        "taken_at_source": media.taken_at_source,
                        "camera_make": media.camera_make,
                        "camera_model": media.camera_model,
                        "has_exif": media.has_exif,
                        "duration_seconds": media.duration_seconds,
                        "video_thumbnail_path": media.video_thumbnail_path,
                    })

    occurred_at = m.occurred_at.isoformat() if m.occurred_at else None
    occurred_date = m.occurred_at.strftime("%Y-%m-%d") if m.occurred_at else None

    return {
        "id": m.id,
        "kind": m.kind,
        "title": m.title,
        "body": m.body,
        "media": media_list,
        "poster_id": poster_id,
        "poster_name": poster_name,
        "poster_photo": poster_photo,
        "occurred_at": occurred_at,
        "occurred_date": occurred_date,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


@router.get("/{trip_id}/timeline")
async def trip_timeline(
    trip_id: str,
    before: str | None = Query(None),
    contributor: str | None = Query(None),
    limit: int = Query(500, ge=1, le=1000),
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Day-by-day timeline of all moments in a trip.

    Returns moments grouped by date, each with full owner attribution
    and GPS data for mini route maps.

    Filters:
    - contributor: filter by poster person_id ("Show only Baba's photos")
    """
    trip = await _get_trip_or_404(db, trip_id)
    await _require_trip_access(db, trip, current_user)

    query = (
        select(Moment)
        .join(TripMoment, TripMoment.moment_id == Moment.id)
        .where(TripMoment.trip_id == trip_id)
    )

    if before:
        result = await db.execute(select(Moment.occurred_at).where(Moment.id == before))
        cursor_time = result.scalar_one_or_none()
        if cursor_time:
            query = query.where(Moment.occurred_at < cursor_time)

    if contributor:
        query = query.where(Moment.posted_by == contributor)

    if not current_user.is_admin:
        query = query.where(Moment.visibility != "hidden")

    query = query.order_by(Moment.occurred_at.asc()).limit(limit)
    result = await db.execute(query)
    moments = result.scalars().all()

    # Build moment cards
    cards = []
    for m in moments:
        cards.append(await _build_timeline_moment(db, m))

    # Group by date for day-by-day pagination
    days: dict[str, dict] = {}
    for card in cards:
        date_key = card["occurred_date"] or "unknown"
        if date_key not in days:
            days[date_key] = {
                "date": date_key,
                "moments": [],
                "gps_points": [],  # For mini route map
                "contributors": {},  # Unique contributors this day
            }
        days[date_key]["moments"].append(card)

        # Collect GPS points from media for route map
        for media in card.get("media", []):
            if media.get("location_lat") is not None and media.get("location_lng") is not None:
                days[date_key]["gps_points"].append({
                    "lat": media["location_lat"],
                    "lng": media["location_lng"],
                    "time": media.get("taken_at") or card["occurred_at"],
                    "media_id": media["id"],
                })

        # Track contributors per day
        if card["poster_id"]:
            days[date_key]["contributors"][card["poster_id"]] = {
                "id": card["poster_id"],
                "name": card["poster_name"],
                "photo": card["poster_photo"],
            }

    # Convert to sorted list
    day_list = []
    for date_key in sorted(days.keys()):
        day = days[date_key]
        day["contributors"] = list(day["contributors"].values())
        # Sort GPS points by time for route rendering
        day["gps_points"].sort(key=lambda p: p.get("time") or "")
        day_list.append(day)

    return {
        "trip_id": trip_id,
        "total_moments": len(cards),
        "total_days": len(day_list),
        "days": day_list,
    }


# ─── Map (GeoJSON) ───────────────────────────────────────────────

@router.get("/{trip_id}/map")
async def trip_map(
    trip_id: str,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    GPS-tagged media from the trip as GeoJSON for map rendering.

    Each feature includes poster_id for color-coded pins by contributor.
    Also returns a contributors array with assigned colors.
    """
    trip = await _get_trip_or_404(db, trip_id)
    await _require_trip_access(db, trip, current_user)

    # Color palette for contributors
    CONTRIBUTOR_COLORS = [
        "#e74c3c", "#3498db", "#2ecc71", "#f39c12",
        "#9b59b6", "#1abc9c", "#e67e22", "#e91e63",
    ]

    # Get all moments in the trip
    result = await db.execute(
        select(Moment)
        .join(TripMoment, TripMoment.moment_id == Moment.id)
        .where(TripMoment.trip_id == trip_id)
        .order_by(Moment.occurred_at.asc())
    )
    moments = result.scalars().all()

    features = []
    contributor_map: dict[str, dict] = {}
    color_idx = 0

    for m in moments:
        if not m.media_ids:
            continue

        # Poster info (cached per poster_id)
        poster_id = m.posted_by
        poster_name = None
        poster_color = "#888"
        if poster_id and poster_id not in contributor_map:
            pr = await db.execute(select(Person).where(Person.id == poster_id))
            poster = pr.scalar_one_or_none()
            if poster:
                contributor_map[poster_id] = {
                    "id": poster_id,
                    "name": poster.display_name,
                    "photo": poster.photo_url,
                    "color": CONTRIBUTOR_COLORS[color_idx % len(CONTRIBUTOR_COLORS)],
                }
                color_idx += 1

        if poster_id and poster_id in contributor_map:
            poster_name = contributor_map[poster_id]["name"]
            poster_color = contributor_map[poster_id]["color"]

        for mid in m.media_ids:
            if mid.startswith("/static/"):
                continue
            mr = await db.execute(select(Media).where(Media.id == mid))
            media = mr.scalar_one_or_none()
            if not media or media.location_lat is None or media.location_lng is None:
                continue

            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [media.location_lng, media.location_lat],
                },
                "properties": {
                    "moment_id": m.id,
                    "media_id": media.id,
                    "media_url": f"/api/media/{media.id}/file",
                    "thumbnail_url": f"/api/media/{media.id}/thumbnail",
                    "caption": media.caption or m.body or "",
                    "poster_id": poster_id,
                    "poster_name": poster_name,
                    "poster_color": poster_color,
                    "occurred_at": m.occurred_at.isoformat() if m.occurred_at else None,
                    "occurred_date": m.occurred_at.strftime("%Y-%m-%d") if m.occurred_at else None,
                },
            })

    return {
        "type": "FeatureCollection",
        "features": features,
        "contributors": list(contributor_map.values()),
    }


# ─── Export (ZIP with originals) ──────────────────────────────────

@router.get("/{trip_id}/export")
async def export_trip(
    trip_id: str,
    quality: str = Query("original", pattern="^(original|high)$"),
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Export trip photos as a ZIP file.
    quality=original: full original files
    quality=high: resized 2048px variants (smaller download)
    """
    import zipfile
    import tempfile
    from fastapi.responses import FileResponse as ZipResponse

    trip = await _get_trip_or_404(db, trip_id)
    await _require_trip_access(db, trip, current_user)

    settings = __import__("app.config", fromlist=["get_settings"]).get_settings()
    media_dir = os.path.join(settings.DATA_DIR, "media")

    # Get all moments + media
    result = await db.execute(
        select(Moment)
        .join(TripMoment, TripMoment.moment_id == Moment.id)
        .where(TripMoment.trip_id == trip_id)
        .order_by(Moment.occurred_at.asc())
    )
    moments = result.scalars().all()

    # Create temp zip
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            seen_media = set()
            for m in moments:
                if not m.media_ids:
                    continue
                date_prefix = m.occurred_at.strftime("%Y-%m-%d") if m.occurred_at else "unknown"
                for mid in m.media_ids:
                    if mid in seen_media or mid.startswith("/static/"):
                        continue
                    seen_media.add(mid)

                    mr = await db.execute(select(Media).where(Media.id == mid))
                    media = mr.scalar_one_or_none()
                    if not media:
                        continue

                    # Choose file path based on quality
                    if quality == "high" and media.resized_path:
                        file_rel = media.resized_path
                    else:
                        file_rel = media.file_path

                    if not file_rel:
                        continue

                    full_path = os.path.join(media_dir, file_rel)
                    if not os.path.isfile(full_path):
                        continue

                    # Archive name: Day/original_filename_or_id
                    arc_name = media.original_filename or f"{media.id}{os.path.splitext(file_rel)[1]}"
                    zf.write(full_path, f"{date_prefix}/{arc_name}")

        safe_name = trip.name.replace("/", "-").replace("\\", "-")[:50]
        return ZipResponse(
            path=tmp_path,
            media_type="application/zip",
            filename=f"{safe_name}.zip",
            background=None,  # let FastAPI handle cleanup
        )
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ─── Revoke Invite ───────────────────────────────────────────────

@router.delete("/{trip_id}/invite", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invite(
    trip_id: str,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Revoke the current invite link (set to null)."""
    trip = await _get_trip_or_404(db, trip_id)
    await _require_trip_edit(db, trip, current_user)
    trip.invite_token = None
    await db.flush()


# ─── Auto-suggest ────────────────────────────────────────────────

@router.get("/suggest/{moment_id}")
async def suggest_trips_for_moment(
    moment_id: str,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Suggest trips for an unassigned moment based on date overlap."""
    result = await db.execute(select(Moment).where(Moment.id == moment_id))
    moment = result.scalar_one_or_none()
    if not moment:
        raise HTTPException(status_code=404, detail="Moment not found")

    # Check if moment is already in any trip
    result = await db.execute(
        select(TripMoment.trip_id).where(TripMoment.moment_id == moment_id)
    )
    existing_trip_ids = {row[0] for row in result.all()}

    # Find trips whose date range overlaps the moment's occurred_at
    moment_date = None
    if moment.occurred_at:
        moment_date = moment.occurred_at.strftime("%Y-%m-%d")

    if not moment_date:
        return {"suggestions": []}

    result = await db.execute(
        select(Trip).where(
            Trip.start_date.isnot(None),
            Trip.end_date.isnot(None),
            Trip.start_date <= moment_date,
            Trip.end_date >= moment_date,
        )
    )
    matching_trips = result.scalars().all()

    suggestions = []
    for trip in matching_trips:
        if trip.id in existing_trip_ids:
            continue
        suggestions.append({
            "trip_id": trip.id,
            "trip_name": trip.name,
            "start_date": trip.start_date,
            "end_date": trip.end_date,
        })

    return {"suggestions": suggestions}
