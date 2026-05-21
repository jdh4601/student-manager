"""SMS-71: 발표 데모용 대용량 시드.

실행 (호스트):
    DATABASE_URL=postgresql+asyncpg://sm:smpass@localhost:5432/student_manager \\
        python scripts/demo_seed.py

실행 (compose 내부):
    docker compose exec backend python /app/../scripts/demo_seed.py

규모:
    - 교사 1 (demo-teacher@example.com / password123)
    - 학급 1 (1학년 3반)
    - 학생 30
    - 학기 6 (최근 3개 학년도 × 1·2학기)
    - 과목 8
    - 성적 30×8×6 = 1440
    - 피드백 ~180
    - 상담 ~60

총 ~1700 도메인 이벤트. analytics-worker가 outbox → Kafka → agg_* 테이블을 갱신한다.
"""

from __future__ import annotations

import asyncio
import random
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

# scripts/ 에서 실행하므로 backend 경로 주입
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select  # noqa: E402

from app.database import async_session  # noqa: E402
from app.models import School, User  # noqa: E402
from app.models.class_ import Class  # noqa: E402
from app.models.counseling import Counseling  # noqa: E402
from app.models.feedback import Feedback  # noqa: E402
from app.models.grade import Grade  # noqa: E402
from app.models.semester import Semester  # noqa: E402
from app.models.student import Student  # noqa: E402
from app.models.subject import Subject  # noqa: E402
from app.utils.security import hash_password  # noqa: E402

random.seed(20260521)

NUM_STUDENTS = 30
SUBJECT_NAMES = ["국어", "수학", "영어", "사회", "과학", "체육", "음악", "미술"]
FEEDBACK_CATEGORIES = ["score", "behavior", "attendance", "attitude"]
LAST_NAMES = list("김이박최정강조윤장임한오서신권황안송류전홍문양손배백허남")
FIRST_NAMES = [
    "지은", "하준", "서연", "예준", "민서", "도윤", "지유", "주원",
    "수아", "지호", "유진", "건우", "지원", "현우", "다은", "시우",
    "윤서", "민준", "수빈", "지훈", "예린", "재민", "은우", "도현",
    "채원", "선우", "유나", "지안", "민찬", "서윤",
]


def _korean_name(idx: int) -> str:
    last = LAST_NAMES[idx % len(LAST_NAMES)]
    first = FIRST_NAMES[idx % len(FIRST_NAMES)]
    return f"{last}{first}"


async def _get_or_create_school(session) -> School:
    res = await session.execute(select(School).limit(1))
    school = res.scalar_one_or_none()
    if school is None:
        school = School(name="데모 초등학교")
        session.add(school)
        await session.flush()
    return school


async def _get_or_create_teacher(session, school: School) -> User:
    email = "demo-teacher@example.com"
    res = await session.execute(select(User).where(User.email == email))
    user = res.scalar_one_or_none()
    if user is None:
        user = User(
            school_id=school.id,
            email=email,
            hashed_password=hash_password("password123"),
            role="teacher",
            name="데모 교사",
        )
        session.add(user)
        await session.flush()
    return user


async def _ensure_semesters(session) -> list[Semester]:
    """최근 3년치 1·2학기."""
    base_year = 2026
    targets = [(y, t) for y in (base_year - 2, base_year - 1, base_year) for t in (1, 2)]
    existing = await session.execute(select(Semester))
    by_key = {(s.year, s.term): s for s in existing.scalars().all()}
    out: list[Semester] = []
    for year, term in targets:
        if (year, term) in by_key:
            out.append(by_key[(year, term)])
            continue
        sem = Semester(year=year, term=term)
        session.add(sem)
        await session.flush()
        out.append(sem)
    return out


async def _ensure_class(session, school: School, teacher: User) -> Class:
    name = "데모반"
    res = await session.execute(
        select(Class).where(
            Class.school_id == school.id,
            Class.name == name,
        )
    )
    cls = res.scalar_one_or_none()
    if cls:
        return cls
    cls = Class(
        school_id=school.id,
        name=name,
        grade=1,
        year=2026,
        teacher_id=teacher.id,
    )
    session.add(cls)
    await session.flush()
    return cls


async def _ensure_subjects(session, cls: Class) -> list[Subject]:
    res = await session.execute(select(Subject).where(Subject.class_id == cls.id))
    subjects = list(res.scalars().all())
    have = {s.name for s in subjects}
    for name in SUBJECT_NAMES:
        if name in have:
            continue
        s = Subject(class_id=cls.id, name=name)
        session.add(s)
        subjects.append(s)
    await session.flush()
    # 최신 순서 보장
    res = await session.execute(select(Subject).where(Subject.class_id == cls.id))
    return list(res.scalars().all())


async def _ensure_students(session, school: School, cls: Class) -> list[Student]:
    res = await session.execute(select(Student).where(Student.class_id == cls.id))
    existing = list(res.scalars().all())
    if len(existing) >= NUM_STUDENTS:
        return existing[:NUM_STUDENTS]

    out = list(existing)
    for i in range(len(existing) + 1, NUM_STUDENTS + 1):
        name = _korean_name(i)
        email = f"demo-student-{i:02d}@example.com"
        user = User(
            school_id=school.id,
            email=email,
            hashed_password=hash_password("password123"),
            role="student",
            name=name,
        )
        session.add(user)
        await session.flush()
        student = Student(
            user_id=user.id,
            class_id=cls.id,
            student_number=i,
            birth_date=date(2014, ((i % 12) + 1), ((i % 28) + 1)),
        )
        session.add(student)
        await session.flush()
        out.append(student)
    return out


async def _seed_grades(
    session,
    students: list[Student],
    subjects: list[Subject],
    semesters: list[Semester],
    teacher: User,
) -> int:
    res = await session.execute(select(Grade))
    if res.first() is not None:
        return 0  # 이미 시드됨 — idempotent

    count = 0
    for student in students:
        # 학생별 평균 능력치 (40-95)
        ability = random.uniform(40, 95)
        for subj in subjects:
            # 과목별 편차
            subj_bias = random.uniform(-8, 8)
            for sem in semesters:
                noise = random.uniform(-6, 6)
                score = max(0.0, min(100.0, ability + subj_bias + noise))
                session.add(
                    Grade(
                        student_id=student.id,
                        subject_id=subj.id,
                        semester_id=sem.id,
                        score=Decimal(f"{score:.1f}"),
                        created_by=teacher.id,
                    )
                )
                count += 1
    await session.flush()
    return count


async def _seed_feedbacks(session, students: list[Student], teacher: User) -> int:
    res = await session.execute(select(Feedback))
    if res.first() is not None:
        return 0

    today = date.today()
    count = 0
    for i, student in enumerate(students):
        # 학생당 평균 6개 피드백
        for _ in range(random.randint(4, 8)):
            cat = random.choice(FEEDBACK_CATEGORIES)
            offset = random.randint(0, 300)
            session.add(
                Feedback(
                    student_id=student.id,
                    teacher_id=teacher.id,
                    category=cat,
                    content=f"{cat} 관련 코멘트 — 학생{i + 1} (auto-seed)",
                    is_visible_to_student=False,
                    is_visible_to_parent=False,
                )
            )
            count += 1
        _ = today  # silence linter
        _ = offset
    await session.flush()
    return count


async def _seed_counselings(session, students: list[Student], teacher: User) -> int:
    res = await session.execute(select(Counseling))
    if res.first() is not None:
        return 0

    today = date.today()
    count = 0
    for student in students:
        # 학생당 평균 2회 상담
        for _ in range(random.randint(1, 3)):
            offset = random.randint(0, 200)
            session.add(
                Counseling(
                    student_id=student.id,
                    teacher_id=teacher.id,
                    date=today - timedelta(days=offset),
                    content="진로 및 학습 상담 (auto-seed).",
                    next_plan="다음 달 후속 면담.",
                    is_shared=True,
                )
            )
            count += 1
    await session.flush()
    return count


async def main() -> None:
    async with async_session() as session:
        school = await _get_or_create_school(session)
        teacher = await _get_or_create_teacher(session, school)
        semesters = await _ensure_semesters(session)
        cls = await _ensure_class(session, school, teacher)
        subjects = await _ensure_subjects(session, cls)
        students = await _ensure_students(session, school, cls)
        await session.commit()

        n_grades = await _seed_grades(session, students, subjects, semesters, teacher)
        n_feedbacks = await _seed_feedbacks(session, students, teacher)
        n_counselings = await _seed_counselings(session, students, teacher)
        await session.commit()

        total = n_grades + n_feedbacks + n_counselings
        print(
            f"demo_seed 완료: students={len(students)} semesters={len(semesters)} "
            f"subjects={len(subjects)} grades={n_grades} feedbacks={n_feedbacks} "
            f"counselings={n_counselings} TOTAL_NEW={total}"
        )
        print("교사 로그인: demo-teacher@example.com / password123")


if __name__ == "__main__":
    asyncio.run(main())
