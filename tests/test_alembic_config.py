import importlib.util
from configparser import ConfigParser
from pathlib import Path


EXPECTED_TABLES = {
    "users",
    "user_profiles",
    "memory_items",
    "agent_runs",
    "plans",
    "tool_events",
    "action_ledger",
}


def test_alembic_ini_uses_local_script_location() -> None:
    config_path = Path("alembic.ini")

    assert config_path.exists()

    parser = ConfigParser()
    parser.read(config_path)

    assert parser["alembic"]["script_location"] == "alembic"


def test_alembic_env_exposes_runtime_metadata() -> None:
    env_path = Path("alembic/env.py")

    assert env_path.exists()

    spec = importlib.util.spec_from_file_location("weekend_pilot_alembic_env", env_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert set(module.target_metadata.tables) == EXPECTED_TABLES
