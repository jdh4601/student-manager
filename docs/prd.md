# PRD: 학생 성적 및 상담 관리 시스템 (교사용 SaaS)

**버전**: 2.2  **최종 업데이트**: 2026-05-31  **상태**: 확정
**v2.2 변경 (발표 보완 5종)**: ① OpenAPI/Swagger 명세 정비(§6.3) · ② 테스트 피라미드 실측(§6.4) · ③ 무중단 배포 probe + 예시 K8s(§7, §8) · ④ Agile/Jira 발표 산출물 · ⑤ 교사 Google OAuth(REQ-006)
**v2.1 변경**: §10 OLAP·분석, §11 AI 어시스턴트(데모), §7 인프라(로컬 docker-compose 유지), §9 RISK 테이블 재구성
**프로젝트 성격**: 졸업 평가용 과제 (로컬 프로토타입). 운영 사용자 0명. 평가 마감 2026-07-03 / 라이브 데모 + 발표.

---

## 1. Executive Summary

중·고등학교 교사들이 학생 성적, 학생부, 피드백, 상담 내역을 하나의 SaaS 플랫폼에서 디지털로 관리하고, 같은 학교 내 교사들 간에 정보를 공유할 수 있는 웹 기반 시스템. **MVP 핵심**: 학생 성적 입력·자동 계산·레이더 차트 시각화.

---

## 2. Problem Statement

- 교사들이 성적·상담 내역을 개별 Excel/수기로 관리 → 데이터 유실·버전 불일치
- 같은 학교 교사 간 학생 정보 공유 느림
- 학생·학부모의 성적·피드백 즉시 확인 방법 없음

---

## 3. Goals & Success Metrics

| 목표 | 지표 | 목표값 |
|------|------|--------|
| 성적 관리 디지털화 | 교사 1인당 성적 입력 소요 시간 | 기존 대비 50% 단축 |
| 데이터 공유 신뢰성 | 교사 간 정보 불일치 건수 | 월 0건 |
| 학부모 만족도 | 성적 확인 관련 문의 전화 건수 | 기존 대비 70% 감소 |
| 시스템 신뢰성 | 월간 가용성 | ≥ 99.5% |
| API 성능 | p95 응답 시간 | ≤ 500ms |

---

## 4. User Stories

- **US-001**: 교사 — 학기별 과목 성적 입력, 총점·평균·9등급 자동 계산
- **US-002**: 교사 — 전 교과목 성적 레이더 차트 시각화, 학기 간 비교
- **US-003**: 교사 — 상담 내역 기록 및 같은 학교 교사 간 공유
- **US-004**: 교사 — 피드백 작성, 학생/학부모 공개 여부 제어
- **US-005**: 학생/학부모 — 성적 및 공개 피드백 조회
- **US-006**: 교사 — 학생 기본 정보·출결·특기사항 관리
- **US-007**: 교사 — 인앱 알림 수신 (성적 입력·피드백·상담 업데이트)

---

## 5. Functional Requirements

> **Must** = MVP 필수 | **Should** = 중요 | **Could** = 있으면 좋음

### 인증 및 권한

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| REQ-001 | 교사/학생/학부모 역할별 로그인·로그아웃 | Must |
| REQ-002 | JWT 인증, 토큰 만료(액세스 1h / 리프레시 7d) | Must |
| REQ-003 | 역할별 접근 범위 제어 | Must |
| REQ-004 | 초대 링크 기반 학생·학부모 계정 등록 | Must |
| REQ-005 | 비밀번호 재설정 (이메일 링크) | Should |
| REQ-006 | 교사 Google OAuth 로그인 (학교 이메일 도메인 화이트리스트) — 미허용 도메인·미검증 이메일 거부 | Should |

### 성적 관리

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| REQ-010 | 학기별·과목별 성적(0~100점) 입력·수정 | Must |
| REQ-011 | 총점·평균·9등급 자동 계산 | Must |
| REQ-012 | 전 교과목 성적 레이더 차트 시각화 | Must |
| REQ-013 | 학기 간 성적 비교 차트 | Should |
| REQ-014 | 성적 데이터 CSV/Excel 가져오기·내보내기 | Must |
| REQ-015 | 과목별 성적 상세 조회 | Must |

### 학생부

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| REQ-020 | 학생 기본 정보(이름·학년·반·번호·생년월일) CRUD | Must |
| REQ-021 | 출결 상태(출석/결석/지각/조퇴) 날짜별 입력·조회 | Must |
| REQ-022 | 특기사항 자유 텍스트 입력·수정·이력 조회 | Must |
| REQ-023 | 학생 정보 CSV 일괄 가져오기 | Must |

### 피드백

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| REQ-030 | 피드백 작성 (카테고리: 성적/행동/출결/태도) | Must |
| REQ-031 | 학생/학부모 공개·비공개 독립 설정 | Must |
| REQ-032 | 피드백 수정·삭제 (작성 교사만) | Must |
| REQ-033 | 피드백 작성 시 학생·학부모 알림 발송 | Must |

### 상담

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| REQ-040 | 상담 내역 등록 (날짜·내용·다음 계획) | Must |
| REQ-041 | 같은 학교 교사 간 공유 여부 설정 | Must |
| REQ-042 | 상담 내역 검색 (학생명·기간·작성 교사) | Must |
| REQ-043 | 상담 내역 필터링 (날짜·학년·반) | Should |

### 알림

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| REQ-050 | 인앱 알림 (성적·피드백·상담 업데이트) | Must |
| REQ-051 | 알림 읽음 처리·목록 조회 | Must |
| REQ-052 | 이메일 알림 | Could |

### 분석·OLAP (v2.1 추가)

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| REQ-070 | 운영 데이터(`public`) ↔ 분석 데이터(`analytics`) 스키마 분리 | Must |
| REQ-071 | 운영 → 분석 이벤트 기반 적재 (Outbox + Postgres LISTEN/NOTIFY + analytics-worker, ADR-003) | Must |
| REQ-072 | 학생별·과목별 학습 현황 집계 테이블 | Must |
| REQ-073 | 교사 개인용 분석 대시보드 (담당 학급 한정) | Must |
| REQ-074 | 분석 데이터 일관성: 운영 변경 후 ≤ 1분 내 반영 | Should |
| REQ-075 | 확장성 시연: `docker-compose --scale analytics-worker=3` 라이브 데모 | Should |

### AI 어시스턴트 (v2.1 추가, 데모용)

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| REQ-080 | 분석 요약 데이터를 컨텍스트로 LLM 호출하는 단일 엔드포인트 (`POST /api/v1/chat`) | Should |
| REQ-081 | 교사 전용 채팅 위젯 — 자연어 질의 → 학습 현황 응답 | Should |
| REQ-082 | 챗봇 응답 범위는 학급 단위 통계로 제한 (k≥5 실질 충족). 단일 학생 식별 가능한 응답 차단 | Must (조건부) |
| REQ-083 | LLM 컨텍스트의 학생명·학번은 `학생A` / `seq_001` 형태로 단순 치환 마스킹 | Must (조건부) |

### 데이터 내보내기

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| REQ-060 | 성적 데이터 Excel 내보내기 | Must |
| REQ-061 | 성적 분석 보고서 PDF 내보내기 | Should |
| REQ-062 | 상담 내역 보고서 PDF 내보내기 | Should |

---

## 6. Non-Functional Requirements

### 성능
| 항목 | 요구값 |
|------|--------|
| API 응답 시간 (p95) | ≤ 500ms |
| 페이지 초기 로딩 (LCP) | ≤ 3초 (3G 기준) |
| 동시 접속 교사 수 | 최소 50명 |
| 성적 입력→계산 표시 | ≤ 200ms (클라이언트 계산) |

### 가용성 및 신뢰성

> 평가용 로컬 환경에서는 가용성·백업·DR 요구를 충족하지 않는다. 아래 수치는 **as-if production 설계 목표**로 명시.

| 항목 | 요구값 (설계 목표) |
|------|--------|
| 월간 가용성 | ≥ 99.5% |
| 데이터 백업 주기 | 매일 자동 (Postgres `pg_dump` 또는 PITR) |
| RTO | ≤ 4시간 |
| RPO | ≤ 24시간 |

### 보안
| 항목 | 요구값 |
|------|--------|
| 비밀번호 해싱 | bcrypt (cost factor ≥ 12) |
| 전송 암호화 | HTTPS (TLS 1.2 이상) 강제 |
| 세션 토큰 | access_token 메모리 / refresh_token HttpOnly Cookie |
| 쿼리 보안 | ORM 파라미터화 쿼리 |
| XSS 방어 | React 이스케이프, CSP 헤더 |
| 개인정보 로그 | 학생 이름·성적 로그 출력 금지 |
| RBAC 검증 | 모든 API에서 역할·school_id 범위 검증 |

### 접근성
| 항목 | 요구값 |
|------|--------|
| 브라우저 지원 | Chrome/Safari/Edge 최신 버전 |
| 모바일 반응형 | 320px 이상 |

### 6.3 API 명세 & 문서화 (v2.2)
| 항목 | 요구값 |
|------|--------|
| OpenAPI 3.1 자동 명세 | FastAPI 내장. 14개 태그 그룹 설명 + 라이선스/연락처 메타데이터 (`app/main.py` `tags_metadata`) |
| 대화형 문서 | Swagger UI(`/docs`) · ReDoc(`/redoc`) 노출 |
| 명세 산출물 | `scripts/export_openapi.py` → `docs/api/openapi.json` (53 paths / 53 schemas). Postman/클라이언트 생성용 |
| 에러 계약 명세 | 모든 비즈니스 에러는 `{ detail, code }` (AppException) — `code`는 머신 판독용 (예: `AUTH_OAUTH_DOMAIN_NOT_ALLOWED`, `DB_NOT_READY`) |

### 6.4 테스트 전략 — 3계층 피라미드 (v2.2)
| 계층 | 도구·위치 | 실측 (2026-05-31) |
|------|-----------|-------------------|
| 단위 (unit) | pytest, `backend/tests/test_*.py` | 200 passed / 10 skip, **백엔드 커버리지 81%** (grade·feedback·auth ≥96%) |
| 통합 (integration) | testcontainers 실 Postgres, `backend/tests/integration/` | outbox→publisher→worker→`analytics.*` 정합성, SKIP LOCKED scale=3 중복 처리 0 |
| E2E | Playwright, `frontend/e2e/*.spec.ts` | 11 spec — 로그인·성적·피드백·분석 RBAC·챗봇 PII·모바일 반응형 |

> Frontend 컴포넌트 단위 테스트는 호스트 환경 이슈(Node 25 ≠ vitest 1.6 + Linux node_modules 바이너리)로 일시 보류 — 근본 원인·해결책은 `docs/notes/frontend-test-env-fix.md`. E2E가 frontend 동작을 실 브라우저로 검증하므로 평가 신뢰성은 확보됨.

---

## 7. Technical Architecture

### 기술 스택

| 레이어 | 기술 |
|--------|------|
| Frontend | React 18, TypeScript, Tailwind CSS, Zustand, TanStack Query, Recharts |
| Backend | FastAPI (Python 3.12), Pydantic v2, SQLAlchemy 2.0, Alembic |
| Outbox Publisher | Python 3.12, asyncpg (SELECT FOR UPDATE SKIP LOCKED + `pg_notify`) |
| Analytics Worker | Python 3.12, asyncpg (LISTEN + SKIP LOCKED claim + UPSERT) |
| Chat 엔드포인트 | FastAPI 백엔드 내부 단일 라우터 (`/api/v1/chat`). LLM SDK 직접 호출 |
| Message Stream | Postgres LISTEN/NOTIFY (외부 broker 없음 — ADR-003) |
| Database | PostgreSQL (`public` + `analytics` + `outbox` 테이블 동일 인스턴스) |
| Auth | JWT (python-jose + passlib bcrypt) |
| 파일 출력 | SheetJS (Excel), jsPDF (PDF) — 클라이언트 사이드 |
| 배포 | **Vercel(Frontend) + Render(Backend Web + 2 Workers + Postgres)** for 외부 demo, 로컬 `docker-compose` for 분산 시연·E2E |

### 핵심 결정사항

- **멀티테넌트**: 단일 DB + `school_id` Row-Level Filtering
- **인증**: access_token 메모리 저장, refresh_token HttpOnly Cookie (현행 유지)
- **교사 OAuth (v2.2)**: Google OAuth 2.0 Authorization Code + OIDC. state CSRF 방어(HttpOnly 쿠키 바인딩 + `secrets.compare_digest`), `email_verified` 가드, `ALLOWED_TEACHER_DOMAINS` 화이트리스트 게이트. `OAUTH_PROVIDER=auto`(client_id 설정 시 real, 아니면 stub). stub은 `ENVIRONMENT≠production` 또는 `ALLOW_OAUTH_STUB=true`에서만 허용 — production 인증 우회 차단. `LlmClient`처럼 `GoogleOAuthClient` Protocol로 DI
- **무중단 배포 게이트 (v2.2)**: `/health`(liveness, 프로세스 생존) / `/ready`(readiness, `SELECT 1` DB 검증 → 실패 시 503 `DB_NOT_READY`) 분리. 롤링 업데이트 시 readiness 통과 후에만 트래픽 수신 (`maxUnavailable=0`)
- **알림**: 30초 폴링 (Realtime push는 평가 후)
- **성적 등급**: 원점수 기준 9등급 참고값 (석차 기반 아님)
- **파일 생성**: 클라이언트 사이드 전용 (서버는 JSON만 제공)
- **교사 스코핑 (MVP)**: 담임 1명 = 담당 Class 1개. 교과 교사 다중 반은 평가 후 (ClassTeacher M:M)
- **OLAP 분리 (v2.1)**: 동일 PG 인스턴스 내 `analytics` 스키마. 외부 DW(ClickHouse/BigQuery) 미도입
- **CDC (v2.1 + ADR-003)**: **Outbox 패턴 + Postgres LISTEN/NOTIFY + `SELECT FOR UPDATE SKIP LOCKED`**. 운영 트랜잭션 안에서 outbox INSERT → publisher가 `pg_notify`로 알림 발행 → worker가 LISTEN + SKIP LOCKED claim으로 `analytics.*` UPSERT. ADR-002 (Kafka)는 도메인 규모 부적합으로 ADR-003에 의해 supersede.
- **인프라 (v1.2)**: **Render(Backend Web + 2 Workers + Postgres) + Vercel(Frontend)**로 외부 라이브 demo 제공. 로컬 `docker-compose`는 분산 컴포넌트 시연·E2E 통합 테스트용 동등 환경 유지. EKS·AWS·Helm·Terraform 미도입.
- **확장성 (v1.2)**: 컨테이너 다이어그램 + `docker-compose --scale analytics-worker=3` 라이브 시연으로 입증. SKIP LOCKED 기반 cooperative worker claim으로 수평 확장 (Kafka consumer group 등가).
- **AI 어시스턴트 (v2.1)**: 별도 서비스 분리하지 않음. FastAPI 단일 엔드포인트. PII는 학급 단위 통계로 답변 범위 제한 + 이름 단순 치환 마스킹.

---

## 8. Out of Scope (MVP 제외)

| 항목 | 이유 |
|------|------|
| NEIS 등 외부 교육행정 시스템 연동 | CSV/Excel로 대체 |
| 모바일 앱 | 웹 반응형으로 대체 |
| 이메일 알림 | 평가 후 |
| 쿠버네티스 / EKS 운영 도입 | 운영 클러스터는 평가 후. 단, 무중단 배포 개념 입증을 위해 **예시 매니페스트**(`deploy/k8s/`, RollingUpdate `maxUnavailable=0` + liveness/readiness probe)를 작성해 발표에 활용. Render Background Worker로 동등 분산 표현 충족 |
| 100개 이상 학교 대규모 확장 | 평가 후 |
| AI 기반 성적 분석·추천 (벡터 검색·RAG 정식 도입) | 평가 후 |
| 학교 간 데이터 공유 | 학교 단위 완전 격리 |
| 실시간 화상 상담, 공문 발송 | 범위 외 |

---

## 9. Risks

| ID | 위험 | 영향도 | 대응 |
|----|------|--------|------|
| RISK-001 | 교과 교사 다중 반 담당 미지원 (MVP 제약) | 높음 | 평가용 시드 데이터는 담임 모델 가정. ClassTeacher M:M 확장은 평가 후 |
| RISK-002 | 학생 PII 노출 (로그·LLM 컨텍스트·발표 데모) | 매우 높음 | 로그 PII 제외, school_id 격리, LLM 컨텍스트는 학급 단위 통계만 + 이름 마스킹 |
| RISK-003 | 성적 등급 계산 기준 오류 | 중간 | `calculate_grade()` 서비스 레이어 분리, 9등급 cutoff 표 명시 |
| RISK-005 | Outbox publisher 다운 → 이벤트 미발행 | 중간 | outbox row는 commit 됨. publisher 부팅 시 `WHERE sent_at IS NULL` catch-up 쿼리로 자동 복구 |
| RISK-007 | LLM 호출 시 학생 PII 유출 | 매우 높음 | 챗봇 답변 범위를 학급 단위 통계로 제한 (k≥5). 컨텍스트의 이름·학번은 단순 치환 마스킹 (`학생A`, `seq_001`) |
| RISK-009 | LISTEN connection 끊김 → NOTIFY 유실 | 낮음 | worker 60s catch-up 폴링(`WHERE processed_at IS NULL`)이 잔여분 자동 처리. 운영 트랜잭션은 영향 없음 (outbox commit 독립) |
| RISK-010 | 라이브 데모 환경 시드/포트/볼륨 누락 | 중간 | W9 리허설 + `scripts/demo_seed.py` + `docker-compose.demo.yml` 정비 |
| RISK-011 | 발표 시 평가자가 "LISTEN/NOTIFY는 message stream인가" 의문 | 낮음 | 발표 슬라이드에 "Postgres NOTIFY = 동일 인스턴스 pub/sub stream" 표기 + Sidekiq/oban 등 production 사례 인용. rubric "예: Kafka"는 한 가지 예시일 뿐 |

---

## 10. OLAP & 분석 (v2.1)

### 10.1 분리 정책
- 운영 스키마 `public` + 분석 스키마 `analytics` (동일 PG 인스턴스)
- 분석 테이블은 **읽기 전용 집계 캐시**. 운영 트랜잭션은 손대지 않음.

### 10.2 분석 테이블 (요약)
- `analytics.fact_grade_event` — Grade INSERT/UPDATE 이벤트 로그 (append-only)
- `analytics.fact_attendance_event` — Attendance 이벤트 로그
- `analytics.fact_feedback_event` — Feedback 이벤트 로그
- `analytics.fact_counseling_event` — Counseling 이벤트 로그 (audit 용도, agg 미생성)
- `analytics.dim_student` — 학생 차원 (snapshot, daily refresh)
- `analytics.agg_student_subject` — 학생×과목 집계 (평균·최고·최저·등급 추이)
- `analytics.agg_student_overall` — 학생 단위 종합 지표 (학기별)
- `analytics.dead_letter_event` — 컨슈머가 처리 불가능한 poison message 격리 (운영 디버깅)

### 10.3 CDC 파이프라인 (Outbox + Postgres LISTEN/NOTIFY)
- 운영 라우터 트랜잭션 안에서 `public.outbox` row INSERT (도메인 변경과 같은 트랜잭션)
- `outbox-publisher` 프로세스가 미발행 row(`sent_at IS NULL`)를 `SELECT FOR UPDATE SKIP LOCKED`로 batch fetch → `SELECT pg_notify(<topic_channel>, '{"event_id":...}')` → `sent_at` 업데이트 (모두 단일 트랜잭션)
- `analytics-worker × N`가 4 channel(`grade_events`/`attendance_events`/`feedback_events`/`counseling_events`) LISTEN. 알림 받으면 해당 event_id의 outbox row를 `SELECT FOR UPDATE SKIP LOCKED + processed_at IS NULL`로 claim → 정확히 1개 워커만 처리 → `analytics.*` UPSERT (idempotent on event_id) → `processed_at = now()`
- 메시지 브로커: **Postgres 자체** (외부 broker 없음)
- Publisher 부팅 시 `WHERE sent_at IS NULL` 쿼리로 catch-up. Worker 부팅 시 + 60초 주기로 `WHERE processed_at IS NULL` 폴링하여 NOTIFY 유실 보완
- Dead-letter: worker가 N회 retry 후 `analytics.dead_letter_event`로 격리 + `processed_at` 마킹 (queue 차단 방지)
- 정합성 검증: testcontainers Postgres 기반 통합 테스트 — publisher → worker → `analytics.fact_*` row 수 일치, scale=3에서도 중복 처리 없음
- 자세한 패턴 비교/근거: ADR-003 (ADR-002 supersede)

### 10.4 분석 API
- `GET /api/v1/analytics/students/{id}/overview` — 학생 학습 요약
- `GET /api/v1/analytics/classes/{id}/distribution` — 학급 점수 분포
- `GET /api/v1/analytics/teachers/me/dashboard` — 교사 메인 대시보드 위젯 데이터
- 모든 엔드포인트 RBAC 동일 (담임 한정)

---

## 11. AI 어시스턴트 (v2.1, 데모용)

> **명명 정정**: 본 기능은 벡터 인덱싱·의미 검색이 없으므로 정식 RAG가 아니다. *"분석 데이터 기반 LLM 자연어 응답"* (이하 AI 어시스턴트)으로 통일한다.

### 11.1 범위
- 교사가 자연어로 담당 학급 학습 현황을 질의 (예: "이번 학기 수학에서 평균 이하인 학생 비율은?")
- 분석 요약 데이터(`analytics.agg_*`)를 컨텍스트로 LLM 호출
- 응답은 텍스트 + 선택적 학생 ID 리스트
- 구현 예산: 약 3일 (W6)

### 11.2 PII 정책
- 컨텍스트 추출 범위는 교사 담임 학급으로 한정. LLM에는 학생 단위 통계(overall + subjects[])를 **마스킹된 형태**로 전달하며, 학생 수가 5 미만이면 LLM 호출 자체를 거부 (k≥5 가드, `SmallSampleError`)
- LLM 컨텍스트의 학생명·학번은 단순 치환 마스킹: `김철수 → 학생A` (26명 초과 시 `학생AA`로 두 글자 확장, ~702명까지 안전), `student_number=15 → seq_015`
- 응답 후처리에서 토큰을 실제 학생으로 역매핑 (서버 메모리)
- 외부 LLM provider에 전송되는 페이로드에는 학생 식별 정보(이름·학번·UUID·이메일·전화번호) 0건을 `tests/test_llm_sanitizer.py`로 보증

### 11.3 아키텍처
- **별도 서비스 분리하지 않음**. FastAPI 백엔드의 단일 엔드포인트 `POST /api/v1/chat`
- LLM 호출은 OpenAI 호환 endpoint 단일 (기본 `https://api.openai.com/v1`, `LLM_BASE_URL`로 Kimi/Together/Groq 등 호환 게이트웨이 사용 가능). `OPENAI_API_KEY` 미설정 또는 `LLM_PROVIDER=stub`이면 결정론적 stub fallback
- 테스트 용이성을 위해 `LlmClient` Protocol + `StubLlmClient` + `OpenAiLlmClient`로 의존성 주입 (`tests/test_chat.py`가 `app.dependency_overrides`로 교체) — 의도된 진화
- Rate limiting: 교사당 분당 10회 (slowapi)

---

## Appendix: 한국 교육 도메인 메모

- **학기**: 1학기(3월~8월), 2학기(9월~2월)
- **성적 등급**: 실제 고교는 석차백분율 기반 9등급제. MVP는 원점수 기준 참고 등급 사용
- **학생부 범위**: 성적 외 출결·특기사항 포함. NEIS 직접 연동은 범위 밖 (CSV/Excel 대체)
- **제품 전제**: SaaS 배포, 학교 단위 완전 격리, 초기 규모 1~10개 학교
