from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any, Mapping

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
_VAR_REF_PREFIX = "${"


class ConfigError(RuntimeError):
    """Raised when required runtime configuration is missing or invalid."""


def load_yaml_file(file_path: str | os.PathLike[str]) -> dict[str, Any]:
    """Load a YAML file and always return a dictionary."""
    with open(file_path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_s_yaml_document(file_path: str | None = None) -> dict[str, Any]:
    """Load the local `s.yaml` used by FC deployment and local development."""
    target = Path(file_path) if file_path else PROJECT_ROOT / "s.yaml"
    if not target.exists():
        raise ConfigError(f"未找到配置文件: {target}")
    return load_yaml_file(target)


def resolve_config_value(document: dict[str, Any], value: Any) -> Any:
    """
    Resolve `${vars.xxx}` references inside `s.yaml`.

    The project uses a small subset of Serverless Dev style variable references.
    This helper keeps that parsing logic in one place so runtime modules can reuse
    the same behavior instead of each re-implementing it.
    """
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(_VAR_REF_PREFIX) and stripped.endswith("}"):
            ref_path = stripped[2:-1]
            return resolve_config_value(document, _resolve_reference(document, ref_path))
        return value
    if isinstance(value, dict):
        return {key: resolve_config_value(document, item) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_config_value(document, item) for item in value]
    return copy.deepcopy(value)


def load_database_config(
    *,
    environ: Mapping[str, str] | None = None,
    s_yaml_path: str | None = None,
) -> dict[str, Any]:
    """
    Load database config from environment variables first, then fall back to `s.yaml`.

    Required keys:
    - `host`
    - `user`
    - `password`
    - `database`
    """
    env = dict(environ or os.environ)
    yaml_config = _load_database_config_from_yaml(s_yaml_path)

    config = {
        "host": _first_non_empty(
            env.get("EXTERNAL_HOST"),
            env.get("DB_HOST"),
            yaml_config.get("EXTERNAL_HOST"),
            yaml_config.get("external_host"),
            yaml_config.get("host"),
        ),
        "port": _parse_port(
            _first_non_empty(
                env.get("DB_PORT"),
                yaml_config.get("port"),
                yaml_config.get("DB_PORT"),
                3306,
            )
        ),
        "user": _first_non_empty(
            env.get("DB_USER"),
            yaml_config.get("DB_USER"),
            yaml_config.get("db_user"),
            yaml_config.get("user"),
        ),
        "password": _first_non_empty(
            env.get("DB_PASSWORD"),
            yaml_config.get("DB_PASSWORD"),
            yaml_config.get("db_password"),
            yaml_config.get("password"),
        ),
        "database": _first_non_empty(
            env.get("DB_NAME"),
            yaml_config.get("DB_NAME"),
            yaml_config.get("db_name"),
            yaml_config.get("database"),
        ),
        "charset": _first_non_empty(
            env.get("DB_CHARSET"),
            yaml_config.get("charset"),
            "utf8mb4",
        ),
    }

    missing = [key for key in ("host", "user", "password", "database") if not config.get(key)]
    if missing:
        raise ConfigError(f"数据库配置缺失: {', '.join(missing)}")
    return config


def _load_database_config_from_yaml(file_path: str | None) -> dict[str, Any]:
    try:
        document = load_s_yaml_document(file_path)
    except ConfigError:
        return {}

    vars_section = document.get("vars", {}) or {}
    common_section = vars_section.get("common", {}) or {}
    raw_database = common_section.get("database", {}) or {}
    if not isinstance(raw_database, dict):
        return {}
    return resolve_config_value(document, raw_database)


def _resolve_reference(document: dict[str, Any], ref_path: str) -> Any:
    current: Any = document
    for part in ref_path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        raise ConfigError(f"无法解析配置引用: {ref_path}")
    return current


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _parse_port(raw_value: Any) -> int:
    try:
        return int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"数据库端口非法: {raw_value}") from exc
