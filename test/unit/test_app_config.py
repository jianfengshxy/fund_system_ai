from __future__ import annotations

import textwrap

import pytest

from src.common.app_config import ConfigError, load_database_config, resolve_config_value


def test_resolve_config_value_supports_nested_refs():
    document = {
        "vars": {
            "common": {
                "database": {
                    "EXTERNAL_HOST": "db.internal",
                    "DB_USER": "fund_user",
                }
            }
        },
        "resources": {
            "demo": {
                "props": {
                    "host": "${vars.common.database.EXTERNAL_HOST}",
                    "user": "${vars.common.database.DB_USER}",
                }
            }
        },
    }

    resolved = resolve_config_value(document, document["resources"]["demo"]["props"])

    assert resolved == {"host": "db.internal", "user": "fund_user"}


def test_load_database_config_prefers_environment(tmp_path):
    s_yaml = tmp_path / "s.yaml"
    s_yaml.write_text(
        textwrap.dedent(
            """
            vars:
              common:
                database:
                  EXTERNAL_HOST: from-yaml
                  port: 3307
                  DB_USER: yaml_user
                  DB_PASSWORD: yaml_pass
                  DB_NAME: yaml_db
            """
        ),
        encoding="utf-8",
    )

    config = load_database_config(
        environ={
            "DB_HOST": "from-env",
            "DB_PORT": "3308",
            "DB_USER": "env_user",
            "DB_PASSWORD": "env_pass",
            "DB_NAME": "env_db",
        },
        s_yaml_path=str(s_yaml),
    )

    assert config["host"] == "from-env"
    assert config["port"] == 3308
    assert config["user"] == "env_user"
    assert config["password"] == "env_pass"
    assert config["database"] == "env_db"


def test_load_database_config_reads_yaml_when_env_missing(tmp_path):
    s_yaml = tmp_path / "s.yaml"
    s_yaml.write_text(
        textwrap.dedent(
            """
            vars:
              common:
                database:
                  EXTERNAL_HOST: yaml-host
                  port: 3306
                  DB_USER: yaml_user
                  DB_PASSWORD: yaml_pass
                  DB_NAME: yaml_db
            """
        ),
        encoding="utf-8",
    )

    config = load_database_config(environ={}, s_yaml_path=str(s_yaml))

    assert config["host"] == "yaml-host"
    assert config["user"] == "yaml_user"
    assert config["password"] == "yaml_pass"
    assert config["database"] == "yaml_db"


def test_load_database_config_requires_complete_configuration():
    with pytest.raises(ConfigError, match="数据库配置缺失"):
        load_database_config(environ={}, s_yaml_path="/tmp/not-exist.yaml")
