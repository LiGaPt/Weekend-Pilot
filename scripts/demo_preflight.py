from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import httpx
from alembic.config import Config
from alembic.script import ScriptDirectory
from redis import Redis
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError
from alembic.runtime.migration import MigrationContext


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.core.config import get_settings


FORMAL_ALIAS_PATHS = (
    Path("var/formal-benchmarks/latest-release_gate_v1-run-report.json"),
    Path("var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json"),
    Path("var/formal-benchmarks/latest-v2_integrity_gate-run-report.json"),
    Path("var/formal-benchmarks/latest-all_registered-run-report.json"),
    Path("var/recovery-reviews/latest-family_route_failure_v1-review.json"),
)


@dataclass(frozen=True)
class CheckResult:
    label: str
    status: str
    detail: str


def build_preflight_report(repo_root: Path | None = None) -> list[CheckResult]:
    root = repo_root or REPO_ROOT
    settings = get_settings()
    results: list[CheckResult] = []

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    connection: Connection | None = None
    try:
      connection = engine.connect()
      connection.execute(text("SELECT 1"))
      results.append(CheckResult("PostgreSQL", "pass", "可用"))
      results.append(_check_alembic(connection, root))
    except SQLAlchemyError as exc:
      results.append(CheckResult("PostgreSQL", "fail", _short_exception(exc)))
      results.append(CheckResult("Alembic", "fail", "数据库不可用，无法检查迁移"))
    finally:
      if connection is not None:
          connection.close()
      engine.dispose()

    redis_client = Redis.from_url(settings.redis_url)
    try:
        redis_client.ping()
        results.append(CheckResult("Redis", "pass", "可用"))
    except Exception as exc:  # pragma: no cover - defensive network handling
        results.append(CheckResult("Redis", "fail", _short_exception(exc)))
    finally:
        try:
            redis_client.close()
        except Exception:
            pass

    results.extend(
        [
            _check_http_endpoint("API Health", "http://127.0.0.1:8000/health", expect_json_status=True),
            _check_http_endpoint("Public Demo", "http://127.0.0.1:5173/"),
            _check_http_endpoint("Internal Review", "http://127.0.0.1:5174/"),
            _check_aliases(root),
            _check_amap_key(),
        ]
    )
    return results


def main(repo_root: Path | None = None) -> int:
    report = build_preflight_report(repo_root=repo_root)
    print(format_checklist(report))
    return 1 if any(item.status == "fail" for item in report) else 0


def format_checklist(results: list[CheckResult]) -> str:
    lines = ["Demo Preflight Checklist"]
    for item in results:
        lines.append(f"[{item.status.upper()}] {item.label}: {item.detail}")
    return "\n".join(lines)


def _check_alembic(connection: Connection, repo_root: Path) -> CheckResult:
    config = Config(str(repo_root / "alembic.ini"))
    config.set_main_option("script_location", str(repo_root / "alembic"))
    script = ScriptDirectory.from_config(config)
    head_revision = script.get_current_head()
    current_revision = MigrationContext.configure(connection).get_current_revision()
    if current_revision == head_revision:
        return CheckResult("Alembic", "pass", f"已迁移到 {head_revision}")
    return CheckResult("Alembic", "fail", f"当前版本 {current_revision or 'none'}，预期 {head_revision}")


def _check_http_endpoint(label: str, url: str, *, expect_json_status: bool = False) -> CheckResult:
    try:
        with httpx.Client(timeout=3.0, follow_redirects=True) as client:
            response = client.get(url)
        if response.status_code != 200:
            return CheckResult(label, "fail", f"{url} 返回 {response.status_code}")
        if expect_json_status:
            payload = response.json()
            if payload.get("status") != "ok":
                return CheckResult(label, "fail", f"{url} status={payload.get('status')!r}")
        return CheckResult(label, "pass", url)
    except Exception as exc:  # pragma: no cover - network failure handling
        return CheckResult(label, "fail", f"{url} 不可访问: {_short_exception(exc)}")


def _check_aliases(repo_root: Path) -> CheckResult:
    missing = [path.as_posix() for path in FORMAL_ALIAS_PATHS if not (repo_root / path).exists()]
    if missing:
        return CheckResult("Evidence Aliases", "fail", f"缺失: {', '.join(missing)}")
    return CheckResult(
        "Evidence Aliases",
        "pass",
        ", ".join(path.name for path in FORMAL_ALIAS_PATHS),
    )


def _check_amap_key() -> CheckResult:
    key = get_settings().amap_maps_api_key
    if key and key.get_secret_value().strip():
        return CheckResult("AMap Preview", "pass", "AMAP_MAPS_API_KEY 已配置，可演示 AMap 预览")
    return CheckResult("AMap Preview", "warn", "AMAP_MAPS_API_KEY 缺失，AMap 预览不可演示")


def _short_exception(exc: Exception) -> str:
    message = str(exc).strip()
    return message or type(exc).__name__


if __name__ == "__main__":
    raise SystemExit(main())
