from __future__ import annotations

from .config import Neo4jConfig
from .cypher import CONSTRAINT_STATEMENTS, IMPACTED_APPLICATIONS_QUERY, seed_query
from .sample_data import SAMPLE_GRAPH

try:
    from neo4j import GraphDatabase
except ImportError:  # pragma: no cover - handled by CLI/runtime
    GraphDatabase = None


class Neo4jGraphClient:
    def __init__(self, config: Neo4jConfig):
        if GraphDatabase is None:
            raise RuntimeError("The neo4j package is not installed.")
        if not config.is_configured():
            raise RuntimeError("Neo4j environment variables are not fully configured.")
        self._config = config
        self._driver = GraphDatabase.driver(
            config.uri,
            auth=(config.username, config.password),
        )

    def close(self) -> None:
        self._driver.close()

    def seed_sample_graph(self) -> None:
        query, parameters = seed_query(SAMPLE_GRAPH)
        with self._driver.session(database=self._config.database) as session:
            for statement in CONSTRAINT_STATEMENTS:
                session.run(statement).consume()
            session.run(query, parameters).consume()

    def impacted_applications(self, service_name: str) -> list[str]:
        with self._driver.session(database=self._config.database) as session:
            result = session.run(IMPACTED_APPLICATIONS_QUERY, service_name=service_name)
            return [record["application"] for record in result]
