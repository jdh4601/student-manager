# 학생 성적 및 상담 관리 시스템 — Design Spec

**버전**: 2.0
**작성일**: 2026-03-19
**상태**: 확정
**기반 문서**: PRD v2.0
**변경 이력**: v1.0 → v2.0 (Critic 리뷰 반영 — Critical 3건, Major 6건, Minor 다수 수정)

---

## 목차

1. [System Overview](#1-system-overview)
2. [Data Model](#2-data-model)
3. [API Specification](#3-api-specification)
4. [Authorization Model (RBAC)](#4-authorization-model-rbac)
5. [Core Flows](#5-core-flows)
6. [State & Data Consistency Rules](#6-state--data-consistency-rules)
7. [Edge Cases](#7-edge-cases)
8. [Design Risks & Ambiguities](#8-design-risks--ambiguities)

---

## 1. System Overview

### 아키텍처 구성

```
[Browser / Mobile Web]
        │
        ▼
[Vercel — React 18 + TypeScript]
        │  HTTPS / REST
        ▼
[Render — FastAPI (Python 3.11)]
        │  SQLAlchemy 2.0
        ▼
[Supabase — PostgreSQL]
```

| 레이어 | 기술 | 역할 |
|--------|------|------|
| Frontend | React 18, TypeScript, Tailwind CSS, Zustand, TanStack Query, Recharts | UI 렌더링, 상태 관리, 차트 |
| Backend | FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic | REST API, 비즈니스 로직, ORM |
| Database | PostgreSQL (Supabase) | 데이터 저장 |
| 인증 | JWT (python-jose + passlib bcrypt) | Access 1h / Refresh 7d |
| 배포 | Vercel + Render + Supabase | 무료 티어 기반 |

### 핵심 설계 결정사항

1. **멀티테넌트 격리**: 단일 DB + `school_id` Row-Level Filtering. FastAPI 레이어에서 1차 스코핑 필수. Supabase RLS는 선택적 보조 레이어로만 사용.
2. **인증**: JWT Bearer 토큰. `access_token`은 메모리(Zustand store) 저장. `refresh_token`은 HttpOnly Cookie. localStorage 금지.
3. **실시간**: MVP에서는 **30초 폴링** 방식으로 인앱 알림 구현 (Supabase Realtime은 v2 전환).
4. **성적 등급**: 원점수 기준 9등급 참고값 제공 (석차 기반 아님). 추후 전환 가능하도록 계산 로직 서비스 레이어에서 분리.
5. **파일 생성**: 클라이언트 사이드 전용 (SheetJS: Excel, jsPDF: PDF). 서버는 JSON 데이터만 제공, 파일 변환은 브라우저에서 수행.
6. **초기 설정 전략**: School 및 교사 계정은 Alembic seed script로 생성. 교사가 앱 내에서 학급/과목/학기를 직접 설정.
7. **교사 스코핑 (MVP 제약)**: 담임 교사 1명 = 담당 Class 1개 구조. 교과 교사 다중 반 담당은 v2에서 ClassTeacher M:M 테이블로 확장 예정.
8. **CORS**: Render 백엔드는 Vercel 프론트엔드 origin만 허용 (`ALLOWED_ORIGINS` 환경변수).
9. **Rate Limiting**: 로그인 엔드포인트에 한해 IP 기반 5회/분 제한 (slowapi 라이브러리 사용).

---

## 2. Data Model

### 2.1 엔티티 목록

#### School
```
id                   UUID         PK
name                 VARCHAR(100) NOT NULL
subscription_status  VARCHAR(20)  NOT NULL  DEFAULT 'trial'
                      -- values: trial | active | suspended
created_at           TIMESTAMP    NOT NULL  DEFAULT now()
```

#### User
```
id               UUID         PK
school_id        UUID         FK → School(id)  NOT NULL
email            VARCHAR(255) UNIQUE NOT NULL
hashed_password  VARCHAR(255) NOT NULL
role             VARCHAR(10)  NOT NULL
                  -- values: teacher | student | parent
name             VARCHAR(50)  NOT NULL
is_active        BOOLEAN      NOT NULL  DEFAULT true
created_at       TIMESTAMP    NOT NULL  DEFAULT now()
```
- 인덱스: `(school_id, role)`, `(email)`

#### Class (학급)
```
id          UUID        PK
school_id   UUID        FK → School(id)  NOT NULL
teacher_id  UUID        FK → User(id)    NOT NULL  -- 담임교사
name        VARCHAR(50) NOT NULL                    -- 예: "2학년 3반"
grade       SMALLINT    NOT NULL                    -- 1~6 (중1~고3)
year        SMALLINT    NOT NULL                    -- 학년도
UNIQUE (school_id, grade, name, year)
```

#### Student (학생 프로필)
```
id              UUID     PK
user_id         UUID     FK → User(id)   UNIQUE NOT NULL
class_id        UUID     FK → Class(id)  NOT NULL
student_number  SMALLINT NOT NULL
birth_date      DATE     NULLABLE
```
- 인덱스: `(class_id)`

#### ParentStudent (학부모-학생 연결)
```
id          UUID  PK
parent_id   UUID  FK → User(id)    NOT NULL
student_id  UUID  FK → Student(id) NOT NULL
UNIQUE (parent_id, student_id)
```

#### Subject (과목)
```
id        UUID        PK
class_id  UUID        FK → Class(id)  NOT NULL
name      VARCHAR(50) NOT NULL
UNIQUE (class_id, name)
```

#### Semester (학기)
```
id    UUID     PK
year  SMALLINT NOT NULL   -- 예: 2026
term  SMALLINT NOT NULL   -- 1 or 2
UNIQUE (year, term)
```
> Semester는 전역 테이블 (school 종속 없음). 교사가 앱에서 직접 생성.

#### Grade (성적)
```
id           UUID          PK
student_id   UUID          FK → Student(id)  NOT NULL
subject_id   UUID          FK → Subject(id)  NOT NULL
semester_id  UUID          FK → Semester(id) NOT NULL
score        NUMERIC(5,2)  NULLABLE            -- 0.00 ~ 100.00
             CHECK (score IS NULL OR (score >= 0 AND score <= 100))
grade_rank   SMALLINT      NULLABLE            -- 1~9 (서비스 레이어 계산 캐시)
created_by   UUID          FK → User(id)      NOT NULL
updated_at   TIMESTAMP     NOT NULL  DEFAULT now()
UNIQUE (student_id, subject_id, semester_id)
```
- `score` NULL = 미입력 상태. `grade_rank`는 score 저장 시 서비스 레이어에서 계산.
- 인덱스: `(student_id, semester_id)`
- **명칭 변경**: ~~`grade_letter`~~ → `grade_rank` (1~9 정수임을 명확히)

#### Attendance (출결)
```
id          UUID        PK
student_id  UUID        FK → Student(id)  NOT NULL
date        DATE        NOT NULL
status      VARCHAR(15) NOT NULL
             -- values: present | absent | late | early_leave
note        TEXT        NULLABLE
UNIQUE (student_id, date)
```
> MVP 제약: 하루 1건만 기록. 오전/오후 분리는 v2에서 처리.
- 인덱스: `(student_id, date)`

#### SpecialNote (특기사항)
```
id          UUID      PK
student_id  UUID      FK → Student(id)  NOT NULL
content     TEXT      NOT NULL
created_by  UUID      FK → User(id)     NOT NULL
created_at  TIMESTAMP NOT NULL  DEFAULT now()
updated_at  TIMESTAMP NOT NULL  DEFAULT now()
```

#### Feedback
```
id                    UUID        PK
student_id            UUID        FK → Student(id) NOT NULL
teacher_id            UUID        FK → User(id)    NOT NULL
category              VARCHAR(15) NOT NULL
                       -- values: score | behavior | attendance | attitude
                       -- ※ 성적 피드백 카테고리는 Grade 엔티티와 구분하기 위해 'score'로 명명
content               TEXT        NOT NULL
is_visible_to_student BOOLEAN     NOT NULL  DEFAULT false
is_visible_to_parent  BOOLEAN     NOT NULL  DEFAULT false
created_at            TIMESTAMP   NOT NULL  DEFAULT now()
updated_at            TIMESTAMP   NOT NULL  DEFAULT now()
```
- 인덱스: `(student_id, teacher_id)`

#### Counseling (상담)
```
id          UUID      PK
student_id  UUID      FK → Student(id) NOT NULL
teacher_id  UUID      FK → User(id)    NOT NULL
date        DATE      NOT NULL
content     TEXT      NOT NULL
next_plan   TEXT      NULLABLE
is_shared   BOOLEAN   NOT NULL  DEFAULT true
created_at  TIMESTAMP NOT NULL  DEFAULT now()
updated_at  TIMESTAMP NOT NULL  DEFAULT now()
```
- 인덱스: `(student_id)`, `(teacher_id)`, `(teacher_id, is_shared)`

#### Notification
```
id            UUID        PK
recipient_id  UUID        FK → User(id)  NOT NULL
type          VARCHAR(30) NOT NULL
               -- values: grade_input | feedback_created | counseling_updated
message       TEXT        NOT NULL
is_read       BOOLEAN     NOT NULL  DEFAULT false
related_id    UUID        NULLABLE   -- 관련 리소스 ID (Grade.id, Feedback.id 등)
related_type  VARCHAR(30) NULLABLE   -- grade | feedback | counseling
created_at    TIMESTAMP   NOT NULL   DEFAULT now()
```
- 인덱스: `(recipient_id, is_read)`, `(recipient_id, created_at DESC)`
- **PRD 대비 추가 필드**: `related_id`, `related_type` (알림 클릭 시 해당 화면 라우팅에 필요)

#### NotificationPreference (알림 설정) — PRD US-007 AC 반영
```
id                UUID        PK
user_id           UUID        FK → User(id)  UNIQUE NOT NULL
grade_input       BOOLEAN     NOT NULL  DEFAULT true
feedback_created  BOOLEAN     NOT NULL  DEFAULT true
counseling_updated BOOLEAN    NOT NULL  DEFAULT true
```
> User당 1행. user_id UNIQUE 제약.

### 2.2 관계 요약

| 관계 | 카디널리티 |
|------|-----------|
| School → User | 1:N |
| School → Class | 1:N |
| Class → Student | 1:N |
| Class → Subject | 1:N |
| User(teacher) → Class | 1:N (담임, MVP 제약) |
| Student ↔ User(parent) | N:M (ParentStudent) |
| Student → Grade | 1:N |
| Student → Attendance | 1:N |
| Student → SpecialNote | 1:N |
| Student → Feedback | 1:N |
| Student → Counseling | 1:N |
| User → Notification | 1:N |
| User → NotificationPreference | 1:1 |

---

## 3. API Specification

### 공통 규칙

- **Base URL**: `/api/v1`
- **Content-Type**: `application/json` (파일 업로드 제외)
- **인증**: `Authorization: Bearer <access_token>` (로그인, 리프레시 제외)
- **오류 응답 형식**: `{ "detail": "message", "code": "ERROR_CODE" }`
- **페이지네이션**: `?skip=0&limit=20` (기본 20, 최대 100). 응답: `{ "total": int, "items": [...] }`
- **페이지네이션 일관성**: 목록 조회는 모두 `{ total, items }` 형식. 단건/요약은 객체 직접 반환.

---

### 3.1 인증 (Auth)

#### POST /auth/login
```
Request:
  { "email": "string", "password": "string" }

Response 200:
  {
    "access_token": "string",      -- 메모리 저장용
    "token_type": "bearer",
    "role": "teacher|student|parent",
    "user_id": "uuid",
    "name": "string"
  }
  Set-Cookie: refresh_token=<token>; HttpOnly; Secure; SameSite=Strict; Max-Age=604800

Response 401: { "detail": "이메일 또는 비밀번호가 올바르지 않습니다.", "code": "AUTH_INVALID_CREDENTIALS" }
Response 429: { "detail": "너무 많은 로그인 시도입니다.", "code": "AUTH_RATE_LIMITED" }

Authorization: None
Rate Limit: 5회/분 (IP 기반)
```

#### POST /auth/refresh
```
Request: Cookie에서 refresh_token 자동 전송 (body 없음)

Response 200:
  { "access_token": "string", "token_type": "bearer" }

Response 401: { "code": "AUTH_TOKEN_EXPIRED" }

Authorization: None
```

#### POST /auth/logout
```
Response 204
Set-Cookie: refresh_token=; Max-Age=0  -- 쿠키 삭제

Authorization: Any authenticated user
```

#### GET /auth/me
```
Response 200:
  { "id": "uuid", "email": "string", "name": "string", "role": "string", "school_id": "uuid" }

Authorization: Any authenticated user
```

---

### 3.2 초기 설정 (Setup) — 시스템 부팅 순서

> **중요**: 앱 사용 전 다음 순서로 초기 설정 필요.
> 1. Alembic seed script로 School + 최초 교사(teacher) 계정 생성 (CLI, 배포 시 1회 실행)
> 2. 교사가 앱 로그인 후: Semester 생성 → Class 생성 → Subject 등록

#### POST /semesters
```
Request: { "year": "integer", "term": 1 | 2 }

Response 201: { "id": "uuid", "year": "integer", "term": "integer" }
Response 409: { "code": "SEMESTER_DUPLICATE" }

Authorization: teacher
```

#### GET /semesters
```
Response 200: [{ "id": "uuid", "year": "integer", "term": "integer" }]

Authorization: Any authenticated user
```

#### POST /classes
```
Request:
  { "name": "string", "grade": "integer (1~6)", "year": "integer" }

Response 201:
  { "id": "uuid", "name": "string", "grade": "integer", "year": "integer", "teacher_id": "uuid" }

Authorization: teacher (자신이 담임으로 자동 배정)
```

#### GET /classes
```
Query: ?year=integer (선택)

Response 200: [{ "id": "uuid", "name": "string", "grade": "integer", "year": "integer" }]

Authorization: teacher (본인 담당 학급만)
```

#### PUT /classes/{id}
```
Request: { "name": "string", "grade": "integer" }
Response 200: (Class 객체)
Authorization: teacher (담임만)
```

#### POST /classes/{class_id}/subjects
```
Request: { "name": "string" }

Response 201: { "id": "uuid", "name": "string", "class_id": "uuid" }
Response 409: { "code": "SUBJECT_DUPLICATE" }

Authorization: teacher (해당 class 담임)
```

#### GET /classes/{class_id}/subjects
```
Response 200: [{ "id": "uuid", "name": "string" }]

Authorization: teacher (담당 class), student (본인 class), parent (자녀 class)
```

#### DELETE /classes/{class_id}/subjects/{subject_id}
```
Response 204
Response 409: { "code": "SUBJECT_HAS_GRADES", "detail": "성적이 등록된 과목은 삭제할 수 없습니다." }

Authorization: teacher (해당 class 담임)
```

---

### 3.3 사용자 관리 (Users)

#### POST /users/students
```
Request:
  {
    "email": "string",
    "password": "string",
    "name": "string",
    "class_id": "uuid",
    "student_number": "integer",
    "birth_date": "date|null"
  }

Response 201:
  { "id": "uuid", "email": "string", "name": "string", "class_id": "uuid", "student_number": "integer" }

Response 409: { "code": "USER_EMAIL_DUPLICATE" }

Authorization: teacher (같은 school_id, 담당 class_id)
```

#### POST /users/parents
```
Request:
  { "email": "string", "password": "string", "name": "string", "student_id": "uuid" }

Response 201:
  { "id": "uuid", "email": "string", "name": "string", "student_id": "uuid" }

Authorization: teacher (같은 school_id, 해당 student 담당)
```

#### GET /users/students
```
Query: ?class_id=uuid&skip=0&limit=20

Response 200:
  {
    "total": "integer",
    "items": [{ "id": "uuid", "user_id": "uuid", "name": "string", "student_number": "integer", "class_id": "uuid" }]
  }

Authorization: teacher (담당 class_id 스코핑)
```

#### GET /users/me/children — 학부모용 자녀 목록
```
Response 200:
  [{ "student_id": "uuid", "name": "string", "class_name": "string", "grade": "integer" }]

Authorization: parent
```

#### PATCH /users/students/{id}/deactivate
```
Response 200: { "id": "uuid", "is_active": false }
Response 403: { "code": "FORBIDDEN_CLASS_ACCESS" }

Authorization: teacher (담당 학급)
Side Effect: 해당 User.is_active = false → 로그인 차단, 데이터 보존
```

---

### 3.4 성적 관리 (Grades)

#### GET /grades
```
Query: ?student_id=uuid&semester_id=uuid (둘 다 필수)

Response 200:
  {
    "total": "integer",
    "items": [
      {
        "id": "uuid",
        "subject_id": "uuid",
        "subject_name": "string",
        "score": "number|null",
        "grade_rank": "integer|null",
        "semester_id": "uuid",
        "updated_at": "datetime"
      }
    ]
  }

Authorization:
  - teacher: 담당 학급 학생만
  - student: 본인만
  - parent: 자녀만
```

#### POST /grades
```
Request:
  {
    "student_id": "uuid",
    "subject_id": "uuid",
    "semester_id": "uuid",
    "score": "number"    -- 0 ~ 100
  }

Response 201:
  { "id": "uuid", "score": "number", "grade_rank": "integer", "updated_at": "datetime" }

Response 400: { "code": "GRADE_SCORE_OUT_OF_RANGE" }
Response 409: { "code": "GRADE_DUPLICATE", "detail": "이미 입력된 성적입니다. PUT /grades/{id}로 수정하세요.", "existing_id": "uuid" }

Authorization: teacher (담당 학급 학생)
Side Effect: Notification 생성 (학생, 학부모 — NotificationPreference.grade_input=true인 경우만)
```

#### PUT /grades/{id}
```
Request: { "score": "number" }

Response 200: { "id": "uuid", "score": "number", "grade_rank": "integer", "updated_at": "datetime" }

Authorization: teacher (해당 Grade 학생의 담당 교사)
Side Effect: grade_rank 재계산 후 저장
```

#### POST /grades/bulk — 한 학급 한 과목 일괄 입력
```
Request:
  {
    "subject_id": "uuid",
    "semester_id": "uuid",
    "grades": [
      { "student_id": "uuid", "score": "number" }
    ]
  }

Response 200:
  { "created": "integer", "updated": "integer", "errors": [{ "student_id": "uuid", "reason": "string" }] }

Authorization: teacher (담당 학급)
Side Effect: 각 학생별 Notification 생성 (preference 확인 후)
```

#### GET /grades/{student_id}/summary
```
Query: ?semester_ids=uuid,uuid (복수 가능, 비교 모드용. 단일도 가능)

Response 200:
  [
    {
      "semester_id": "uuid",
      "year": "integer",
      "term": "integer",
      "total_score": "number|null",
      "average_score": "number|null",
      "subject_count": "integer",
      "grades": [{ "subject_name": "string", "score": "number|null", "grade_rank": "integer|null" }]
    }
  ]

-- 단일 학기 요청 시 배열 길이=1, 복수 시 각 학기별 객체 반환 (레이더 차트 비교 모드용)

Authorization: teacher (담당), student (본인), parent (자녀)
```

---

### 3.5 학생 정보 / 학생부 (Students)

#### GET /students/{id}
```
Response 200:
  { "id": "uuid", "name": "string", "student_number": "integer", "class_id": "uuid", "birth_date": "date|null" }

Authorization: teacher (담당), student (본인), parent (자녀)
```

#### PUT /students/{id}
```
Request: { "name": "string", "student_number": "integer", "birth_date": "date|null" }
Response 200: (Student 객체)
Authorization: teacher (담당 학급)
```

#### GET /students/{id}/attendance
```
Query: ?start_date=date&end_date=date

Response 200:
  {
    "total": "integer",
    "items": [{ "id": "uuid", "date": "date", "status": "string", "note": "string|null" }]
  }

Authorization: teacher (담당), student (본인), parent (자녀)
```

#### POST /students/{id}/attendance
```
Request: { "date": "date", "status": "present|absent|late|early_leave", "note": "string|null" }

Response 201: { "id": "uuid", "date": "date", "status": "string", "note": "string|null" }
Response 409: { "code": "ATTENDANCE_DATE_DUPLICATE" }

Authorization: teacher (담당 학급)
```

#### PUT /students/{id}/attendance/{attendance_id}
```
-- attendance_id (UUID) 사용. date를 path에 쓰지 않음 (URL encoding 이슈 방지)

Request: { "status": "string", "note": "string|null" }
Response 200: (Attendance 객체)
Authorization: teacher (담당 학급)
```

#### GET /students/{id}/special-notes
```
Response 200:
  {
    "total": "integer",
    "items": [{ "id": "uuid", "content": "string", "created_by_name": "string", "created_at": "datetime", "updated_at": "datetime" }]
  }

Authorization: teacher (담당)
```

#### POST /students/{id}/special-notes
```
Request: { "content": "string" }
Response 201: (SpecialNote 객체)
Authorization: teacher (담당 학급)
```

#### PUT /students/{id}/special-notes/{note_id}
```
Request: { "content": "string" }
Response 200: (SpecialNote 객체)
Response 403: { "code": "SPECIAL_NOTE_NOT_OWNER" }
Authorization: teacher (작성자만)
```

---

### 3.6 피드백 (Feedback)

#### GET /feedbacks
```
Query: ?student_id=uuid&skip=0&limit=20

Response 200:
  {
    "total": "integer",
    "items": [
      {
        "id": "uuid",
        "category": "string",
        "content": "string",
        "is_visible_to_student": "boolean",   -- teacher만 반환
        "is_visible_to_parent": "boolean",    -- teacher만 반환
        "teacher_name": "string",
        "created_at": "datetime"
      }
    ]
  }

Authorization:
  - teacher: 모든 필드, 담당 학생 전체 조회
  - student: is_visible_to_student=true인 것만, visibility 필드 제외
  - parent: is_visible_to_parent=true인 것만, visibility 필드 제외
```

#### POST /feedbacks
```
Request:
  {
    "student_id": "uuid",
    "category": "score|behavior|attendance|attitude",
    "content": "string",
    "is_visible_to_student": "boolean",
    "is_visible_to_parent": "boolean"
  }

Response 201: (Feedback 객체, teacher 뷰)
Authorization: teacher (담당 학생)
Side Effect: Notification 생성 (preference 확인 후)
  - is_visible_to_student=true → 학생에게
  - is_visible_to_parent=true → 해당 학생의 모든 학부모에게
```

#### PUT /feedbacks/{id}
```
Request:
  { "content": "string", "is_visible_to_student": "boolean", "is_visible_to_parent": "boolean" }

Response 200: (Feedback 객체)
Response 403: { "code": "FEEDBACK_NOT_OWNER" }
Authorization: teacher (작성자만)
```

#### DELETE /feedbacks/{id}
```
Response 204
Response 403: { "code": "FEEDBACK_NOT_OWNER" }
Authorization: teacher (작성자만)
```

---

### 3.7 상담 내역 (Counseling)

#### GET /counselings
```
Query:
  ?student_id=uuid
  &student_name=string     -- 학생명 검색 (ILIKE '%name%')
  &teacher_id=uuid
  &start_date=date
  &end_date=date
  &grade=integer           -- 학년 필터 (1~6)
  &class_id=uuid           -- 학급 필터
  &skip=0
  &limit=20

Response 200:
  {
    "total": "integer",
    "items": [
      {
        "id": "uuid",
        "student_id": "uuid",
        "student_name": "string",
        "class_name": "string",
        "teacher_name": "string",
        "date": "date",
        "content": "string",
        "next_plan": "string|null",
        "is_shared": "boolean",
        "created_at": "datetime"
      }
    ]
  }

Authorization: teacher만
  - 작성자: is_shared 관계없이 본인 작성 내역 모두
  - 같은 학교 다른 교사: is_shared=true인 내역만
  - student, parent: 403
```

#### POST /counselings
```
Request:
  {
    "student_id": "uuid",
    "date": "date",
    "content": "string",
    "next_plan": "string|null",
    "is_shared": "boolean"
  }

Response 201: (Counseling 객체)
Authorization: teacher (담당 학생)
Side Effect: is_shared=true → 같은 학교 다른 교사 전체에게 Notification 생성 (preference 확인 후)
```

#### PUT /counselings/{id}
```
Request: { "content": "string", "next_plan": "string|null", "is_shared": "boolean" }
Response 200: (Counseling 객체)
Response 403: { "code": "COUNSELING_NOT_OWNER" }
Authorization: teacher (작성자만)
```

---

### 3.8 알림 (Notifications)

#### GET /notifications
```
Query: ?is_read=boolean&skip=0&limit=20

Response 200:
  {
    "total": "integer",
    "unread_count": "integer",
    "items": [
      {
        "id": "uuid",
        "type": "string",
        "message": "string",
        "is_read": "boolean",
        "related_id": "uuid|null",
        "related_type": "string|null",
        "created_at": "datetime"
      }
    ]
  }

Authorization: Any authenticated user (본인 알림만)
```

#### PATCH /notifications/{id}/read
```
Response 200: { "id": "uuid", "is_read": true }
Response 403: { "code": "NOTIFICATION_NOT_OWNER" }
Authorization: Any authenticated user (본인 알림만)
```

#### PATCH /notifications/read-all
```
Response 200: { "updated_count": "integer" }
Authorization: Any authenticated user
```

#### GET /notifications/preferences
```
Response 200:
  { "grade_input": "boolean", "feedback_created": "boolean", "counseling_updated": "boolean" }

Authorization: Any authenticated user
```

#### PUT /notifications/preferences
```
Request:
  { "grade_input": "boolean", "feedback_created": "boolean", "counseling_updated": "boolean" }

Response 200: (NotificationPreference 객체)
Authorization: Any authenticated user
Side Effect: 없는 경우 자동 생성 (Upsert)
```

---

### 3.9 데이터 가져오기/내보내기 (Import/Export)

> **파일 생성 전략**: 서버는 JSON 데이터를 제공하고, 클라이언트(SheetJS/jsPDF)가 파일로 변환.
> 별도 파일 스트리밍 API 없음. 기존 GET API 응답 데이터를 프론트에서 변환.

#### POST /import/students — 학생 일괄 등록
```
Request: multipart/form-data { "file": CSV, "class_id": uuid }

CSV 컬럼 (순서 고정): name, email, password, student_number, birth_date(YYYY-MM-DD, 선택)

Response 200:
  { "created": "integer", "skipped": "integer", "errors": [{ "row": "integer", "reason": "string" }] }

Authorization: teacher
```

#### POST /import/grades — 성적 일괄 등록
```
Request: multipart/form-data { "file": CSV, "class_id": uuid, "semester_id": uuid }

CSV 컬럼: student_number, subject_name, score

Response 200:
  { "created": "integer", "updated": "integer", "errors": [{ "row": "integer", "reason": "string" }] }

Authorization: teacher (담당 학급)
```

> **Excel/PDF 내보내기**: 클라이언트에서 `GET /grades/{student_id}/summary` 등 기존 API로 데이터 취득 후 SheetJS/jsPDF로 변환. 별도 export API 불필요.

---

## 4. Authorization Model (RBAC)

### 4.1 역할 정의

| 역할 | 설명 |
|------|------|
| `teacher` | 학교 소속 교사. 담당 Class(담임)에 속한 학생 데이터 접근. MVP: 담임 1명 = 1 Class |
| `student` | 학생 계정. 본인 데이터만 접근 |
| `parent` | 학부모 계정. ParentStudent 테이블로 연결된 자녀 데이터만 접근 |

### 4.2 권한 매트릭스

| 리소스 | teacher | student | parent |
|--------|---------|---------|--------|
| Class/Subject/Semester 관리 | 담당 학급 | ✕ | ✕ |
| 학생 목록 조회 | 담당 학급 전체 | 본인 | 자녀 |
| 학생 정보 수정 | 담당 학급 | ✕ | ✕ |
| 학생 계정 비활성화 | 담당 학급 | ✕ | ✕ |
| 성적 조회 | 담당 학급 전체 | 본인 | 자녀 |
| 성적 입력/수정 | 담당 학급 | ✕ | ✕ |
| 출결 조회 | 담당 학급 전체 | 본인 | 자녀 |
| 출결 입력/수정 | 담당 학급 | ✕ | ✕ |
| 특기사항 조회 | 담당 학급 전체 | ✕ | ✕ |
| 특기사항 작성/수정 | 담당(작성자만 수정) | ✕ | ✕ |
| 피드백 조회 | 담당 전체 (전체 필드) | 공개된 것만 | 공개된 것만 |
| 피드백 작성 | 담당 학생 | ✕ | ✕ |
| 피드백 수정/삭제 | 작성자만 | ✕ | ✕ |
| 상담 조회 | 본인 작성 + 공유된 것 | ✕ | ✕ |
| 상담 작성 | 담당 학생 | ✕ | ✕ |
| 상담 수정 | 작성자만 | ✕ | ✕ |
| 알림 조회/설정 | 본인 | 본인 | 본인 |
| 학생/학부모 계정 생성 | ✓ (같은 학교) | ✕ | ✕ |
| 자녀 목록 조회 | ✕ | ✕ | 본인 자녀만 |

### 4.3 스코핑 구현 전략

```python
# JWT payload 구조 (access_token)
{
  "sub": "user_uuid",
  "role": "teacher",
  "school_id": "school_uuid",
  "exp": 1234567890
}
```

**역할별 데이터 필터링 쿼리 패턴:**

```python
# Teacher: 담당 Class의 학생만 (MVP: 담임 1명 = 1 Class)
JOIN Student ON Student.class_id = Class.id
JOIN Class ON Class.teacher_id = current_user.id
         AND Class.school_id = current_user.school_id

# Student: 본인만
WHERE Student.user_id = current_user.id

# Parent: 자녀만
JOIN ParentStudent ON ParentStudent.student_id = Student.id
                  AND ParentStudent.parent_id = current_user.id
```

**타 학교 데이터 접근 시도**: 404 반환 (403 대신 — 존재 자체를 숨김. IDOR 방지)

---

## 5. Core Flows

### 5.1 성적 입력 플로우 (AutoSave 포함)

```
[Frontend — 성적 입력 UI]
  교사가 점수 입력 → debounce 500ms →
  클라이언트 즉시 계산 (calculate_grade) → UI 등급 표시 →
  PUT /grades/{id} 또는 POST /grades 호출
         │
         ▼
[Service Layer]
  1. score 유효성 검사 (0 ≤ score ≤ 100)
  2. 교사의 school_id + 담당 class_id로 student 접근 권한 검증
  3. subject가 해당 class에 속하는지 검증
  4. grade_rank 계산 (calculate_grade(score))
  5. Grade UPSERT (unique: student_id + subject_id + semester_id)
  6. NotificationPreference 확인 후 Notification 생성
         │
         ▼
[Response] Grade 객체 반환 (score, grade_rank, updated_at)
```

**AutoSave 전략:**
- 입력 필드 onChange → debounce 500ms → API 호출
- 실패 시: TanStack Query retry 1회 → 실패 Toast 표시 ("저장 실패. 재시도 중...")
- Optimistic Update: UI는 즉시 반영, 서버 실패 시 롤백
- 네트워크 오프라인 시: 로컬 큐에 보관 후 재연결 시 일괄 전송 (v2 고려)

**등급 계산 로직** (프론트/백엔드 동일 로직 적용):
```python
# 원점수 기준 9등급 참고값 (석차 기반 아님)
GRADE_CUTOFFS = [96, 89, 77, 60, 40, 23, 11, 4]  # 1등급~8등급 하한

def calculate_grade(score: float) -> int:
    for rank, cutoff in enumerate(GRADE_CUTOFFS, start=1):
        if score >= cutoff:
            return rank
    return 9
```

### 5.2 피드백 생성 플로우

```
교사 → POST /feedbacks { student_id, category, content, visibility }
         │
         ▼
[Service Layer]
  1. 교사의 담당 학생인지 검증
  2. Feedback 저장
  3. NotificationPreference 확인 후 Notification 생성:
     - is_visible_to_student=true AND preference.feedback_created=true → 학생에게
     - is_visible_to_parent=true AND preference.feedback_created=true → 자녀의 모든 학부모에게
     (비공개인 경우 알림 없음)
         │
         ▼
[Response] Feedback 객체
```

### 5.3 상담 공유 플로우

```
교사 → POST /counselings { student_id, date, content, next_plan, is_shared }
         │
         ▼
[Service Layer]
  1. 교사의 담당 학생인지 검증
  2. Counseling 저장
  3. is_shared=true인 경우:
     - 같은 school_id의 다른 교사 전체 조회
     - preference.counseling_updated=true인 교사에게만 Notification 생성
     - message: "{교사명}님이 {학생명} 학생 상담 내역을 공유했습니다."
         │
         ▼
[Response] Counseling 객체
```

> **주의**: 학교에 교사 50명이면 최대 49개 Notification 일괄 생성. MVP 규모(1~10학교, 학교당 교사 수십 명)에서는 허용 범위. v2에서 명시적 수신자 선택 기능 추가 검토.

### 5.4 알림 폴링 플로우

```
[Frontend — TanStack Query]
  useQuery({ queryKey: ['notifications'], refetchInterval: 30_000 })
         │
         ▼
GET /notifications?is_read=false&limit=5   -- 최신 5개만 polling
         │
         ▼
[Zustand Store] unread_count 업데이트 → 헤더 뱃지 표시
         │
         ▼
[사용자 클릭]
  → PATCH /notifications/{id}/read
  → related_type + related_id 기반 라우팅:
    "grade"       → /students/{student_id}/grades
    "feedback"    → /students/{student_id}/feedbacks
    "counseling"  → /counselings/{counseling_id}
```

### 5.5 레이더 차트 렌더링 플로우

```
[Frontend]
  학생 선택 + 학기 선택 (단일 또는 복수)
         │
         ▼
GET /grades/{student_id}/summary?semester_ids=uuid1,uuid2
         │
         ▼
[응답 데이터 → Recharts RadarChart]
  - 단일 학기: 과목별 score를 축으로 차트 렌더링
  - 복수 학기: 각 학기 데이터를 다른 색상으로 overlay (비교 모드)
  - 점수 미입력(null) 과목: 0으로 표시 + 점선 처리

[차트 내보내기]
  PNG: html2canvas 라이브러리로 DOM 캡처
  PDF: jsPDF + html2canvas 조합
```

---

## 6. State & Data Consistency Rules

### 6.1 수정/삭제 권한 규칙

| 리소스 | 수정 가능 | 삭제 가능 |
|--------|----------|----------|
| Grade | 담당 교사 (score만 수정) | ✕ |
| Attendance | 담당 교사 | ✕ |
| SpecialNote | 작성자(교사)만 | ✕ |
| Feedback | 작성자(교사)만 | 작성자(교사)만 |
| Counseling | 작성자(교사)만 | ✕ |
| Subject | 담임 교사 (성적 없는 경우만) | 담임 교사 (성적 없는 경우만) |
| Notification | ✕ (읽음 처리만) | ✕ |

### 6.2 데이터 가시성 규칙

| 상황 | 규칙 |
|------|------|
| 피드백 비공개 전환 | 즉시 숨김 (이미 본 경우에도 다음 조회 시 미노출) |
| 상담 is_shared=false 변경 | 즉시 다른 교사 조회 불가 (작성자만 조회) |
| 학생 계정 비활성화 | 로그인 차단, 모든 데이터 보존, 교사는 여전히 조회 가능 |
| 학급 이동 (class_id 변경) | 신규 담임 교사만 조회 가능. 이전 담임 접근 불가. |

### 6.3 충돌 방지 규칙

| 시나리오 | 처리 |
|----------|------|
| 동일 학생+과목+학기 성적 중복 POST | 409 + existing_id 반환 → 프론트에서 PUT으로 재시도 |
| 동일 학생+날짜 출결 중복 | 409: ATTENDANCE_DATE_DUPLICATE |
| 학부모-학생 중복 연결 | 409: PARENT_STUDENT_DUPLICATE |
| 같은 학기/학년/반 클래스 중복 | 409: CLASS_DUPLICATE |
| 같은 학급 내 과목명 중복 | 409: SUBJECT_DUPLICATE |

---

## 7. Edge Cases

### 7.1 입력 유효성

| 케이스 | 처리 |
|--------|------|
| score < 0 or > 100 | 400: GRADE_SCORE_OUT_OF_RANGE |
| score = null (빈 입력) | null 허용, grade_rank도 null |
| grade = 1~6 범위 외 | 400: CLASS_GRADE_INVALID |
| 존재하지 않는 subject_id | 404: SUBJECT_NOT_FOUND |
| 존재하지 않는 semester_id | 404: SEMESTER_NOT_FOUND |
| 존재하지 않는 class_id | 404: CLASS_NOT_FOUND |
| 이메일 중복 가입 | 409: USER_EMAIL_DUPLICATE |
| CSV 가져오기 — 필수 컬럼 누락 | 400 + 누락 컬럼 목록 반환 |
| CSV 가져오기 — 중복 학생번호 | 건너뜀(skip) + skipped 카운트 반환 |
| CSV 가져오기 — 존재하지 않는 과목명 (성적 import) | errors 배열에 추가, 나머지는 처리 |

### 7.2 권한 위반

| 케이스 | 처리 |
|--------|------|
| 다른 학교 학생 데이터 접근 시도 | 404 (존재 자체를 숨김, IDOR 방지) |
| 담당 외 학급 성적 입력 시도 | 403: FORBIDDEN_CLASS_ACCESS |
| 학생이 피드백 수정 시도 | 403: INSUFFICIENT_ROLE |
| 상담 내역에 student/parent 접근 | 403: INSUFFICIENT_ROLE |
| 비활성 사용자 로그인 | 401: AUTH_ACCOUNT_INACTIVE |
| 다른 사람의 알림 읽음 처리 | 403: NOTIFICATION_NOT_OWNER |

### 7.3 데이터 없음 시나리오

| 케이스 | 처리 |
|--------|------|
| 성적 미입력 학생의 summary 조회 | `{ total_score: null, average_score: null, subject_count: 0, grades: [] }` |
| 피드백 없는 학생 조회 | `{ total: 0, items: [] }` |
| 알림 없는 사용자 | `{ total: 0, unread_count: 0, items: [] }` |
| Semester 미생성 시 성적 입력 | 404: SEMESTER_NOT_FOUND |
| 학부모의 자녀가 없는 경우 | `[]` 빈 배열 |
| 담당 학급이 없는 교사 | GET /classes → `[]` 빈 배열 |

---

## 8. Design Risks & Ambiguities

### 8.1 PRD 대비 Design Spec 변경/추가 사항

| 항목 | PRD | Design Spec | 사유 |
|------|-----|-------------|------|
| Notification 필드 | id, recipient_id, type, message, is_read, created_at | + related_id, related_type 추가 | 알림 클릭 시 화면 라우팅 필수 |
| grade_letter → grade_rank | grade_letter (PRD ERD) | grade_rank | 1~9 정수임을 명확히 |
| feedback category 'grade' → 'score' | grade | score | Grade 엔티티와 명칭 혼동 방지 |
| attendance path param | 미명시 | attendance_id (UUID) 사용 | date string URL encoding 이슈 방지 |
| NotificationPreference 테이블 추가 | PRD US-007 AC 명시 | 신규 엔티티 추가 | 알림 유형별 ON/OFF 구현 |
| 초기 설정 API (Semester/Class/Subject) | 미명시 | 명시적 CRUD 추가 | 시스템 부팅 불가 이슈 해결 |

### 8.2 PRD의 불명확한 부분 및 가정

| ID | 항목 | 결정 및 근거 |
|----|------|-------------|
| A-001 | 담당 교사 범위 | MVP: `Class.teacher_id = 현재 교사`인 Class만 담당. 교과 교사 다중 반 담당은 v2 (ClassTeacher M:M 테이블). **고객과 사전 합의 필수.** |
| A-002 | Subject 생성 주체 | 담임 교사가 직접 생성. Class 생성 후 Subject 추가 플로우. |
| A-003 | 상담 공유 범위 | 학교 전체 교사 (단순화). OQ-004 미결이나 MVP에서는 전체 공유로 구현. |
| A-004 | 성적 입력 알림 수신 대상 | 학생 + 해당 학생의 모든 학부모. |
| A-005 | 비밀번호 재설정 | Should 우선순위. Sprint 5 버퍼로 배치. 이메일 발송 구현 필요 (SendGrid 등 v2). |
| A-006 | School/Teacher 초기 생성 | Alembic seed script (CLI). 앱 내 관리자 UI 없음 (MVP 범위 외). |

### 8.3 잠재적 설계 위험

| ID | 위험 | 영향도 | 대응 |
|----|------|--------|------|
| R-001 | 교과 교사 미지원 → 담임이 모든 과목 성적 입력 | 높음 | **고객 합의 필수**. 합의 없으면 MVP 운영 불가. |
| R-002 | Render cold start → 첫 API 응답 30초 지연 | 높음 | Keep-alive cron ping. 데모 전 사전 워밍. |
| R-003 | 성적 등급 계산 기준 (원점수 vs 석차백분율) | 높음 | 서비스 레이어 calculate_grade() 함수 분리. 고객과 Sprint 0 종료 전 합의. |
| R-004 | CSV 가져오기 컬럼 매핑 미정 | 중간 | Sprint 2 전 표준 템플릿 확정 (docs/csv-templates/ 작성). |
| R-005 | 상담 공유 시 알림 폭탄 (교사 수 × 알림) | 중간 | MVP 규모(학교당 교사 10~30명)에서 허용. v2에서 수신자 선택 기능 추가. |
| R-006 | 학생 반 이동 시 이전 담임 데이터 접근 불가 | 낮음 | MVP에서는 반 이동 이력 없음. 이동 전 담임이 필요한 데이터 수동 확인 필요. |
| R-007 | Supabase 무료 DB 500MB 한도 | 낮음 | 1~10학교 MVP 규모에서 충분. v2 전환 시 유료 플랜. |
| R-008 | school_id 필터 누락 버그 → 타 학교 데이터 노출 | 매우 높음 | 모든 서비스 메서드에 school_id 검증 단위 테스트 필수. Supabase RLS 보조 레이어로 설정. |

---

## Appendix: PRD → Design Spec 요구사항 추적표

| PRD REQ | 구현 위치 | 상태 |
|---------|-----------|------|
| REQ-001~004 | §3.1, §3.3 Auth + Users | ✅ |
| REQ-010 | §3.4 POST/PUT /grades | ✅ |
| REQ-011 | §5.1 calculate_grade() | ✅ |
| REQ-012 | §5.5 레이더 차트 + §3.4 summary | ✅ |
| REQ-013 | §3.4 summary ?semester_ids=복수 | ✅ |
| REQ-014 | §3.9 Import/Export | ✅ |
| REQ-015 | §3.4 GET /grades | ✅ |
| REQ-020~022 | §3.5 Students CRUD | ✅ |
| REQ-023 | §3.9 POST /import/students | ✅ |
| REQ-030~032 | §3.6 Feedback | ✅ |
| REQ-033 | §5.2 Feedback Side Effect | ✅ |
| REQ-040~042 | §3.7 Counseling + 검색 파라미터 | ✅ |
| REQ-043 | §3.7 GET /counselings ?grade, ?class_id | ✅ |
| REQ-050~051 | §3.8 Notifications | ✅ |
| REQ-060 | §3.9 (클라이언트 SheetJS) | ✅ |
| REQ-061~062 | §3.9 (클라이언트 jsPDF) | ✅ |
| REQ-005 | 비밀번호 재설정 | ⏳ Sprint 5 버퍼 |
| US-007 AC (알림 ON/OFF) | §3.8 NotificationPreference | ✅ |

---

*Design Spec v2.0 — 확정*
