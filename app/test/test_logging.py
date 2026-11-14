import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def logging_outputs(tmp_path: Path) -> tuple[str, str, str]:
    script = """
from pathlib import Path
import sys

from app.utils.logging import get_process_logger

logger = get_process_logger("api", Path(sys.argv[1]))
logger.info("info-message")
logger.warning("warning-message")
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    api_log = (tmp_path / "api.log").read_text(encoding="utf-8")
    warning_log = (tmp_path / "api.warning.log").read_text(encoding="utf-8")
    return result.stdout, api_log, warning_log


def test_api_logger_writes_to_stdout(
    logging_outputs: tuple[str, str, str],
) -> None:
    stdout, _, _ = logging_outputs

    assert "info-message" in stdout
    assert "warning-message" in stdout


def test_api_logger_writes_to_api_log(
    logging_outputs: tuple[str, str, str],
) -> None:
    _, api_log, _ = logging_outputs

    assert "info-message" in api_log
    assert "warning-message" in api_log


def test_api_logger_writes_warnings_to_warning_log(
    logging_outputs: tuple[str, str, str],
) -> None:
    _, _, warning_log = logging_outputs

    assert "info-message" not in warning_log
    assert "warning-message" in warning_log
