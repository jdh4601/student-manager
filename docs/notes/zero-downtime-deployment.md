# 발표용 — 배포 / 무중단 (③)

**목적**: 교수 커리큘럼(Argo CD · K8s · 무중단 배포 · EKS)을 **정면으로 인정**하면서,
평가 규모에 맞는 동등 개념을 어떻게 충족했는지 + 의도적 트레이드오프를 설득.
**관련 코드**: `render.yaml`(`healthCheckPath: /ready`), `app/main.py`(`/health`·`/ready`),
`.github/workflows/cd.yml`, `deploy/k8s/*`, `docker-compose.yml`(healthcheck)

---

## 1. 재프레이밍 스크립트 (이 톤으로 발표)

> 중간발표 PRD의 "K8s = rubric 가점 항목 아님" 톤은 교수 커리큘럼을 부정하는 인상 → 교체.

"수업에서 배운 **K8s · Argo CD · 무중단 배포**는 대규모 운영의 표준입니다.
저희는 그 **핵심 개념**을 평가 규모에 맞는 형태로 구현했습니다:

- **무중단**: `readinessProbe(/ready)` + `maxUnavailable=0` — 새 인스턴스가 DB 연결을 확인하고 Ready가 된 뒤에만 옛 인스턴스를 교체. Render `healthCheckPath`가 이를 매니지드로 제공합니다.
- **선언적 배포(GitOps)**: `render.yaml` + GitHub Actions(`cd.yml`)로 main push → 자동 배포. Argo CD의 '선언적 desired state' 개념과 동일합니다.
- **수평 확장**: `--scale analytics-worker=3` + SKIP LOCKED 워커 분배 = Kafka consumer group 등가.

풀 K8s 클러스터는 운영 사용자 0명인 평가 환경에서 과한 인프라 비용이라 **의도적으로 제외**했고,
도입 트리거(HPA·노드풀)는 ADR과 architecture.md §10에 명시했습니다.
개념 증명용 K8s 매니페스트는 `deploy/k8s/`에 두었습니다."

핵심: **부정("필요 없다") ❌ → 등가+트레이드오프("개념은 충족, 규모상 형태만 다르다") ✅**

---

## 2. 무중단 배포 시퀀스 (슬라이드 다이어그램)

```
배포 트리거 (main push)
        │
        ▼
  새 버전 Pod/인스턴스 부팅  ──┐
        │                      │  이 동안 옛 인스턴스가 계속 트래픽 처리 (가용성 유지)
        ▼                      │
  readinessProbe GET /ready ◄──┘
        │ (DB SELECT 1 OK?)
        ├─ 실패 → 트래픽 안 받음, 재시도 (옛 인스턴스 유지)
        └─ 성공 → Service 엔드포인트 편입 → 트래픽 전환
                        │
                        ▼
              옛 인스턴스 graceful 종료
                        │
                        ▼
                  배포 완료 (다운타임 0)
```

**liveness vs readiness 구분 (발표 포인트)**:
- `/health` (liveness): 프로세스가 살아있는가? → 응답 없으면 **재시작**. DB 미접근(가벼움).
- `/ready` (readiness): 트래픽 받을 준비가 됐는가? → DB 연결 확인. 안 되면 **트래픽 제외**(재시작 X).
- 둘을 분리해야 "DB 일시 단절 시 재시작 폭주" 없이 트래픽만 우회시킬 수 있다.

---

## 3. 이미 갖춘 것 (실데이터)

| 개념 | 구현 위치 | 상태 |
|------|----------|------|
| readiness 게이트 | `render.yaml: healthCheckPath: /ready` | ✅ |
| liveness/readiness 분리 | `app/main.py` `/health`·`/ready` | ✅ |
| GitOps 자동 배포 | `.github/workflows/cd.yml` (main push) | ✅ |
| 로컬 healthcheck | `docker-compose.yml` db·backend `healthcheck:` | ✅ |
| 수평 확장 시연 | `docker-compose --scale analytics-worker=3` | ✅ |
| K8s 개념 매니페스트 | `deploy/k8s/*.yaml` (illustrative) | ✅ |

---

## 4. 슬라이드 구성 (③+④ 합쳐 1.5분)

- (좌) 무중단 시퀀스 다이어그램 (§2)
- (우상) 재프레이밍 표 (커리큘럼 ↔ 우리 구현, `deploy/k8s/README.md` 표)
- (우하) `deploy/k8s/backend-deployment.yaml`의 `maxUnavailable: 0` + probe 발췌
- 말풍선: "Render 매니지드 롤링 = K8s RollingUpdate와 동일 개념, 비용 0"

---

## 5. 예상 Q&A

- **Q. 왜 진짜 K8s를 안 썼나요?**
  A. 운영 사용자 0명 평가 환경에서 클러스터 운영 비용 대비 효용이 낮습니다. 핵심 개념(무중단·확장·선언적 배포)은 Render+compose+yaml로 동등하게 증명했고, 도입 트리거는 문서화했습니다.
- **Q. Render free tier는 cold start 있지 않나요?**
  A. 맞습니다. 그래서 `healthCheckPath`로 readiness가 통과한 뒤 트래픽을 받도록 했고, 무중단이 중요한 운영 단계에선 paid tier 또는 K8s로 전환하는 트리거를 ADR에 명시했습니다.
- **Q. Argo CD는요?**
  A. GitHub Actions로 선언적 배포의 핵심(desired state를 git으로 관리, push가 배포 트리거)을 충족했습니다. Argo CD의 drift 감지·자동 sync는 멀티클러스터 규모에서 필요해지는 기능이라 평가 후 트랙입니다.
