
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger():
    log_directory = Path("logs")
    log_directory.mkdir(exist_ok=True)

    file_handler = RotatingFileHandler(
        log_directory / "app.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8"
    )

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    logger = logging.getLogger("email_sender")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        logger.addHandler(file_handler)

    return logger


logger = setup_logger()
