import json
import logging
import logging.config
import os
from pathlib import Path


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=True)


def setup_logging() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", "text").strip().lower()
    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    log_file = os.getenv("LOG_FILE", "app.log")
    log_max_bytes = int(os.getenv("LOG_MAX_BYTES", "10485760"))
    log_backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))

    log_dir.mkdir(parents=True, exist_ok=True)
    file_path = log_dir / log_file

    text_formatter = {
        "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        "datefmt": "%Y-%m-%d %H:%M:%S",
    }

    formatters = {
        "text": text_formatter,
        "json": {
            "()": "src.core.logging_config.JsonFormatter",
            "datefmt": "%Y-%m-%dT%H:%M:%S",
        },
    }

    selected_formatter = "json" if log_format == "json" else "text"

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": formatters,
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": selected_formatter,
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": log_level,
                "formatter": selected_formatter,
                "filename": str(file_path),
                "maxBytes": log_max_bytes,
                "backupCount": log_backup_count,
                "encoding": "utf-8",
            },
        },
        "root": {
            "level": log_level,
            "handlers": ["console", "file"],
        },
    }

    logging.config.dictConfig(config)

    if log_format == "json":
        logging.getLogger("uvicorn.access").handlers = []
