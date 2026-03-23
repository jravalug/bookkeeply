import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(app):
    """Configure app logging (console + rotating file) with environment-based level."""
    log_level_name = str(app.config.get("LOG_LEVEL", "INFO")).upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    log_dir = Path(app.config.get("LOG_DIR", Path(app.root_path).parents[0] / "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / app.config.get("LOG_FILE", "bookkeeply.log")
    max_bytes = int(app.config.get("LOG_MAX_BYTES", 5 * 1024 * 1024))
    backup_count = int(app.config.get("LOG_BACKUP_COUNT", 5))

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    if not any(
        getattr(handler, "name", "") == "bookkeeply_console"
        for handler in root_logger.handlers
    ):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        console_handler.name = "bookkeeply_console"
        root_logger.addHandler(console_handler)

    log_file_abs = str(log_file.resolve())
    has_file_handler = any(
        isinstance(handler, RotatingFileHandler)
        and getattr(handler, "baseFilename", "") == log_file_abs
        for handler in root_logger.handlers
    )
    if not has_file_handler:
        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    app.logger.setLevel(log_level)
    app.logger.propagate = True
    app.logger.info(
        "Logging initialized | level=%s | file=%s | pid=%s",
        log_level_name,
        log_file,
        os.getpid(),
    )
