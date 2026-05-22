# 발표 아웃라인 — Student Manager v2.1

**연관**: SMS-71 / Architecture §8 / Phase 8

총 15분 + 시연 10분.

## 1. 문제 (2분)

- 한국 학교 교사는 성적·피드백·상담·알림을 4개의 분산된 도구(엑셀/문서/카톡/지필)
  에서 다룬다. 단일 학생 분석을 위해 평균 8~12분 소요.
- 학부모는 학기 종료 전엔 자녀의 학교 데이터에 거의 접근 불가.

## 2. 솔루션 한 줄

> **SaaS 형 학생 관리 + 실시간 분석 + 안전한 AI 비서**

## 3. 아키텍처 (3분)

```
[Vite/React] ──HTTPS──▶ [FastAPI]
                          │  ├── outbox (PG)
                          ▼  ▼
                       [Kafka, partitions=3]
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
        analytics-w1  analytics-w2  analytics-w3
                          │
                          ▼
                  [analytics.agg_*]
                          ▲
                          │
[교사 대시보드 / 챗봇] ────┘
```

- **Outbox + Kafka**: 운영 트랜잭션과 분석 처리 분리 → 실패 격리
- **Consumer group**: 워커 수평 확장 (라이브 시연 포인트)
- **PII 마스킹 + k≥5**: LLM 전송 전 학생명/학번 토큰화

## 4. 시연 (10분)

자세한 순서는 `docs/notes/demo-rehearsal-checklist.md` 참조.

| # | 시연 | 강조 |
|---|------|------|
| 1 | 교사 로그인 → 대시보드 | 30명 학급의 평균/분포가 즉시 보임 |
| 2 | 성적 1건 입력 | Outbox commit |
| 3 | 분석 위젯 자동 갱신 | < 1초 (REQ-074) |
| 4 | `make demo-scale` | worker 3개 분산 처리 로그 |
| 5 | AI 비서에 "이 반 영어 평균은?" | 답변, 학생명은 토큰으로만 |
| 6 | 1명만 있는 반에서 같은 질문 | k<5 거부 메시지 |

## 5. 기술 의사결정 하이라이트 (2분)

- **왜 Kafka?** 학교 도메인 이벤트가 다수 분석 워커에 fan-out 필요. RabbitMQ도
  가능했지만 partition별 ordered consumer + replay가 명확.
- **왜 PG outbox?** 도메인 트랜잭션과 메시지 발행을 atomic하게 묶기 위함. 2PC 회피.
- **왜 OpenAI LLM?** `openai` 공식 SDK로 직접 호출. `LLM_BASE_URL`만 바꾸면
  Kimi/Moonshot 등 OpenAI 호환 provider로 즉시 교체 가능.
- **왜 React + Vite?** 빌드/HMR 속도 + Vercel 호환. Next.js는 SSR이 필요 없어 회피.

## 6. 정량 결과

- REQ-074 SLA(분석 반영 ≤60s) — `docs/notes/analytics-sla-baseline.md` 참조
- 16개 회귀 테스트 (analytics, chat, ratelimit) + 5개 E2E 시나리오
- 백엔드 176 passed / 100% coverage on sanitizer

## 7. 다음 단계 (1분)

- 학부모 모바일 알림 (FCM)
- 교과서/시험지 OCR → 자동 채점
- LLM 응답 캐시 + 비용 모니터링
