from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from leadfinder.errors import redact_secrets
from leadfinder.paths import default_log_path

LOGGER_NAME = "leadfinder"


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact_secrets(super().format(record))


def configure_logging(*, to_file: bool = True) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    formatter = RedactingFormatter("%(asctime)s %(levelname)s %(message)s")
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    logger.addHandler(stream)
    if to_file:
        handler = RotatingFileHandler(
            default_log_path(),
            maxBytes=512_000,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.propagate = False
    return logger
