import logging
import os
from datetime import datetime
from enum import IntEnum
from typing import Any

from util.datetime_util import format_date


class LogLevel(IntEnum):
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class Logger:
    def __init__(
        self,
        system_name: str,
        log_file_path: str,
        level: int = logging.INFO,
    ):
        self.logger = logging.getLogger(system_name)
        self.logger.setLevel(level)

        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

        file_handler = logging.FileHandler(log_file_path)
        file_handler.setLevel(level)

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )
        file_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)

    def log(
        self,
        source: str,
        log_datetime: datetime,
        log_level: LogLevel,
        message: str,
        additional_info: dict[str, Any] | None = None,
    ) -> None:
        """
        Logs "[log_datetime] [source] message. key: value, key: value".
        additional_info maps a variable name to its value, e.g. {"leg": leg}.
        """
        text = f"[{format_date(log_datetime)}] [{source}] {message}."
        if additional_info:
            info = ", ".join(
                f"{key}: {value}" for key, value in additional_info.items()
            )
            text = f"{text} {info}"

        self.logger.log(log_level, text)
