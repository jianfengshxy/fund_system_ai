import json
from src.common.logger import get_logger

def test_json_logger_output(capsys):
    logger = get_logger("test")
    logger.info("hello", extra={"account": "acc", "sub_account_name": "sub", "action": "act"})
    out = capsys.readouterr().out.strip()
    data = json.loads(out)
    assert data["level"] == "INFO"
    assert data["logger"] == "test"
    assert data["message"] == "hello"
    assert data["account"] == "acc"
    assert data["sub_account_name"] == "sub"
    assert data["action"] == "act"
