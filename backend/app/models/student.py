import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    class_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("classes.id"))
    student_number: Mapped[int] = mapped_column(SmallInteger)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)

