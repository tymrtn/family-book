from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_auth
from app.database import get_db
from app.models.media import Media
from app.models.moments import Moment, MomentComment, MomentReaction
from app.models.person import Person

router = APIRouter(prefix="/api/moments", tags=["moments"])


# --- Schemas ---

class MomentCreate(BaseModel):
    kind: str
    person_id: str | None = None
    body: str | None = Field(None, max_length=5000)
    title: str | None = Field(None, max_length=300)
    media_ids: list[str] = []
    milestone_type: str | None = None
    occurred_at: datetime | None = None
    visibility: str = "members"


class MomentUpdate(BaseModel):
    body: str | None = Field(None, max_length=5000)
    title: str | None = Field(None, max_length=300)
    visibility: str | None = None


class PersonBrief(BaseModel):
    id: str
    display_name: str
    photo_url: str | None


class MediaBrief(BaseModel):
    id: str
    url: str
    width: int | None
    height: int | None


class MomentCard(BaseModel):
    id: str
    kind: str
    poster: PersonBrief | None
    about: PersonBrief | None
    title: str | None
    body: str | None
    media: list[MediaBrief]
    milestone_type: str | None
    occurred_at: str
    reactions: dict[str, int]
    my_reaction: str | None
    comment_count: int
    created_at: str


class CommentCreate(BaseModel):
    body: str = Field(max_length=2000)


class CommentResponse(BaseModel):
    id: str
    moment_id: str
    person_id: str
    person_name: str
    body: str
    created_at: str


class ReactionCreate(BaseModel):
    emoji: str = Field(max_length=10)


# --- Helpers ---

async def _build_moment_card(
    db: AsyncSession, moment: Moment, current_user_id: str
) -> dict:
    """Build a MomentCard response dict from a Moment ORM object."""
    # Poster
    poster = None
    if moment.posted_by:
        result = await db.execute(select(Person).where(Person.id == moment.posted_by))
        poster_person = result.scalar_one_or_none()
        if poster_person:
            poster = {
                "id": poster_person.id,
                "display_name": poster_person.display_name,
                "photo_url": poster_person.photo_url,
            }

    # About (the person the moment is about)
    about = None
    result = await db.execute(select(Person).where(Person.id == moment.person_id))
    about_person = result.scalar_one_or_none()
    if about_person:
        about = {
            "id": about_person.id,
            "display_name": about_person.display_name,
            "photo_url": about_person.photo_url,
        }

    # Media
    media_list = []
    if moment.media_ids:
        for mid in moment.media_ids:
            result = await db.execute(select(Media).where(Media.id == mid))
            m = result.scalar_one_or_none()
            if m:
                media_list.append({
                    "id": m.id,
                    "url": f"/api/media/{m.id}/file",
                    "width": m.width,
                    "height": m.height,
                })

    # Reactions aggregation
    result = await db.execute(
        select(MomentReaction.emoji, func.count(MomentReaction.id))
        .where(MomentReaction.moment_id == moment.id)
        .group_by(MomentReaction.emoji)
    )
    reactions = {row[0]: row[1] for row in result.all()}

    # My reaction
    result = await db.execute(
        select(MomentReaction.emoji).where(
            MomentReaction.moment_id == moment.id,
            MomentReaction.person_id == current_user_id,
        )
    )
    my_reaction_row = result.scalar_one_or_none()

    # Comment count
    result = await db.execute(
        select(func.count(MomentComment.id)).where(
            MomentComment.moment_id == moment.id
        )
    )
    comment_count = result.scalar()

    return {
        "id": moment.id,
        "kind": moment.kind,
        "poster": poster,
        "about": about,
        "title": moment.title,
        "body": moment.body,
        "media": media_list,
        "milestone_type": moment.milestone_type,
        "occurred_at": moment.occurred_at.isoformat() if moment.occurred_at else None,
        "reactions": reactions,
        "my_reaction": my_reaction_row,
        "comment_count": comment_count or 0,
        "created_at": moment.created_at.isoformat() if moment.created_at else None,
    }


# --- Routes ---

@router.get("")
async def list_moments(
    before: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    person: str | None = Query(None),
    branch: str | None = Query(None),
    kind: str | None = Query(None),
    year: int | None = Query(None),
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """List moments feed, reverse-chronological, paginated."""
    query = select(Moment)

    if before:
        # Cursor-based: get the moment to use as cursor
        result = await db.execute(select(Moment.occurred_at).where(Moment.id == before))
        cursor_time = result.scalar_one_or_none()
        if cursor_time:
            query = query.where(Moment.occurred_at < cursor_time)

    if person:
        query = query.where(Moment.person_id == person)

    if branch:
        # Join to Person to filter by branch
        query = query.join(Person, Moment.person_id == Person.id).where(
            Person.branch == branch
        )

    if kind:
        query = query.where(Moment.kind == kind)

    if year:
        query = query.where(extract("year", Moment.occurred_at) == year)

    # Filter by visibility
    if not current_user.is_admin:
        query = query.where(Moment.visibility != "hidden")

    query = query.order_by(Moment.occurred_at.desc()).limit(limit)
    result = await db.execute(query)
    moments = result.scalars().all()

    cards = []
    for m in moments:
        card = await _build_moment_card(db, m, current_user.id)
        cards.append(card)

    return cards


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_moment(
    body: MomentCreate,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Create a new moment."""
    person_id = body.person_id or current_user.id

    # Verify person exists
    result = await db.execute(select(Person).where(Person.id == person_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Person not found")

    moment = Moment(
        person_id=person_id,
        kind=body.kind,
        title=body.title,
        body=body.body,
        milestone_type=body.milestone_type,
        occurred_at=body.occurred_at or datetime.now(timezone.utc),
        visibility=body.visibility,
        posted_by=current_user.id,
    )
    moment.media_ids = body.media_ids

    db.add(moment)
    await db.flush()

    card = await _build_moment_card(db, moment, current_user.id)
    return card


@router.get("/{moment_id}")
async def get_moment(
    moment_id: str,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Get a single moment detail."""
    result = await db.execute(select(Moment).where(Moment.id == moment_id))
    moment = result.scalar_one_or_none()
    if not moment:
        raise HTTPException(status_code=404, detail="Moment not found")

    if moment.visibility == "hidden" and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not visible")

    return await _build_moment_card(db, moment, current_user.id)


@router.put("/{moment_id}")
async def update_moment(
    moment_id: str,
    body: MomentUpdate,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Edit a moment (author only, or admin)."""
    result = await db.execute(select(Moment).where(Moment.id == moment_id))
    moment = result.scalar_one_or_none()
    if not moment:
        raise HTTPException(status_code=404, detail="Moment not found")

    if moment.posted_by != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(moment, field, value)

    await db.flush()
    return await _build_moment_card(db, moment, current_user.id)


@router.delete("/{moment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_moment(
    moment_id: str,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Delete a moment (admin or poster only)."""
    result = await db.execute(select(Moment).where(Moment.id == moment_id))
    moment = result.scalar_one_or_none()
    if not moment:
        raise HTTPException(status_code=404, detail="Moment not found")

    if moment.posted_by != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    await db.delete(moment)
    await db.flush()


# --- Comments ---

@router.get("/{moment_id}/comments")
async def list_comments(
    moment_id: str,
    limit: int = Query(50, ge=1, le=200),
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """List comments on a moment."""
    result = await db.execute(select(Moment).where(Moment.id == moment_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Moment not found")

    result = await db.execute(
        select(MomentComment)
        .where(MomentComment.moment_id == moment_id)
        .order_by(MomentComment.created_at.asc())
        .limit(limit)
    )
    comments = result.scalars().all()

    response = []
    for c in comments:
        person_result = await db.execute(select(Person).where(Person.id == c.person_id))
        person = person_result.scalar_one_or_none()
        response.append({
            "id": c.id,
            "moment_id": c.moment_id,
            "person_id": c.person_id,
            "person_name": person.display_name if person else "Unknown",
            "body": c.body,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return response


@router.post("/{moment_id}/comments", status_code=status.HTTP_201_CREATED)
async def create_comment(
    moment_id: str,
    body: CommentCreate,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Add a comment to a moment."""
    result = await db.execute(select(Moment).where(Moment.id == moment_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Moment not found")

    comment = MomentComment(
        moment_id=moment_id,
        person_id=current_user.id,
        body=body.body,
    )
    db.add(comment)
    await db.flush()

    return {
        "id": comment.id,
        "moment_id": comment.moment_id,
        "person_id": comment.person_id,
        "person_name": current_user.display_name,
        "body": comment.body,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    }


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: str,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Delete a comment (admin or author only)."""
    result = await db.execute(
        select(MomentComment).where(MomentComment.id == comment_id)
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if comment.person_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    await db.delete(comment)
    await db.flush()


# --- Reactions ---

@router.post("/{moment_id}/reactions")
async def add_reaction(
    moment_id: str,
    body: ReactionCreate,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Add or replace a reaction on a moment. One per person."""
    result = await db.execute(select(Moment).where(Moment.id == moment_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Moment not found")

    # Check for existing reaction
    result = await db.execute(
        select(MomentReaction).where(
            MomentReaction.moment_id == moment_id,
            MomentReaction.person_id == current_user.id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.emoji = body.emoji
        await db.flush()
    else:
        reaction = MomentReaction(
            moment_id=moment_id,
            person_id=current_user.id,
            emoji=body.emoji,
        )
        db.add(reaction)
        await db.flush()

    # Return aggregated count for this emoji
    result = await db.execute(
        select(func.count(MomentReaction.id)).where(
            MomentReaction.moment_id == moment_id,
            MomentReaction.emoji == body.emoji,
        )
    )
    count = result.scalar()

    return {"emoji": body.emoji, "count": count}


@router.delete("/{moment_id}/reactions", status_code=status.HTTP_204_NO_CONTENT)
async def remove_reaction(
    moment_id: str,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Remove the current user's reaction from a moment."""
    result = await db.execute(select(Moment).where(Moment.id == moment_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Moment not found")

    result = await db.execute(
        select(MomentReaction).where(
            MomentReaction.moment_id == moment_id,
            MomentReaction.person_id == current_user.id,
        )
    )
    reaction = result.scalar_one_or_none()
    if not reaction:
        raise HTTPException(status_code=404, detail="No reaction to remove")

    await db.delete(reaction)
    await db.flush()
