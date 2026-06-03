"""Server settings for the AlphaMind workbench API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_USER_ID = "default_user"
DEFAULT_WORKSPACE_ID = "default_workspace"


@dataclass(frozen=True)
class ServerSettings:
    database_path: Path
    cors_origins: tuple[str, ...]


def get_settings() -> ServerSettings:
    db_path = Path(
        os.getenv(
            "ALPHAMIND_DB_PATH",
            str(Path.home() / ".alphamind" / "alphamind.sqlite3"),
        )
    )
    origins = os.getenv("ALPHAMIND_CORS_ORIGINS", "http://localhost:5173")
    return ServerSettings(
        database_path=db_path,
        cors_origins=tuple(origin.strip() for origin in origins.split(",") if origin.strip()),
    )
