import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import os
from app.database import async_session, Base, engine
from app.models import School, User
from app.models.subject import Subject
from app.models.class_ import Class
from app.utils.security import hash_password


async def seed() -> None:
    # Create tables (dev/test convenience; in prod use Alembic migrations)
    # Only run create_all for sqlite or when explicitly allowed.
    backend = getattr(getattr(engine, "url", None), "get_backend_name", lambda: "")( ) if hasattr(engine, "url") else ""
    try:
        backend = engine.url.get_backend_name()  # type: ignore[attr-defined]
    except Exception:
        backend = str(getattr(engine, "url", ""))
    allow_create_all = os.getenv("RUN_CREATE_ALL", "").lower() in {"1", "true", "yes"}
    if "sqlite" in str(backend).lower() or allow_create_all:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:  # type: AsyncSession
        # Seed a default school and teacher if not present
        result = await session.execute(select(School).limit(1))
        school = result.scalar_one_or_none()
        if school is None:
            school = School(name="Demo School")
            session.add(school)
            await session.flush()

        result = await session.execute(select(User).where(User.email == "teacher@example.com"))
        teacher = result.scalar_one_or_none()
        if teacher is None:
            teacher = User(
                school_id=school.id,
                email="teacher@example.com",
                hashed_password=hash_password("password123"),
                role="teacher",
                name="교사",
            )
            session.add(teacher)

        # Seed default subjects for all classes in the school
        DEFAULT_SUBJECTS = ["국어", "수학", "영어", "사회", "과학", "체육", "음악", "미술"]
        result = await session.execute(select(Class).where(Class.school_id == school.id))
        classes = result.scalars().all()
        for cls in classes:
            existing = await session.execute(select(Subject).where(Subject.class_id == cls.id))
            if existing.scalars().first() is None:
                for subj_name in DEFAULT_SUBJECTS:
                    session.add(Subject(class_id=cls.id, name=subj_name))

        await session.commit()
        print("Seed complete:", {"school": school.name, "teacher": teacher.email})


if __name__ == "__main__":
    asyncio.run(seed())
