# 학생 성적 및 상담 관리 시스템 — Design Spec

**버전**: 2.1
**작성일**: 2026-05-03
**상태**: 확정
**기반 문서**: PRD v2.1, ADR-001 (재작성), ADR-002 (CDC — Outbox + Kafka)
**프로젝트 성격**: 졸업 평가용 로컬 프로토타입 (사용자 0명)
**변경 이력**:
- v1.0 → v2.0: Critic 리뷰 반영
- v2.0 → v2.1: §1 docker-compose 로컬 인프라, §9 Outbox+Kafka 기반 Analytics Layer, §10 단일 엔드포인트 챗봇

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
9. [Analytics Layer (v2.1)](#9-analytics-layer-v21)
10. [AI 어시스턴트 (v2.1)](#10-ai-어시스턴트-v21-데모용)

---

## 1. System Overview

### 아키텍처 구성 (v2.1)

```
                  [Browser]
                      │  HTTPS / REST
                      ▼
   ┌─────────────────────────────────────────────────────┐
   │  docker-compose (로컬)                              │
   │                                                     │
   │  ┌─────────────────┐                                │
   │  │ frontend (Vite) │                                │
   │  │ React 18 + TS   │                                │
   │  └────────┬────────┘                                │
   │           │ /api/v1                                 │
   │           ▼                                         │
   │  ┌─────────────────────────────────────┐            │
   │  │ fastapi-api                         │            │
   │  │  - 운영 라우터 (grades, ...)        │            │
   │  │  - /api/v1/analytics/* (read agg)   │            │
   │  │  - /api/v1/chat (LLM 호출)          │            │
   │  └──┬──────────────┬────────────────┬──┘            │
   │     │ SQL          │ outbox INSERT  │ HTTPS         │
   │     ▼              ▼                ▼               │
   │  ┌──────────────────────┐    [LLM Provider (외부)]  │
   │  │ Postgres             │                           │
   │  │  public.*  (OLTP)    │                           │
   │  │  public.outbox       │                           │
   │  │  analytics.* (OLAP)  │                           │
   │  └──┬──────────────▲────┘                           │
   │     │ poll unsent  │ UPSERT agg                     │
   │     ▼              │                                │
   │  ┌─────────────┐   │                                │
   │  │ outbox-     │   │                                │
   │  │ publisher   │   │                                │
   │  │ (aiokafka)  │   │                                │
   │  └──────┬──────┘   │                                │
   │         │ produce  │                                │
   │         ▼          │                                │
   │  ┌──────────────┐  │                                │
   │  │ Kafka KRaft  │  │                                │
   │  │ (단일 노드)  │  │ Fallback: Redpanda             │
   │  └──────┬───────┘  │                                │
   │         │ consume  │                                │
   │         ▼          │                                │
   │  ┌──────────────────┐                               │
   │  │ analytics-worker │                               │
   │  │ (aiokafka cons.) │  scale=N (consumer group)     │
   │  └──────────────────┘                               │
   └─────────────────────────────────────────────────────┘
```

| 레이어 | 기술 | 역할 |
|--------|------|------|
| Frontend | React 18, TS, Tailwind, Zustand, TanStack Query, Recharts | UI, 상태, 차트, 챗 위젯 |
| Backend API | FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic | REST, 비즈니스 로직, RBAC, outbox INSERT, 챗봇 엔드포인트 |
| Outbox Publisher | Python 3.11, aiokafka | `public.outbox` polling → Kafka topic produce |
| Analytics Worker | Python 3.11, aiokafka | Kafka consumer (consumer group) → `analytics.*` UPSERT |
| Message Stream | Apache Kafka KRaft (단일 노드) | 운영 → 분석 이벤트 전달. Fallback: Redpanda |
| Database | PostgreSQL — `public` (OLTP) + `public.outbox` + `analytics` (OLAP) | 단일 인스턴스 |
| 인증 | JWT (python-jose + passlib bcrypt) | Access 1h / Refresh 7d |
| 배포 | docker-compose (로컬 평가) | 모든 서비스 단일 compose 파일 |

### 핵심 설계 결정사항

1. **멀티테넌트 격리**: 단일 DB + `school_id` Row-Level Filtering. FastAPI 레이어에서 1차 스코핑 필수. Postgres RLS는 선택적 보조 레이어 (평가 후 검토).
2. **인증**: JWT Bearer 토큰. `access_token`은 메모리(Zustand store) 저장. `refresh_token`은 HttpOnly Cookie. localStorage 금지.
3. **실시간**: **30초 폴링** 방식으로 인앱 알림 구현 (SSE/WebSocket push는 평가 후).
4. **성적 등급**: 원점수 기준 9등급 참고값 제공 (석차 기반 아님). 추후 전환 가능하도록 계산 로직 서비스 레이어에서 분리.
5. **파일 생성**: 클라이언트 사이드 전용 (SheetJS: Excel, jsPDF: PDF). 서버는 JSON 데이터만 제공, 파일 변환은 브라우저에서 수행.
6. **초기 설정 전략**: School 및 교사 계정은 Alembic seed script로 생성. 교사가 앱 내에서 학급/과목/학기를 직접 설정.
7. **교사 스코핑 (MVP 제약)**: 담임 교사 1명 = 담당 Class 1개 구조. 교과 교사 다중 반 담당은 평가 후 ClassTeacher M:M 테이블로 확장 예정.
8. **CORS**: 로컬 docker-compose 환경에서 frontend origin만 허용 (`ALLOWED_ORIGINS` 환경변수).
9. **Rate Limiting**: 로그인 엔드포인트와 `/api/v1/chat`에 IP/사용자 기반 제한 (slowapi 라이브러리 사용).
10. **OLAP 분리 (v2.1)**: 운영 트랜잭션은 `public` 스키마, 분석 집계는 `analytics` 스키마. 두 스키마는 동일 PG 인스턴스.
11. **CDC 파이프라인 (v2.1)**: **Outbox 패턴 + Kafka KRaft**. 운영 라우터가 도메인 변경과 같은 트랜잭션으로 `public.outbox`에 INSERT → `outbox-publisher`(aiokafka)가 미발행 row를 polling해 Kafka 토픽으로 produce → `analytics-worker`(aiokafka consumer group)가 `analytics.*` UPSERT. 자세한 근거는 ADR-002.
12. **컨테이너 (v2.1)**: 모든 서비스(`frontend`, `fastapi-api`, `outbox-publisher`, `analytics-worker`, `kafka`, `postgres`)는 단일 `docker-compose.yml`로 묶는다. 확장성은 `docker-compose up --scale analytics-worker=3`으로 시연.
13. **Chatbot (v2.1)**: 별도 서비스 분리하지 않고 FastAPI 백엔드의 단일 라우터(`POST /api/v1/chat`)로 구현. 답변 범위를 학급 단위 통계로 제한(k≥5 실질). 컨텍스트 학생명·학번은 `chatbot/sanitizer.py`에서 단순 치환(`학생A`, `seq_001`).

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
- **페이지네이션**: MVP 구현은 대부분 목록을 배열로 반환합니다. `skip/limit`은 future contract로 남겨두고, 현재 코드 기준으로는 배열 응답을 우선합니다.
- **페이지네이션 일관성**: 현재 구현 기준 목록 조회는 배열 형식입니다. 단건/요약은 객체 직접 반환.

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
| A-005 | 비밀번호 재설정 | 링크 기반 비밀번호 재설정 구현 완료. 기본 전달 전략은 stub/preview이며 운영 환경에서는 이메일 발송 어댑터 연결 필요. |
| A-006 | School/Teacher 초기 생성 | Alembic seed script (CLI). 앱 내 관리자 UI 없음 (MVP 범위 외). |

### 8.3 잠재적 설계 위험

| ID | 위험 | 영향도 | 대응 |
|----|------|--------|------|
| R-001 | 교과 교사 미지원 → 담임이 모든 과목 성적 입력 | 높음 | **고객 합의 필수**. 합의 없으면 MVP 운영 불가. |
| R-005 | 상담 공유 시 알림 폭탄 (교사 수 × 알림) | 중간 | MVP 규모(학교당 교사 10~30명)에서 허용. v2에서 수신자 선택 기능 추가. |
| R-006 | 학생 반 이동 시 이전 담임 데이터 접근 불가 | 낮음 | MVP에서는 반 이동 이력 없음. 이동 전 담임이 필요한 데이터 수동 확인 필요. |
| R-008 | school_id 필터 누락 버그 → 타 학교 데이터 노출 | 매우 높음 | 모든 서비스 메서드에 school_id 검증 단위 테스트 필수. Postgres RLS 보조 레이어 도입 검토 (평가 후). |

### 8.4 2026-04 구현 정렬 사항

- Auth 세션은 `access token(memory)` + `refresh token(HttpOnly cookie)`로 고정되었습니다.
- 공개 회원가입 페이지는 제거되고 초대 링크 기반 가입(`/auth/invitations/*`)으로 전환되었습니다.
- 학생/학부모 계정 생성은 초대 대기 상태(`pending_invite`)로 반환되며, 초기 비밀번호를 서버가 더 이상 고정 주입하지 않습니다.
- teacher CRUD는 `/grades`, `/feedbacks`, `/counselings`, `/notifications`에 유지되고, student/parent read-only는 `/my/*`로 분리되어 있습니다.
- 목록 응답은 현재 구현 기준 배열 형식입니다.
- `GET /grades/{student_id}/summary`는 단일 학기(`semester_id`) 기준 응답이며, 비교 모드는 프런트엔드에서 여러 번 호출합니다.
- 성적 bulk 입력은 `/grades/bulk`가 아니라 `/import/grades`와 `/import/grades/xlsx`로 처리합니다.
- 학생 CSV/XLSX import는 이메일을 포함하며, 성적 CSV import는 `student_number + subject_name` 계약과 update 동작을 지원합니다.
- 상담 상세 화면은 클라이언트 PDF 리포트 내보내기를 지원합니다.

---

## 9. Analytics Layer (v2.1)

> **CDC 패턴**: Outbox + Kafka. 자세한 근거·대안 비교는 ADR-002 참조.

### 9.1 스키마

```sql
-- 분석 스키마 분리
CREATE SCHEMA IF NOT EXISTS analytics;

-- Outbox 테이블 (운영 스키마, 트랜잭션 안에서 INSERT)
CREATE TABLE public.outbox (
  event_id        BIGSERIAL PRIMARY KEY,
  aggregate_type  VARCHAR(50) NOT NULL,   -- 'grade' | 'attendance' | 'feedback' | 'counseling'
  aggregate_id    UUID NOT NULL,
  topic           VARCHAR(50) NOT NULL,   -- 'grade_events' 등
  payload         JSONB NOT NULL,
  created_at      TIMESTAMP NOT NULL DEFAULT now(),
  sent_at         TIMESTAMP NULL          -- publisher가 발행 후 update
);
CREATE INDEX outbox_unsent_idx ON public.outbox (event_id) WHERE sent_at IS NULL;

-- 이벤트 로그 (append-only)
CREATE TABLE analytics.fact_grade_event (
  event_id      BIGSERIAL PRIMARY KEY,
  grade_id      UUID NOT NULL,
  student_id    UUID NOT NULL,
  subject_id    UUID NOT NULL,
  semester_id   UUID NOT NULL,
  score         NUMERIC(5,2),
  grade_rank    SMALLINT,
  op            VARCHAR(10) NOT NULL,  -- INSERT | UPDATE
  occurred_at   TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX ON analytics.fact_grade_event (student_id, occurred_at DESC);

CREATE TABLE analytics.fact_attendance_event (
  event_id      BIGSERIAL PRIMARY KEY,
  attendance_id UUID NOT NULL,
  student_id    UUID NOT NULL,
  semester_id   UUID,                  -- SMS-78: outbox publisher가 resolve해 채움 (nullable, 백필 여유)
  date          DATE NOT NULL,
  status        VARCHAR(15) NOT NULL,
  op            VARCHAR(10) NOT NULL,
  occurred_at   TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX ix_fact_attendance_event_student_semester
  ON analytics.fact_attendance_event (student_id, semester_id);

CREATE TABLE analytics.fact_feedback_event (
  event_id      BIGSERIAL PRIMARY KEY,
  feedback_id   UUID NOT NULL,
  student_id    UUID NOT NULL,
  semester_id   UUID,
  category      VARCHAR(15),           -- score | behavior | attendance | attitude
  op            VARCHAR(10) NOT NULL,  -- INSERT | UPDATE | DELETE
  occurred_at   TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX ix_fact_feedback_event_student_semester
  ON analytics.fact_feedback_event (student_id, semester_id);
CREATE INDEX ix_fact_feedback_event_feedback
  ON analytics.fact_feedback_event (feedback_id, occurred_at DESC);

CREATE TABLE analytics.fact_counseling_event (
  event_id      BIGSERIAL PRIMARY KEY,
  counseling_id UUID NOT NULL,
  student_id    UUID NOT NULL,
  teacher_id    UUID NOT NULL,
  date          DATE,
  op            VARCHAR(10) NOT NULL,  -- INSERT | UPDATE
  occurred_at   TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX ix_fact_counseling_event_student
  ON analytics.fact_counseling_event (student_id, occurred_at DESC);

-- 집계 캐시 (UPSERT, consumer가 갱신)
CREATE TABLE analytics.agg_student_subject (
  student_id      UUID NOT NULL,
  subject_id      UUID NOT NULL,
  semester_id     UUID NOT NULL,
  avg_score       NUMERIC(5,2),
  max_score       NUMERIC(5,2),
  min_score       NUMERIC(5,2),
  latest_rank     SMALLINT,
  sample_count    INTEGER NOT NULL,
  refreshed_at    TIMESTAMP NOT NULL DEFAULT now(),
  PRIMARY KEY (student_id, subject_id, semester_id)
);

CREATE TABLE analytics.agg_student_overall (
  student_id     UUID NOT NULL,
  semester_id    UUID NOT NULL,
  total_score    NUMERIC(7,2),
  avg_score      NUMERIC(5,2),
  subject_count  INTEGER NOT NULL,
  attendance_present_rate NUMERIC(4,3),
  feedback_count INTEGER NOT NULL DEFAULT 0,
  refreshed_at   TIMESTAMP NOT NULL DEFAULT now(),
  PRIMARY KEY (student_id, semester_id)
);

-- Dead-letter sink (SMS-80): poison 메시지(decode 실패 / 필수 필드 누락 / 알 수 없는 topic)는
-- 이 테이블에 기록 후 consumer offset commit. transient error(DB 일시 오류 등)는 commit 안 함.
CREATE TABLE analytics.dead_letter_event (
  id           BIGSERIAL PRIMARY KEY,
  topic        VARCHAR(50) NOT NULL,
  partition    INTEGER,
  offset_      BIGINT,
  raw_value    BYTEA,
  error        TEXT NOT NULL,
  occurred_at  TIMESTAMP NOT NULL DEFAULT now()
);
```

**Counseling은 집계 미반영**: counseling 이벤트는 `fact_counseling_event`에 audit 목적으로만 기록되며 `agg_student_overall`에 영향 없음. 향후 BI 요구가 생기면 별도 agg 테이블 추가.

**Semester 바인딩 주의**: `Semester` 모델은 (year, term)만 가지며 date range가 없어 `Attendance`/`Feedback`을 의미적으로 매핑할 수 없다. v2.1에선 operational 라우터가 outbox INSERT 시점에 "가장 최근 (year DESC, term DESC) 학기"를 resolve해 payload·fact row에 박는다 (`app/services/semester.py:current_semester_id`). 의미적 정확도가 필요하면 향후 `Semester`에 date range 컬럼 추가 또는 `Attendance`/`Feedback`에 직접 FK 부여 필요.

### 9.2 운영 라우터의 Outbox INSERT (트랜잭션 일관성)

운영 도메인 변경(예: grade UPSERT) 직후 **같은 트랜잭션** 안에서 `public.outbox`에 row를 INSERT한다. 이로써 도메인 변경이 commit되면 outbox row도 반드시 함께 영속화되며, broker가 다운돼도 이벤트가 유실되지 않는다.

```python
# app/services/grade.py — pseudo
async def create_grade(db: AsyncSession, *, student_id: UUID, ...) -> Grade:
    grade = Grade(student_id=student_id, ...)
    db.add(grade)
    await db.flush()  # grade.id 채워야 outbox row의 aggregate_id로 사용 가능
    db.add(Outbox(
        aggregate_type="grade",
        aggregate_id=grade.id,
        topic="grade_events",
        payload={
            "grade_id": str(grade.id),
            "student_id": str(student_id),
            "subject_id": str(grade.subject_id),
            "semester_id": str(grade.semester_id),
            "score": float(grade.score) if grade.score is not None else None,
            "grade_rank": grade.grade_rank,
            "op": "INSERT",  # update_grade는 "UPDATE", delete는 "DELETE"
        },
    ))
    await db.commit()
    return grade
```

`attendance`, `feedback`, `counseling` 라우터에서 동일한 패턴 적용. `op` 값은 도메인 작업 종류 그대로 (`INSERT`/`UPDATE`/`DELETE`).

**event_id envelope**: outbox row의 `event_id`는 publisher가 publish 직전에 payload에 주입한다 (`{**row.payload, "event_id": row.event_id}`). consumer는 이 값을 PK로 사용해 `INSERT ... ON CONFLICT (event_id) DO NOTHING`으로 idempotency를 보장. 운영 라우터는 outbox row를 만들 때만 책임지고 event_id 주입은 신경 쓰지 않는다.

### 9.3 Outbox Publisher (Kafka producer)

`public.outbox` 테이블의 미발행 row(`sent_at IS NULL`)를 polling하여 Kafka 토픽으로 발행한다.

```python
# app/workers/outbox_publisher.py — pseudo
async def main() -> None:
    producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP,
        enable_idempotence=True,
        acks="all",
    )
    await producer.start()
    try:
        while True:
            rows = await fetch_unsent(limit=100)  # ORDER BY event_id
            if not rows:
                await asyncio.sleep(0.5)
                continue
            for row in rows:
                await producer.send_and_wait(
                    row.topic,
                    value=json.dumps(row.payload).encode(),
                    key=str(row.aggregate_id).encode(),
                )
                await mark_sent(row.event_id)
    finally:
        await producer.stop()
```

**부팅 시 catch-up**: 별도 로직 불필요. `WHERE sent_at IS NULL` 쿼리가 자동 catch-up 역할 수행.

### 9.4 Analytics Worker (Kafka consumer)

단일 worker 프로세스가 4개 topic을 구독하고 record의 `topic` 필드로 핸들러를 dispatch한다.

```python
# app/workers/analytics.py — pseudo
SUBSCRIBED_TOPICS = (
    "grade_events", "attendance_events", "feedback_events", "counseling_events",
)


async def dispatch_event(payload: dict, *, repo: AnalyticsRepository, topic: str) -> None:
    if topic == "grade_events":         await process_event(payload, repo=repo)
    elif topic == "attendance_events":  await process_attendance_event(payload, repo=repo)
    elif topic == "feedback_events":    await process_feedback_event(payload, repo=repo)
    elif topic == "counseling_events":  await process_counseling_event(payload, repo=repo)
    else:                               raise ValueError(f"unknown topic: {topic!r}")


async def run(*, consumer, session_factory, ...):
    await consumer.start()
    try:
        while not stop_event.is_set():
            record = await consumer.getone()
            try:
                try:
                    payload = decode_record(record.value)  # raises ValueError on bad JSON
                except (JSONDecodeError, ValueError) as exc:
                    raise PoisonMessageError(f"decode failed: {exc}") from exc
                async with session_factory() as db:
                    repo = PostgresAnalyticsRepo(db)
                    try:
                        await dispatch_event(payload, repo=repo, topic=record.topic)
                    except (KeyError, ValueError) as exc:
                        raise PoisonMessageError(f"dispatch failed: {exc}") from exc
                    await db.commit()
                await consumer.commit()
            except PoisonMessageError as exc:
                # 영구 오류: dead_letter_event에 기록, offset commit해서 같은 메시지 무한 retry 회피
                async with session_factory() as db:
                    await PostgresAnalyticsRepo(db).record_dead_letter(
                        topic=record.topic, partition=record.partition,
                        offset=record.offset, raw_value=record.value, error=str(exc),
                    )
                    await db.commit()
                await consumer.commit()
            except Exception:
                # transient: DB 일시 오류 등. offset commit 안 함 → 다음 iteration에서 같은 메시지 재시도
                logger.exception("transient error; will retry")
                await asyncio.sleep(backoff)
    finally:
        await consumer.stop()
```

#### 핸들러 별 처리 매트릭스

| Topic | Fact 테이블 | Agg 영향 |
|---|---|---|
| `grade_events` | `fact_grade_event` (INSERT ON CONFLICT) | `agg_student_subject` + `agg_student_overall` UPSERT |
| `attendance_events` | `fact_attendance_event` | `agg_student_overall.attendance_present_rate` |
| `feedback_events` | `fact_feedback_event` | `agg_student_overall.feedback_count` (DELETE op 제외) |
| `counseling_events` | `fact_counseling_event` | (없음 — audit only) |

#### Agg 재계산 패턴 (`recompute_agg_overall`)

운영의 부분 변경(INSERT/UPDATE/DELETE)이 아니라 **현재 fact 상태로부터 항상 전체 재계산** 한다. UPDATE 이벤트가 fact를 중복으로 쌓는 문제는 `DISTINCT ON (<aggregate_id>) ORDER BY occurred_at DESC` CTE로 해결.

```sql
-- agg_student_overall은 grade/attendance/feedback 컬럼을 한 번에 UPSERT
WITH latest_grades AS (
  SELECT DISTINCT ON (grade_id) score
  FROM analytics.fact_grade_event WHERE student_id=$1 AND semester_id=$2
  ORDER BY grade_id, occurred_at DESC, event_id DESC
),
latest_attendance AS (...),
latest_feedback AS (
  SELECT DISTINCT ON (feedback_id) op
  FROM analytics.fact_feedback_event WHERE student_id=$1 AND semester_id=$2
  ORDER BY feedback_id, occurred_at DESC, event_id DESC
)
INSERT INTO analytics.agg_student_overall (...) VALUES (...)
ON CONFLICT (student_id, semester_id) DO UPDATE SET ...
```

#### Idempotency

- 모든 fact 테이블이 `event_id` PK + `ON CONFLICT (event_id) DO NOTHING` → 중복 메시지 0 행 추가
- consumer는 fact INSERT가 no-op(이미 처리됨)이면 agg recompute를 skip
- 즉 동일 메시지가 N번 와도 fact rowcount·agg 값 모두 불변

#### 수평 확장

`docker-compose up --scale analytics-worker=3` → consumer group이 파티션 자동 분배. group_id가 동일하면 Kafka가 partition rebalance를 처리. 단, 각 (student_id, semester_id)에 대한 agg UPSERT는 동시 실행 가능성이 있어 row-level lock에 의존 — Postgres `ON CONFLICT DO UPDATE`는 자동 lock.

#### Dead-Letter 정책

| 에러 유형 | 처리 | offset commit |
|---|---|---|
| Permanent (decode 실패, 필수 필드 누락, 알 수 없는 topic) | `analytics.dead_letter_event` INSERT | ✅ commit (poison 메시지가 consumer를 무한 차단하지 않도록) |
| Transient (DB 다운, 일시 네트워크 오류) | log + exponential backoff | ❌ no commit → 다음 iteration에서 재시도 |

운영 측에선 `SELECT * FROM analytics.dead_letter_event ORDER BY occurred_at DESC` 로 poison 메시지를 검토 후 producer 측 수정 또는 수동 replay.

### 9.5 분석 API

| Method | Path | 설명 | Auth |
|--------|------|------|------|
| GET | `/api/v1/analytics/teachers/me/dashboard` | 교사 메인 위젯 (담당 학급 요약) | teacher |
| GET | `/api/v1/analytics/students/{id}/overview` | 학생 학습 요약 (학기 추이) | teacher (담당) |
| GET | `/api/v1/analytics/classes/{id}/distribution` | 학급 점수 분포 | teacher (담임) |
| GET | `/api/v1/analytics/subjects/{id}/trend` | 과목 평균 추이 | teacher (담임) |

응답은 `analytics.agg_*` 테이블에서 직접 조회. 무거운 집계 쿼리 금지.

### 9.6 일관성 보장

| 항목 | 정책 |
|------|------|
| 실시간성 | 운영 변경 → 분석 반영 ≤ 1분 (Kafka 발행 + consumer 처리는 통상 sub-second) |
| 정합성 검증 | 통합 테스트(testcontainers) + `scripts/check_consistency.py` (운영 row vs fact row 비교) |
| Publisher 다운 | outbox row commit됨 → 부팅 시 `WHERE sent_at IS NULL` 자동 catch-up |
| Consumer 다운 | Kafka offset 보관 → 재기동 시 마지막 commit offset부터 재구독 |
| Broker 다운 | publisher가 producer.send에서 retry. 운영 트랜잭션은 정상 commit (outbox row 누적) |
| 백필 | Alembic data migration 스크립트 (`scripts/backfill_analytics.py`): 운영 테이블 전체 스캔 → outbox INSERT (publisher가 catch-up) |

---

## 10. AI 어시스턴트 (v2.1, 데모용)

> **명명 정정**: 본 기능은 벡터 인덱싱·의미 검색이 없으므로 정식 RAG가 아니다. *"분석 데이터 기반 LLM 자연어 응답"*으로 통일한다.

### 10.1 구성

```
[Frontend Chat Widget]
        │  POST /api/v1/chat
        ▼
[fastapi-api : routers/chat.py]
        │ 1. RBAC 검증 (teacher 한정)
        │ 2. 의도 분류 (간단한 키워드 라우팅)
        │ 3. analytics.agg_* 쿼리 → context 구성 (학급 단위 통계만, k≥5)
        │ 4. PII 마스킹 (chatbot/sanitizer.py)
        │ 5. LLM SDK 호출 (provider는 환경변수로 단일 선택)
        │ 6. 응답 후처리 (token → 실제 학생 매핑)
        ▼
[LLM Provider (외부, OpenAI 또는 Anthropic)]
```

### 10.2 LLM 호출 (단일 provider 직접 호출)

별도 `LLMClient` 추상화 인터페이스는 도입하지 않는다. 환경변수 `LLM_PROVIDER`로 하나의 SDK를 선택해 직접 호출.

```python
# app/chatbot/llm.py — pseudo
async def complete(prompt: str, context: list[dict]) -> str:
    provider = settings.LLM_PROVIDER  # "openai" | "anthropic"
    if provider == "openai":
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        resp = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "system", "content": system_prompt(context)},
                      {"role": "user", "content": prompt}],
            max_tokens=1024,
        )
        return resp.choices[0].message.content
    elif provider == "anthropic":
        client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        resp = await client.messages.create(
            model=settings.LLM_MODEL,
            max_tokens=1024,
            system=system_prompt(context),
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text
    raise ValueError(f"unknown provider: {provider}")
```

### 10.3 PII 마스킹 규약

```python
# app/chatbot/sanitizer.py — pseudo
def mask_context(rows: list[dict]) -> tuple[list[dict], dict[str, UUID]]:
    """학급 단위 통계만 받음. 단일 학생 식별 불가능한 응답이 보장되도록 사전에 k≥5 필터."""
    token_map: dict[str, UUID] = {}
    masked_rows = []
    for i, row in enumerate(rows, start=1):
        token = f"학생{chr(64 + i)}"  # 학생A, 학생B, ...
        if "student_id" in row:
            token_map[token] = row["student_id"]
            row = {**row, "student_name": token, "student_number": f"seq_{i:03d}"}
            row.pop("student_id", None)
            row.pop("email", None)
            row.pop("phone", None)
        masked_rows.append(row)
    return masked_rows, token_map
```

| 원본 | 마스킹 |
|------|--------|
| `김철수` (학생명) | `학생A` |
| `student_number=15` | `seq_015` |
| 학부모 이메일/전화 | (컨텍스트에서 제거) |
| `student_id` (UUID) | (컨텍스트에서 제거, 서버 메모리 매핑만 유지) |
| 교사명 | 유지 (질의자 본인) |

응답 후처리에서 `학생A` 등의 token을 매핑 테이블로 실제 학생 객체로 치환하여 클라이언트에 전달.

### 10.4 API

```
POST /api/v1/chat
Request:  { "thread_id": "uuid|null", "message": "string" }
Response: {
  "thread_id": "uuid",
  "reply": "string",
  "referenced_students": [{ "id": "uuid", "name": "string" }]
}

Authorization: teacher only
Rate Limit: 10회/분 per user (slowapi)
```

### 10.5 비용·안전 제어

- 컨텍스트 크기 상한: 8K tokens (분석 요약만 포함, 학급 단위)
- 응답 토큰 상한: 1024
- 답변 범위 제한: 학급 단위 통계 (k≥5). 단일 학생 식별 가능한 질의는 거부 메시지 반환.
- 프롬프트 인젝션 방어: 컨텍스트 데이터를 system message에, 사용자 입력을 user message로 분리. 사용자 입력은 길이 1000자로 제한.

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
| REQ-005 | 비밀번호 재설정 | ✅ |
| US-007 AC (알림 ON/OFF) | §3.8 NotificationPreference | ✅ |
| REQ-070 (분석 스키마 분리) | §9.1 analytics.* (Sprint 1 SMS-49) | ✅ v2.1 |
| REQ-071 (Outbox + Kafka 이벤트 적재) | §9.2~9.4 (Sprint 1 SMS-50~53, Sprint 2 SMS-78~80 4 도메인 확장) | ✅ v2.1 |
| REQ-072 (집계 테이블) | §9.1 agg_student_subject/overall (Sprint 2에서 attendance_present_rate + feedback_count까지 채움) | ✅ v2.1 |
| REQ-073 (교사 대시보드) | §9.5 GET /analytics/* | 🚧 v2.1 (Sprint 3 SMS-74) |
| REQ-074 (≤ 1분 반영) | §9.6 + Sprint 1 SMS-54 + Sprint 2 SMS-81 e2e idempotency | ✅ v2.1 |
| REQ-075 (scale=N 시연) | §1 docker-compose `--scale analytics-worker=3` | 🚧 v2.1 |
| REQ-080~083 (AI 어시스턴트 단일 엔드포인트 + PII 마스킹) | §10 AI 어시스턴트 | 🚧 v2.1 |

---

*Design Spec v2.1 — 확정*
