# ADR-001: OLAP 분석 파이프라인 + 인프라 방향

**상태**: Accepted
**작성일**: 2026-05-03
**작성자**: DongHyun Jung
**선행 결정**: `history/2026-05-03-v2.1-architecture-grill.md`
**연관 ADR**: ADR-002 (CDC 패턴 — Outbox + Kafka)

---

## Context

본 프로젝트는 **졸업 평가용 과제**다. 운영 사용자는 0명이며, 로컬 환경에서만 실행한다. 평가 마감은 **2026-07-03 (약 2개월 후)**이며 평가 방식은 **라이브 데모 + 발표**다.

### 평가 rubric의 핵심 가점 항목

- (a) **데이터 변경 이벤트 기반 분석 DB 갱신** — *"Apache Kafka와 같은 메시지 스트림"* 명시
- (b) **확장 가능한 설계** — 정성 가점
- (c) AI/LLM 활용 — 정성 가점
- EKS·Kubernetes 도입은 **비필수** (가점 항목이 아님)

### 신규 요구사항 (OLAP)

- 운영 데이터(출결·평가·피드백 등)를 분석용으로 분리 적재
- 학생별·과목별 학습 현황 집계 대시보드
- 데이터 변경 이벤트 기반 적재 구조 → 가점
- (선택) 분석 요약 데이터 기반 AI 어시스턴트

### 자원 제약

- 1인 + Claude Code
- Kafka·Redpanda·Debezium 미경험
- 두 번 만들 시간 없음 (재작업 비용 큼)

---

## Decision

### 1. OLAP 분리: 동일 PG DB + `analytics` 스키마

운영 스키마(`public`)와 분석 스키마(`analytics`)를 단일 PostgreSQL 인스턴스 내에서 분리한다.

**이유**
- 별도 DB 인스턴스 비용·운영 부담 없음
- 운영-분석 간 일관성 검증이 SQL 한 번에 가능
- 데이터 규모(평가용 시드)에서 단일 인스턴스로 충분
- 추후 별도 DB로 분리 시 schema dump → 신규 인스턴스 import로 전환 가능

### 2. CDC: Outbox 패턴 + Kafka KRaft 단일 노드

운영 트랜잭션 안에서 `outbox` 테이블에 이벤트를 INSERT하고, 별도 publisher 프로세스가 미발행 row를 polling하여 Kafka 토픽으로 발행한다. `analytics-worker`(consumer)는 토픽을 구독하여 `analytics.*` 테이블을 UPSERT한다.

**이유**
- **메시지 스트림 가점 충족**: Kafka 명시적으로 사용
- **이벤트 유실 방지**: outbox row가 commit되면 publisher가 다운돼도 부팅 시 catch-up
- **단일 학습 곡선**: Debezium 같은 별도 인프라 추가 없이 application 코드로 처리 → 1인·미경험 자원에 적합
- 자세한 비교는 ADR-002 참조

**Fallback**: Week 3 금요일 PoC 실패 시 Redpanda로 전환 (Kafka API 호환, publisher/consumer 코드 변경 0).

### 3. 인프라: 로컬 docker-compose 유지

EKS·AWS·Helm·Terraform·External Secrets Operator 도입을 폐기한다. FastAPI · Outbox publisher · analytics-worker · Kafka(KRaft) · Postgres · Frontend dev 서버를 단일 `docker-compose.yml`로 묶는다.

**이유**
- **사용자 0명**: 운영 환경 cold start·HA·관제 요구 없음
- **EKS는 가점 항목이 아님**: rubric에 EKS·Kubernetes는 명시되지 않음
- **2개월 안에 두 번 만들 시간 없음**: 인프라 학습이 critical path를 잡아먹으면 가점 항목(메시지 스트림·챗봇)이 부실해짐
- **확장성은 설계로 입증**: 컨테이너 다이어그램 + `docker-compose up --scale analytics-worker=3` 라이브 시연으로 "확장 가능한 설계" 정성 가점 확보

### 4. 인증: 현재 유지

JWT + 이메일/비밀번호 방식 유지. OAuth/SSO 도입은 평가 후로 연기.

### 5. 대시보드: 교사 개인용

분석 대시보드는 교사 본인이 담당하는 학급의 학생별·과목별 집계만 표시. 학교 관리자/학생/학부모 대시보드는 평가 후로 연기.

### 6. AI 어시스턴트: 데모용 단일 엔드포인트

별도 마이크로서비스가 아닌, FastAPI 백엔드에 단일 엔드포인트(`POST /api/v1/chat`)로 구현. 분석 SQL 결과를 LLM에 컨텍스트로 주입하고 자연어 응답을 반환한다.

**이유**
- 마이크로서비스 분리는 평가용 1인 환경에서 ROI 음수
- 벡터 인덱싱 없음 → "RAG"가 아닌 "**LLM 기반 자연어 분석 응답**"으로 명명 정정
- PII는 학급 단위 통계로 답변 범위를 제한 + 이름 단순 치환(`학생A`)으로 마스킹
- 구현 예산: 약 3일

---

## Consequences

### 긍정적
- 메시지 스트림 가점 항목 명시적 충족 (Kafka)
- 확장성 가점은 다이어그램 + scale 시연으로 입증 → narrative 일관성 ("이벤트 기반 OLTP/OLAP 분리로 확장 가능한 설계")
- 인프라 학습 부담을 critical path에서 제거 → 평가 항목에 자원 집중
- AI 정성 가점은 단일 엔드포인트 데모로 비용 효율적으로 확보

### 부정적
- Kafka KRaft 운영 학습 부담 (1인 미경험) → W3 PoC fail 시 Redpanda fallback으로 완화
- 운영 트랜잭션 안에 outbox INSERT 추가 → 약간의 latency 증가 (측정 후 수용 여부 확인)
- "운영 환경 학습"은 EKS 폐기로 포기 → 평가 후 별도 학습 트랙으로 이전

### 중립적
- 기존 도메인 API/UX 계약 유지 (운영 엔드포인트 변경 없음)
- 분석은 별도 API 네임스페이스(`/api/v1/analytics/*`)로 분리

---

## Alternatives Considered

| 대안 | 선택하지 않은 이유 |
|------|----------------|
| **AWS EKS 도입** | rubric에 EKS 명시 없음. 2개월·1인 자원에서 가점 항목(메시지 스트림·챗봇)을 압도. 사용자 0명에서 cold start·HA 정당화 불가 |
| **LISTEN/NOTIFY ETL** | 메시지 스트림 가점 기준 모호. 외부 브로커가 아니므로 평가자 해석에 의존하는 위험 |
| **Debezium + Kafka Connect** | 학습 곡선 급격 + 인프라 디버깅 위험. 1인 미경험 자원에서 critical path 위험 (ADR-002 참조) |
| **App-direct Kafka publish** | broker 다운 시 이벤트 유실. 발표 Q&A 방어 약함 (ADR-002 참조) |
| **ClickHouse / BigQuery** | 단일 DB 정책, 학교당 데이터량 작음 (수만 row), 평가용 환경에 과도 |
| **Cron 배치 ETL** | 가점 기준(이벤트 기반) 미충족 |
| **별도 챗봇 마이크로서비스 + 벡터 인덱싱** | 1인 자원에서 ROI 음수, "RAG" 명명 오류, PII 마스킹 본질적 결함 |

---

## Roadmap

| Phase | 내용 | 산출물 |
|-------|------|--------|
| **W1. 문서화** | PRD/Design Spec v2.1, Architecture v1.1, ADR-001 재작성 + ADR-002 신규 | docs/* |
| W2. 분석 스키마 + Outbox | `analytics.*` 테이블 + Alembic + outbox 테이블 + 운영 라우터 outbox INSERT | DB migration + TX 일관성 테스트 |
| W3. Kafka + Publisher | Kafka KRaft docker-compose + Outbox publisher (aiokafka). **금요일 PoC fail → Redpanda fallback** | 토픽 발행 검증 |
| W4. Analytics Worker | Kafka consumer + `analytics.*` UPSERT | end-to-end event flow |
| W5. 분석 API + 대시보드 | `/api/v1/analytics/*` + 교사 대시보드 (FE) | API + 차트 |
| W6. 챗봇 단일 엔드포인트 | `/api/v1/chat` + 채팅 위젯 (3일) | 데모용 챗봇 |
| W7. Scale 시연 + 통합 테스트 | `--scale analytics-worker=3` 검증 + testcontainers Kafka | 통합 테스트 green |
| W8. E2E + SLA 검증 | Playwright (REQ-074: 1분 SLA) | E2E green |
| W9. 발표 준비 | 슬라이드 + 데모 리허설 + 버퍼 | 발표 ready |

Critical path: **W2 → W5** (DB → publisher → worker → API → UI).

---

## References

- 평가 rubric (메시지 스트림 가점 — *"Apache Kafka와 같은 메시지 스트림"*; EKS 비필수)
- `docs/decisions/history/2026-05-03-v2.1-architecture-grill.md` (결정 트리 Q1~Q8)
- `docs/decisions/002-cdc-pattern-outbox-kafka.md` (CDC 대안 비교)
- PRD v2.1 §10 (OLAP & 분석), §11 (AI 어시스턴트)
- Design Spec v2.1 §9 (Analytics Layer), §10 (Chatbot)
- Architecture v1.1 (data flow, scalability)
