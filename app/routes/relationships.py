from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin, require_auth
from app.database import get_db
from app.models.person import Person
from app.models.relationships import ParentChild, Partnership
from app.schemas import (
    ParentChildCreate,
    ParentChildResponse,
    PartnershipCreate,
    PartnershipResponse,
    PartnershipUpdate,
)
from app.services.audit_service import log_audit

router = APIRouter(prefix="/api/relationships", tags=["relationships"])


# --- ParentChild ---

@router.post("/parent-child", response_model=ParentChildResponse, status_code=status.HTTP_201_CREATED)
async def create_parent_child(
    body: ParentChildCreate,
    current_user: Person = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if body.parent_id == body.child_id:
        raise HTTPException(status_code=400, detail="Parent and child cannot be the same person")

    # Verify both persons exist
    for pid in (body.parent_id, body.child_id):
        result = await db.execute(select(Person).where(Person.id == pid))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Person {pid} not found")

    pc = ParentChild(
        parent_id=body.parent_id,
        child_id=body.child_id,
        kind=body.kind,
        confidence=body.confidence,
        source=body.source,
        source_detail=body.source_detail,
        notes=body.notes,
        start_date=body.start_date,
        end_date=body.end_date,
        created_by=current_user.id,
    )
    db.add(pc)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="This parent-child relationship already exists")

    await log_audit(db, current_user.id, "create", "parent_child", pc.id,
                    new_value={"parent_id": pc.parent_id, "child_id": pc.child_id, "kind": pc.kind})

    return ParentChildResponse.model_validate(pc)


@router.delete("/parent-child/{rel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_parent_child(
    rel_id: str,
    current_user: Person = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ParentChild).where(ParentChild.id == rel_id))
    pc = result.scalar_one_or_none()
    if not pc:
        raise HTTPException(status_code=404, detail="Relationship not found")

    await log_audit(db, current_user.id, "delete", "parent_child", pc.id,
                    old_value={"parent_id": pc.parent_id, "child_id": pc.child_id})

    await db.delete(pc)
    await db.flush()


# --- Partnership ---

@router.post("/partnership", response_model=PartnershipResponse, status_code=status.HTTP_201_CREATED)
async def create_partnership(
    body: PartnershipCreate,
    current_user: Person = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if body.person_a_id == body.person_b_id:
        raise HTTPException(status_code=400, detail="Cannot create partnership with self")

    # Enforce canonical ordering
    a_id, b_id = sorted([body.person_a_id, body.person_b_id])

    # Verify both persons exist
    for pid in (a_id, b_id):
        result = await db.execute(select(Person).where(Person.id == pid))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Person {pid} not found")

    partnership = Partnership(
        person_a_id=a_id,
        person_b_id=b_id,
        kind=body.kind,
        status=body.status,
        start_date=body.start_date,
        start_date_precision=body.start_date_precision,
        end_date=body.end_date,
        end_date_precision=body.end_date_precision,
        source=body.source,
        notes=body.notes,
        created_by=current_user.id,
    )
    db.add(partnership)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="This partnership already exists")

    await log_audit(db, current_user.id, "create", "partnership", partnership.id,
                    new_value={"person_a_id": a_id, "person_b_id": b_id, "kind": body.kind})

    return PartnershipResponse.model_validate(partnership)


@router.put("/partnership/{rel_id}", response_model=PartnershipResponse)
async def update_partnership(
    rel_id: str,
    body: PartnershipUpdate,
    current_user: Person = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Partnership).where(Partnership.id == rel_id))
    partnership = result.scalar_one_or_none()
    if not partnership:
        raise HTTPException(status_code=404, detail="Partnership not found")

    old_data = {"status": partnership.status}
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(partnership, field, value)

    await db.flush()
    await log_audit(db, current_user.id, "update", "partnership", partnership.id,
                    old_value=old_data,
                    new_value=update_data)

    return PartnershipResponse.model_validate(partnership)


@router.delete("/partnership/{rel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_partnership(
    rel_id: str,
    current_user: Person = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Partnership).where(Partnership.id == rel_id))
    partnership = result.scalar_one_or_none()
    if not partnership:
        raise HTTPException(status_code=404, detail="Partnership not found")

    await log_audit(db, current_user.id, "delete", "partnership", partnership.id,
                    old_value={"person_a_id": partnership.person_a_id,
                               "person_b_id": partnership.person_b_id})

    await db.delete(partnership)
    await db.flush()
