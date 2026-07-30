import logging
import os
import sys

_logging_configured = False


def setup_logging() -> None:
    global _logging_configured
    if _logging_configured:
        return

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        root.addHandler(handler)

    log_file = os.getenv("LOG_FILE")
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    _logging_configured = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
