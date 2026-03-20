# Student Manager Full Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a full-stack student grade & counseling management SaaS (FastAPI + React 18) following the Design Spec v2.0

**Architecture:** FastAPI backend with SQLAlchemy 2.0 ORM, PostgreSQL (Supabase), JWT auth. React 18 frontend with TypeScript, Tailwind CSS, Zustand, TanStack Query, Recharts. Multi-tenant isolation via `school_id` row-level filtering. Client-side file generation (SheetJS, jsPDF).

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, pytest / React 18, TypeScript, Vite, Tailwind CSS, Zustand, TanStack Query, Recharts

**Spec:** `docs/design-spec.md` (v2.0 확정)
**PRD:** `docs/PRD.md` (v2.0 확정)

---

## File Structure

### Backend

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                        # FastAPI app, CORS, router includes
│   ├── config.py                      # Settings via pydantic-settings
│   ├── database.py                    # async engine, sessionmaker, Base
│   ├── dependencies/
│   │   ├── __init__.py
│   │   ├── auth.py                    # get_current_user, require_role, require_teacher_of_student
│   │   └── db.py                      # get_db async generator
│   ├── models/
│   │   ├── __init__.py                # re-export all models for Alembic
│   │   ├── school.py                  # School
│   │   ├── user.py                    # User
│   │   ├── class_.py                  # Class (학급)
│   │   ├── student.py                 # Student
│   │   ├── parent_student.py          # ParentStudent (M:N)
│   │   ├── subject.py                 # Subject
│   │   ├── semester.py                # Semester (global)
│   │   ├── grade.py                   # Grade (성적)
│   │   ├── attendance.py              # Attendance (출결)
│   │   ├── special_note.py            # SpecialNote (특기사항)
│   │   ├── feedback.py                # Feedback
│   │   ├── counseling.py              # Counseling (상담)
│   │   ├── notification.py            # Notification
│   │   └── notification_preference.py # NotificationPreference
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py                    # LoginRequest, TokenResponse
│   │   ├── user.py                    # UserCreate, UserResponse, StudentCreate, ParentCreate
│   │   ├── class_.py                  # ClassCreate, ClassResponse
│   │   ├── semester.py                # SemesterCreate, SemesterResponse
│   │   ├── subject.py                 # SubjectCreate, SubjectResponse
│   │   ├── grade.py                   # GradeCreate, GradeResponse, GradeSummary, BulkGradeRequest
│   │   ├── student.py                 # StudentResponse, StudentUpdate
│   │   ├── attendance.py              # AttendanceCreate, AttendanceResponse
│   │   ├── special_note.py            # SpecialNoteCreate, SpecialNoteResponse
│   │   ├── feedback.py                # FeedbackCreate, FeedbackResponse
│   │   ├── counseling.py              # CounselingCreate, CounselingResponse
│   │   ├── notification.py            # NotificationResponse, NotificationPreferenceUpdate
│   │   └── common.py                  # PaginatedResponse, ErrorResponse
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py                    # /auth/*
│   │   ├── users.py                   # /users/*
│   │   ├── semesters.py               # /semesters
│   │   ├── classes.py                 # /classes/*, /classes/{id}/subjects/*
│   │   ├── grades.py                  # /grades/*
│   │   ├── students.py                # /students/{id}/*
│   │   ├── feedbacks.py               # /feedbacks/*
│   │   ├── counselings.py             # /counselings/*
│   │   ├── notifications.py           # /notifications/*
│   │   └── imports.py                 # /import/*
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth.py                    # authenticate_user, create_tokens, refresh_token
│   │   ├── user.py                    # create_student, create_parent, list_students, deactivate
│   │   ├── grade.py                   # create_grade, update_grade, bulk_grades, get_summary
│   │   ├── student.py                 # get_student, update_student, attendance CRUD, special notes
│   │   ├── feedback.py                # create_feedback, update_feedback, delete_feedback, list
│   │   ├── counseling.py              # create_counseling, update_counseling, list/search
│   │   ├── notification.py            # create_notification, mark_read, mark_all_read, preferences
│   │   └── import_.py                 # import_students_csv, import_grades_csv
│   └── utils/
│       ├── __init__.py
│       ├── grade_calculator.py        # calculate_grade(score) -> rank
│       └── security.py                # hash_password, verify_password, create_jwt, decode_jwt
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/                      # migration files
├── alembic.ini
├── seed.py                            # Alembic seed script (School + Teacher)
├── requirements.txt
├── pyproject.toml
└── tests/
    ├── __init__.py
    ├── conftest.py                    # test DB, client fixture, auth helpers
    ├── test_auth.py
    ├── test_users.py
    ├── test_semesters.py
    ├── test_classes.py
    ├── test_grades.py
    ├── test_students.py
    ├── test_feedbacks.py
    ├── test_counselings.py
    ├── test_notifications.py
    └── test_imports.py
```

### Frontend

```
frontend/
├── src/
│   ├── main.tsx                       # ReactDOM.createRoot
│   ├── App.tsx                        # Router, QueryClient, global providers
│   ├── api/
│   │   ├── client.ts                  # axios instance, interceptors (refresh token)
│   │   ├── auth.ts                    # login, logout, refresh, getMe
│   │   ├── semesters.ts
│   │   ├── classes.ts
│   │   ├── subjects.ts
│   │   ├── users.ts
│   │   ├── grades.ts
│   │   ├── students.ts
│   │   ├── feedbacks.ts
│   │   ├── counselings.ts
│   │   └── notifications.ts
│   ├── components/
│   │   ├── ui/                        # Button, Input, Select, Modal, Toast, Badge
│   │   ├── layout/
│   │   │   ├── AppLayout.tsx          # sidebar + header + main
│   │   │   ├── Sidebar.tsx
│   │   │   └── Header.tsx             # notification bell, user menu
│   │   ├── auth/
│   │   │   ├── LoginForm.tsx
│   │   │   └── ProtectedRoute.tsx
│   │   ├── grades/
│   │   │   ├── GradeTable.tsx         # editable grade input grid
│   │   │   ├── GradeSummary.tsx
│   │   │   └── RadarChart.tsx
│   │   ├── students/
│   │   │   ├── StudentList.tsx
│   │   │   ├── StudentDetail.tsx
│   │   │   ├── AttendanceForm.tsx
│   │   │   └── SpecialNoteForm.tsx
│   │   ├── feedbacks/
│   │   │   ├── FeedbackForm.tsx
│   │   │   └── FeedbackList.tsx
│   │   ├── counselings/
│   │   │   ├── CounselingForm.tsx
│   │   │   └── CounselingList.tsx
│   │   └── notifications/
│   │       ├── NotificationBell.tsx
│   │       └── NotificationList.tsx
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── useGrades.ts
│   │   ├── useStudents.ts
│   │   ├── useFeedbacks.ts
│   │   ├── useCounselings.ts
│   │   └── useNotifications.ts
│   ├── stores/
│   │   ├── authStore.ts               # access_token, user info, role
│   │   └── notificationStore.ts       # unread_count
│   ├── pages/
│   │   ├── LoginPage.tsx
│   │   ├── DashboardPage.tsx
│   │   ├── SetupPage.tsx              # Semester/Class/Subject creation
│   │   ├── StudentListPage.tsx
│   │   ├── StudentDetailPage.tsx
│   │   ├── GradesPage.tsx
│   │   ├── FeedbackPage.tsx
│   │   ├── CounselingPage.tsx
│   │   └── NotificationsPage.tsx
│   ├── utils/
│   │   ├── gradeCalculator.ts         # same logic as backend
│   │   └── formatters.ts              # date, number formatters
│   └── types/
│       └── index.ts                   # shared TypeScript interfaces
├── package.json
├── tsconfig.json
├── tailwind.config.ts
├── vite.config.ts
├── postcss.config.js
└── index.html
```

---

## Phase 1: Backend Foundation (Sprint 0 — Project Setup)

### Task 1: Backend Project Scaffolding

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/.env.example`

- [ ] **Step 1: Create backend directory and pyproject.toml**

```bash
mkdir -p backend/app backend/tests
```

```toml
# backend/pyproject.toml
[project]
name = "student-manager-backend"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 88
target-version = "py311"
```

- [ ] **Step 2: Create requirements.txt**

```txt
# backend/requirements.txt
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
alembic==1.14.1
pydantic[email]==2.10.4
pydantic-settings==2.7.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.19
slowapi==0.1.9
httpx==0.28.1

# dev
pytest==8.3.4
pytest-asyncio==0.25.0
pytest-cov==6.0.0
ruff==0.8.6
aiosqlite==0.21.0
```

- [ ] **Step 3: Create config.py with pydantic-settings**

```python
# backend/app/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://localhost:5432/student_manager"
    test_database_url: str = "sqlite+aiosqlite:///./test.db"
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    allowed_origins: list[str] = ["http://localhost:5173"]

    model_config = {"env_file": ".env"}


settings = Settings()
```

- [ ] **Step 4: Create database.py with async engine**

```python
# backend/app/database.py
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 5: Create main.py with FastAPI app and custom error handler**

```python
# backend/app/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings


class AppException(Exception):
    """Custom exception with machine-readable error code."""
    def __init__(self, status_code: int, detail: str, code: str):
        self.status_code = status_code
        self.detail = detail
        self.code = code


app = FastAPI(title="Student Manager API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
    )


@app.get("/health")
async def health_check():
    return {"status": "ok"}
```

> **Note:** All API error responses use `AppException` to return `{ "detail": "...", "code": "ERROR_CODE" }` per Design Spec §3 공통 규칙. Never use plain `HTTPException` for business errors.

- [ ] **Step 6: Create .env.example and app/__init__.py**

```bash
# backend/.env.example
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/student_manager
SECRET_KEY=change-me-in-production
ALLOWED_ORIGINS=["http://localhost:5173"]
```

```python
# backend/app/__init__.py
```

- [ ] **Step 7: Create test conftest.py with async test DB**

```python
# backend/tests/conftest.py
import asyncio
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.dependencies.db import get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

engine_test = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_test = async_sessionmaker(engine_test, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_test() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

- [ ] **Step 8: Create db dependency**

```python
# backend/app/dependencies/__init__.py
```

```python
# backend/app/dependencies/db.py
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
```

- [ ] **Step 9: Run health check test to verify setup**

```python
# backend/tests/test_health.py
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

Run: `cd backend && pip install -r requirements.txt && pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git init
git add backend/
git commit -m "feat(backend): scaffold FastAPI project with async DB, config, and test setup"
```

---

### Task 2: SQLAlchemy Models — All Entities

**Files:**
- Create: `backend/app/models/school.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/class_.py`
- Create: `backend/app/models/student.py`
- Create: `backend/app/models/parent_student.py`
- Create: `backend/app/models/subject.py`
- Create: `backend/app/models/semester.py`
- Create: `backend/app/models/grade.py`
- Create: `backend/app/models/attendance.py`
- Create: `backend/app/models/special_note.py`
- Create: `backend/app/models/feedback.py`
- Create: `backend/app/models/counseling.py`
- Create: `backend/app/models/notification.py`
- Create: `backend/app/models/notification_preference.py`
- Create: `backend/app/models/__init__.py`
- Test: `backend/tests/test_models.py`

- [ ] **Step 1: Write test — all models can create tables without error**

```python
# backend/tests/test_models.py
import pytest
from sqlalchemy import inspect

from app.database import Base


@pytest.mark.asyncio
async def test_all_tables_created(setup_db):
    """All 14 entity tables should be created from models."""
    from app.models import (  # noqa: F401 — triggers registration
        Attendance, Class, Counseling, Feedback, Grade,
        Notification, NotificationPreference, ParentStudent,
        School, Semester, SpecialNote, Student, Subject, User,
    )
    from tests.conftest import engine_test

    async with engine_test.connect() as conn:
        table_names = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )

    expected = {
        "schools", "users", "classes", "students", "parent_students",
        "subjects", "semesters", "grades", "attendances", "special_notes",
        "feedbacks", "counselings", "notifications", "notification_preferences",
    }
    assert expected.issubset(set(table_names))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_models.py -v`
Expected: FAIL — ImportError (models don't exist yet)

- [ ] **Step 3: Implement School and User models**

```python
# backend/app/models/school.py
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class School(Base):
    __tablename__ = "schools"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    subscription_status: Mapped[str] = mapped_column(String(20), default="trial")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="school")
    classes: Mapped[list["Class"]] = relationship(back_populates="school")
```

```python
# backend/app/models/user.py
import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(10))  # teacher | student | parent
    name: Mapped[str] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    school: Mapped["School"] = relationship(back_populates="users")
```

- [ ] **Step 4: Implement Class, Student, ParentStudent, Subject, Semester models**

```python
# backend/app/models/class_.py
import uuid

from sqlalchemy import String, SmallInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Class(Base):
    __tablename__ = "classes"
    __table_args__ = (UniqueConstraint("school_id", "grade", "name", "year"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"))
    teacher_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(50))
    grade: Mapped[int] = mapped_column(SmallInteger)
    year: Mapped[int] = mapped_column(SmallInteger)

    school: Mapped["School"] = relationship(back_populates="classes")
    teacher: Mapped["User"] = relationship()
    students: Mapped[list["Student"]] = relationship(back_populates="class_")
    subjects: Mapped[list["Subject"]] = relationship(back_populates="class_")
```

```python
# backend/app/models/student.py
import uuid
from datetime import date

from sqlalchemy import SmallInteger, Date, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True)
    class_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("classes.id"))
    student_number: Mapped[int] = mapped_column(SmallInteger)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    user: Mapped["User"] = relationship()
    class_: Mapped["Class"] = relationship(back_populates="students")

    __table_args__ = (Index("ix_students_class_id", "class_id"),)
```

```python
# backend/app/models/parent_student.py
import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ParentStudent(Base):
    __tablename__ = "parent_students"
    __table_args__ = (UniqueConstraint("parent_id", "student_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    parent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id"))

    parent: Mapped["User"] = relationship()
    student: Mapped["Student"] = relationship()
```

```python
# backend/app/models/subject.py
import uuid

from sqlalchemy import String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (UniqueConstraint("class_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    class_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("classes.id"))
    name: Mapped[str] = mapped_column(String(50))

    class_: Mapped["Class"] = relationship(back_populates="subjects")
```

```python
# backend/app/models/semester.py
import uuid

from sqlalchemy import SmallInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Semester(Base):
    __tablename__ = "semesters"
    __table_args__ = (UniqueConstraint("year", "term"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    year: Mapped[int] = mapped_column(SmallInteger)
    term: Mapped[int] = mapped_column(SmallInteger)
```

- [ ] **Step 5: Implement Grade, Attendance, SpecialNote models**

```python
# backend/app/models/grade.py
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Numeric, SmallInteger, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Grade(Base):
    __tablename__ = "grades"
    __table_args__ = (
        UniqueConstraint("student_id", "subject_id", "semester_id"),
        CheckConstraint("score IS NULL OR (score >= 0 AND score <= 100)", name="ck_grade_score_range"),
        Index("ix_grades_student_semester", "student_id", "semester_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id"))
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"))
    semester_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("semesters.id"))
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    grade_rank: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student: Mapped["Student"] = relationship()
    subject: Mapped["Subject"] = relationship()
    semester: Mapped["Semester"] = relationship()
```

```python
# backend/app/models/attendance.py
import uuid
from datetime import date

from sqlalchemy import String, Text, Date, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Attendance(Base):
    __tablename__ = "attendances"
    __table_args__ = (
        UniqueConstraint("student_id", "date"),
        Index("ix_attendances_student_date", "student_id", "date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id"))
    date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(15))  # present|absent|late|early_leave
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    student: Mapped["Student"] = relationship()
```

```python
# backend/app/models/special_note.py
import uuid
from datetime import datetime

from sqlalchemy import Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SpecialNote(Base):
    __tablename__ = "special_notes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id"))
    content: Mapped[str] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student: Mapped["Student"] = relationship()
    creator: Mapped["User"] = relationship()
```

- [ ] **Step 6: Implement Feedback, Counseling, Notification, NotificationPreference models**

```python
# backend/app/models/feedback.py
import uuid
from datetime import datetime

from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Feedback(Base):
    __tablename__ = "feedbacks"
    __table_args__ = (Index("ix_feedbacks_student_teacher", "student_id", "teacher_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id"))
    teacher_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    category: Mapped[str] = mapped_column(String(15))  # score|behavior|attendance|attitude
    content: Mapped[str] = mapped_column(Text)
    is_visible_to_student: Mapped[bool] = mapped_column(Boolean, default=False)
    is_visible_to_parent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student: Mapped["Student"] = relationship()
    teacher: Mapped["User"] = relationship()
```

```python
# backend/app/models/counseling.py
import uuid
from datetime import date, datetime

from sqlalchemy import Text, Boolean, Date, DateTime, ForeignKey, Index
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
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student: Mapped["Student"] = relationship()
    teacher: Mapped["User"] = relationship()
```

```python
# backend/app/models/notification.py
import uuid
from datetime import datetime

from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_recipient_read", "recipient_id", "is_read"),
        Index("ix_notifications_recipient_created", "recipient_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    recipient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String(30))  # grade_input|feedback_created|counseling_updated
    message: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    related_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    related_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    recipient: Mapped["User"] = relationship()
```

```python
# backend/app/models/notification_preference.py
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

    user: Mapped["User"] = relationship()
```

- [ ] **Step 7: Create models/__init__.py to re-export all models**

```python
# backend/app/models/__init__.py
from app.models.school import School
from app.models.user import User
from app.models.class_ import Class
from app.models.student import Student
from app.models.parent_student import ParentStudent
from app.models.subject import Subject
from app.models.semester import Semester
from app.models.grade import Grade
from app.models.attendance import Attendance
from app.models.special_note import SpecialNote
from app.models.feedback import Feedback
from app.models.counseling import Counseling
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference

__all__ = [
    "School", "User", "Class", "Student", "ParentStudent",
    "Subject", "Semester", "Grade", "Attendance", "SpecialNote",
    "Feedback", "Counseling", "Notification", "NotificationPreference",
]
```

- [ ] **Step 8: Run model tests to verify they pass**

Run: `cd backend && pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add backend/app/models/
git commit -m "feat(models): add all 14 SQLAlchemy entity models per Design Spec v2.0"
```

---

### Task 3: Alembic Setup + Initial Migration

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`

- [ ] **Step 1: Initialize Alembic**

```bash
cd backend && alembic init alembic
```

- [ ] **Step 2: Configure alembic/env.py for async + import all models**

Update `alembic/env.py`:
- Set `target_metadata = Base.metadata`
- Import `from app.models import *` to register models
- Use async engine from `app.config.settings.database_url`

- [ ] **Step 3: Update alembic.ini**

Set `sqlalchemy.url` to empty (loaded from env.py).

- [ ] **Step 4: Generate initial migration**

```bash
cd backend && alembic revision --autogenerate -m "initial schema: all 14 tables"
```

- [ ] **Step 5: Verify migration file has all tables**

Inspect the generated migration. Confirm all 14 tables present.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/ backend/alembic.ini
git commit -m "feat(db): add Alembic setup with initial migration for all entities"
```

---

### Task 4: Security Utilities

**Files:**
- Create: `backend/app/utils/__init__.py`
- Create: `backend/app/utils/security.py`
- Create: `backend/app/utils/grade_calculator.py`
- Test: `backend/tests/test_utils.py`

- [ ] **Step 1: Write tests for security utilities**

```python
# backend/tests/test_utils.py
import pytest

from app.utils.security import hash_password, verify_password, create_access_token, decode_token
from app.utils.grade_calculator import calculate_grade


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "testpass123"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed) is True

    def test_wrong_password(self):
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False


class TestJWT:
    def test_create_and_decode(self):
        data = {"sub": "user-123", "role": "teacher", "school_id": "school-456"}
        token = create_access_token(data)
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["role"] == "teacher"

    def test_invalid_token(self):
        payload = decode_token("invalid.token.here")
        assert payload is None


class TestGradeCalculator:
    @pytest.mark.parametrize("score,expected_rank", [
        (100, 1), (96, 1), (95, 2), (89, 2), (88, 3),
        (77, 3), (76, 4), (60, 4), (59, 5), (40, 5),
        (39, 6), (23, 6), (22, 7), (11, 7), (10, 8),
        (4, 8), (3, 9), (0, 9),
    ])
    def test_grade_calculation(self, score: int, expected_rank: int):
        assert calculate_grade(score) == expected_rank
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_utils.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement security.py**

```python
# backend/app/utils/security.py
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    to_encode["exp"] = expire
    to_encode["type"] = "refresh"
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None
```

- [ ] **Step 4: Implement grade_calculator.py**

```python
# backend/app/utils/grade_calculator.py
GRADE_CUTOFFS = [96, 89, 77, 60, 40, 23, 11, 4]


def calculate_grade(score: float) -> int:
    """Calculate 9-grade rank from raw score (원점수 기준)."""
    for rank, cutoff in enumerate(GRADE_CUTOFFS, start=1):
        if score >= cutoff:
            return rank
    return 9
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_utils.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/utils/ backend/tests/test_utils.py
git commit -m "feat(utils): add password hashing, JWT, and grade calculator utilities"
```

---

### Task 5: Notification Service Stub (Early Dependency)

> **Why here:** Grade (Task 10), Feedback (Task 20), Counseling (Task 22) all create notifications as side-effects. The notification service must exist before those tasks, even though the notification *router* comes later in Task 23.

**Files:**
- Create: `backend/app/services/notification.py`

- [ ] **Step 1: Create notification service with core create function**

```python
# backend/app/services/notification.py
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference


async def create_notification(
    db: AsyncSession,
    *,
    recipient_id: uuid.UUID,
    type: str,
    message: str,
    related_id: uuid.UUID | None = None,
    related_type: str | None = None,
) -> Notification | None:
    """Create a notification if the recipient's preference allows it.

    Returns the Notification if created, None if suppressed by preference.
    """
    # Check preference
    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == recipient_id)
    )
    pref = result.scalar_one_or_none()

    if pref is not None:
        pref_map = {
            "grade_input": pref.grade_input,
            "feedback_created": pref.feedback_created,
            "counseling_updated": pref.counseling_updated,
        }
        if not pref_map.get(type, True):
            return None

    notification = Notification(
        recipient_id=recipient_id,
        type=type,
        message=message,
        related_id=related_id,
        related_type=related_type,
    )
    db.add(notification)
    return notification
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/notification.py
git commit -m "feat(notifications): add notification service stub for side-effect usage"
```

---

### Task 6: Common Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/common.py`
- Create: `backend/app/schemas/auth.py`

- [ ] **Step 1: Create common schemas**

```python
# backend/app/schemas/common.py
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    total: int
    items: list[T]


class ErrorResponse(BaseModel):
    detail: str
    code: str
```

- [ ] **Step 2: Create auth schemas**

```python
# backend/app/schemas/auth.py
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: str
    name: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    school_id: str
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/
git commit -m "feat(schemas): add common and auth Pydantic schemas"
```

---

### Task 6: Auth Dependencies + Shared Test Fixtures

**Files:**
- Create: `backend/app/dependencies/auth.py`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: Implement auth dependency**

```python
# backend/app/dependencies/auth.py
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.db import get_db
from app.models.user import User
from app.utils.security import decode_token

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="계정이 비활성화되었습니다." if user and not user.is_active else "Invalid token",
        )
    return user


def require_role(*roles: str):
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="권한이 부족합니다.")
        return current_user
    return role_checker
```

- [ ] **Step 2: Add all shared test fixtures to conftest.py**

> **Critical:** These fixtures are used by ALL subsequent test files. Define them here once.

Add to `tests/conftest.py`:

```python
from app.models import School, User, Class, Student, Semester, Subject
from app.utils.security import hash_password, create_access_token


@pytest.fixture
async def seed_school(setup_db) -> School:
    async with async_session_test() as session:
        school = School(name="Test School")
        session.add(school)
        await session.commit()
        await session.refresh(school)
        return school


@pytest.fixture
async def seed_teacher(seed_school) -> User:
    async with async_session_test() as session:
        teacher = User(
            school_id=seed_school.id,
            email="teacher@test.com",
            hashed_password=hash_password("password123"),
            role="teacher",
            name="김교사",
        )
        session.add(teacher)
        await session.commit()
        await session.refresh(teacher)
        return teacher


@pytest.fixture
async def seed_inactive_user(seed_school) -> User:
    async with async_session_test() as session:
        user = User(
            school_id=seed_school.id,
            email="inactive@test.com",
            hashed_password=hash_password("password123"),
            role="student",
            name="비활성유저",
            is_active=False,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


@pytest.fixture
async def seed_class(seed_school, seed_teacher) -> Class:
    async with async_session_test() as session:
        cls = Class(
            school_id=seed_school.id,
            teacher_id=seed_teacher.id,
            name="2학년 3반",
            grade=2,
            year=2026,
        )
        session.add(cls)
        await session.commit()
        await session.refresh(cls)
        return cls


@pytest.fixture
async def seed_semester(setup_db) -> Semester:
    async with async_session_test() as session:
        semester = Semester(year=2026, term=1)
        session.add(semester)
        await session.commit()
        await session.refresh(semester)
        return semester


@pytest.fixture
async def auth_client_teacher(client, seed_teacher) -> AsyncClient:
    """Pre-authenticated HTTP client with teacher Bearer token."""
    token = create_access_token({
        "sub": str(seed_teacher.id),
        "role": "teacher",
        "school_id": str(seed_teacher.school_id),
    })
    client.headers["Authorization"] = f"Bearer {token}"
    return client
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/dependencies/auth.py backend/tests/conftest.py
git commit -m "feat(auth): add get_current_user, require_role, and shared test fixtures"
```

> **Note:** Auth endpoint tests (`/auth/me` 200/401) are in Task 7 alongside the router, avoiding testing a dependency before the route exists.

---

## Phase 2: Sprint 1 — Auth + Users + Grades

### Task 7: Auth Router (Login / Refresh / Logout / Me)

**Files:**
- Create: `backend/app/services/auth.py`
- Create: `backend/app/routers/auth.py`
- Test: `backend/tests/test_auth.py`

- [ ] **Step 1: Write auth tests**

```python
# backend/tests/test_auth.py
import pytest


@pytest.mark.asyncio
async def test_login_success(client, seed_teacher):
    response = await client.post("/api/v1/auth/login", json={
        "email": "teacher@test.com",
        "password": "password123",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "teacher"
    assert "refresh_token" in response.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client, seed_teacher):
    response = await client.post("/api/v1/auth/login", json={
        "email": "teacher@test.com",
        "password": "wrongpassword",
    })
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_inactive_user(client, seed_inactive_user):
    response = await client.post("/api/v1/auth/login", json={
        "email": "inactive@test.com",
        "password": "password123",
    })
    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_ACCOUNT_INACTIVE"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_auth.py -v`
Expected: FAIL

- [ ] **Step 3: Implement auth service**

```python
# backend/app/services/auth.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.utils.security import verify_password, create_access_token, create_refresh_token


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        return None
    return user


def create_tokens(user: User) -> tuple[str, str]:
    payload = {"sub": str(user.id), "role": user.role, "school_id": str(user.school_id)}
    access_token = create_access_token(payload)
    refresh_token = create_refresh_token(payload)
    return access_token, refresh_token
```

- [ ] **Step 4: Implement auth router**

> **Important:** Use `AppException` (not `HTTPException`) for all business errors to produce `{ "detail": "...", "code": "ERROR_CODE" }` response format per Design Spec.

```python
# backend/app/routers/auth.py
import uuid

from fastapi import APIRouter, Depends, Response, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user
from app.dependencies.db import get_db
from app.main import AppException
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, RefreshResponse, MeResponse
from app.services.auth import authenticate_user, create_tokens
from app.utils.security import create_access_token, decode_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, body.email, body.password)
    if user is None:
        raise AppException(401, "이메일 또는 비밀번호가 올바르지 않습니다.", "AUTH_INVALID_CREDENTIALS")
    if not user.is_active:
        raise AppException(401, "비활성화된 계정입니다.", "AUTH_ACCOUNT_INACTIVE")
    access_token, refresh_token = create_tokens(user)
    response.set_cookie(
        key="refresh_token", value=refresh_token,
        httponly=True, secure=True, samesite="strict", max_age=604800,
    )
    return TokenResponse(
        access_token=access_token, role=user.role,
        user_id=str(user.id), name=user.name,
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise AppException(401, "No refresh token", "AUTH_TOKEN_EXPIRED")
    payload = decode_token(token)
    if payload is None or payload.get("type") != "refresh":
        raise AppException(401, "Invalid refresh token", "AUTH_TOKEN_EXPIRED")

    # Verify user still exists and is active
    result = await db.execute(select(User).where(User.id == uuid.UUID(payload["sub"])))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AppException(401, "비활성화된 계정입니다.", "AUTH_ACCOUNT_INACTIVE")

    access_token = create_access_token({
        "sub": payload["sub"], "role": payload["role"], "school_id": payload["school_id"],
    })
    return RefreshResponse(access_token=access_token)


@router.post("/logout", status_code=204)
async def logout(response: Response, _: User = Depends(get_current_user)):
    response.delete_cookie("refresh_token")


@router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user)):
    return MeResponse(
        id=str(current_user.id), email=current_user.email,
        name=current_user.name, role=current_user.role,
        school_id=str(current_user.school_id),
    )
```

- [ ] **Step 5: Wire auth router into main.py**

Add to `app/main.py`:
```python
from app.routers import auth
app.include_router(auth.router, prefix="/api/v1")
```

- [ ] **Step 6: Add fixtures for inactive user, update conftest**

Add `seed_inactive_user` fixture and update error response format.

- [ ] **Step 7: Run auth tests**

Run: `cd backend && pytest tests/test_auth.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/routers/auth.py backend/app/services/auth.py backend/tests/test_auth.py backend/app/main.py
git commit -m "feat(auth): implement login, refresh, logout, me endpoints with JWT"
```

---

### Task 8: Setup APIs — Semester, Class, Subject CRUD

**Files:**
- Create: `backend/app/schemas/semester.py`
- Create: `backend/app/schemas/class_.py`
- Create: `backend/app/schemas/subject.py`
- Create: `backend/app/routers/semesters.py`
- Create: `backend/app/routers/classes.py`
- Test: `backend/tests/test_semesters.py`
- Test: `backend/tests/test_classes.py`

- [ ] **Step 1: Write semester tests**

```python
# backend/tests/test_semesters.py
import pytest


@pytest.mark.asyncio
async def test_create_semester(auth_client_teacher):
    response = await auth_client_teacher.post("/api/v1/semesters", json={"year": 2026, "term": 1})
    assert response.status_code == 201
    assert response.json()["year"] == 2026


@pytest.mark.asyncio
async def test_create_duplicate_semester(auth_client_teacher):
    await auth_client_teacher.post("/api/v1/semesters", json={"year": 2026, "term": 1})
    response = await auth_client_teacher.post("/api/v1/semesters", json={"year": 2026, "term": 1})
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_list_semesters(auth_client_teacher):
    await auth_client_teacher.post("/api/v1/semesters", json={"year": 2026, "term": 1})
    response = await auth_client_teacher.get("/api/v1/semesters")
    assert response.status_code == 200
    assert len(response.json()) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_semesters.py -v`
Expected: FAIL

- [ ] **Step 3: Implement semester schemas + router**

Schemas: `SemesterCreate(year: int, term: int)`, `SemesterResponse(id, year, term)`
Router: `POST /semesters`, `GET /semesters`
Wire into `main.py`.

- [ ] **Step 4: Run semester tests**

Run: `cd backend && pytest tests/test_semesters.py -v`
Expected: PASS

- [ ] **Step 5: Write class + subject tests**

Test: create class (teacher becomes homeroom), list classes (own only), create subject, delete subject (with/without grades).

- [ ] **Step 6: Implement class + subject schemas + router**

`POST /classes`, `GET /classes`, `PUT /classes/{id}`, `POST /classes/{class_id}/subjects`, `GET /classes/{class_id}/subjects`, `DELETE /classes/{class_id}/subjects/{subject_id}`

- [ ] **Step 7: Run class tests**

Run: `cd backend && pytest tests/test_classes.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/semester.py backend/app/schemas/class_.py backend/app/schemas/subject.py
git add backend/app/routers/semesters.py backend/app/routers/classes.py
git add backend/tests/test_semesters.py backend/tests/test_classes.py
git commit -m "feat(setup): add Semester, Class, Subject CRUD endpoints"
```

---

### Task 9: User Management — Student + Parent Creation

**Files:**
- Create: `backend/app/schemas/user.py`
- Create: `backend/app/services/user.py`
- Create: `backend/app/routers/users.py`
- Test: `backend/tests/test_users.py`

- [ ] **Step 1: Write user management tests**

Tests for:
- `POST /users/students` — teacher creates student in own class
- `POST /users/students` — 409 on duplicate email
- `POST /users/parents` — teacher creates parent linked to student
- `GET /users/students?class_id=...` — paginated list
- `GET /users/me/children` — parent sees children
- `PATCH /users/students/{id}/deactivate` — teacher deactivates student

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement user service + schemas + router**

Service: `create_student_account`, `create_parent_account`, `list_students`, `deactivate_student`
Router: wire all endpoints with `require_role("teacher")` or `require_role("parent")`

- [ ] **Step 4: Run user tests**

Run: `cd backend && pytest tests/test_users.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/user.py backend/app/services/user.py backend/app/routers/users.py backend/tests/test_users.py
git commit -m "feat(users): add student/parent account creation, student list, deactivation"
```

---

### Task 10: Grade CRUD + Auto-calculation

**Files:**
- Create: `backend/app/schemas/grade.py`
- Create: `backend/app/services/grade.py`
- Create: `backend/app/routers/grades.py`
- Test: `backend/tests/test_grades.py`

- [ ] **Step 1: Write grade tests**

Tests for:
- `POST /grades` — create grade, returns grade_rank auto-calculated
- `POST /grades` — 409 on duplicate (student+subject+semester)
- `POST /grades` — 400 on score out of range
- `PUT /grades/{id}` — update score, grade_rank recalculated
- `GET /grades?student_id=&semester_id=` — list with subject_name
- `GET /grades/{student_id}/summary?semester_ids=` — summary calculation
- `POST /grades/bulk` — bulk create/update
- Authorization: student can only GET own grades, parent can GET child's grades

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement grade service**

Key logic:
- `calculate_grade(score)` from utils
- Notification side-effect: import `create_notification` from `app.services.notification` (already created in Task 5)
- Summary: aggregate scores per semester, compute total/average
- Bulk: iterate with error collection

- [ ] **Step 4: Implement grade schemas + router**

`GradeCreate`, `GradeResponse`, `GradeSummary`, `BulkGradeRequest`, `BulkGradeResponse`

- [ ] **Step 5: Run grade tests**

Run: `cd backend && pytest tests/test_grades.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/grade.py backend/app/services/grade.py backend/app/routers/grades.py backend/tests/test_grades.py
git commit -m "feat(grades): add grade CRUD with auto-calculation, bulk input, and summary"
```

---

### Task 11: Seed Script

**Files:**
- Create: `backend/seed.py`

- [ ] **Step 1: Write seed script**

Creates: 1 School, 1 Teacher, 1 Semester, 1 Class, 5 Subjects, 5 Students with sample grades.

- [ ] **Step 2: Test seed script runs without error**

Run: `cd backend && python seed.py`
Expected: "Seed data created successfully"

- [ ] **Step 3: Commit**

```bash
git add backend/seed.py
git commit -m "feat(seed): add demo seed script with school, teacher, students, grades"
```

---

## Phase 3: Sprint 1 — Frontend Foundation

### Task 12: Frontend Project Scaffolding

**Files:**
- Create: `frontend/` (Vite + React + TypeScript + Tailwind)

- [ ] **Step 1: Create Vite project**

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install
```

- [ ] **Step 2: Install dependencies**

```bash
cd frontend && npm install @tanstack/react-query zustand axios react-router-dom recharts
npm install -D tailwindcss @tailwindcss/vite
```

- [ ] **Step 3: Configure Tailwind**

Update `vite.config.ts` with `@tailwindcss/vite` plugin. Add `@import "tailwindcss"` to `src/index.css`.

- [ ] **Step 4: Configure tsconfig strict mode**

Ensure `"strict": true` in `tsconfig.json`.

- [ ] **Step 5: Create types/index.ts with shared interfaces**

```typescript
// frontend/src/types/index.ts
export interface User {
  id: string;
  email: string;
  name: string;
  role: 'teacher' | 'student' | 'parent';
  school_id: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: string;
  user_id: string;
  name: string;
}

export interface Semester { id: string; year: number; term: number; }
export interface ClassInfo { id: string; name: string; grade: number; year: number; teacher_id: string; }
export interface Subject { id: string; name: string; class_id: string; }
export interface Student { id: string; user_id: string; name: string; student_number: number; class_id: string; birth_date: string | null; }

export interface GradeItem {
  id: string; subject_id: string; subject_name: string;
  score: number | null; grade_rank: number | null;
  semester_id: string; updated_at: string;
}

export interface GradeSummary {
  semester_id: string; year: number; term: number;
  total_score: number | null; average_score: number | null;
  subject_count: number;
  grades: { subject_name: string; score: number | null; grade_rank: number | null; }[];
}

export interface PaginatedResponse<T> { total: number; items: T[]; }
```

- [ ] **Step 6: Create API client with interceptors**

```typescript
// frontend/src/api/client.ts
import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
  withCredentials: true, // send cookies (refresh_token)
});

// Use lazy dynamic import to avoid circular dependency with authStore
let _getAuthStore: (() => typeof import('../stores/authStore'))| null = null;
async function getAuthStore() {
  if (!_getAuthStore) {
    const mod = await import('../stores/authStore');
    _getAuthStore = () => mod;
  }
  return _getAuthStore();
}

apiClient.interceptors.request.use(async (config) => {
  const { useAuthStore } = await getAuthStore();
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (res) => res,
  async (error) => {
    if (error.response?.status === 401 && !error.config._retry) {
      error.config._retry = true;
      try {
        const { data } = await axios.post(
          `${apiClient.defaults.baseURL}/auth/refresh`, {},
          { withCredentials: true },
        );
        const { useAuthStore } = await getAuthStore();
        useAuthStore.getState().setAccessToken(data.access_token);
        error.config.headers.Authorization = `Bearer ${data.access_token}`;
        return apiClient(error.config);
      } catch {
        const { useAuthStore } = await getAuthStore();
        useAuthStore.getState().logout();
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);

export default apiClient;
```

- [ ] **Step 7: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): scaffold React 18 + TypeScript + Tailwind + TanStack Query"
```

---

### Task 13: Auth Store + Login Page

**Files:**
- Create: `frontend/src/stores/authStore.ts`
- Create: `frontend/src/api/auth.ts`
- Create: `frontend/src/pages/LoginPage.tsx`
- Create: `frontend/src/components/auth/ProtectedRoute.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create Zustand auth store**

```typescript
// frontend/src/stores/authStore.ts
import { create } from 'zustand';
import type { User } from '../types';

interface AuthState {
  accessToken: string | null;
  user: User | null;
  setAccessToken: (token: string) => void;
  setUser: (user: User) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  user: null,
  setAccessToken: (token) => set({ accessToken: token }),
  setUser: (user) => set({ user }),
  logout: () => set({ accessToken: null, user: null }),
}));
```

- [ ] **Step 2: Create auth API functions**

```typescript
// frontend/src/api/auth.ts
import apiClient from './client';
import type { TokenResponse, User } from '../types';

export async function login(email: string, password: string): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>('/auth/login', { email, password });
  return data;
}

export async function getMe(): Promise<User> {
  const { data } = await apiClient.get<User>('/auth/me');
  return data;
}

export async function logout(): Promise<void> {
  await apiClient.post('/auth/logout');
}
```

- [ ] **Step 3: Create LoginPage**

Build a centered login form with email/password fields, error handling, redirect on success.

- [ ] **Step 4: Create ProtectedRoute**

Checks `useAuthStore` for token, redirects to `/login` if absent.

- [ ] **Step 5: Wire App.tsx with React Router**

Routes: `/login` → LoginPage, `/*` → ProtectedRoute wrapping main layout.

- [ ] **Step 6: Verify login flow manually**

Start backend (`uvicorn app.main:app --reload`) and frontend (`npm run dev`). Run seed. Login with teacher account.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/
git commit -m "feat(frontend): add auth store, login page, and protected routing"
```

---

### Task 14: Teacher Dashboard + Student List

**Files:**
- Create: `frontend/src/components/layout/AppLayout.tsx`
- Create: `frontend/src/components/layout/Sidebar.tsx`
- Create: `frontend/src/components/layout/Header.tsx`
- Create: `frontend/src/pages/DashboardPage.tsx`
- Create: `frontend/src/pages/StudentListPage.tsx`
- Create: `frontend/src/hooks/useStudents.ts`
- Create: `frontend/src/api/users.ts`

- [ ] **Step 1: Create AppLayout with Sidebar + Header**

Sidebar: navigation links (Dashboard, Students, Grades, Feedback, Counseling, Notifications).
Header: user name, notification bell, logout button.

- [ ] **Step 2: Create student list hooks + API**

TanStack Query hook: `useStudents(classId)` → paginated student list.

- [ ] **Step 3: Create StudentListPage**

Table showing student_number, name with link to detail page.

- [ ] **Step 4: Create DashboardPage**

Simple dashboard showing class info and quick stats.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/
git commit -m "feat(frontend): add layout, dashboard, and student list page"
```

---

### Task 15: Grade Input UI + Radar Chart Prototype

**Files:**
- Create: `frontend/src/pages/GradesPage.tsx`
- Create: `frontend/src/components/grades/GradeTable.tsx`
- Create: `frontend/src/components/grades/RadarChart.tsx`
- Create: `frontend/src/hooks/useGrades.ts`
- Create: `frontend/src/api/grades.ts`
- Create: `frontend/src/utils/gradeCalculator.ts`

- [ ] **Step 1: Create gradeCalculator utility (same logic as backend)**

```typescript
// frontend/src/utils/gradeCalculator.ts
const GRADE_CUTOFFS = [96, 89, 77, 60, 40, 23, 11, 4];

export function calculateGrade(score: number): number {
  for (let rank = 0; rank < GRADE_CUTOFFS.length; rank++) {
    if (score >= GRADE_CUTOFFS[rank]) return rank + 1;
  }
  return 9;
}
```

- [ ] **Step 2: Create grades API + hooks**

`useGrades(studentId, semesterId)` — fetch grade list.
`useGradeSummary(studentId, semesterIds)` — fetch summary for chart.
`useUpdateGrade()` — mutation with optimistic update.

- [ ] **Step 3: Create GradeTable with AutoSave**

Editable table: student rows × subject columns. onChange → debounce 500ms → PUT/POST.
Show grade_rank instantly via client-side `calculateGrade()`.
Optimistic update via TanStack Query.

- [ ] **Step 4: Create RadarChart component**

Use Recharts `<RadarChart>` with subject axes, score data. Support multi-semester overlay.

- [ ] **Step 5: Create GradesPage wiring table + chart**

Select student → show grade table + radar chart below.

- [ ] **Step 6: Verify grade input → auto-save → chart update**

Manual test: input score → see rank update → chart reflects.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/
git commit -m "feat(frontend): add grade input with autosave, radar chart visualization"
```

---

## Phase 4: Sprint 2 — Student Records + Grade Visualization Polish

### Task 16: Student Detail + Attendance + Special Notes (Backend)

**Files:**
- Create: `backend/app/schemas/student.py`
- Create: `backend/app/schemas/attendance.py`
- Create: `backend/app/schemas/special_note.py`
- Create: `backend/app/services/student.py`
- Create: `backend/app/routers/students.py`
- Test: `backend/tests/test_students.py`

- [ ] **Step 1: Write student endpoint tests**

Tests for:
- `GET /students/{id}` — teacher/student/parent access
- `PUT /students/{id}` — teacher updates student info
- `POST /students/{id}/attendance` — create attendance record
- `POST /students/{id}/attendance` — 409 on duplicate date
- `GET /students/{id}/attendance?start_date=&end_date=` — list
- `PUT /students/{id}/attendance/{attendance_id}` — update
- `POST /students/{id}/special-notes` — create
- `PUT /students/{id}/special-notes/{note_id}` — 403 if not owner
- `GET /students/{id}/special-notes` — list

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement student service + schemas + router**

- [ ] **Step 4: Run student tests**

Run: `cd backend && pytest tests/test_students.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/student.py backend/app/schemas/attendance.py backend/app/schemas/special_note.py
git add backend/app/services/student.py backend/app/routers/students.py backend/tests/test_students.py
git commit -m "feat(students): add student detail, attendance, special notes endpoints"
```

---

### Task 17: Student Detail Frontend

**Files:**
- Create: `frontend/src/pages/StudentDetailPage.tsx`
- Create: `frontend/src/components/students/StudentDetail.tsx`
- Create: `frontend/src/components/students/AttendanceForm.tsx`
- Create: `frontend/src/components/students/SpecialNoteForm.tsx`
- Create: `frontend/src/api/students.ts`

- [ ] **Step 1: Create student API functions**

- [ ] **Step 2: Create StudentDetailPage with tabs**

Tabs: Overview | Grades | Attendance | Special Notes | Feedbacks

- [ ] **Step 3: Create AttendanceForm**

Date picker, status dropdown, note textarea. Teacher only.

- [ ] **Step 4: Create SpecialNoteForm**

Text input for notes. List view with edit button (owner only).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/
git commit -m "feat(frontend): add student detail page with attendance and special notes"
```

---

### Task 18: Radar Chart Polish + Multi-semester Comparison

**Files:**
- Modify: `frontend/src/components/grades/RadarChart.tsx`
- Modify: `frontend/src/pages/GradesPage.tsx`

- [ ] **Step 1: Add multi-semester selector**

Dropdown/checkbox to select multiple semesters for comparison overlay.

- [ ] **Step 2: Update RadarChart for multi-dataset**

Each semester → different color line on the radar. Legend showing semester names.

- [ ] **Step 3: Handle null scores**

Show as 0 with dashed line styling.

- [ ] **Step 4: Add PNG/PDF export**

Install `html2canvas` and `jspdf`. Add export buttons.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/
git commit -m "feat(frontend): polish radar chart with multi-semester comparison and export"
```

---

### Task 19: Student/Parent View (Read-only)

**Files:**
- Create: `frontend/src/pages/StudentGradesViewPage.tsx`

- [ ] **Step 1: Create read-only grades view for student/parent roles**

Same radar chart + grade summary, no edit controls. Role-based rendering.

- [ ] **Step 2: Update routing for role-based pages**

Student login → `/my-grades` (read-only view)
Parent login → `/children` → select child → `/children/{id}/grades`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/
git commit -m "feat(frontend): add student/parent read-only grades view"
```

---

## Phase 5: Sprint 3 — Feedback

### Task 20: Feedback Backend

**Files:**
- Create: `backend/app/schemas/feedback.py`
- Create: `backend/app/services/feedback.py`
- Create: `backend/app/routers/feedbacks.py`
- Test: `backend/tests/test_feedbacks.py`

- [ ] **Step 1: Write feedback tests**

Tests for:
- `POST /feedbacks` — teacher creates feedback with visibility settings
- `GET /feedbacks?student_id=` — teacher sees all fields, student sees visible-to-student only
- `PUT /feedbacks/{id}` — owner only
- `DELETE /feedbacks/{id}` — owner only, 403 for others
- Notification side-effect: visible_to_student=true → student notification created

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement feedback service + schemas + router**

Key: role-based response filtering — teacher gets `is_visible_to_*` fields, student/parent don't.
Notification: use `create_notification` from `app.services.notification` (created in Task 5). Check visibility flags before sending.

- [ ] **Step 4: Run feedback tests**

Run: `cd backend && pytest tests/test_feedbacks.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/feedback.py backend/app/services/feedback.py
git add backend/app/routers/feedbacks.py backend/tests/test_feedbacks.py
git commit -m "feat(feedback): add feedback CRUD with visibility control and notifications"
```

---

### Task 21: Feedback Frontend

**Files:**
- Create: `frontend/src/pages/FeedbackPage.tsx`
- Create: `frontend/src/components/feedbacks/FeedbackForm.tsx`
- Create: `frontend/src/components/feedbacks/FeedbackList.tsx`
- Create: `frontend/src/hooks/useFeedbacks.ts`
- Create: `frontend/src/api/feedbacks.ts`

- [ ] **Step 1: Create feedback API + hooks**

- [ ] **Step 2: Create FeedbackForm**

Category selector (score/behavior/attendance/attitude), content textarea, visibility checkboxes.

- [ ] **Step 3: Create FeedbackList with role-based rendering**

Teacher: shows visibility toggles, edit/delete buttons.
Student/Parent: shows only visible feedbacks, no controls.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/
git commit -m "feat(frontend): add feedback page with form, list, and role-based visibility"
```

---

## Phase 6: Sprint 4 — Counseling + Notifications

### Task 22: Counseling Backend

**Files:**
- Create: `backend/app/schemas/counseling.py`
- Create: `backend/app/services/counseling.py`
- Create: `backend/app/routers/counselings.py`
- Test: `backend/tests/test_counselings.py`

- [ ] **Step 1: Write counseling tests**

Tests for:
- `POST /counselings` — teacher creates, notification to other teachers if shared
- `GET /counselings` — author sees all own, other teachers see shared only
- `GET /counselings` — search by student_name, date range, grade, class_id
- `PUT /counselings/{id}` — owner only
- Student/parent access → 403

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement counseling service + schemas + router**

Key: complex visibility logic — `is_shared` filtering for non-author teachers.
Search: ILIKE for student_name, JOIN to Class for grade/class_id filter.

- [ ] **Step 4: Run counseling tests**

Run: `cd backend && pytest tests/test_counselings.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/counseling.py backend/app/services/counseling.py
git add backend/app/routers/counselings.py backend/tests/test_counselings.py
git commit -m "feat(counseling): add counseling CRUD with sharing and search/filter"
```

---

### Task 23: Notification Router + Preferences

> **Note:** The core `create_notification()` function was created in Task 5 (stub). This task adds the notification *router* (list, mark-read, preferences) and extends the service with those methods.

**Files:**
- Create: `backend/app/schemas/notification.py`
- Modify: `backend/app/services/notification.py` (add mark_read, mark_all_read, get/upsert preferences)
- Create: `backend/app/routers/notifications.py`
- Test: `backend/tests/test_notifications.py`

- [ ] **Step 1: Write notification tests**

Tests for:
- `GET /notifications?is_read=false` — own notifications only
- `PATCH /notifications/{id}/read` — mark as read, 403 for others
- `PATCH /notifications/read-all`
- `GET /notifications/preferences`
- `PUT /notifications/preferences` — upsert

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement notification service + schemas + router**

Extend `app.services.notification` (from Task 5) with: `list_notifications`, `mark_read`, `mark_all_read`, `get_preferences`, `upsert_preferences`.
Preferences: upsert logic (create if not exists, update if exists).

- [ ] **Step 4: Run notification tests**

Run: `cd backend && pytest tests/test_notifications.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/notification.py backend/app/services/notification.py
git add backend/app/routers/notifications.py backend/tests/test_notifications.py
git commit -m "feat(notifications): add notification CRUD with preferences and side-effects"
```

---

### Task 24: Counseling + Notification Frontend

**Files:**
- Create: `frontend/src/pages/CounselingPage.tsx`
- Create: `frontend/src/components/counselings/CounselingForm.tsx`
- Create: `frontend/src/components/counselings/CounselingList.tsx`
- Create: `frontend/src/components/notifications/NotificationBell.tsx`
- Create: `frontend/src/components/notifications/NotificationList.tsx`
- Create: `frontend/src/pages/NotificationsPage.tsx`
- Create: `frontend/src/stores/notificationStore.ts`

- [ ] **Step 1: Create counseling API + hooks + pages**

CounselingForm: date, content, next_plan, is_shared toggle.
CounselingList: search bar (student name), date range filter, grade/class filter.

- [ ] **Step 2: Create notification polling with TanStack Query**

```typescript
useQuery({
  queryKey: ['notifications', 'unread'],
  queryFn: () => fetchNotifications({ is_read: false, limit: 5 }),
  refetchInterval: 30_000, // 30s polling
});
```

- [ ] **Step 3: Create NotificationBell in Header**

Badge showing unread count. Dropdown with latest notifications. Click → mark read + navigate.

- [ ] **Step 4: Create NotificationsPage**

Full notification list with mark-all-read button. Preferences settings panel.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/
git commit -m "feat(frontend): add counseling pages and notification system with 30s polling"
```

---

## Phase 7: Sprint 5 — Import/Export + QA

### Task 25: CSV Import Backend

**Files:**
- Create: `backend/app/services/import_.py`
- Create: `backend/app/routers/imports.py`
- Test: `backend/tests/test_imports.py`

- [ ] **Step 1: Write import tests**

Tests for:
- `POST /import/students` — valid CSV creates students
- `POST /import/students` — missing columns → 400
- `POST /import/students` — duplicate email → skipped
- `POST /import/grades` — valid CSV creates/updates grades
- `POST /import/grades` — unknown subject → error in response

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement import service + router**

Parse CSV with `csv` stdlib. Validate each row. Collect errors/skips.

- [ ] **Step 4: Run import tests**

Run: `cd backend && pytest tests/test_imports.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/import_.py backend/app/routers/imports.py backend/tests/test_imports.py
git commit -m "feat(import): add CSV import for students and grades"
```

---

### Task 26: Client-side Export (Excel + PDF)

**Files:**
- Modify: `frontend/src/pages/GradesPage.tsx`
- Modify: `frontend/src/pages/StudentDetailPage.tsx`

- [ ] **Step 1: Install export libraries**

```bash
cd frontend && npm install xlsx jspdf html2canvas
```

- [ ] **Step 2: Add Excel export button**

Use SheetJS to convert grade summary data → `.xlsx` file download.

- [ ] **Step 3: Add PDF export button**

Use jsPDF + html2canvas to capture grade table/chart → `.pdf` file download.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/
git commit -m "feat(frontend): add Excel and PDF export for grades"
```

---

### Task 27: Rate Limiting + Security Hardening

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/routers/auth.py`

- [ ] **Step 1: Add slowapi rate limiting to login endpoint**

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# In auth router:
@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, ...):
```

- [ ] **Step 2: Add school_id validation tests**

Write tests verifying that Teacher A (school 1) cannot access Student B (school 2) data — should get 404.

- [ ] **Step 3: Commit**

```bash
git add backend/
git commit -m "feat(security): add rate limiting on login, verify school_id isolation"
```

---

### Task 28: Mobile Responsive + Final Polish

**Files:**
- Modify: Various frontend components

- [ ] **Step 1: Add responsive breakpoints to layout**

Sidebar: collapsible on mobile. Tables: horizontal scroll on small screens.

- [ ] **Step 2: Test on 320px viewport**

Verify all pages render correctly.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/
git commit -m "feat(frontend): add mobile responsive layout"
```

---

### Task 29: Full Integration Test Suite

**Files:**
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/test_integration.py`

- [ ] **Step 1: Write end-to-end integration test**

Test full flow:
1. Login as teacher
2. Create semester, class, subjects
3. Create student accounts
4. Input grades → verify auto-calculation
5. Create feedback → verify notification
6. Create counseling → verify sharing
7. Login as student → verify read-only access
8. Login as parent → verify child data only

- [ ] **Step 2: Run full test suite**

Run: `cd backend && pytest -v --cov=app --cov-report=term-missing`
Expected: ALL PASS, coverage ≥ 80%

- [ ] **Step 3: Commit**

```bash
git add backend/tests/
git commit -m "test: add full integration test suite covering all user flows"
```

---

## Summary: Sprint → Task Mapping

| Sprint | Tasks | PRD Requirements |
|--------|-------|-----------------|
| S0 (Week 1-2) | Task 1-6 | Project setup, DB models, auth infra, notification stub |
| S1 (Week 3-4) | Task 7-15 | REQ-001~004, 010, 011, 012(proto) |
| S2 (Week 5-6) | Task 16-19 | REQ-012(완성), 015, 020~022 |
| S3 (Week 7-8) | Task 20-21 | REQ-030~032 |
| S4 (Week 9-10) | Task 22-24 | REQ-033, 040~042, 050, 051 |
| S5 (Week 11-12) | Task 25-29 | REQ-014, 023, 060, QA |

**Total: 29 tasks, ~150 steps**

### Reviewer Issues Addressed

| Issue | Fix |
|-------|-----|
| Error response format (`{ detail, code }`) | `AppException` custom handler in Task 1, used everywhere instead of `HTTPException` |
| Notification service dependency cycle | Stub created early in Task 5, router/remaining methods in Task 23 |
| Missing `auth_client_teacher` fixture | Defined in Task 6 conftest alongside `seed_teacher`, `seed_inactive_user`, etc. |
| `api/client.ts` circular import | Replaced with lazy `await import()` pattern |
| `/auth/refresh` doesn't check `is_active` | Added DB lookup in refresh endpoint (Task 7) |

Each task follows TDD: write failing test → implement → verify pass → commit.
