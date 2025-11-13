import logging
import json
import sys

class JsonFormatter(logging.Formatter):
    def format(self, record):
        data = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for k in ("account", "sub_account_name", "action"):
            v = getattr(record, k, None)
            if v is not None:
                data[k] = v
        return json.dumps(data, ensure_ascii=False)

_configured_loggers = set()

def _configure_named_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if name in _configured_loggers:
        return logger
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.handlers = []
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    _configured_loggers.add(name)
    return logger

def get_logger(name: str) -> logging.Logger:
    return _configure_named_logger(name)
