# 학생 성적 및 상담 관리 시스템 — Design Spec

**버전**: 2.3
**작성일**: 2026-05-31 (v2.2 → 2026-05-23)
**상태**: 확정
**기반 문서**: PRD v2.2, ADR-001 (재작성), ~~ADR-002 (Outbox + Kafka)~~ → **ADR-003** (Outbox + Postgres LISTEN/NOTIFY + SKIP LOCKED)
**프로젝트 성격**: 졸업 평가용 프로토타입 (Render + Vercel 클라우드 + 로컬 docker-compose, 사용자 0명)
**변경 이력**:
- v1.0 → v2.0: Critic 리뷰 반영
- v2.0 → v2.1: §1 docker-compose 로컬 인프라, §9 Outbox+Kafka 기반 Analytics Layer, §10 단일 엔드포인트 챗봇
- v2.1 → v2.2: ADR-003 반영 — Kafka 제거, Postgres LISTEN/NOTIFY + SKIP LOCKED로 §9 CDC 메커니즘 교체. 클라우드 surface (Vercel + Render Worker × 2) 추가.
- v2.2 → v2.3: 발표 보완 5종 반영 — 교사 Google OAuth(§3.1.1) · 무중단 배포 헬스 probe(§3.10) · OpenAPI 명세 산출 강화(§3 머리말) · 테스트 피라미드 실측(§8.5). (②④는 프로세스/산출물 항목으로 `docs/notes/` 참조)

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

> **다이어그램·기술 스택은 다른 문서로 위임**
> - 컨테이너 다이어그램 + 데이터 흐름: `architecture.md` §3 (C4 Level 2), §4 (모듈 흐름)
> - 기술 스택 표: `prd.md` §7
> - 멀티테넌트 격리·인증 토큰 전략·30초 폴링·9등급 계산·교사 스코핑·OLAP 분리·CDC 파이프라인·컨테이너 구성·챗봇 범위: `prd.md` §7 "핵심 결정사항"

본 절은 위 문서에 없는 **구현·운영 디테일**만 보존한다.

### 핵심 설계 결정사항 (구현 디테일)

1. **초기 설정 전략**: School + 최초 교사(teacher) 계정은 Alembic seed script로 생성 (CLI, 배포 시 1회 실행). 교사가 앱 로그인 후 Semester → Class → Subject 순으로 직접 생성. **앱 내 관리자 UI 없음** (MVP 범위 외).
2. **CORS**: 로컬 docker-compose 환경에서 frontend origin만 허용 (`ALLOWED_ORIGINS` 환경변수, JSON 배열 문자열).
3. **Rate Limiting**: 로그인 엔드포인트와 `/api/v1/chat`에 slowapi 기반 제한. 챗봇은 사용자 ID 키, 로그인은 IP 키.
4. **타 학교 데이터 접근**: 404 반환 (403 대신 — 존재 자체를 숨김. IDOR 방지). §4.3과 일관.
5. **챗봇 마스킹 토큰 확장**: 학생 26명 초과 시 `학생A..Z` → `학생AA..ZZ`로 두 글자 확장 (~702명까지 안전). 라우터 정규식 `학생[A-Z]{1,2}`로 양쪽 매칭. 상세 §10.3.
6. **교사 Google OAuth (v2.3, REQ-006)**: Authorization Code + OIDC. state는 HttpOnly 쿠키 바인딩 + `secrets.compare_digest`로 검증(CSRF 방어). `email_verified` 가드 + `ALLOWED_TEACHER_DOMAINS` 화이트리스트 게이트. `GoogleOAuthClient` Protocol + Stub/Real 구현으로 DI (LLM 클라이언트와 동일 패턴). stub은 `ENVIRONMENT≠production` 또는 `ALLOW_OAUTH_STUB=true`에서만 동작 — production 인증 우회 차단. 상세 §3.1.1.
7. **무중단 배포 헬스 probe (v2.3)**: `/health`(liveness) / `/ready`(readiness, `SELECT 1` DB 검증) 분리. 상세 §3.10.

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

> **OpenAPI 자동 생성**: 모든 엔드포인트의 요청·응답 Pydantic 스키마는 백엔드 기동 후 `http://localhost:8000/docs` (Swagger UI) 또는 `/openapi.json`에서 확인 가능. 본 절은 OpenAPI에 표현되지 않는 **에러 코드 / RBAC 뉘앙스 / side effect / 도메인 규칙**을 명시한다.

### 공통 규칙

- **Base URL**: `/api/v1`
- **Content-Type**: `application/json` (파일 업로드 제외)
- **인증**: `Authorization: Bearer <access_token>` (로그인, 리프레시, 자명한 표 아래 단순 엔드포인트 제외)
- **오류 응답 형식**: `{ "detail": "message", "code": "ERROR_CODE" }`
- **페이지네이션**: 목록 조회는 배열 형식. 단건/요약은 객체 직접 반환. `skip/limit`은 future contract.

### 단순 엔드포인트 인벤토리

요청·응답이 자명하고 별도 contract가 없는 엔드포인트는 다음 표로 갈음한다. 상세 스키마는 `/docs` 참조.

| Method | Path | 설명 | Authorization |
|--------|------|------|---------------|
| POST | `/auth/logout` | refresh_token 쿠키 삭제, 204 | 인증된 모든 사용자 |
| GET | `/auth/me` | 본인 user 정보 | 인증된 모든 사용자 |
| GET | `/semesters` | 학기 목록 | 인증된 모든 사용자 |
| PATCH | `/notifications/read-all` | 본인 알림 전체 읽음 처리 | 인증된 모든 사용자 |
| GET | `/notifications/preferences` | 본인 알림 설정 조회 | 인증된 모든 사용자 |

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

> `POST /auth/logout`, `GET /auth/me` — §3 머리말 "단순 엔드포인트 인벤토리" 표 참조.

#### 3.1.1 교사 Google OAuth (v2.3, REQ-006)

> 학생·학부모는 초대 링크 가입, **교사는 Google OAuth + 학교 이메일 도메인 화이트리스트**로 계정 발급 문제를 완결한다.

#### GET /auth/oauth/google/login
```
Response 200:
  { "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth?..." }
  Set-Cookie: oauth_state=<random>; HttpOnly; SameSite=lax; Max-Age=600

-- 클라이언트는 authorize_url로 redirect. state는 쿠키에 바인딩되어 CSRF 방어.
Authorization: None
```

#### GET /auth/oauth/google/callback
```
Query: ?code=<auth_code>&state=<state>

Response 200: (POST /auth/login과 동일한 TokenResponse — access_token + refresh 쿠키)

Response 400: { "code": "AUTH_OAUTH_STATE_MISMATCH",   "detail": "잘못된 OAuth 요청입니다 (state 불일치)." }
Response 403: { "code": "AUTH_OAUTH_DOMAIN_NOT_ALLOWED", "detail": "허용되지 않은 이메일 도메인입니다." }
Response 503: { "code": "AUTH_OAUTH_NOT_CONFIGURED",    "detail": "OAuth가 구성되지 않았습니다." }  -- production에서 stub 호출 시

Authorization: None
처리 순서: state↔쿠키 compare_digest → code→token→userinfo → email_verified 가드
          → 도메인 화이트리스트 게이트 → 기존 교사 로그인 / 신규 교사 생성(oauth_default_school_id)
환경변수: OAUTH_PROVIDER(auto|real|stub), GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI,
          ALLOWED_TEACHER_DOMAINS(CSV), OAUTH_DEFAULT_SCHOOL_ID, ALLOW_OAUTH_STUB, ENVIRONMENT
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

> `GET /semesters` — 인벤토리 표 참조.

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

> `PATCH /notifications/read-all`, `GET /notifications/preferences` — 인벤토리 표 참조.

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

### 3.10 헬스체크 / 무중단 배포 게이트 (v2.3)

> 인증 불필요. `/api/v1` prefix 밖의 루트 엔드포인트. liveness ≠ readiness 분리로 무중단 롤링 배포를 지원.

#### GET /health — Liveness probe
```
Response 200: { "status": "ok" }   -- 프로세스 생존만 확인 (DB 미접근, 즉시 응답)
용도: 컨테이너 오케스트레이터가 프로세스 데드락/행 감지 → 실패 시 재시작
```

#### GET /ready — Readiness probe
```
Response 200: { "status": "ready" }
Response 503: { "code": "DB_NOT_READY", "detail": "데이터베이스 준비가 되지 않았습니다." }
검증: SELECT 1로 DB 연결 확인. 실패 시 503 → LB가 트래픽 제외 (재시작 아님)
용도: 롤링 배포 시 신 인스턴스가 ready가 된 후에만 트래픽 수신 (maxUnavailable=0).
      Render는 healthCheckPath로, 예시 K8s(`deploy/k8s/`)는 readinessProbe로 동일 의미론.
```

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

### 8.5 테스트 전략 — 3계층 피라미드 (v2.3, 실측 2026-05-31)

| 계층 | 도구·위치 | 실측 | 검증 대상 |
|------|-----------|------|-----------|
| 단위 (unit) | pytest, `backend/tests/test_*.py` | 200 passed / 10 skip, **커버리지 81%** | 9등급 계산, RBAC 스코프, school_id 격리, LLM sanitizer, OAuth 도메인 게이트 |
| 통합 (integration) | testcontainers 실 Postgres, `backend/tests/integration/` | `pytest -m integration` | outbox→publisher→worker→`analytics.*` 정합성, SKIP LOCKED scale=3 중복 0, idempotency |
| E2E | Playwright, `frontend/e2e/*.spec.ts` | 11 spec | 로그인·성적·피드백·분석 RBAC·챗봇 PII 마스킹·모바일 반응형 |

> Frontend 컴포넌트 단위 테스트는 호스트 환경 이슈(Node 25 ≠ vitest 1.6 + Linux node_modules 바이너리)로 일시 보류 — 근본 원인·해결 명령은 `docs/notes/frontend-test-env-fix.md`. E2E가 frontend 동작을 실 브라우저로 검증하므로 평가 신뢰성은 확보. 발표 서사는 `docs/notes/test-pyramid-presentation.md`.

---

## 9. Analytics Layer (v2.1)

> **CDC 패턴**: Outbox + Postgres LISTEN/NOTIFY + `SELECT FOR UPDATE SKIP LOCKED`. 자세한 근거·대안 비교는 ADR-003 (ADR-002 supersede) 참조.

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

### 9.3 Outbox Publisher (NOTIFY relay)

`public.outbox` 테이블의 미발행 row(`sent_at IS NULL`)를 `SELECT FOR UPDATE SKIP LOCKED`로 batch fetch한 뒤 row마다 `pg_notify(<topic_channel>, <envelope>)`를 emit하고 `sent_at`을 업데이트한다. **전체가 단일 transaction**이라 발행/마킹이 원자적이며, SKIP LOCKED 덕분에 publisher를 여러 인스턴스 띄워도 race-free.

```python
# app/workers/outbox_publisher.py — pseudo (ADR-003)
async def _drain_once(db, notifier, *, batch_size=100) -> int:
    async with db.begin():
        rows = await fetch_unsent_locked(db, limit=batch_size)  # FOR UPDATE SKIP LOCKED
        if not rows:
            return 0
        for row in rows:
            envelope = json.dumps({"event_id": row.event_id})  # ≤ 8KB NOTIFY limit
            await notifier.notify(db, channel=row.topic, payload=envelope)
            #  ↑ SELECT pg_notify(:channel, :payload)
        await db.execute(
            update(Outbox).where(Outbox.event_id.in_([r.event_id for r in rows]))
            .values(sent_at=datetime.utcnow())
        )
    return len(rows)
```

**부팅 시 catch-up**: 별도 로직 불필요. `WHERE sent_at IS NULL` 쿼리가 자동 catch-up 역할 수행.
**Envelope**: NOTIFY payload는 `{"event_id": <id>}`만 담는다 (Postgres NOTIFY 8KB 한도 보호). worker는 event_id로 outbox row를 다시 SELECT해서 full payload 획득.

### 9.4 Analytics Worker (LISTEN + SKIP LOCKED claim)

각 worker 프로세스가 4개 채널을 LISTEN하고 NOTIFY가 도착하면 outbox row를 `SELECT FOR UPDATE SKIP LOCKED + processed_at IS NULL`로 claim해서 처리한다. N개 워커가 동일 NOTIFY를 받지만 row lock 경쟁에서 정확히 1개만 잠그고 처리 — Kafka consumer group의 partition 분배 등가.

```python
# app/workers/analytics.py — pseudo (ADR-003)
SUBSCRIBED_CHANNELS = (
    "grade_events", "attendance_events", "feedback_events", "counseling_events",
)


async def dispatch_event(payload: dict, *, repo, topic: str) -> None:
    if topic == "grade_events":         await process_event(payload, repo=repo)
    elif topic == "attendance_events":  await process_attendance_event(payload, repo=repo)
    elif topic == "feedback_events":    await process_feedback_event(payload, repo=repo)
    elif topic == "counseling_events":  await process_counseling_event(payload, repo=repo)
    else:                               raise ValueError(f"unknown topic: {topic!r}")


async def _process_one(event_id, *, topic, session_factory, repo_builder, max_retries):
    async with session_factory() as db, db.begin():
        row = await claim_outbox_row(db, event_id)   # FOR UPDATE SKIP LOCKED + processed_at IS NULL
        if row is None:
            return  # another worker won, or row already processed
        try:
            payload = {**row.payload, "event_id": row.event_id}
            await dispatch_event(payload, repo=repo_builder(db), topic=topic)
        except (KeyError, ValueError) as exc:
            await _dead_letter(db, row, topic, str(exc), repo_builder=repo_builder)
            await mark_processed(db, row.event_id)
            return
        except Exception as exc:
            count = await record_failure(db, row.event_id, str(exc))
            if count >= max_retries:
                await _dead_letter(db, row, topic, "max retries", repo_builder=repo_builder)
                await mark_processed(db, row.event_id)
                return
            raise  # rollback → row stays claimable for next NOTIFY/catch-up
        await mark_processed(db, row.event_id)


async def run(*, listener, session_factory, repo_builder=..., max_retries=3, catchup_interval=60):
    queue: asyncio.Queue[tuple[str, int]] = asyncio.Queue()
    for ch in SUBSCRIBED_CHANNELS:
        await listener.add_listener(ch, lambda c, p, ch, payload, ch=ch:
            queue.put_nowait((ch, json.loads(payload)["event_id"])))

    # Periodic catch-up: NOTIFY 유실 시 안전망
    async def catchup():
        while True:
            async with session_factory() as db, db.begin():
                rows = await fetch_unprocessed_locked(db, limit=200)
                for r in rows: queue.put_nowait((r.topic, r.event_id))
            await asyncio.sleep(catchup_interval)

    asyncio.create_task(catchup())
    while True:
        topic, event_id = await queue.get()
        await _process_one(event_id, topic=topic,
                           session_factory=session_factory,
                           repo_builder=repo_builder, max_retries=max_retries)
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

`docker-compose up --scale analytics-worker=3` → N개 워커가 동일 NOTIFY를 수신하지만 `SELECT FOR UPDATE SKIP LOCKED`로 outbox row 경쟁 → 정확히 1개 워커만 row를 잠그고 처리 (Kafka consumer group의 partition 분배 등가). agg UPSERT 동시 실행 가능성은 Postgres `ON CONFLICT DO UPDATE`의 자동 lock으로 직렬화. 같은 패턴이 Sidekiq `bulk_dequeue`, oban `Oban.Job` 등 production 큐 시스템에서 사용됨.

#### Dead-Letter 정책

| 에러 유형 | 처리 | outbox.processed_at |
|---|---|---|
| Permanent (필수 필드 누락, 알 수 없는 topic) | `analytics.dead_letter_event` INSERT (`outbox_event_id` 함께 저장) | ✅ mark (poison row가 queue를 무한 차단하지 않도록) |
| Transient (DB 다운, 일시 네트워크 오류) | `outbox.retry_count` 증분 + `last_error` 기록 + rollback | ❌ no mark → 다음 NOTIFY/catch-up tick에서 재claim |
| Transient × N회 초과 | `analytics.dead_letter_event` INSERT + `last_error` 보존 | ✅ mark |

운영 측에선 `SELECT * FROM analytics.dead_letter_event ORDER BY occurred_at DESC` 로 poison 메시지를 검토 후 producer 측 수정 또는 수동 replay (outbox row의 `processed_at`을 NULL로 되돌리면 다음 catch-up에서 재처리).

### 9.5 분석 API

| Method | Path | 설명 | Auth |
|--------|------|------|------|
| GET | `/api/v1/analytics/teachers/me/dashboard` | 교사 메인 위젯 (담당 학급 요약) | teacher |
| GET | `/api/v1/analytics/students/{id}/overview` | 학생 학습 요약 (학기 추이) | teacher (담당) |
| GET | `/api/v1/analytics/classes/{id}/distribution` | 학급 점수 분포 | teacher (담임) |

응답은 `analytics.agg_*` 테이블에서 직접 조회. 무거운 집계 쿼리 금지.

> 과목 추이(`/analytics/subjects/{id}/trend`)는 미구현 — 평가 후 트랙. 학생별 학기 추이는 `students/{id}/overview` 응답의 `semester_history`로 갈음한다.

### 9.6 일관성 보장

| 항목 | 정책 | 검증 |
|------|------|------|
| 실시간성 | 운영 변경 → 분석 반영 ≤ 1분 (NOTIFY 발행 + worker 처리는 통상 sub-second; catch-up 폴링이 60s 안전망) | `test_pipeline_propagates_grade_event_within_sla` (SMS-54) |
| 정합성 검증 | testcontainers 통합 테스트가 운영 row 수 vs `analytics.fact_*` row 수를 자동 비교 (별도 CLI 스크립트 미도입) | `backend/tests/integration/*` (Sprint 1·2, `pytest -m integration`) |
| Idempotency (중복 메시지) | 모든 fact 테이블이 `event_id` PK + `ON CONFLICT DO NOTHING`. consumer가 no-op 감지 시 agg recompute skip → fact rowcount·agg 값 모두 불변 | `test_idempotency_e2e.py` 5개 시나리오 (SMS-81) |
| Publisher 다운 | outbox row commit됨 → 부팅 시 `WHERE sent_at IS NULL` 자동 catch-up | `test_publisher_drains_backlog_after_late_start` (SMS-54) |
| Worker 다운 | outbox.processed_at IS NULL 상태로 잔여 → 재기동 시 catch-up이 `WHERE processed_at IS NULL` 모두 SKIP LOCKED 드레인, 이벤트 누락 0 | `test_worker_resumes_after_restart_without_loss` (SMS-54) |
| Broker 다운 | publisher가 producer.send에서 retry. 운영 트랜잭션은 정상 commit (outbox row 누적) | SMS-52 catch-up 단위 테스트 |
| Poison message | decode 실패 / 필수 필드 누락 / 알 수 없는 topic → `analytics.dead_letter_event` 기록 + offset commit. main consumer는 차단되지 않음 | `test_malformed_payload_routes_to_dead_letter_table` (SMS-81) |
| Transient error (DB 일시 오류 등) | offset commit 안 함 + exponential backoff. 다음 iteration에서 재시도 | run() 루프 코드 |
| 백필 | **평가 후 트랙**. 평가용 시드는 `scripts/demo_seed.py`가 운영 INSERT와 함께 outbox row를 stage하므로 publisher/consumer가 정상 흐름으로 채운다. 실운영 도입 시 전체 스캔 → outbox 발행 스크립트 필요 | 미구현 |

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
[LLM Provider (외부, OpenAI 호환 endpoint — 단일)]
```

### 10.2 LLM 호출 (OpenAI 호환 endpoint, 단일)

`OPENAI_API_KEY` + `LLM_BASE_URL`(기본 `https://api.openai.com/v1`, Kimi/Together/Groq 등 호환 게이트웨이로 전환 가능)로 OpenAI SDK 하나를 호출한다. 키 미설정 또는 `LLM_PROVIDER=stub`이면 결정론적 `StubLlmClient`로 폴백.

테스트 용이성을 위해 `LlmClient` Protocol을 두고 의존성 주입(`tests/test_chat.py`가 `app.dependency_overrides[get_llm_client]`로 `FakeLlm` 주입) — 의도된 진화.

```python
# app/services/llm_client.py — 실제 구조 (요약)
class LlmClient(Protocol):
    async def complete(self, *, system: str, user: str) -> str: ...

class StubLlmClient:
    async def complete(self, *, system, user) -> str:
        return f"[stub] ctx_chars={len(system)} msg={user[:80]}"

class OpenAiLlmClient:
    def __init__(self, *, api_key, base_url, model, timeout_seconds, max_tokens):
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout_seconds)
        ...
    async def complete(self, *, system, user) -> str:
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                max_tokens=self._max_tokens,
            )
        except APITimeoutError as exc:
            raise AppException(504, "LLM 응답 시간 초과", "CHAT_TIMEOUT") from exc
        except APIError as exc:
            raise AppException(502, "LLM 서비스 오류", "CHAT_UPSTREAM_ERROR") from exc
        return resp.choices[0].message.content or ""
```

Anthropic 어댑터는 평가 후 트랙. 현재는 OpenAI 호환 endpoint 하나만 지원한다.

### 10.3 PII 마스킹 규약

```python
# app/services/llm_sanitizer.py — 실제 구조 (요약)
MIN_SAMPLE_SIZE = 5
_PII_FIELDS = ("student_id", "email", "phone")
_SUBJECT_NOISE_FIELDS = ("subject_id",)  # SMS-96 — UUID는 LLM이 ground 불가

class SmallSampleError(Exception): ...

def _index_to_token(i: int) -> str:
    """1-indexed → 학생A..Z (i≤26), 학생AA..ZZ (i≤702). chr(64+i) 한 글자만 쓰면
    i≥27에서 [A-Z] 밖 문자가 생성돼 라우터 정규식이 silent drop 한다."""

def mask_context(rows: list[dict]) -> tuple[list[dict], dict[str, UUID]]:
    if len(rows) < MIN_SAMPLE_SIZE:
        raise SmallSampleError(...)  # 라우터가 잡아 거부 메시지 반환
    token_map: dict[str, UUID] = {}
    masked_rows: list[dict] = []
    for i, row in enumerate(rows, start=1):
        if "student_id" not in row:        # 집계 행은 통과
            masked_rows.append(row); continue
        token = _index_to_token(i)
        token_map[token] = row["student_id"]
        new_row = {**row, "student_name": token, "student_number": f"seq_{i:03d}"}
        for f in _PII_FIELDS: new_row.pop(f, None)
        if isinstance(new_row.get("subjects"), list):
            new_row["subjects"] = [
                {k: v for k, v in s.items() if k not in _SUBJECT_NOISE_FIELDS}
                for s in new_row["subjects"]
            ]
        masked_rows.append(new_row)
    return masked_rows, token_map
```

| 원본 | 마스킹 |
|------|--------|
| `김철수` (학생명) | `학생A`, `학생B`, …, `학생Z`, `학생AA`, … (~702명까지 안전) |
| `student_number=15` | `seq_015` |
| 학부모 이메일/전화 | (컨텍스트에서 제거) |
| `student_id` (UUID) | (컨텍스트에서 제거, 서버 메모리 매핑만 유지) |
| `subjects[].subject_id` (UUID) | (컨텍스트에서 제거, SMS-96) |
| 교사명 | 유지 (질의자 본인) |
| 학생 수 < 5 (k≥5 미달) | `SmallSampleError` → LLM 호출 안 함, 거부 메시지 반환 |

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
| REQ-071 (Outbox + LISTEN/NOTIFY 이벤트 적재) | §9.2~9.4 (Sprint 1 SMS-50~53, Sprint 2 SMS-78~80 4 도메인 확장, ADR-003 메커니즘 전환) | ✅ v2.2 |
| REQ-072 (집계 테이블) | §9.1 agg_student_subject/overall (Sprint 2에서 attendance_present_rate + feedback_count까지 채움) | ✅ v2.1 |
| REQ-073 (교사 대시보드) | §9.5 GET /analytics/* | 🚧 v2.1 (Sprint 3 SMS-74) |
| REQ-074 (≤ 1분 반영) | §9.6 + Sprint 1 SMS-54 + Sprint 2 SMS-81 e2e idempotency | ✅ v2.1 |
| REQ-075 (scale=N 시연) | §1 docker-compose `--scale analytics-worker=3` | 🚧 v2.1 |
| REQ-080~083 (AI 어시스턴트 단일 엔드포인트 + PII 마스킹) | §10 AI 어시스턴트 | 🚧 v2.1 |

---

*Design Spec v2.1 — 확정*
