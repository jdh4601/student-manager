"""Settings 파싱 회귀 테스트.

배경: pydantic-settings v2는 `list[str]` 필드를 env에서 읽을 때 JSON으로 먼저
디코딩하므로, CSV 문자열("a.ac.kr,b.edu")이 SettingsError로 부팅을 깨뜨렸다.
`allowed_teacher_domains`에 `NoDecode`를 달아 split_domains(CSV)가 처리하도록 수정.
이 테스트는 env CSV 경로가 다시 깨지지 않도록 고정한다.
"""

import pytest

from app.config import Settings


def test_allowed_teacher_domains_parses_single_csv_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_TEACHER_DOMAINS", "inu.ac.kr")
    settings = Settings()
    assert settings.allowed_teacher_domains == ["inu.ac.kr"]


def test_allowed_teacher_domains_parses_multi_csv_with_trim_and_lowercase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALLOWED_TEACHER_DOMAINS", " INU.ac.kr , snu.ac.kr ,")
    settings = Settings()
    assert settings.allowed_teacher_domains == ["inu.ac.kr", "snu.ac.kr"]


def test_allowed_teacher_domains_defaults_empty_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALLOWED_TEACHER_DOMAINS", raising=False)
    settings = Settings()
    assert settings.allowed_teacher_domains == []
