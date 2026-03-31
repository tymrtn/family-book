"""
Demo mode routes — parallel read-only view of seed data, no auth required.

These routes mirror the real app routes but skip authentication entirely.
Templates receive `demo_mode=True` to show the demo banner and hide edit controls.
"""

import os

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.i18n import t as translate
from app.models.media import Media
from app.models.moments import Moment, MomentComment
from app.models.person import Person, Visibility
from app.models.relationships import ParentChild, Partnership
from app.schemas import (
    ParentChildResponse,
    PartnershipResponse,
    TreeResponse,
    person_to_summary,
)

router = APIRouter(prefix="/demo", tags=["demo"])

_template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=_template_dir)


# ─── Helpers ───────────────────────────────────────────────────────

def _get_locale(request: Request) -> str:
    return request.cookies.get("locale", "en")


def _country_flag(code: str | None) -> str:
    if not code or len(code) != 2:
        return ""
    offset = 127397
    return chr(ord(code[0]) + offset) + chr(ord(code[1]) + offset)


def _ctx(request: Request, **kwargs):
    """Build template context for demo mode — no current_user, demo_mode=True."""
    locale = _get_locale(request)

    def _person_name(person):
        """Locale-aware display name — uses tree.our_family for root person."""
        if person and getattr(person, "is_root", False):
            return translate("tree.our_family", locale)
        return person.display_name if person else ""

    return {
        "request": request,
        "current_user": None,
        "demo_mode": True,
        "url_prefix": "/demo",
        "locale": locale,
        "t": lambda key: translate(key, locale),
        "country_flag": _country_flag,
        "person_name": _person_name,
        **kwargs,
    }


# ─── Demo Landing (redirects to tree) ─────────────────────────────

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def demo_home(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Demo home — shows the moments feed from seed data."""
    query = (
        select(Moment)
        .where(Moment.visibility != "hidden")
        .order_by(Moment.occurred_at.desc())
        .limit(20)
    )
    result = await db.execute(query)
    moments_orm = result.scalars().all()

    moments = []
    for m in moments_orm:
        card = await _build_demo_moment(db, m)
        moments.append(card)

    return templates.TemplateResponse("home.html", _ctx(
        request, active_page="home", moments=moments,
    ))


# ─── Demo Tree ────────────────────────────────────────────────────

@router.get("/tree", response_class=HTMLResponse)
async def demo_tree(request: Request):
    return templates.TemplateResponse("tree.html", _ctx(
        request, active_page="tree",
    ))


# ─── Demo Tree API (JSON endpoint for D3) ─────────────────────────

@router.get("/api/tree", response_model=TreeResponse)
async def demo_tree_api(
    db: AsyncSession = Depends(get_db),
):
    """Tree data for demo mode — same shape as /api/tree but no auth."""
    result = await db.execute(select(Person).where(Person.is_root == True))
    root = result.scalar_one_or_none()
    root_id = root.id if root else ""

    result = await db.execute(
        select(Person).where(Person.visibility != Visibility.hidden.value)
    )
    persons = result.scalars().all()
    visible_ids = {p.id for p in persons}

    result = await db.execute(select(ParentChild))
    parent_children = [
        r for r in result.scalars().all()
        if r.parent_id in visible_ids and r.child_id in visible_ids
    ]

    result = await db.execute(select(Partnership))
    partnerships = [
        r for r in result.scalars().all()
        if r.person_a_id in visible_ids and r.person_b_id in visible_ids
    ]

    return TreeResponse(
        root_id=root_id,
        persons=[person_to_summary(p) for p in persons],
        parent_child=[ParentChildResponse.model_validate(pc) for pc in parent_children],
        partnerships=[PartnershipResponse.model_validate(p) for p in partnerships],
    )


# ─── Demo People ──────────────────────────────────────────────────

@router.get("/people", response_class=HTMLResponse)
async def demo_people(
    request: Request,
    branch: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    query = select(Person).where(Person.visibility != Visibility.hidden.value)
    if branch:
        query = query.where(Person.branch == branch)
    query = query.order_by(Person.last_name, Person.first_name)
    result = await db.execute(query)
    persons = result.scalars().all()

    branch_result = await db.execute(
        select(Person.branch).where(Person.branch.isnot(None)).distinct()
    )
    branches = sorted([row[0] for row in branch_result.all() if row[0]])

    return templates.TemplateResponse("people.html", _ctx(
        request, active_page="people",
        persons=persons, branches=branches, branch_filter=branch,
    ))


# ─── Demo Person Detail ───────────────────────────────────────────

@router.get("/people/{person_id}", response_class=HTMLResponse)
async def demo_person_detail(
    person_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    from fastapi.responses import RedirectResponse

    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    if not person:
        return RedirectResponse("/demo/people", status_code=302)

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

    # Siblings
    parent_ids = [p.id for p in parents]
    siblings = []
    if parent_ids:
        result = await db.execute(
            select(Person).join(ParentChild, ParentChild.child_id == Person.id)
            .where(ParentChild.parent_id.in_(parent_ids), Person.id != person_id)
        )
        siblings = list({s.id: s for s in result.scalars().all()}.values())

    return templates.TemplateResponse("person.html", _ctx(
        request, active_page="people",
        person=person, parents=parents, children=children,
        partners=partners, siblings=siblings, can_edit=False,
    ))


# ─── Demo Person Card (sidebar for tree) ──────────────────────────

@router.get("/people/{person_id}/card", response_class=HTMLResponse)
async def demo_person_card(
    person_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    if not person:
        return HTMLResponse("<p>Person not found</p>")

    return templates.TemplateResponse("partials/person_sidebar.html", _ctx(
        request, person=person,
    ))


# ─── Demo Partials ────────────────────────────────────────────────

@router.get("/partials/people-grid", response_class=HTMLResponse)
async def demo_partial_people_grid(
    request: Request,
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
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
        request, persons=persons,
    ))


@router.get("/partials/media-gallery", response_class=HTMLResponse)
async def demo_partial_media_gallery(
    request: Request,
    person_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Media).where(Media.person_id == person_id).order_by(Media.created_at.desc())
    )
    media_list = result.scalars().all()

    return templates.TemplateResponse("partials/media_gallery.html", _ctx(
        request, media_list=media_list,
        can_upload=False, person_id=person_id,
    ))


@router.get("/partials/moments", response_class=HTMLResponse)
async def demo_partial_moments(
    request: Request,
    before: str | None = Query(None),
    person: str | None = Query(None),
    kind: str | None = Query(None),
    limit: int = Query(20),
    db: AsyncSession = Depends(get_db),
):
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
    query = query.where(Moment.visibility != "hidden")
    query = query.order_by(Moment.occurred_at.desc()).limit(limit)
    result = await db.execute(query)
    moments_orm = result.scalars().all()

    moments = []
    for m in moments_orm:
        card = await _build_demo_moment(db, m)
        moments.append(card)

    html_parts = []
    for m in moments:
        html_parts.append(
            templates.get_template("partials/moment_card.html").render(
                _ctx(request, m=m)
            )
        )

    if len(moments) >= limit:
        last_id = moments[-1]["id"]
        html_parts.append(
            f'<div hx-get="/demo/partials/moments?before={last_id}" '
            f'hx-trigger="revealed" hx-swap="afterend">'
            f'<div style="text-align:center;padding:20px;">'
            f'<div class="spinner" style="margin:0 auto;"></div></div></div>'
        )

    return HTMLResponse("".join(html_parts))


@router.get("/partials/comments/{moment_id}", response_class=HTMLResponse)
async def demo_partial_comments(
    moment_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
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
        request, comments=comments, moment_id=moment_id,
    ))


# ─── Helper ───────────────────────────────────────────────────────

async def _build_demo_moment(db: AsyncSession, moment: Moment) -> dict:
    """Build moment card data without requiring a current user."""
    from app.models.moments import MomentReaction

    poster = None
    if moment.posted_by:
        result = await db.execute(select(Person).where(Person.id == moment.posted_by))
        p = result.scalar_one_or_none()
        if p:
            poster = {"id": p.id, "display_name": p.display_name, "photo_url": p.photo_url}

    about = None
    result = await db.execute(select(Person).where(Person.id == moment.person_id))
    p = result.scalar_one_or_none()
    if p:
        about = {"id": p.id, "display_name": p.display_name, "photo_url": p.photo_url}

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

    result = await db.execute(
        select(MomentReaction.emoji, func.count(MomentReaction.id))
        .where(MomentReaction.moment_id == moment.id)
        .group_by(MomentReaction.emoji)
    )
    reactions = {row[0]: row[1] for row in result.all()}

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
        "my_reaction": None,
        "comment_count": comment_count,
        "created_at": moment.created_at.isoformat() if moment.created_at else None,
    }
