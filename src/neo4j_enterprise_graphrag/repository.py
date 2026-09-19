from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Protocol

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

from .config import Neo4jConfig
from . import cypher
from .models import (
    DependencyPath,
    EnterpriseGraph,
    ImpactRecord,
    RetrievedDocument,
    ServiceOwner,
)

LOGGER = logging.getLogger(__name__)


class RepositoryError(RuntimeError):
    """Raised when graph storage operations fail."""


class EntityNotFoundError(LookupError):
    """Raised when the requested entity does not exist."""


@dataclass(frozen=True)
class TimedResult:
    value: object
    duration_ms: float


class GraphRepository(Protocol):
    def initialize_graph(self, graph: EnterpriseGraph, reset: bool = False) -> float: ...

    def list_services(self) -> list[str]: ...

    def get_direct_dependencies(self, service_name: str) -> TimedResult: ...

    def get_multi_hop_dependencies(self, service_name: str, max_depth: int) -> TimedResult: ...

    def get_impacted_applications(self, service_name: str, max_depth: int) -> TimedResult: ...

    def find_dependency_paths(
        self, source_name: str, target_name: str, max_depth: int, limit: int
    ) -> TimedResult: ...

    def get_service_owners(self, service_name: str) -> TimedResult: ...

    def search_documents(self, tokens: list[str], limit: int) -> TimedResult: ...


class Neo4jGraphRepository:
    def __init__(self, config: Neo4jConfig) -> None:
        self._database = config.database
        self._driver = GraphDatabase.driver(
            config.uri,
            auth=(config.username, config.password),
        )

    def close(self) -> None:
        self._driver.close()

    def initialize_graph(self, graph: EnterpriseGraph, reset: bool = False) -> float:
        payload = graph.to_payload()
        started = time.perf_counter()

        try:
            with self._driver.session(database=self._database) as session:
                for statement in cypher.CREATE_CONSTRAINTS:
                    session.run(statement).consume()
                if reset:
                    session.run(cypher.DELETE_SAMPLE_GRAPH).consume()
                session.run(cypher.UPSERT_SERVICES, services=payload["services"]).consume()
                session.run(
                    cypher.UPSERT_APPLICATIONS,
                    applications=payload["applications"],
                ).consume()
                session.run(cypher.UPSERT_TEAMS, teams=payload["teams"]).consume()
                session.run(cypher.UPSERT_DOCUMENTS, documents=payload["documents"]).consume()
                session.run(
                    cypher.UPSERT_SERVICE_DEPENDENCIES,
                    service_dependencies=payload["service_dependencies"],
                ).consume()
                session.run(
                    cypher.UPSERT_APPLICATION_USAGE,
                    application_usage=payload["application_usage"],
                ).consume()
                session.run(cypher.UPSERT_OWNERSHIPS, ownerships=payload["ownerships"]).consume()
                session.run(
                    cypher.UPSERT_DOCUMENT_LINKS,
                    document_links=payload["document_links"],
                ).consume()
        except Neo4jError as exc:
            raise RepositoryError(f"Failed to initialize sample graph: {exc}") from exc

        return _elapsed_ms(started)

    def list_services(self) -> list[str]:
        records = self._run_query(cypher.LIST_SERVICES)
        return [record["name"] for record in records]

    def get_direct_dependencies(self, service_name: str) -> TimedResult:
        self._ensure_service_exists(service_name)
        started = time.perf_counter()
        records = self._run_query(cypher.DIRECT_DEPENDENCIES, service_name=service_name)
        return TimedResult(
            value=[record["dependency"] for record in records],
            duration_ms=_elapsed_ms(started),
        )

    def get_multi_hop_dependencies(self, service_name: str, max_depth: int) -> TimedResult:
        self._ensure_service_exists(service_name)
        started = time.perf_counter()
        records = self._run_query(
            cypher.MULTI_HOP_DEPENDENCIES,
            service_name=service_name,
            max_depth=max_depth,
        )
        return TimedResult(
            value=[
                {"dependency": record["dependency"], "hops": record["hops"]}
                for record in records
            ],
            duration_ms=_elapsed_ms(started),
        )

    def get_impacted_applications(self, service_name: str, max_depth: int) -> TimedResult:
        self._ensure_service_exists(service_name)
        started = time.perf_counter()
        records = self._run_query(
            cypher.DOWNSTREAM_APPLICATION_IMPACT,
            service_name=service_name,
            max_depth=max_depth,
        )
        impacts = [
            ImpactRecord(
                application=record["application"],
                dependent_service=record["dependent_service"],
                service_path=record["service_path"],
                hops=record["hops"],
            )
            for record in records
        ]
        return TimedResult(value=impacts, duration_ms=_elapsed_ms(started))

    def find_dependency_paths(
        self, source_name: str, target_name: str, max_depth: int, limit: int
    ) -> TimedResult:
        self._ensure_service_exists(source_name)
        self._ensure_service_exists(target_name)
        started = time.perf_counter()
        records = self._run_query(
            cypher.DEPENDENCY_PATH_DISCOVERY,
            source_name=source_name,
            target_name=target_name,
            max_depth=max_depth,
            limit=limit,
        )
        paths = [DependencyPath(path=record["path"], hops=record["hops"]) for record in records]
        return TimedResult(value=paths, duration_ms=_elapsed_ms(started))

    def get_service_owners(self, service_name: str) -> TimedResult:
        self._ensure_service_exists(service_name)
        started = time.perf_counter()
        records = self._run_query(
            cypher.SERVICE_OWNERSHIP_LOOKUP,
            service_name=service_name,
        )
        owners = [
            ServiceOwner(team=record["team"], description=record["description"])
            for record in records
        ]
        return TimedResult(value=owners, duration_ms=_elapsed_ms(started))

    def search_documents(self, tokens: list[str], limit: int) -> TimedResult:
        started = time.perf_counter()
        records = self._run_query(cypher.DOCUMENT_SEARCH, tokens=tokens, limit=limit)
        documents = [
            RetrievedDocument(
                id=record["id"],
                title=record["title"],
                content=record["content"],
                score=record["score"],
                related_services=[item for item in record["related_services"] if item],
            )
            for record in records
        ]
        return TimedResult(value=documents, duration_ms=_elapsed_ms(started))

    def _ensure_service_exists(self, service_name: str) -> None:
        records = self._run_query(cypher.SERVICE_EXISTS, service_name=service_name)
        if not records or not records[0]["exists"]:
            raise EntityNotFoundError(f"Service not found: {service_name}")

    def _run_query(self, statement: str, **parameters: object) -> list[dict]:
        try:
            with self._driver.session(database=self._database) as session:
                result = session.run(statement, **parameters)
                return [record.data() for record in result]
        except Neo4jError as exc:
            raise RepositoryError(f"Neo4j query failed: {exc}") from exc


class InMemoryGraphRepository:
    def __init__(self, graph: EnterpriseGraph) -> None:
        self._graph = graph
        self._service_names = {service.name for service in graph.services}
        self._documents = {document.id: document for document in graph.documents}
        self._document_links = defaultdict(set)
        self._dependencies = defaultdict(set)
        self._reverse_dependencies = defaultdict(set)
        self._application_usage = defaultdict(set)
        self._applications = {}
        self._owners = defaultdict(list)

        for document_link in graph.document_links:
            self._document_links[document_link.document_id].add(document_link.service)
        for dependency in graph.service_dependencies:
            self._dependencies[dependency.source].add(dependency.target)
            self._reverse_dependencies[dependency.target].add(dependency.source)
        for usage in graph.application_usage:
            self._application_usage[usage.service].add(usage.application)
        for application in graph.applications:
            self._applications[application.name] = application
        for owner in graph.ownerships:
            team_description = next(
                team.description for team in graph.teams if team.name == owner.team
            )
            self._owners[owner.service].append(
                ServiceOwner(team=owner.team, description=team_description)
            )

    def initialize_graph(self, graph: EnterpriseGraph, reset: bool = False) -> float:
        return 0.0

    def list_services(self) -> list[str]:
        return sorted(self._service_names)

    def get_direct_dependencies(self, service_name: str) -> TimedResult:
        self._ensure_service_exists(service_name)
        return TimedResult(value=sorted(self._dependencies[service_name]), duration_ms=0.0)

    def get_multi_hop_dependencies(self, service_name: str, max_depth: int) -> TimedResult:
        self._ensure_service_exists(service_name)
        distances = self._walk_dependencies(service_name, max_depth)
        rows = [
            {"dependency": dependency, "hops": hops}
            for dependency, hops in sorted(distances.items(), key=lambda item: (item[1], item[0]))
        ]
        return TimedResult(value=rows, duration_ms=0.0)

    def get_impacted_applications(self, service_name: str, max_depth: int) -> TimedResult:
        self._ensure_service_exists(service_name)
        paths = self._walk_reverse_dependencies(service_name, max_depth)
        impacts: list[ImpactRecord] = []

        for dependent_service, service_path in sorted(paths.items()):
            for application_name in sorted(self._application_usage[dependent_service]):
                application = self._applications[application_name]
                if not application.customer_facing:
                    continue
                impacts.append(
                    ImpactRecord(
                        application=application_name,
                        dependent_service=dependent_service,
                        service_path=service_path,
                        hops=max(len(service_path) - 1, 0),
                    )
                )
        impacts.sort(key=lambda item: (item.application, item.hops, item.dependent_service))
        return TimedResult(value=impacts, duration_ms=0.0)

    def find_dependency_paths(
        self, source_name: str, target_name: str, max_depth: int, limit: int
    ) -> TimedResult:
        self._ensure_service_exists(source_name)
        self._ensure_service_exists(target_name)
        found_paths: list[DependencyPath] = []
        queue: deque[tuple[str, list[str]]] = deque([(source_name, [source_name])])

        while queue and len(found_paths) < limit:
            current, path = queue.popleft()
            if len(path) - 1 > max_depth:
                continue
            if current == target_name and len(path) > 1:
                found_paths.append(DependencyPath(path=path, hops=len(path) - 1))
                continue
            for dependency in sorted(self._dependencies[current]):
                if dependency in path:
                    continue
                queue.append((dependency, [*path, dependency]))

        return TimedResult(value=found_paths, duration_ms=0.0)

    def get_service_owners(self, service_name: str) -> TimedResult:
        self._ensure_service_exists(service_name)
        return TimedResult(value=list(self._owners[service_name]), duration_ms=0.0)

    def search_documents(self, tokens: list[str], limit: int) -> TimedResult:
        normalized_tokens = [token.lower() for token in tokens if token]
        results: list[RetrievedDocument] = []

        for document in self._documents.values():
            haystack = f"{document.title} {document.content}".lower()
            score = sum(1 for token in normalized_tokens if token in haystack)
            if score == 0:
                continue
            results.append(
                RetrievedDocument(
                    id=document.id,
                    title=document.title,
                    content=document.content,
                    score=score,
                    related_services=sorted(self._document_links[document.id]),
                )
            )

        results.sort(key=lambda item: (-item.score, item.title))
        return TimedResult(value=results[:limit], duration_ms=0.0)

    def _walk_dependencies(self, service_name: str, max_depth: int) -> dict[str, int]:
        distances: dict[str, int] = {}
        queue: deque[tuple[str, int]] = deque([(service_name, 0)])

        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for dependency in sorted(self._dependencies[current]):
                next_depth = depth + 1
                existing = distances.get(dependency)
                if existing is not None and existing <= next_depth:
                    continue
                distances[dependency] = next_depth
                queue.append((dependency, next_depth))

        return distances

    def _walk_reverse_dependencies(self, service_name: str, max_depth: int) -> dict[str, list[str]]:
        paths: dict[str, list[str]] = {service_name: [service_name]}
        queue: deque[tuple[str, list[str]]] = deque([(service_name, [service_name])])

        while queue:
            current, path = queue.popleft()
            if len(path) - 1 >= max_depth:
                continue
            for dependent in sorted(self._reverse_dependencies[current]):
                if dependent in path:
                    continue
                next_path = [dependent, *path]
                existing = paths.get(dependent)
                if existing is not None and len(existing) <= len(next_path):
                    continue
                paths[dependent] = next_path
                queue.append((dependent, next_path))

        return paths

    def _ensure_service_exists(self, service_name: str) -> None:
        if service_name not in self._service_names:
            raise EntityNotFoundError(f"Service not found: {service_name}")


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)
