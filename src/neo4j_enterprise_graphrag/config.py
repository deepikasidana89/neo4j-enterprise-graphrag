from __future__ import annotations

import logging
import os
from dataclasses import dataclass


class ConfigurationError(ValueError):
    """Raised when required runtime configuration is missing."""


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str
    username: str
    password: str
    database: str = "neo4j"
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Neo4jConfig":
        uri = os.getenv("NEO4J_URI", "").strip()
        username = os.getenv("NEO4J_USERNAME", "").strip()
        password = os.getenv("NEO4J_PASSWORD", "").strip()
        database = os.getenv("NEO4J_DATABASE", "neo4j").strip() or "neo4j"
        log_level = os.getenv("NEO4J_LOG_LEVEL", "INFO").strip() or "INFO"

        missing = [
            name
            for name, value in {
                "NEO4J_URI": uri,
                "NEO4J_USERNAME": username,
                "NEO4J_PASSWORD": password,
            }.items()
            if not value
        ]
        if missing:
            raise ConfigurationError(
                f"Missing required Neo4j environment variables: {', '.join(missing)}"
            )

        return cls(uri, username, password, database, log_level.upper())


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
