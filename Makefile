.PHONY: help up down logs seed demo-scale demo-scale-logs demo-scale-down qa e2e

help:
	@echo "Targets:"
	@echo "  up               docker compose up -d (싱글 analytics-worker)"
	@echo "  down             docker compose down"
	@echo "  logs             docker compose logs -f"
	@echo "  seed             호스트 python으로 demo_seed.py 실행 → outbox 행이 stage되어"
	@echo "                   publisher → analytics-worker가 analytics.agg_*를 채움 (SMS-71/94)"
	@echo "  demo-scale       analytics-worker 3개로 라이브 데모용 기동 (SMS-67)"
	@echo "  demo-scale-logs  3개 worker의 로그를 한 화면에서 follow (분산 처리 시연)"
	@echo "  demo-scale-down  데모 컨테이너 정리"
	@echo "  qa               백엔드/프런트 정적·단위 검증 (npm run qa)"
	@echo "  e2e              Playwright E2E (npm run e2e)"

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

seed:
	DATABASE_URL=postgresql+asyncpg://sm:smpass@localhost:5432/student_manager \
		backend/.venv312/bin/python scripts/demo_seed.py

demo-scale:
	docker compose up -d --scale analytics-worker=3
	@echo ""
	@echo "✅ analytics-worker x3 기동 완료. 다음 명령으로 분산 로그 확인:"
	@echo "   make demo-scale-logs"

demo-scale-logs:
	docker compose logs -f --tail=20 analytics-worker

demo-scale-down:
	docker compose down

qa:
	npm run qa

e2e:
	npm run e2e
