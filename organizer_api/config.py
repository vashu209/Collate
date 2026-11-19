"""API configuration settings."""

import os
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        self.host: str = "127.0.0.1"
        self.port: int = int(os.environ.get("ORGANIZER_API_PORT", "8000"))
        self.db_path: Path = Path(
            os.environ.get("ORGANIZER_DB_PATH", "data/organizer.db")
        ).resolve()
        self.rules_path: Path = Path(
            os.environ.get("ORGANIZER_RULES_PATH", "config/rules.yaml")
        ).resolve()


settings = Settings()
