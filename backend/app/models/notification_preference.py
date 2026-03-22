import uuid

from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    grade_input: Mapped[bool] = mapped_column(Boolean, default=True)
    feedback_created: Mapped[bool] = mapped_column(Boolean, default=True)
    counseling_updated: Mapped[bool] = mapped_column(Boolean, default=True)

    user = relationship("User")

