import logging
import os


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

    def get_logger(self) -> logging.Logger:
        return self.logger
