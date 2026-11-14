import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 3
LOG_FORMAT = (
    "%(asctime)s - %(name)s - %(levelname)s - "
    "%(processName)s[%(process)d] - %(message)s"
)
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _get_log_level(log_level: str | int) -> int:
    if isinstance(log_level, int):
        return log_level

    resolved_level = getattr(logging, log_level.upper(), None)
    if not isinstance(resolved_level, int):
        raise ValueError(f"Unknown log level: {log_level}")
    return resolved_level


def _get_formatter() -> logging.Formatter:
    return logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)


def _get_process_name(process_name: str) -> str:
    normalized_name = "".join(
        character if character.isalnum() or character in "._-" else "_"
        for character in process_name.strip()
    )
    if not normalized_name:
        raise ValueError("Process name must not be empty")
    return normalized_name


def _has_file_handler(logger: logging.Logger, log_path: Path) -> bool:
    resolved_log_path = log_path.resolve()
    return any(
        isinstance(handler, RotatingFileHandler)
        and Path(handler.baseFilename).resolve() == resolved_log_path
        for handler in logger.handlers
    )


def _add_file_handler(
    logger: logging.Logger,
    log_path: Path,
    log_level: int,
) -> None:
    if log_path.is_dir():
        raise RuntimeError(f"Log path must be a file: {log_path}")
    if _has_file_handler(logger, log_path):
        return

    handler = RotatingFileHandler(
        log_path,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setLevel(log_level)
    handler.setFormatter(_get_formatter())
    logger.addHandler(handler)


def setup_logging(log_level: str | int = "INFO") -> logging.Logger:
    resolved_level = _get_log_level(log_level)
    root_logger = logging.getLogger()
    root_logger.setLevel(resolved_level)

    if not any(
        isinstance(handler, logging.StreamHandler)
        and not isinstance(handler, logging.FileHandler)
        for handler in root_logger.handlers
    ):
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(resolved_level)
        handler.setFormatter(_get_formatter())
        root_logger.addHandler(handler)

    return root_logger


def get_process_logger(
    process_name: str,
    log_dir: Path = Path("logs"),
    log_level: str | int = "INFO",
) -> logging.Logger:
    resolved_level = _get_log_level(log_level)
    normalized_name = _get_process_name(process_name)
    resolved_log_dir = log_dir.resolve()
    resolved_log_dir.mkdir(parents=True, exist_ok=True)

    setup_logging(resolved_level)

    logger = logging.getLogger(normalized_name)
    logger.setLevel(resolved_level)
    logger.propagate = True

    _add_file_handler(
        logger,
        resolved_log_dir / f"{normalized_name}.log",
        resolved_level,
    )
    _add_file_handler(
        logger,
        resolved_log_dir / f"{normalized_name}.warning.log",
        logging.WARNING,
    )
    return logger


def get_logger(
    process_name: str,
    log_dir: Path = Path("logs"),
    log_level: str | int = "INFO",
) -> logging.Logger:
    return get_process_logger(
        process_name=process_name,
        log_dir=log_dir,
        log_level=log_level,
    )
