# 최종 발표 보완 계획서 (SW설계 수업)

**작성일**: 2026-05-31 · **발표/평가 마감**: 2026-07-03 (약 5주) · **상태**: 계획 (구현 전)
**완성 깊이 기준**: "발표 시연 가능 수준" — 깊은 구현보다 **교수 커리큘럼 축 복구**가 목표
**관련 문서**: `docs/prd.md`, `docs/architecture.md`, 중간발표 자료

---

## 0. 핵심 인식

이 보완의 본질은 "기능 추가"가 아니라 **평가자(교수)의 채점표와 정렬**이다.
수업 커리큘럼 = 루브릭이며, 그 축은 다음과 같다:

> 요구사항/기획 → UML 모델링 → 풀스택 개발 → **API 명세(OpenAPI/Swagger/Postman)** →
> **정적분석(SonarQube/Snyk)** → **테스트(unit→integration→E2E)** →
> **배포(Argo CD/K8s/무중단)** → **QA/동적분석(Burp)** → AWS(EKS) → **Agile(Jira)**

**중대한 정정 — 코드베이스 실측 결과, 우리는 생각보다 많이 갖춰져 있다:**

| 항목 | 중간발표/PRD 인식 | 실제 코드베이스 상태 |
|------|------------------|---------------------|
| 단위 테스트 | "테스트 통과" 한 줄 | `backend/tests/` **38개** |
| 통합 테스트 | 언급 없음 | `backend/tests/integration/` testcontainers (`test_grade_pipeline_e2e`, `test_idempotency_e2e` 등) |
| E2E | **"미작성"** (PRD §남은작업) | `frontend/e2e/` **Playwright 11개** (rbac, chat-pii, prd-user-stories…) |
| CI/CD | "Render 자동배포" | `.github/workflows/{ci,cd,e2e}.yml` **이미 존재** |
| 무중단 | 언급 없음 | `render.yaml`에 `healthCheckPath: /ready` **이미 존재** (헬스체크 후 롤링) |
| Swagger | 언급 없음 | FastAPI `/docs` **자동 생성** |

→ **5개 항목 중 ②③④는 "신규 구현"이 아니라 "이미 있는 것을 발표로 끌어올리고 + 빈틈만 메우기"**.
→ **실질 신규 구현은 ⑤(교사 OAuth) 하나뿐.** 나머지는 적은 비용으로 큰 점수.

---

## 1. 항목별 계획

### ① OpenAPI / Swagger / 계약 우선(contract-first)

**목표(발표 수준)**: "우리는 API를 계약 우선으로 합의했다"를 증명하는 슬라이드 1~2장 + 라이브 `/docs`.

**현재 상태**: FastAPI가 `/docs`(Swagger UI), `/openapi.json`을 자동 제공. Pydantic v2 스키마(`backend/app/schemas/`)가 그대로 명세가 됨. 단, 발표에 한 번도 등장 안 함.

**작업**:
- [ ] (코드) 주요 라우터에 `summary`/`description`/`response_model` 보강, 태그 정리 — `routers/*.py`
- [ ] (코드) `openapi.json`을 빌드 산출물로 export하는 스크립트 1개 (`scripts/export_openapi.py`) → "팀이 이 파일로 FE/BE 계약 합의" 서사
- [ ] (선택) Postman/Bruno 컬렉션을 `openapi.json`에서 생성 → "Postman으로 동작 테스트" 커리큘럼 항목 충족
- [ ] (발표) 슬라이드: "Pydantic 스키마 = 단일 진실 공급원 → Swagger 자동생성 → FE TanStack Query 타입 일치" 다이어그램

**발표 산출물**: `/docs` 라이브 1컷 + contract-first 다이어그램 1장.
**예상**: 0.5일 · **검증**: `curl localhost:8000/openapi.json` 200, Swagger UI에서 인증 플로우 실행.

---

### ② 테스트 피라미드 (unit → integration → E2E)

**목표(발표 수준)**: "유닛(38) → 통합(testcontainers) → E2E(Playwright 11)" 피라미드 1장 + 커버리지 숫자 + E2E 라이브 1개.

**현재 상태**: 위 표대로 **3계층 모두 이미 존재**. 문제는 두 가지:
1. PRD §남은작업 "E2E 미작성"이 **stale** (실제로는 작성됨) → 문서/발표가 자기 성과를 깎고 있음.
2. **Frontend `npm test` hang** → `qa`에서 제외됨 (CLAUDE.md 명시). 이게 "테스트 신뢰성" 흠집.

**작업**:
- [ ] (triage) `frontend npm test` hang 원인 규명 — vitest watch 모드/미종료 핸들 의심. `--run` 플래그 또는 `pool` 설정으로 해결 시도. (※ 2회 실패 시 멈추고 원인 보고 — 글로벌 테스트 규칙)
- [ ] (문서) PRD §남은작업에서 "E2E 미작성" 삭제, "E2E 11 spec 보유"로 정정
- [ ] (코드) 커버리지 측정: `pytest --cov` 숫자 확보 (이미 pytest-cov 설치됨)
- [ ] (발표) 피라미드 다이어그램: 각 층 개수 + 무엇을 검증하는지 (unit=계산/권한, integration=outbox→analytics 정합성, E2E=사용자 플로우)
- [ ] (데모) E2E 1개를 라이브 실행 (`landing-login-grade.spec.ts` 추천 — 짧고 시각적)

**발표 산출물**: 테스트 피라미드 1장 + 커버리지 % + E2E 실행 GIF/라이브.
**예상**: 1일 (대부분 npm test hang triage) · **검증**: `npm run qa` 그린, `npx playwright test` 그린.

---

### ③ Argo CD / K8s / 무중단 배포

> **결정**: K8s/Argo 전면 도입 **안 함**. **무중단 배포 개념만 추가** + 기존 자산 시연 + "K8s 의도적 제외" 재프레이밍.

**목표(발표 수준)**: 교수 커리큘럼(GitOps/롤링/무중단)을 **정면으로 인정**하면서, 우리가 동등 개념을 어떻게 충족했는지 + 의도적 트레이드오프를 설득.

**현재 상태**:
- `render.yaml` → `healthCheckPath: /ready` (Render는 새 인스턴스 health 통과 후 트래픽 전환 = 롤링/무중단)
- `.github/workflows/cd.yml` → main push 시 CD (= GitOps의 단순형)
- `docker-compose --scale analytics-worker=3` → 수평 확장 시연 (= consumer scaling)

**작업**:
- [ ] (코드) liveness/readiness 분리 명확화: `/health`(liveness, 프로세스 생존) vs `/ready`(readiness, DB 연결 OK) — 무중단 배포의 핵심 개념을 코드로 증명
- [ ] (코드, 선택) `docker-compose.yml`에 `healthcheck:` 블록 추가 → 로컬에서도 "unhealthy면 트래픽 안 받음" 시연
- [ ] (발표) **재프레이밍 슬라이드** (아래 §3 스크립트 사용): "K8s/Argo를 안 쓴 게 아니라, 평가 규모에 맞는 동등 개념을 선택했다"
- [ ] (발표) 무중단 배포 시퀀스: old 인스턴스 유지 → new 부팅 → `/ready` 통과 → 트래픽 전환 → old 종료
- [ ] (문서) `e2e.yml` 주석의 stale "real Kafka" 문구 제거 (ADR-003에서 제거됨)
- [ ] (선택, 여유 시) kind/minikube 매니페스트 1세트만 작성해 "Deployment + readinessProbe + RollingUpdate strategy"를 **다이어그램+yaml로만** 제시 (실배포 X)

**발표 산출물**: 무중단 배포 시퀀스 1장 + 재프레이밍 1장 + (선택) k8s yaml 발췌.
**예상**: 0.5일 (코드) + 0.5일 (선택 k8s yaml) · **검증**: `/ready`가 DB down 시 503 반환.

---

### ④ Agile / Jira

**목표(발표 수준)**: "워터폴이 아니라 애자일로 운영했다" 1장 — 백로그 → 스프린트 → 이슈 흐름 + 실제 보드 스크린샷.

**현재 상태**: CLAUDE.md에 Jira 워크플로우(Project SMS, Board 2, 스프린트 전환 11/21/31) 실제 운영 중. 발표엔 0줄.

**작업**:
- [ ] (수집) Jira 보드/스프린트/번다운 스크린샷 — MCP `jira` 도구로 현재 스프린트·완료 이슈 목록 추출
- [ ] (발표) 슬라이드: PRD 요구사항(REQ-xxx) → Jira 에픽/스토리 매핑 → 스프린트 진행 → 완료. "요구사항 추적성" 강조
- [ ] (발표) 한 줄: "AI 워크플로우(Ralph Loop)도 이 애자일 백로그를 입력으로 동작" → ②⑤와 연결

**발표 산출물**: Jira 보드 1컷 + 요구사항→이슈 추적 다이어그램 1장.
**예상**: 0.5일 (대부분 스크린샷/정리) · **검증**: 발표 슬라이드에 실제 이슈 키(SMS-xx) 노출.

---

### ⑤ 교사 인증 — Google OAuth + edu 도메인 화이트리스트 (실질 신규 구현)

**목표**: 교사가 Google OAuth로 로그인 → 이메일 도메인이 허용 목록(.edu/.ac.kr 등)일 때만 교사 권한 부여. 중간발표의 "가장 큰 문제(계정 발급)"에서 교사 부분의 미해결을 실제로 해결.

**현재 상태**: `routers/auth.py`에 invite/refresh/password-reset만. OAuth 없음. `services/auth.py`에 토큰 발급 로직 존재 → 재사용 가능.

**작업 (TDD: 실패 테스트 먼저)**:
- [ ] (설계, 승인 필요) OAuth 플로우 결정: Authorization Code (서버 교환) vs FE에서 id_token 받아 검증. **3줄 계획 제시 후 진행** (글로벌 규칙: 익숙치 않은 영역)
- [ ] (test) `test_oauth.py`: ① 허용 도메인 → 교사 가입/로그인 성공 ② 비허용 도메인 → 거부 ③ 기존 이메일 충돌 처리
- [ ] (코드) `GET /auth/oauth/google/login` (리다이렉트) + `GET /auth/oauth/google/callback` (code 교환 → 도메인 검증 → User upsert → 기존 `create_tokens` 재사용)
- [ ] (코드) `ALLOWED_TEACHER_DOMAINS` env (`config.py`) — 화이트리스트
- [ ] (코드) `LLM_PROVIDER=stub`처럼 **OAuth stub 모드** 추가 → 테스트/데모에서 실제 구글 호출 없이 결정론적 동작 (기존 stub 패턴 일관성)
- [ ] (FE) 로그인 화면에 "Google로 로그인(교사)" 버튼
- [ ] (발표) 시퀀스 다이어그램: Google → callback → 도메인 검증 → 토큰 발급. "학생=초대링크 / 교사=OAuth+도메인"으로 계정 발급 문제 **완결**

**발표 산출물**: 교사 OAuth 시퀀스 1장 + 라이브 로그인 데모 (stub 또는 실제).
**예상**: 1.5~2일 · **검증**: `test_oauth.py` 그린 + 비허용 도메인 차단 확인.
**리스크**: 구글 OAuth 앱 등록/리다이렉트 URI 설정 필요 → stub 모드로 데모 리스크 차단.

---

## 2. 권장 진행 순서 (ROI 순)

> Q4에서 "먼저 계획서만" 선택 → 본 문서가 1차 산출물. 실구현 착수 시 아래 순서 권장.

| # | 항목 | 예상 | 누적 | 근거 |
|---|------|------|------|------|
| 1 | ① Swagger 슬라이드 + export | 0.5d | 0.5d | 거저 먹는 점수, 코드 영향 최소 |
| 2 | ④ Jira 슬라이드 | 0.5d | 1.0d | 스크린샷 위주, 즉시 완료 |
| 3 | ② npm test hang fix + 피라미드 | 1.0d | 2.0d | 가장 강조된 축, 자산은 이미 존재 |
| 4 | ③ ready/health 분리 + 재프레이밍 | 1.0d | 3.0d | 무중단 개념 + 교수 심기 관리 |
| 5 | ⑤ 교사 OAuth (TDD) | 2.0d | 5.0d | 유일한 실질 신규, 시간 필요 |
| - | 발표 슬라이드 재구성 + 리허설 | 1.0d | 6.0d | §4 참고 |

**총 ~6 작업일** — 5주 여유 내 충분. ⑤를 먼저 시작해 병렬로 굴려도 됨(설계 승인 게이트 있음).

---

## 3. ③ K8s 재프레이밍 스크립트 (발표용 초안)

> 지금 PRD 톤("rubric 가점 항목 아님")은 교수 커리큘럼을 부정하는 인상 → 아래로 교체.

"수업에서 배운 K8s·Argo CD·무중단 배포는 **대규모 운영의 표준**입니다.
저희는 그 **핵심 개념**(헬스체크 기반 무중단 전환, 선언적 배포, 수평 확장)을
평가 규모에 맞는 형태로 구현했습니다 —
무중단은 `/ready` readiness 게이트로, 선언적 배포는 `render.yaml`+GitHub Actions GitOps로,
수평 확장은 `--scale`과 SKIP LOCKED 워커 분배(= Kafka consumer group 등가)로요.
풀 K8s 클러스터는 운영 사용자 0명인 평가 환경에서 **과한 인프라 비용**이라 판단해
의도적으로 제외했고, 도입 트리거(HPA·노드풀)는 ADR과 §10 '추후 고려'에 명시해 뒀습니다."

핵심: **부정("필요 없다")이 아니라 등가+트레이드오프("개념은 충족, 규모상 형태만 다르다")**.

---

## 4. 발표 슬라이드 재구성 (10분)

현재(스택1+UML2+ERD1+AI2+문제1=7분, 데모·테스트·배포·API 누락)을 아래로 재배분:

| 구간 | 시간 | 변경점 |
|------|------|--------|
| 1. 기술스택 | 1.0 | 유지 |
| 2. UML (use case+sequence) | 1.5 | sequence를 **CDC(outbox/notify)**로 교체 검토, 인증은 축약 |
| 3. ERD | 1.0 | CASCADE vs soft-delete 모순 정리, "3NF" 용어 교정 |
| 4. **API 계약 + 테스트 피라미드** | 1.5 | **신규** (① + ②) |
| 5. **배포(무중단)+Agile** | 1.5 | **신규** (③ + ④), K8s 재프레이밍 |
| 6. AI 워크플로우 | 1.0 | 2분→1분 축소 |
| 7. **라이브 데모** | 1.5 | scale=3 + E2E + OAuth 로그인 |
| 8. 문제/마무리 | 1.0 | ⑤로 계정발급 문제 **완결**(교사 OAuth 추가) |

AI 워크플로우를 줄이고 그 시간을 루브릭 핵심축(API/테스트/배포/데모)에 재투자.

---

## 5. 함께 정리할 부수 항목 (Q&A 방어, 저비용)

- [ ] ERD: `ON DELETE CASCADE` vs `deleted_at` soft-delete 모순 → 하나로 통일 후 발표 일관화
- [ ] "User/Student 분리 = 3정규형" → "역할별 **서브타입 분리**(sparse table/NULL 방지)"로 용어 교정
- [ ] Middleware "school_id 강제 주입" 주장 → 실제는 `Depends` 앱레벨 필터. **(택1)** Postgres RLS 실도입(강력) 또는 정직한 톤다운
- [ ] 토큰 메모리 저장: "XSS를 푼다" → "영속 탈취 방지 + XSS는 CSP 다층 방어"로 정정
- [ ] `e2e.yml` 주석 stale "real Kafka" 제거

---

## 6. 결정 사항 (2026-05-31 확정)

1. **Middleware 보안 주장 → Postgres RLS 실도입** ✅ — "DB가 school_id를 강제한다"를 사실로 만듦 (발표 가점). §5 부수항목에서 §1 정식 작업으로 승격.
2. **③ kind/minikube yaml → 작성함** ✅ — 실배포 X, Deployment+readinessProbe+RollingUpdate yaml+다이어그램만.
3. **진행 방식 → §2 ROI 순서로 즉시 착수** ✅ — ① Swagger부터.

**남은 승인 게이트**:
- **⑤ OAuth 플로우 방식** (Auth Code 서버교환 vs FE id_token 검증) — ⑤ 착수 전 3줄 계획 승인 필요

---

*다음 단계: 위 §6 승인 게이트 해소 후 §2 순서대로 착수. 각 항목 완료 시 conventional commit + (해당 시) Jira 이슈 전환.*
