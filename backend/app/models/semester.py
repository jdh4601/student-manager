import uuid

from sqlalchemy import SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Semester(Base):
    __tablename__ = "semesters"
    __table_args__ = (UniqueConstraint("year", "term", name="uq_semester_year_term"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    year: Mapped[int] = mapped_column(SmallInteger)
    term: Mapped[int] = mapped_column(SmallInteger)

