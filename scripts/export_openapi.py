"""OpenAPI 스펙을 파일로 추출 (contract-first 산출물).

발표 서사: "Pydantic 스키마 = 단일 진실 공급원 → 이 openapi.json이 FE/BE API 합의안".
추출한 파일은 (1) 팀 PR 리뷰, (2) Postman/Bruno 임포트, (3) 프론트 타입 생성에 사용한다.

실행 (backend 가상환경):
    cd backend && python ../scripts/export_openapi.py

출력:
    docs/api/openapi.json   (버전 관리 대상 — diff로 API 변경 추적)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# backend 패키지 경로 주입 (스크립트를 어디서 실행하든 app import 가능)
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402  (sys.path 주입 후 import)


def export_openapi(output_path: Path) -> dict:
    """현재 FastAPI 앱의 OpenAPI 스키마를 JSON 파일로 기록한다."""
    spec = app.openapi()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return spec


def main() -> None:
    output = Path(__file__).resolve().parent.parent / "docs" / "api" / "openapi.json"
    spec = export_openapi(output)
    path_count = len(spec.get("paths", {}))
    schema_count = len(spec.get("components", {}).get("schemas", {}))
    print(f"OpenAPI {spec['info']['version']} → {output}")
    print(f"  paths: {path_count}, schemas: {schema_count}")


if __name__ == "__main__":
    main()
