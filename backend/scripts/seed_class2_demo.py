"""데모용: 2반에 학생을 ~30명까지 채우고 과목별 랜덤 성적을 생성한다.

성적은 다양한 분포가 나오도록 학생별 기초 능력치 + 과목별 노이즈로 샘플링하며,
각 성적 INSERT마다 운영 코드와 동일한 outbox 행을 같은 트랜잭션에 넣는다.
실행 중인 analytics-worker가 outbox를 소비해 analytics.agg_* 를 갱신하므로
대시보드 분포 차트까지 자동 반영된다.

컨테이너에서 실행:
    docker exec -i sm-backend python - < backend/scripts/seed_class2_demo.py
"""

import asyncio
import random
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from app.database import async_session
from app.models.class_ import Class
from app.models.grade import Grade
from app.models.student import Student
from app.models.subject import Subject
from app.models.semester import Semester
from app.models.user import User
from app.services.grade import _grade_outbox_row
from app.utils.grade_calculator import calculate_grade
from app.utils.security import hash_password

TARGET_TOTAL = 30
CLASS_NAME = "2반"

SURNAMES = list("김이박최정강조윤장임한오서신권황안송류전홍고문양손배백허유남심노")
GIVEN = [
    "민준", "서연", "도윤", "지우", "예준", "하은", "주원", "지유", "지호", "수아",
    "준우", "서아", "건우", "하윤", "현우", "지민", "우진", "채원", "선우", "다은",
    "유준", "은서", "정우", "예린", "시우", "유나", "지훈", "소율", "준서", "윤서",
]


def sample_score() -> int:
    """다양한 분포(저·중·고)를 위해 혼합 가우시안에서 점수를 뽑는다."""
    roll = random.random()
    if roll < 0.15:
        mu, sigma = 54, 9   # 하위권
    elif roll < 0.80:
        mu, sigma = 76, 10  # 중위권
    else:
        mu, sigma = 92, 5   # 상위권
    return max(0, min(100, round(random.gauss(mu, sigma))))


async def main() -> None:
    async with async_session() as db:
        cls = (
            await db.execute(select(Class).where(Class.name == CLASS_NAME))
        ).scalars().first()
        if cls is None:
            raise SystemExit(f"'{CLASS_NAME}' 학급을 찾을 수 없습니다.")

        teacher_id = cls.teacher_id
        if teacher_id is None:
            teacher_id = (
                await db.execute(
                    select(User.id).where(
                        User.school_id == cls.school_id, User.role == "teacher"
                    )
                )
            ).scalars().first()
        if teacher_id is None:
            raise SystemExit("성적 작성자(교사)를 찾을 수 없습니다.")

        subjects = (
            await db.execute(select(Subject).where(Subject.class_id == cls.id))
        ).scalars().all()
        if not subjects:
            raise SystemExit(f"'{CLASS_NAME}'에 과목이 없습니다.")

        semester = (
            await db.execute(
                select(Semester).order_by(Semester.year.desc(), Semester.term.desc())
            )
        ).scalars().first()
        if semester is None:
            raise SystemExit("학기가 없습니다.")

        existing_count = (
            await db.execute(
                select(func.count()).select_from(Student).where(Student.class_id == cls.id)
            )
        ).scalar_one()
        max_num = (
            await db.execute(
                select(func.max(Student.student_number)).where(Student.class_id == cls.id)
            )
        ).scalar() or 0

        to_add = max(0, TARGET_TOTAL - existing_count)
        if to_add == 0:
            print(f"이미 {existing_count}명 — 추가 없음.")
            return

        pw = hash_password("password123")
        created = 0
        for i in range(to_add):
            number = max_num + 1 + i
            name = random.choice(SURNAMES) + random.choice(GIVEN)
            user = User(
                school_id=cls.school_id,
                email=f"s2-{number}-{uuid.uuid4().hex[:6]}@example.com",
                hashed_password=pw,
                role="student",
                name=name,
                is_active=True,
            )
            db.add(user)
            await db.flush()

            student = Student(
                user_id=user.id,
                class_id=cls.id,
                student_number=number,
                gender=random.choice(["male", "female"]),
                birth_date=date(2010, random.randint(1, 12), random.randint(1, 28)),
            )
            db.add(student)
            await db.flush()

            for subject in subjects:
                score = sample_score()
                grade = Grade(
                    student_id=student.id,
                    subject_id=subject.id,
                    semester_id=semester.id,
                    score=Decimal(str(score)),
                    grade_rank=calculate_grade(score),
                    created_by=teacher_id,
                )
                db.add(grade)
                await db.flush()  # populate grade.id before staging outbox row
                db.add(_grade_outbox_row(grade, op="INSERT"))
            created += 1

        await db.commit()
        print(
            f"완료: {CLASS_NAME}에 {created}명 추가 (총 {existing_count + created}명), "
            f"과목 {len(subjects)}개 × {created}명 = {len(subjects) * created} 성적 생성, "
            f"학기={semester.year}-{semester.term}"
        )


if __name__ == "__main__":
    asyncio.run(main())
