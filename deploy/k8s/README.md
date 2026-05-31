# Kubernetes 매니페스트 (발표/시연용)

> ⚠️ **실배포하지 않는다.** 이 디렉토리는 수업에서 배운 K8s 개념(롤링 무중단 배포,
> readiness/liveness probe, 수평 확장)을 **우리 아키텍처에 어떻게 적용하는지** 코드로
> 보이기 위한 illustrative manifest다. 운영 surface는 Render(매니지드 롤링) + Vercel이다.

## 왜 실배포가 아니라 yaml인가 (재프레이밍)

| 수업 커리큘럼 | 우리 구현 (동등 개념) |
|--------------|----------------------|
| K8s RollingUpdate | Render 헬스체크 기반 롤링 전환 + 본 yaml의 `maxUnavailable=0` |
| readinessProbe | `GET /ready` (DB 연결 확인) — Render `healthCheckPath`로 이미 동작 |
| livenessProbe | `GET /health` (프로세스 생존) |
| HPA / 수평 확장 | `--scale analytics-worker=N` + SKIP LOCKED claim (= Kafka consumer group) |
| Argo CD GitOps | GitHub Actions(`.github/workflows/cd.yml`) main push → 자동 배포 |

운영 사용자 0명인 평가 환경에서 풀 K8s 클러스터는 **과한 인프라 비용**이라 의도적으로 제외했고,
도입 트리거(HPA·노드풀)는 `docs/architecture.md §10 추후 고려`에 명시했다.

## 파일

- `backend-deployment.yaml` — API Deployment(2 replicas, RollingUpdate maxUnavailable=0) + Service + liveness/readiness probe
- `analytics-worker-deployment.yaml` — worker Deployment(3 replicas = 수평 확장 시연) + single publisher

## 개념 검증 (실제로 돌려보고 싶다면, 평가 후 트랙)

```bash
# kind/minikube 로컬 클러스터에서 개념 확인 (선택)
kind create cluster
kubectl create secret generic sm-secrets --from-literal=database-url=postgresql+asyncpg://...
kubectl apply -f deploy/k8s/
kubectl rollout status deploy/student-manager-backend   # 무중단 롤링 관찰
kubectl scale deploy/student-manager-analytics-worker --replicas=5  # 수평 확장
```

## 무중단 배포의 핵심 (발표 1줄)

`maxUnavailable: 0` + `readinessProbe(/ready)` 조합 → 새 버전 Pod가 **DB 연결을 확인하고
Ready 상태가 된 뒤에야** 옛 Pod가 종료된다. 가용 Pod 수가 배포 중 절대 0으로 떨어지지 않음 = 무중단.
