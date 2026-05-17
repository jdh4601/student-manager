"""Dependency factories for analytics-side repos.

Kept separate from operational dependencies so tests can override just the
analytics repo without touching the DB session dependency.
"""
from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.db import get_db
from app.services.analytics_query import (
    ClassDistributionRepo,
    PostgresClassDistributionRepo,
    PostgresStudentOverviewRepo,
    StudentOverviewRepo,
)


def get_student_overview_repo(
    db: AsyncSession = Depends(get_db),
) -> StudentOverviewRepo:
    return PostgresStudentOverviewRepo(db)


def get_class_distribution_repo(
    db: AsyncSession = Depends(get_db),
) -> ClassDistributionRepo:
    return PostgresClassDistributionRepo(db)
