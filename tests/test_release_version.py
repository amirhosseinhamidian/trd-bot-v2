import json
import tomllib
from pathlib import Path
from typing import Any

from trd_bot import __version__
from trd_bot.core.config import Settings

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RELEASE_VERSION = "0.2.0"


def test_release_version_is_consistent_across_runtime_and_manifests() -> None:
    with (REPOSITORY_ROOT / "pyproject.toml").open("rb") as stream:
        pyproject: dict[str, Any] = tomllib.load(stream)

    frontend_package: dict[str, Any] = json.loads(
        (REPOSITORY_ROOT / "frontend/package.json").read_text(encoding="utf-8")
    )
    frontend_lock: dict[str, Any] = json.loads(
        (REPOSITORY_ROOT / "frontend/package-lock.json").read_text(encoding="utf-8")
    )
    environment = dict(
        line.split("=", maxsplit=1)
        for line in (REPOSITORY_ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )

    assert __version__ == RELEASE_VERSION
    assert Settings.model_fields["app_version"].default == RELEASE_VERSION
    assert pyproject["project"]["version"] == RELEASE_VERSION
    assert environment["TRD_BOT_APP_VERSION"] == RELEASE_VERSION
    assert frontend_package["version"] == RELEASE_VERSION
    assert frontend_lock["version"] == RELEASE_VERSION
    assert frontend_lock["packages"][""]["version"] == RELEASE_VERSION
