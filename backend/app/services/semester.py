"""Shared semester helpers used by domains that need to bind events to a
specific (year, term) but lack an explicit FK on their own row.

The Semester model carries (year, term) only — no date range — so we pick
the most recent semester as a proxy for "current". Used by attendance,
feedback, and counseling outbox stagers.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.semester import Semester


async def current_semester_id(db: AsyncSession) -> uuid.UUID | None:
    """Return the latest semester id by (year DESC, term DESC), or None
    if no semester rows exist yet (early bootstrap)."""
    result = await db.execute(
        select(Semester.id)
        .order_by(Semester.year.desc(), Semester.term.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
