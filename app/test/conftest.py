import os
import tempfile
from pathlib import Path

os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/test"
os.environ["LOG_DIR"] = str(Path(tempfile.gettempdir()) / "checkstock-tests-logs")
