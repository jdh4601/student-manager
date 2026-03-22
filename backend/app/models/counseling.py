import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Counseling(Base):
    __tablename__ = "counselings"
    __table_args__ = (
        Index("ix_counselings_student_id", "student_id"),
        Index("ix_counselings_teacher_id", "teacher_id"),
        Index("ix_counselings_teacher_shared", "teacher_id", "is_shared"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id"))
    teacher_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    date: Mapped[date] = mapped_column(Date)
    content: Mapped[str] = mapped_column(Text)
    next_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    student = relationship("Student")
    teacher = relationship("User")

