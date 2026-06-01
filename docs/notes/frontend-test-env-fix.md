# Frontend 테스트 "hang" — 근본 원인 및 해결

**증상**: `npm test`가 끝나지 않음(hang). CLAUDE.md에서 `qa`에서 제외된 그 이슈.
**규명일**: 2026-05-31

---

## 근본 원인 (2가지 복합)

### 1. `npm test`가 watch 모드
`"test": "vitest"`는 watch 모드라 종료되지 않는다(정상 동작이나 "hang"처럼 보임).
→ `"test:run": "vitest run"` 추가로 분리 (이번 커밋).

### 2. (진짜 원인) 환경 불일치
`vitest run`으로 바꿔도 **100% CPU로 멈춤**. 원인 둘:

1. **node_modules가 Linux 바이너리** — `node_modules/@rollup/`에 `rollup-linux-arm64-*`만 존재.
   이 머신은 macOS(darwin-arm64)인데 darwin 바이너리가 없어 rollup이 `Cannot find module
   '@rollup/rollup-darwin-arm64'`로 실패. (node_modules가 Docker/Linux에서 설치된 잔재로 추정)
2. **Node 25 ≠ vitest 1.6** — 시스템 Node가 v25.x인데 vitest 1.x는 Node 18/20 지원.
   불일치 시 tinypool 워커가 100% CPU로 spin (멈춤의 직접 원인).

---

## 해결 (호스트에서 1회)

```bash
# 1) vitest 1.6과 호환되는 Node 20 사용
nvm install 20 && nvm use 20

# 2) 플랫폼 맞는 node_modules로 클린 재설치 (Linux 바이너리 → darwin)
cd frontend
rm -rf node_modules package-lock.json
npm install

# 3) 실행 (watch 아님)
npm run test:run
```

⚠️ **주의**: `rm -rf package-lock.json && npm install`은 lockfile을 재생성한다.
Docker 빌드가 `npm ci`로 Linux 바이너리를 기대한다면, **호스트와 컨테이너의 optional dep
차이**를 검토할 것. 안전한 대안: Docker 컨테이너 안에서 테스트를 실행하거나,
CI(Node 20 리눅스)에서 `vitest run`을 돌린다 (`.github/workflows/ci.yml`).

---

## 권장: CI에서 frontend 단위 테스트 실행

호스트 환경 변수를 제거하려면 CI(Ubuntu + Node 20)에서 `npm run test:run`을 돌리는 게 가장
안정적이다. 로컬 darwin 바이너리 이슈와 무관하게 결정론적으로 통과/실패가 나온다.
