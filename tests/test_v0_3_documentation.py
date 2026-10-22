import json
import tomllib
from pathlib import Path
from typing import Any, cast

from alembic.config import Config
from alembic.script import ScriptDirectory

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPOSITORY_ROOT / "docs/v0.3/release-documentation-manifest.json"
GUIDE_PATH = REPOSITORY_ROOT / "docs/v0.3/52-v0.2-to-v0.3-migration-guide.md"


def _load_manifest() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(MANIFEST_PATH.read_text(encoding="utf-8")))


def test_documentation_manifest_matches_release_and_migration_chain() -> None:
    manifest = _load_manifest()
    with (REPOSITORY_ROOT / "pyproject.toml").open("rb") as stream:
        pyproject: dict[str, Any] = tomllib.load(stream)
    frontend_package: dict[str, Any] = json.loads(
        (REPOSITORY_ROOT / "frontend/package.json").read_text(encoding="utf-8")
    )

    alembic_config = Config(str(REPOSITORY_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(alembic_config)
    head = script.get_current_head()
    revision_chain = {revision.revision for revision in script.iterate_revisions(head, "base")}

    assert manifest["schema_version"] == "v0.3-release-documentation-manifest-v1"
    assert manifest["source_release"] == {
        "version": "0.2.0",
        "git_tag": "v0.2.0",
        "commit_sha": "6e101f9f66ba83720335077f409b53d012cdbf5c",
        "migration_revision": "20260926_0017",
    }
    assert manifest["source_release"]["migration_revision"] in revision_chain
    assert manifest["target_release"]["version"] == pyproject["project"]["version"]
    assert manifest["target_release"]["version"] == frontend_package["version"]
    assert manifest["target_release"]["migration_revision"] == head
    assert manifest["target_release"]["commit_sha_required"] is True


def test_documentation_manifest_references_existing_documents_and_environment() -> None:
    manifest = _load_manifest()
    environment = dict(
        line.split("=", maxsplit=1)
        for line in (REPOSITORY_ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )

    for relative_path in manifest["documents"]:
        assert (REPOSITORY_ROOT / relative_path).is_file(), relative_path
    assert set(manifest["required_environment_keys"]) <= environment.keys()
    assert manifest["runtime"] == {
        "python": "3.12",
        "node": "22",
        "postgresql": "17",
    }


def test_migration_guide_covers_backup_restore_gates_and_retired_routes() -> None:
    manifest = _load_manifest()
    guide = GUIDE_PATH.read_text(encoding="utf-8")
    normalized_guide = " ".join(guide.split())

    required_commands = (
        "pg_dump",
        "pg_restore",
        "python -m alembic current",
        "python -m alembic upgrade head",
        "python -m alembic check",
        'python -m pytest -m "not integration"',
        "python -m pytest -m integration -q",
        "npm ci",
        "npm run build",
    )
    for command in required_commands:
        assert command in guide

    for route in manifest["retired_routes"]:
        assert f"`{route['method']} {route['path']}`" in guide
        assert f"`POST {route['replacement']}`" in guide

    assert "alembic downgrade base" in guide
    assert "docker compose down -v" in guide
    assert "روی دیتابیس دارای داده" in normalized_guide
    assert "اجرا نکنید" in normalized_guide
    assert "P6-06" in guide


def test_documentation_preserves_the_no_live_operating_boundary() -> None:
    manifest = _load_manifest()
    guide = GUIDE_PATH.read_text(encoding="utf-8")
    normalized_guide = " ".join(guide.split())
    safety = manifest["safety_boundary"]

    assert safety["supported_modes"] == ["RESEARCH", "BACKTEST", "PAPER", "SHADOW"]
    assert safety["live_execution"] is False
    assert safety["exchange_credentials"] is False
    assert safety["real_asset_management"] is False
    assert "Live Execution" in guide
    assert "API key یا secret صرافی" in normalized_guide
    assert "مدیریت دارایی واقعی" in guide
