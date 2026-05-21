# Screenshots

README와 발표 자료에 사용하는 이미지를 보관합니다.

수동 캡처(SMS-87 리허설 시):

- `dashboard.png` — `/analytics` 대시보드 (Recharts 위젯이 표시되는 상태)
- `chat.png` — `/chat` AI 비서 (예시 질의/응답)

캡처 가이드:
1. `make demo-scale && docker compose exec backend python /scripts/demo_seed.py`
2. 브라우저를 1280×800 또는 1440×900으로 리사이즈
3. macOS: `Shift+Cmd+4`로 영역 캡처 → 이 디렉터리에 저장
4. 파일 크기가 500KB 넘으면 `pngquant` 또는 ImageOptim으로 압축
