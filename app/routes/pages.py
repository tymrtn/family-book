"""
HTML page routes — serves Jinja2 templates for the HTMX frontend.

All data fetching happens server-side. Templates use HTMX for dynamic interactions.
"""

import os

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_admin, require_auth
from app.database import get_db
from app.i18n import t as translate
from app.models.media import Media
from app.models.moments import Moment, MomentComment
from app.models.person import Person, AccountState, Visibility
from app.models.relationships import ParentChild, Partnership
from app.models.trips import Trip, TripParticipant, TripMoment
from app.services.auth_service import get_valid_invite

router = APIRouter(tags=["pages"])

_template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=_template_dir)


# ─── Helpers ───────────────────────────────────────────────────────

def _get_locale(request: Request) -> str:
    """Detect locale: cookie > Accept-Language header > 'en' default."""
    # 1. Explicit cookie always wins (user chose this)
    cookie_locale = request.cookies.get("locale")
    if cookie_locale and cookie_locale in ("en", "es", "ru"):
        return cookie_locale

    # 2. Parse Accept-Language header (e.g. "ru-RU,ru;q=0.9,en;q=0.8")
    accept = request.headers.get("accept-language", "")
    if accept:
        for part in accept.split(","):
            tag = part.split(";")[0].strip().lower()
            # Match primary subtag: "ru-RU" → "ru", "es-419" → "es"
            lang = tag.split("-")[0]
            if lang in ("ru", "es", "en"):
                return lang

    return "en"


def _country_flag(code: str | None) -> str:
    if not code or len(code) != 2:
        return ""
    offset = 127397
    return chr(ord(code[0]) + offset) + chr(ord(code[1]) + offset)


def _ctx(request: Request, current_user: Person | None = None, **kwargs):
    """Build common template context."""
    locale = _get_locale(request)

    def _person_name(person):
        """Locale-aware display name — uses tree.our_family for root person."""
        if person and getattr(person, "is_root", False):
            return translate("tree.our_family", locale)
        return person.display_name if person else ""

    return {
        "request": request,
        "current_user": current_user,
        "demo_mode": False,
        "url_prefix": "",
        "locale": locale,
        "t": lambda key: translate(key, locale),
        "country_flag": _country_flag,
        "person_name": _person_name,
        **kwargs,
    }


async def _build_moment_card_simple(db: AsyncSession, moment: Moment, current_user_id: str) -> dict:
    """Lightweight moment card builder for template rendering."""
    from app.models.moments import MomentReaction

    # Poster
    poster = None
    if moment.posted_by:
        result = await db.execute(select(Person).where(Person.id == moment.posted_by))
        p = result.scalar_one_or_none()
        if p:
            poster = {"id": p.id, "display_name": p.display_name, "photo_url": p.photo_url}

    # About person
    about = None
    result = await db.execute(select(Person).where(Person.id == moment.person_id))
    p = result.scalar_one_or_none()
    if p:
        about = {"id": p.id, "display_name": p.display_name, "photo_url": p.photo_url}

    # Media
    media_list = []
    if moment.media_ids:
        for mid in moment.media_ids:
            # Support static demo photos referenced by path
            if mid.startswith("/static/"):
                media_list.append({"id": mid, "url": mid, "width": 800, "height": 600})
            else:
                result = await db.execute(select(Media).where(Media.id == mid))
                m = result.scalar_one_or_none()
                if m:
                    media_list.append({"id": m.id, "url": f"/api/media/{m.id}/file", "width": m.width, "height": m.height})

    # Reactions
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
    my_reaction = result.scalar_one_or_none()

    # Comment count
    result = await db.execute(
        select(func.count(MomentComment.id)).where(MomentComment.moment_id == moment.id)
    )
    comment_count = result.scalar() or 0

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
        "source": moment.source if hasattr(moment, "source") else None,
        "reactions": reactions,
        "my_reaction": my_reaction,
        "comment_count": comment_count,
        "created_at": moment.created_at.isoformat() if moment.created_at else None,
    }


# ─── Landing / Home ───────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    kind: str | None = Query(None),
    current_user: Person | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user:
        return templates.TemplateResponse("landing.html", _ctx(request))

    # Build moments feed
    query = select(Moment)
    if kind:
        query = query.where(Moment.kind == kind)
    if not current_user.is_admin:
        query = query.where(Moment.visibility != "hidden")
    query = query.order_by(Moment.occurred_at.desc()).limit(20)
    result = await db.execute(query)
    moments_orm = result.scalars().all()

    moments = []
    for m in moments_orm:
        card = await _build_moment_card_simple(db, m, current_user.id)
        moments.append(card)

    return templates.TemplateResponse("home.html", _ctx(
        request, current_user, active_page="home", moments=moments,
    ))


# ─── Auth Pages ───────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, current_user: Person | None = Depends(get_current_user)):
    if current_user:
        return RedirectResponse("/", status_code=302)
    from app.config import get_settings
    settings = get_settings()
    return templates.TemplateResponse("login.html", _ctx(
        request, fb_enabled=settings.FB_ENABLED,
    ))


@router.get("/invite/{token}", response_class=HTMLResponse)
async def invite_page(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    invite = await get_valid_invite(db, token)
    if not invite:
        return templates.TemplateResponse("invite.html", _ctx(
            request, error="Invalid or expired invite link.", token=token,
            person_name="", branch="",
        ))

    result = await db.execute(select(Person).where(Person.id == invite.person_id))
    person = result.scalar_one_or_none()
    if not person:
        return templates.TemplateResponse("invite.html", _ctx(
            request, error="Person not found.", token=token,
            person_name="", branch="",
        ))

    return templates.TemplateResponse("invite.html", _ctx(
        request, token=token, person_name=person.display_name,
        branch=person.branch, error=None,
    ))


# ─── Tree ─────────────────────────────────────────────────────────

@router.get("/tree", response_class=HTMLResponse)
async def tree_page(
    request: Request,
    current_user: Person = Depends(require_auth),
):
    return templates.TemplateResponse("tree.html", _ctx(
        request, current_user, active_page="tree",
    ))


# ─── People ───────────────────────────────────────────────────────

@router.get("/people", response_class=HTMLResponse)
async def people_page(
    request: Request,
    branch: str | None = Query(None),
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    query = select(Person).where(Person.visibility != Visibility.hidden.value)
    if branch:
        query = query.where(Person.branch == branch)
    query = query.order_by(Person.last_name, Person.first_name)
    result = await db.execute(query)
    persons = result.scalars().all()

    # Get distinct branches
    branch_result = await db.execute(
        select(Person.branch).where(Person.branch.isnot(None)).distinct()
    )
    branches = sorted([row[0] for row in branch_result.all() if row[0]])

    return templates.TemplateResponse("people.html", _ctx(
        request, current_user, active_page="people",
        persons=persons, branches=branches, branch_filter=branch,
    ))


@router.get("/people/{person_id}", response_class=HTMLResponse)
async def person_detail_page(
    person_id: str,
    request: Request,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    if not person:
        return RedirectResponse("/people", status_code=302)

    # Parents
    result = await db.execute(
        select(Person).join(ParentChild, ParentChild.parent_id == Person.id)
        .where(ParentChild.child_id == person_id)
    )
    parents = result.scalars().all()

    # Children
    result = await db.execute(
        select(Person).join(ParentChild, ParentChild.child_id == Person.id)
        .where(ParentChild.parent_id == person_id)
    )
    children = result.scalars().all()

    # Partners
    result = await db.execute(
        select(Partnership).where(
            (Partnership.person_a_id == person_id) | (Partnership.person_b_id == person_id)
        )
    )
    partnerships = result.scalars().all()
    partner_ids = set()
    for p in partnerships:
        pid = p.person_b_id if p.person_a_id == person_id else p.person_a_id
        partner_ids.add(pid)
    partners = []
    for pid in partner_ids:
        result = await db.execute(select(Person).where(Person.id == pid))
        partner = result.scalar_one_or_none()
        if partner:
            partners.append(partner)

    # Siblings (share a parent)
    parent_ids = [p.id for p in parents]
    siblings = []
    if parent_ids:
        result = await db.execute(
            select(Person).join(ParentChild, ParentChild.child_id == Person.id)
            .where(ParentChild.parent_id.in_(parent_ids), Person.id != person_id)
        )
        siblings = list({s.id: s for s in result.scalars().all()}.values())

    can_edit = person.id == current_user.id or current_user.is_admin

    return templates.TemplateResponse("person.html", _ctx(
        request, current_user, active_page="people",
        person=person, parents=parents, children=children,
        partners=partners, siblings=siblings, can_edit=can_edit,
    ))


@router.get("/people/{person_id}/edit", response_class=HTMLResponse)
async def person_edit_page(
    person_id: str,
    request: Request,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    if person_id != current_user.id and not current_user.is_admin:
        return RedirectResponse(f"/people/{person_id}", status_code=302)

    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    if not person:
        return RedirectResponse("/people", status_code=302)

    return templates.TemplateResponse("person_edit.html", _ctx(
        request, current_user, active_page="people", person=person,
    ))


@router.get("/people/{person_id}/card", response_class=HTMLResponse)
async def person_card(
    person_id: str,
    request: Request,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Person card fragment for tree sidebar."""
    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    if not person:
        return HTMLResponse("<p>Person not found</p>")

    return templates.TemplateResponse("partials/person_sidebar.html", _ctx(
        request, current_user, person=person,
    ))


# ─── Admin ────────────────────────────────────────────────────────

@router.get("/admin", response_class=HTMLResponse)
async def admin_page(
    request: Request,
    current_user: Person = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    # Stats
    persons_count = (await db.execute(select(func.count(Person.id)))).scalar() or 0
    moments_count = (await db.execute(select(func.count(Moment.id)))).scalar() or 0
    media_count = (await db.execute(select(func.count(Media.id)))).scalar() or 0
    pending_count = (await db.execute(
        select(func.count(Person.id)).where(Person.account_state == AccountState.pending.value)
    )).scalar() or 0

    stats = {
        "persons": persons_count,
        "moments": moments_count,
        "media": media_count,
        "pending": pending_count,
    }

    # Pending persons
    result = await db.execute(
        select(Person).where(Person.account_state == AccountState.pending.value)
    )
    pending_persons = result.scalars().all()

    # All persons for invite select
    result = await db.execute(
        select(Person).order_by(Person.last_name, Person.first_name)
    )
    all_persons = result.scalars().all()

    return templates.TemplateResponse("admin.html", _ctx(
        request, current_user, active_page="admin",
        stats=stats, pending_persons=pending_persons, all_persons=all_persons,
    ))


@router.get("/admin/people/new", response_class=HTMLResponse)
async def admin_new_person_page(
    request: Request,
    current_user: Person = Depends(require_admin),
):
    return templates.TemplateResponse("person_new.html", _ctx(
        request, current_user, active_page="admin",
    ))


# ─── Trips ────────────────────────────────────────────────────────

@router.get("/trips", response_class=HTMLResponse)
async def trips_page(
    request: Request,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Trip albums list page."""
    from sqlalchemy import or_

    if current_user.is_admin:
        query = select(Trip).order_by(Trip.start_date.desc().nullslast(), Trip.created_at.desc())
    else:
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
    trips_orm = result.scalars().all()

    trips = []
    for trip in trips_orm:
        # Counts
        p_count = (await db.execute(
            select(func.count(TripParticipant.id)).where(TripParticipant.trip_id == trip.id)
        )).scalar() or 0
        m_count = (await db.execute(
            select(func.count(TripMoment.id)).where(TripMoment.trip_id == trip.id)
        )).scalar() or 0

        cover_url = f"/api/media/{trip.cover_media_id}/file" if trip.cover_media_id else None

        trips.append({
            "id": trip.id,
            "name": trip.name,
            "description": trip.description,
            "start_date": trip.start_date,
            "end_date": trip.end_date,
            "cover_url": cover_url,
            "participant_count": p_count,
            "moment_count": m_count,
        })

    return templates.TemplateResponse("trips.html", _ctx(
        request, current_user, active_page="trips", trips=trips,
    ))


@router.get("/trips/{trip_id}", response_class=HTMLResponse)
async def trip_detail_page(
    trip_id: str,
    request: Request,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Trip detail page with timeline, map, contributors."""
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = result.scalar_one_or_none()
    if not trip:
        return RedirectResponse("/trips", status_code=302)

    # Build trip response data
    p_count = (await db.execute(
        select(func.count(TripParticipant.id)).where(TripParticipant.trip_id == trip.id)
    )).scalar() or 0
    m_count = (await db.execute(
        select(func.count(TripMoment.id)).where(TripMoment.trip_id == trip.id)
    )).scalar() or 0

    cover_url = f"/api/media/{trip.cover_media_id}/file" if trip.cover_media_id else None

    trip_data = {
        "id": trip.id,
        "name": trip.name,
        "description": trip.description,
        "start_date": trip.start_date,
        "end_date": trip.end_date,
        "cover_url": cover_url,
        "participant_count": p_count,
        "moment_count": m_count,
        "invite_token": trip.invite_token,
    }

    # Participants
    result = await db.execute(
        select(TripParticipant).where(TripParticipant.trip_id == trip_id)
        .order_by(TripParticipant.joined_at)
    )
    participants_orm = result.scalars().all()

    participants = []
    is_participant = False
    is_organizer = False
    for p in participants_orm:
        pr = await db.execute(select(Person).where(Person.id == p.person_id))
        person = pr.scalar_one_or_none()
        participants.append({
            "person_id": p.person_id,
            "person_name": person.display_name if person else "Unknown",
            "photo_url": person.photo_url if person else None,
            "role": p.role,
        })
        if p.person_id == current_user.id:
            is_participant = True
            if p.role == "organizer":
                is_organizer = True

    # Build day-by-day timeline via API helper
    result = await db.execute(
        select(Moment)
        .join(TripMoment, TripMoment.moment_id == Moment.id)
        .where(TripMoment.trip_id == trip_id)
        .order_by(Moment.occurred_at.asc())
        .limit(500)
    )
    moments_orm = result.scalars().all()

    # Build rich moment cards with owner attribution + media metadata
    cards = []
    all_contributors_map: dict[str, dict] = {}
    for m in moments_orm:
        poster_id = None
        poster_name = None
        poster_photo = None
        if m.posted_by:
            pr = await db.execute(select(Person).where(Person.id == m.posted_by))
            poster = pr.scalar_one_or_none()
            if poster:
                poster_id = poster.id
                poster_name = poster.display_name
                poster_photo = poster.photo_url
                if poster_id not in all_contributors_map:
                    all_contributors_map[poster_id] = {
                        "id": poster_id,
                        "name": poster_name,
                        "photo": poster_photo,
                    }

        media_list = []
        if m.media_ids:
            for mid in m.media_ids:
                if mid.startswith("/static/"):
                    media_list.append({
                        "id": mid, "url": mid, "thumbnail_url": mid,
                        "resized_url": mid, "width": 800, "height": 600,
                        "media_type": "image",
                    })
                else:
                    mr = await db.execute(select(Media).where(Media.id == mid))
                    media_obj = mr.scalar_one_or_none()
                    if media_obj:
                        media_list.append({
                            "id": media_obj.id,
                            "url": f"/api/media/{media_obj.id}/file",
                            "thumbnail_url": f"/api/media/{media_obj.id}/thumbnail",
                            "resized_url": (f"/api/media/{media_obj.id}/resized"
                                           if media_obj.resized_path
                                           else f"/api/media/{media_obj.id}/file"),
                            "width": media_obj.width,
                            "height": media_obj.height,
                            "media_type": media_obj.media_type,
                            "location_lat": media_obj.location_lat,
                            "location_lng": media_obj.location_lng,
                            "taken_at": (media_obj.taken_at.isoformat()
                                        if media_obj.taken_at else None),
                            "taken_at_source": media_obj.taken_at_source,
                            "has_exif": media_obj.has_exif,
                            "duration_seconds": media_obj.duration_seconds,
                        })

        occurred_date = m.occurred_at.strftime("%Y-%m-%d") if m.occurred_at else None
        cards.append({
            "id": m.id,
            "kind": m.kind,
            "title": m.title,
            "body": m.body,
            "media": media_list,
            "poster_id": poster_id,
            "poster_name": poster_name,
            "poster_photo": poster_photo,
            "occurred_at": m.occurred_at.isoformat() if m.occurred_at else None,
            "occurred_date": occurred_date,
        })

    # Group into days
    days: dict[str, dict] = {}
    for card in cards:
        date_key = card["occurred_date"] or "unknown"
        if date_key not in days:
            days[date_key] = {
                "date": date_key,
                "moments": [],
                "gps_points": [],
                "contributors": {},
            }
        days[date_key]["moments"].append(card)
        for media_item in card.get("media", []):
            if (media_item.get("location_lat") is not None
                    and media_item.get("location_lng") is not None):
                days[date_key]["gps_points"].append({
                    "lat": media_item["location_lat"],
                    "lng": media_item["location_lng"],
                    "time": media_item.get("taken_at") or card["occurred_at"],
                })
        if card["poster_id"]:
            days[date_key]["contributors"][card["poster_id"]] = {
                "id": card["poster_id"],
                "name": card["poster_name"],
                "photo": card["poster_photo"],
            }

    day_list = []
    for date_key in sorted(days.keys()):
        day = days[date_key]
        day["contributors"] = list(day["contributors"].values())
        day["gps_points"].sort(key=lambda p: p.get("time") or "")
        day_list.append(day)

    timeline_data = {
        "total_moments": len(cards),
        "total_days": len(day_list),
        "days": day_list,
    }

    all_contributors = list(all_contributors_map.values())

    # Invite URL
    from app.config import get_settings
    settings = get_settings()
    invite_url = ""
    if trip.invite_token:
        invite_url = f"{settings.BASE_URL}/trips/join/{trip.invite_token}"

    return templates.TemplateResponse("trip_detail.html", _ctx(
        request, current_user, active_page="trips",
        trip=trip_data, participants=participants,
        timeline_data=timeline_data, all_contributors=all_contributors,
        is_participant=is_participant, is_organizer=is_organizer,
        invite_url=invite_url,
    ))


@router.get("/trips/join/{invite_token}", response_class=HTMLResponse)
async def trip_join_page(
    invite_token: str,
    request: Request,
    current_user: Person | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trip invite join page."""
    result = await db.execute(select(Trip).where(Trip.invite_token == invite_token))
    trip = result.scalar_one_or_none()

    if not trip:
        return templates.TemplateResponse("trip_join.html", _ctx(
            request, current_user,
            error="Invalid or expired invite link.",
            invite_token=invite_token,
            trip_name="", trip_id="", trip_dates="",
            already_member=False,
        ))

    if not current_user:
        # Redirect to login, then back here
        return RedirectResponse(f"/login?return_to=/trips/join/{invite_token}", status_code=302)

    # Check if already a participant
    result = await db.execute(
        select(TripParticipant).where(
            TripParticipant.trip_id == trip.id,
            TripParticipant.person_id == current_user.id,
        )
    )
    already_member = result.scalar_one_or_none() is not None

    trip_dates = ""
    if trip.start_date:
        trip_dates = trip.start_date
        if trip.end_date:
            trip_dates += f" → {trip.end_date}"

    return templates.TemplateResponse("trip_join.html", _ctx(
        request, current_user,
        trip_name=trip.name,
        trip_id=trip.id,
        trip_dates=trip_dates,
        invite_token=invite_token,
        already_member=already_member,
        error=None,
    ))


@router.post("/trips/join/{invite_token}/confirm")
async def trip_join_confirm(
    invite_token: str,
    request: Request,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Confirm joining a trip via invite link."""
    result = await db.execute(select(Trip).where(Trip.invite_token == invite_token))
    trip = result.scalar_one_or_none()
    if not trip:
        return RedirectResponse("/trips", status_code=302)

    # Check not already a participant
    result = await db.execute(
        select(TripParticipant).where(
            TripParticipant.trip_id == trip.id,
            TripParticipant.person_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        participant = TripParticipant(
            trip_id=trip.id,
            person_id=current_user.id,
            role="contributor",
        )
        db.add(participant)
        await db.flush()

    return RedirectResponse(f"/trips/{trip.id}", status_code=302)


# ─── Settings ─────────────────────────────────────────────────────

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    current_user: Person = Depends(require_auth),
):
    return templates.TemplateResponse("settings.html", _ctx(
        request, current_user, active_page="settings",
    ))


# ─── HTMX Partials ───────────────────────────────────────────────

@router.get("/partials/moments", response_class=HTMLResponse)
async def partial_moments(
    request: Request,
    before: str | None = Query(None),
    person: str | None = Query(None),
    kind: str | None = Query(None),
    limit: int = Query(20),
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """HTMX partial: render moment cards for infinite scroll."""
    from sqlalchemy import extract

    query = select(Moment)
    if before:
        result = await db.execute(select(Moment.occurred_at).where(Moment.id == before))
        cursor_time = result.scalar_one_or_none()
        if cursor_time:
            query = query.where(Moment.occurred_at < cursor_time)
    if person:
        query = query.where(Moment.person_id == person)
    if kind:
        query = query.where(Moment.kind == kind)
    if not current_user.is_admin:
        query = query.where(Moment.visibility != "hidden")
    query = query.order_by(Moment.occurred_at.desc()).limit(limit)
    result = await db.execute(query)
    moments_orm = result.scalars().all()

    moments = []
    for m in moments_orm:
        card = await _build_moment_card_simple(db, m, current_user.id)
        moments.append(card)

    # Build HTML from moment cards
    html_parts = []
    for m in moments:
        html_parts.append(
            templates.get_template("partials/moment_card.html").render(
                _ctx(request, current_user, m=m)
            )
        )

    # Add next load-more trigger if we got a full page
    if len(moments) >= limit:
        last_id = moments[-1]["id"]
        html_parts.append(
            f'<div hx-get="/partials/moments?before={last_id}" '
            f'hx-trigger="revealed" hx-swap="afterend">'
            f'<div style="text-align:center;padding:20px;">'
            f'<div class="spinner" style="margin:0 auto;"></div></div></div>'
        )

    return HTMLResponse("".join(html_parts))


@router.get("/partials/people-grid", response_class=HTMLResponse)
async def partial_people_grid(
    request: Request,
    search: str | None = Query(None),
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """HTMX partial: people grid for live search."""
    query = select(Person).where(Person.visibility != Visibility.hidden.value)
    if search:
        like = f"%{search}%"
        query = query.where(
            (Person.first_name.ilike(like))
            | (Person.last_name.ilike(like))
            | (Person.nickname.ilike(like))
        )
    query = query.order_by(Person.last_name, Person.first_name)
    result = await db.execute(query)
    persons = result.scalars().all()

    return templates.TemplateResponse("partials/people_grid.html", _ctx(
        request, current_user, persons=persons,
    ))


@router.get("/partials/media-gallery", response_class=HTMLResponse)
async def partial_media_gallery(
    request: Request,
    person_id: str = Query(...),
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """HTMX partial: media gallery for person page."""
    result = await db.execute(
        select(Media).where(Media.person_id == person_id).order_by(Media.created_at.desc())
    )
    media_list = result.scalars().all()
    can_upload = person_id == current_user.id or current_user.is_admin

    return templates.TemplateResponse("partials/media_gallery.html", _ctx(
        request, current_user, media_list=media_list,
        can_upload=can_upload, person_id=person_id,
    ))


@router.get("/partials/comments/{moment_id}", response_class=HTMLResponse)
async def partial_comments(
    moment_id: str,
    request: Request,
    current_user: Person = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """HTMX partial: comment thread for a moment."""
    result = await db.execute(
        select(MomentComment)
        .where(MomentComment.moment_id == moment_id)
        .order_by(MomentComment.created_at.asc())
        .limit(50)
    )
    comments_orm = result.scalars().all()

    comments = []
    for c in comments_orm:
        person_result = await db.execute(select(Person).where(Person.id == c.person_id))
        person = person_result.scalar_one_or_none()
        comments.append({
            "id": c.id,
            "person_name": person.display_name if person else "Unknown",
            "body": c.body,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })

    return templates.TemplateResponse("partials/comments.html", _ctx(
        request, current_user, comments=comments, moment_id=moment_id,
    ))


@router.get("/partials/audit-log", response_class=HTMLResponse)
async def partial_audit_log(
    request: Request,
    current_user: Person = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """HTMX partial: recent audit log entries."""
    from app.models.audit import AuditLog

    result = await db.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(50)
    )
    entries_orm = result.scalars().all()

    entries = []
    for e in entries_orm:
        entries.append({
            "action": e.action,
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
            "new_value": e.new_value,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        })

    return templates.TemplateResponse("partials/audit_log.html", _ctx(
        request, current_user, entries=entries,
    ))
