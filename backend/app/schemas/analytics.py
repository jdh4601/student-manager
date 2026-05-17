"""Pydantic schemas for analytics API responses (Design Spec §9.5)."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class OverallSummary(BaseModel):
    """Per-semester roll-up from analytics.agg_student_overall.

    Null fields mean no events have been projected yet (new student, or no
    grades/attendance/feedback in scope).
    """
    model_config = ConfigDict(from_attributes=True)

    avg_score: float | None
    total_score: float | None
    subject_count: int
    attendance_present_rate: float | None
    feedback_count: int


class SubjectOverview(BaseModel):
    """Per-subject roll-up from analytics.agg_student_subject, enriched with
    the human-readable name from the operational ``subjects`` table."""
    model_config = ConfigDict(from_attributes=True)

    subject_id: str
    name: str
    avg_score: float | None
    max_score: float | None
    min_score: float | None
    latest_rank: int | None
    sample_count: int


class StudentOverviewResponse(BaseModel):
    overall: OverallSummary | None
    subjects: list[SubjectOverview]
