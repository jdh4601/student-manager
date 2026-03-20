# 12주 애자일 개발 계획 — 교사용 학생 관리 시스템

## Context

대학교 소프트웨어설계 실습 과제 (개인 프로젝트, 12주).
고객 요구사항 명세서(`docs/고객 요구사항 명세서.md`)를 기반으로 Scrum 방식으로 개발.
산출물: **Jira 보드/스프린트 관리** + **실제 동작하는 웹 애플리케이션**.
6주차 중간 발표, 12주차 최종 발표 존재.
요구사항은 중간에 변경될 수 있으므로 우선순위 기반 스프린트 구성.

---

## 요구사항 우선순위 (변경 대응 기준)

| 기능 | 우선순위 | 스프린트 |
|------|---------|---------|
| 사용자 인증 (로그인/권한) | 최우선 | Sprint 1 |
| 학생 성적 관리 | 높음 | Sprint 1–2 |
| 학생부 관리 | 높음 | Sprint 2 |
| 학생 정보 검색/조회 | 중간 | Sprint 3 |
| 피드백 제공 | 중간 | Sprint 3 |
| 상담 내역 관리 | 중간 | Sprint 4 |
| 알림 기능 | 중간 | Sprint 4 |
| 보고서 생성 (PDF/Excel) | 낮음 | Sprint 5 |

---

## 기술 스택 결정 (Sprint 0에서 확정)

**확정 스택** (2026-03-19):

| 레이어 | 기술 | 선택 이유 |
|--------|------|-----------|
| **Frontend** | React 18 + TypeScript + Tailwind CSS | React 경험 보유, 타입 안정성, 빠른 UI 구성 |
| **차트** | Recharts | React 친화적, 레이더 차트 지원 |
| **Backend** | FastAPI (Python 3.11) | Python 친숙, 빠른 개발, Swagger 자동 생성 |
| **스키마 검증** | Pydantic v2 | FastAPI 내장, 입력 검증 자동화 |
| **ORM** | SQLAlchemy 2.0 + Alembic | SQL 추상화, 마이그레이션 관리 |
| **Database** | PostgreSQL (Supabase) | 관계형 구조, 무료 관리형 DB |
| **Auth** | JWT (python-jose + passlib) | FastAPI 표준 패턴, 역할 기반 권한 |
| **배포** | Vercel (FE) + Render (BE) + Supabase (DB) | 모두 무료 티어, 학생 프로젝트 적합 |

**Spring Boot 미선택 이유**: Java 경험 없음, 12주 기간 내 러닝커브 과다, 보일러플레이트 부담

> 기술 선택 근거는 Jira 기술 스택 에픽 및 Sprint 0 리뷰에 기록

---

## RBAC 권한 모델 (Sprint 0 확정)

### 역할 정의

| 역할 | 설명 | 계정 생성 방식 |
|------|------|--------------|
| `teacher` | 담당 학급 교사 | 관리자 seed 또는 직접 생성 |
| `student` | 학생 본인 | 교사가 생성 |
| `parent` | 학부모 | 교사가 생성 (자녀 연결) |

### 데이터 접근 범위

| 리소스 | teacher | student | parent |
|--------|---------|---------|--------|
| 학생 목록 | 담당 학급 전체 조회 | 본인만 | 자녀만 |
| 성적 | 담당 학급 입력/수정/조회 | 본인 조회만 | 자녀 조회만 |
| 출결 | 담당 학급 입력/수정/조회 | 본인 조회만 | 자녀 조회만 |
| 피드백 | 작성/수정, 공개 여부 설정 | 공개된 것만 조회 | 공개된 것만 조회 |
| 상담 내역 | 작성 + 공유 허용된 것 조회 | 접근 불가 | 접근 불가 |
| 알림 | 발송 주체 | 수신 | 수신 |
| 보고서 | 생성/다운로드 | 접근 불가 | 접근 불가 |

### 권한 구현 전략
- JWT payload에 `role`, `user_id`, `class_id` 포함
- FastAPI `Depends(get_current_user)` 미들웨어로 모든 엔드포인트 보호
- 데이터 스코핑: `class_id` 기반 쿼리 필터 (teacher는 자신의 class만)

---

## 핵심 엔티티 ERD (Sprint 0 설계)

### 엔티티 목록

```
User            (id, email, hashed_password, role, name, created_at)
Class           (id, name, grade, year, teacher_id → User)
Student         (id, user_id → User, class_id → Class, student_number, birth_date)
ParentStudent   (id, parent_id → User, student_id → Student)  -- 학부모-자녀 연결
Subject         (id, name, class_id → Class)
Semester        (id, year, term)  -- ex: 2026년 1학기
Grade           (id, student_id, subject_id, semester_id, score, grade_letter, created_by → User)
Attendance      (id, student_id, date, status[present/absent/late/early_leave], note)
SpecialNote     (id, student_id, content, created_by → User, created_at)
Feedback        (id, student_id, teacher_id → User, category[behavior/attendance/attitude],
                 content, is_visible_to_student, is_visible_to_parent, created_at)
Counseling      (id, student_id, teacher_id → User, date, content, next_plan,
                 is_shared, created_at)
Notification    (id, recipient_id → User, type, message, is_read, created_at)
```

### 주요 관계
- User 1 ↔ N Class (교사 담당 학급)
- Class 1 ↔ N Student
- Student N ↔ N User (학부모, via ParentStudent)
- Student 1 ↔ N Grade, Attendance, SpecialNote, Feedback, Counseling

---

## API 엔드포인트 명세 (Sprint 1 범위)

### Auth
```
POST /auth/login          → { access_token, token_type, role }
POST /auth/logout         → 204
GET  /auth/me             → UserResponse
```

### Users (교사용 계정 관리)
```
POST /users/students      → 학생 계정 생성 (teacher only)
POST /users/parents       → 학부모 계정 생성 + 자녀 연결 (teacher only)
GET  /users/students      → 담당 학급 학생 목록
```

### Grades
```
GET  /grades?student_id=&semester_id=   → 성적 목록
POST /grades                            → 성적 입력 (teacher only)
PUT  /grades/{id}                       → 성적 수정 (teacher only)
GET  /grades/{student_id}/summary       → 총점/평균/등급 자동 계산 결과
```

> Sprint 2 이후 엔드포인트는 해당 스프린트 시작 시 설계 후 추가

---

## 데이터 보안 전략

| 항목 | 전략 |
|------|------|
| **비밀번호** | passlib + bcrypt 해싱 (Sprint 1에서 구현) |
| **전송 암호화** | HTTPS (Vercel/Render 자동 제공) |
| **저장 암호화** | Supabase PostgreSQL 저장소 암호화 기본 제공 |
| **백업/복구** | Supabase 자동 일일 백업 + Point-in-Time Recovery 활용 |
| **PII 보호** | 학생 개인정보 로그 출력 금지, API 응답에서 hashed_password 제외 |
| **접근 제어** | 모든 엔드포인트 JWT 인증 필수, role 기반 데이터 스코핑 |

---

## Definition of Done (스프린트 공통)

각 태스크 완료 기준:
- [ ] 기능이 정의된 동작대로 작동함
- [ ] 관련 API 엔드포인트에 단위/통합 테스트 작성
- [ ] Pydantic 스키마로 입력 검증 처리
- [ ] 역할 기반 접근 제어 적용 확인
- [ ] Swagger 문서에 엔드포인트 반영 확인

---

## Jira 구성

### Epics (요구사항 → Epic 매핑)

| Epic | 내용 |
|------|------|
| **Epic 1**: 사용자 인증 & 권한 관리 | 로그인, 권한별 접근 제어 |
| **Epic 2**: 학생 성적 관리 | 성적 입력/수정, 자동 계산, 레이더 차트 |
| **Epic 3**: 학생부 관리 | 기본 정보, 출결, 특기사항 |
| **Epic 4**: 학생 검색 & 조회 | 기간/과목 필터링, 통합 조회 |
| **Epic 5**: 피드백 관리 | 피드백 작성/저장, 학부모 공유 옵션 |
| **Epic 6**: 상담 내역 관리 | 상담 기록, 교사 간 공유, 검색 |
| **Epic 7**: 알림 기능 | 성적/피드백 업데이트 알림 |
| **Epic 8**: 보고서 생성 | PDF/Excel 다운로드 |

### Story Point 기준 (개인 프로젝트)
- 1 point = 약 2~3시간 작업
- 스프린트당 목표: 8~12 points

---

## 12주 스프린트 계획

### Sprint 0 — 프로젝트 셋업 + 설계 (Week 1–2)
**목표**: 개발 환경 구성, 기술 설계 산출물 완성, Jira 설정

**환경 셋업:**
- [ ] Jira 프로젝트 생성 (Scrum 보드, 8개 Epic, User Story 작성)
- [ ] 기술 스택 확정 및 Jira 기록
- [ ] 개발 환경 셋업 (repo, linting, CI/CD 파이프라인)
- [ ] Vercel + Render + Supabase 초기 배포 연결 확인 (인프라 early validation)

**설계 산출물 (Sprint 1 착수 전 필수):**
- [ ] **ERD 완성**: 전체 엔티티 관계도 (위 엔티티 목록 기반, draw.io 또는 dbdiagram.io)
- [ ] **RBAC 권한 매트릭스 문서화**: role × resource × action 표 (위 데이터 접근 범위 기반)
- [ ] **API 엔드포인트 명세**: Sprint 1 범위 (Auth + Users + Grades) Pydantic 스키마 포함
- [ ] **데이터 보안 전략 문서화** (위 표 기반, Jira 에픽에 기록)
- [ ] **알림 방식 결정**: 이메일(SMTP/SendGrid) vs in-app 중 하나로 확정 → Sprint 4 범위 결정
- [ ] **와이어프레임**: Sprint 1–2 핵심 화면 (로그인, 학생 목록, 성적 입력, 레이더 차트)
- [ ] **시드 데이터 스크립트 초안**: 데모용 교사 1명, 학생 5명, 과목 5개, 성적 데이터

**산출물**: Jira 보드 완성, ERD 문서, RBAC 매트릭스, API 명세, 개발 환경 동작 확인

---

### Sprint 1 — 인증 + 계정 관리 + 성적 기초 (Week 3–4)
**목표**: 핵심 기능 뼈대 구축 + 보안 기반 확립

Backlog (Epic 1 + Epic 2 일부):
- [ ] 교사 로그인/로그아웃 (JWT + passlib bcrypt 해싱)
- [ ] JWT 미들웨어 + role 기반 라우트 가드 구현
- [ ] 교사의 학생/학부모 계정 생성 기능
- [ ] 학생 목록 조회 화면 (담당 학급 스코핑)
- [ ] 학기별 성적 입력 화면
- [ ] 총점/평균/등급 자동 계산 로직
- [ ] Recharts 레이더 차트 프로토타입 (stretch goal)
- [ ] Sprint 1 기능 단위/통합 테스트 작성

Story Points: ~10 points
Sprint Review: 로그인 → 학생 선택 → 성적 입력 플로우 데모

---

### Sprint 2 — 성적 시각화 + 학생부 (Week 5–6) ⭐ 중간 발표
**목표**: 중간 발표용 핵심 기능 완성 (Sprint 2 부하 최소화)

Backlog (Epic 2 완료 + Epic 3):
- [ ] 레이더 차트로 전 교과목 성적 시각화 (Sprint 1 stretch 미완 시 여기서 완성)
- [ ] 과목별 성적 상세 조회
- [ ] 학생 기본 정보 (이름/학년/반/번호) CRUD
- [ ] 출결 기록 기능
- [ ] 특기사항 입력/수정
- [ ] 학생/학부모 기본 뷰 (본인 성적 조회 화면)
- [ ] Sprint 2 기능 단위/통합 테스트 작성

Story Points: ~10 points (중간 발표 버퍼 확보를 위해 12→10으로 조정)

**중간 발표 데모 시나리오**:
1. 교사 로그인
2. 학생 성적 입력 → 자동 계산 확인
3. 레이더 차트 시각화
4. 학생부 정보 조회
5. (보너스) 학생 계정으로 본인 성적 조회

---

### Sprint 3 — 검색 + 피드백 (Week 7–8)
**목표**: 조회/검색 + 피드백 기능

Backlog (Epic 4 + Epic 5):
- [ ] 학생 성적/상담/피드백 통합 검색
- [ ] 기간별/과목별 필터링
- [ ] 피드백 작성 및 저장 (행동/출결/태도 항목)
- [ ] 학생·학부모 공개 여부 옵션
- [ ] 학부모 뷰: 자녀 피드백 조회 화면
- [ ] Sprint 3 기능 단위/통합 테스트 작성

Story Points: ~10 points

---

### Sprint 4 — 상담 내역 + 알림 (Week 9–10)
**목표**: 교사 협업 기능 + 알림

> 알림 방식(이메일 vs in-app)은 Sprint 0에서 확정된 결정 적용

Backlog (Epic 6 + Epic 7):
- [ ] 상담 내역 작성 (날짜/내용/다음 계획)
- [ ] 상담 내역 교사 간 공유 & 검색/필터 (공유 대상 명시적 지정)
- [ ] 성적 입력 시 알림 발송
- [ ] 피드백 업데이트 알림
- [ ] Sprint 4 기능 단위/통합 테스트 작성

Story Points: ~10 points

---

### Sprint 5 — 보고서 + QA + 완성도 (Week 11–12) ⭐ 최종 발표
**목표**: 보고서 기능 + 전체 QA + 발표 준비

Backlog (Epic 8 + 버퍼):
- [ ] 성적 분석 보고서 PDF 다운로드
- [ ] 상담 내역 보고서 생성 (PDF)
- [ ] 피드백 요약 보고서 생성
- [ ] Excel 내보내기 (성적 데이터)
- [ ] 모바일 반응형 확인
- [ ] **보안 검증**: passlib 해싱 적용 확인, JWT 만료 처리, SQL Injection 방어 확인 (구현 아닌 검증)
- [ ] **백업 복구 검증**: Supabase 백업/복구 절차 테스트
- [ ] 전체 E2E 테스트
- [ ] 버그 수정 & 폴리싱
- [ ] Sprint Retrospective 문서화 (전체 5개 스프린트)

**최종 발표 데모 시나리오**:
1. 교사 로그인 → 학생 성적 입력/조회
2. 레이더 차트 시각화
3. 피드백 작성 → 학부모 공개 → 학부모 계정으로 확인
4. 상담 내역 기록 → 다른 교사와 공유
5. 보고서 PDF/Excel 다운로드

---

## 변경 대응 전략

요구사항 변경 발생 시:
1. Jira 백로그에 새 User Story 추가
2. 현재 스프린트 영향 없으면 다음 스프린트 배정
3. 우선순위 높으면 현 스프린트 저우선순위 항목과 교체
4. Sprint Review 때 변경 내용 기록

**버퍼 스프린트**: Sprint 5가 사실상 버퍼 역할 — 낮은 우선순위 기능을 여기서 처리하거나 교체 가능

---

## Scrum 산출물 체크리스트

| 산출물 | 생성 시점 | 담당 |
|--------|----------|------|
| Product Backlog | Sprint 0 | 개인 |
| Sprint Backlog | 각 스프린트 시작 | 개인 |
| ERD 문서 | Sprint 0 | 개인 |
| RBAC 권한 매트릭스 | Sprint 0 | 개인 |
| API 명세 (Swagger) | 각 스프린트 산출물 | FastAPI 자동 생성 |
| Sprint Review 노트 | 각 스프린트 종료 | 개인 |
| Sprint Retrospective | 각 스프린트 종료 | 개인 |
| Burndown Chart | Jira 자동 생성 | Jira |

---

## 검증 기준

| 주차 | 검증 항목 |
|------|----------|
| 2주차 (Sprint 0 종료) | ERD, RBAC 매트릭스, API 명세 완성 여부 확인 |
| 6주차 (중간) | 로그인, 성적 입력/조회, 레이더 차트 동작 확인 |
| 10주차 | 피드백, 상담, 알림 기능 통합 테스트 |
| 12주차 (최종) | 전체 기능 E2E 테스트, 보안/백업 검증, 데모 완료 |
