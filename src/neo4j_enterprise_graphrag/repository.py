from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Protocol

from neo4j import GraphDatabase
from neo4j.exceptions import DriverError, Neo4jError

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
        self._graph_source = config.graph_source
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
                self._ensure_constraints(session)
            with self._driver.session(database=self._database) as session:
                session.execute_write(
                    self._initialize_graph_tx,
                    payload,
                    reset,
                    self._graph_source,
                )
        except (Neo4jError, DriverError) as exc:
            raise RepositoryError(f"Failed to initialize sample graph: {exc}") from exc

        return _elapsed_ms(started)

    def list_services(self) -> list[str]:
        records = self._run_query(cypher.LIST_SERVICES)
        return [record["name"] for record in records]

    def get_direct_dependencies(self, service_name: str) -> TimedResult:
        started = time.perf_counter()
        records = self._run_query(cypher.DIRECT_DEPENDENCIES, service_name=service_name)
        self._ensure_service_exists_on_empty(service_name, records)
        return TimedResult(
            value=[record["dependency"] for record in records],
            duration_ms=_elapsed_ms(started),
        )

    def get_multi_hop_dependencies(self, service_name: str, max_depth: int) -> TimedResult:
        started = time.perf_counter()
        records = self._run_query(
            cypher.render_bounded_query(cypher.MULTI_HOP_DEPENDENCIES, max_depth),
            service_name=service_name,
        )
        self._ensure_service_exists_on_empty(service_name, records)
        return TimedResult(
            value=[
                {"dependency": record["dependency"], "hops": record["hops"]}
                for record in records
            ],
            duration_ms=_elapsed_ms(started),
        )

    def get_impacted_applications(self, service_name: str, max_depth: int) -> TimedResult:
        started = time.perf_counter()
        records = self._run_query(
            cypher.render_bounded_query(cypher.DOWNSTREAM_APPLICATION_IMPACT, max_depth),
            service_name=service_name,
        )
        self._ensure_service_exists_on_empty(service_name, records)
        impacts = [
            ImpactRecord(
                application=record["application"],
                dependent_service=record["dependent_service"],
                service_path=record["service_path"],
                dependency_paths=record["dependency_paths"],
                hops=record["hops"],
            )
            for record in records
        ]
        return TimedResult(value=impacts, duration_ms=_elapsed_ms(started))

    def find_dependency_paths(
        self, source_name: str, target_name: str, max_depth: int, limit: int
    ) -> TimedResult:
        started = time.perf_counter()
        records = self._run_query(
            cypher.render_bounded_query(cypher.DEPENDENCY_PATH_DISCOVERY, max_depth),
            source_name=source_name,
            target_name=target_name,
            limit=limit,
        )
        if not records:
            self._ensure_service_exists(source_name)
            self._ensure_service_exists(target_name)
        paths = [DependencyPath(path=record["path"], hops=record["hops"]) for record in records]
        return TimedResult(value=paths, duration_ms=_elapsed_ms(started))

    def get_service_owners(self, service_name: str) -> TimedResult:
        started = time.perf_counter()
        records = self._run_query(
            cypher.SERVICE_OWNERSHIP_LOOKUP,
            service_name=service_name,
        )
        self._ensure_service_exists_on_empty(service_name, records)
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

    def _ensure_service_exists_on_empty(
        self, service_name: str, records: list[dict]
    ) -> None:
        if not records:
            self._ensure_service_exists(service_name)

    def _run_query(self, statement: str, **parameters: object) -> list[dict]:
        try:
            with self._driver.session(database=self._database) as session:
                result = session.run(
                    statement,
                    graph_source=self._graph_source,
                    **parameters,
                )
                return [record.data() for record in result]
        except (Neo4jError, DriverError) as exc:
            raise RepositoryError(f"Neo4j query failed: {exc}") from exc

    def _initialize_graph_tx(
        self,
        tx,
        payload: dict[str, list[dict]],
        reset: bool,
        graph_source: str,
    ) -> None:
        # Relationship batches depend on the node batches having completed first.
        # Keep these operations in node-then-relationship order inside one write
        # transaction so seeding remains deterministic and recoverable.
        if reset:
            tx.run(
                cypher.DELETE_SAMPLE_GRAPH,
                graph_source=graph_source,
            ).consume()
        self._execute_seed_operations(
            tx,
            payload,
            graph_source,
            operations=(
                ("services", cypher.UPSERT_SERVICES),
                ("applications", cypher.UPSERT_APPLICATIONS),
                ("teams", cypher.UPSERT_TEAMS),
                ("documents", cypher.UPSERT_DOCUMENTS),
            ),
        )
        self._execute_seed_operations(
            tx,
            payload,
            graph_source,
            operations=(
                ("service_dependencies", cypher.UPSERT_SERVICE_DEPENDENCIES),
                ("application_usage", cypher.UPSERT_APPLICATION_USAGE),
                ("ownerships", cypher.UPSERT_OWNERSHIPS),
                ("document_links", cypher.UPSERT_DOCUMENT_LINKS),
            ),
        )

    def _execute_seed_operations(
        self,
        tx,
        payload: dict[str, list[dict]],
        graph_source: str,
        operations: tuple[tuple[str, str], ...],
    ) -> None:
        for parameter_name, statement in operations:
            values = payload[parameter_name]
            if not values:
                LOGGER.info("Skipping empty seed batch for %s", parameter_name)
                continue
            tx.run(
                statement,
                graph_source=graph_source,
                **{parameter_name: values},
            ).consume()

    def _ensure_constraints(self, session) -> None:
        for statement in cypher.CREATE_CONSTRAINTS:
            session.run(statement).consume()


class InMemoryGraphRepository:
    def __init__(self, graph: EnterpriseGraph) -> None:
        self._load_graph(graph)

    def initialize_graph(self, graph: EnterpriseGraph, reset: bool = False) -> float:
        del reset
        self._load_graph(graph)
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

        for dependent_service, dependency_paths in sorted(paths.items()):
            ordered_paths = sorted(
                (list(path) for path in dependency_paths),
                key=lambda path: (len(path), path),
            )
            service_path = ordered_paths[0]
            for application_name in sorted(self._application_usage[dependent_service]):
                application = self._applications[application_name]
                if not application.customer_facing:
                    continue
                impacts.append(
                    ImpactRecord(
                        application=application_name,
                        dependent_service=dependent_service,
                        service_path=service_path,
                        dependency_paths=ordered_paths,
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
        queue: deque[tuple[str, list[str], set[str]]] = deque(
            [(source_name, [source_name], {source_name})]
        )

        while queue and len(found_paths) < limit:
            current, path, visited = queue.popleft()
            if len(path) - 1 > max_depth:
                continue
            if current == target_name and len(path) > 1:
                found_paths.append(DependencyPath(path=path, hops=len(path) - 1))
                continue
            for dependency in sorted(self._dependencies[current]):
                if dependency in visited:
                    continue
                queue.append((dependency, [*path, dependency], visited | {dependency}))

        return TimedResult(value=found_paths, duration_ms=0.0)

    def get_service_owners(self, service_name: str) -> TimedResult:
        self._ensure_service_exists(service_name)
        return TimedResult(
            value=sorted(self._owners[service_name], key=lambda owner: owner.team),
            duration_ms=0.0,
        )

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
                if dependency == service_name:
                    continue
                existing = distances.get(dependency)
                if existing is not None and existing <= next_depth:
                    continue
                distances[dependency] = next_depth
                queue.append((dependency, next_depth))

        return distances

    def _walk_reverse_dependencies(self, service_name: str, max_depth: int) -> dict[str, set[tuple[str, ...]]]:
        paths: dict[str, set[tuple[str, ...]]] = {service_name: {(service_name,)}}
        queue: deque[tuple[str, list[str], set[str]]] = deque(
            [(service_name, [service_name], {service_name})]
        )

        while queue:
            current, path, visited = queue.popleft()
            if len(path) - 1 >= max_depth:
                continue
            for dependent in sorted(self._reverse_dependencies[current]):
                if dependent in visited:
                    continue
                next_path = [dependent, *path]
                paths.setdefault(dependent, set()).add(tuple(next_path))
                queue.append((dependent, next_path, visited | {dependent}))

        return paths

    def _ensure_service_exists(self, service_name: str) -> None:
        if service_name not in self._service_names:
            raise EntityNotFoundError(f"Service not found: {service_name}")

    def _load_graph(self, graph: EnterpriseGraph) -> None:
        self._graph = graph
        self._service_names = {service.name for service in graph.services}
        self._documents = {document.id: document for document in graph.documents}
        self._document_links = defaultdict(set)
        self._dependencies = defaultdict(set)
        self._reverse_dependencies = defaultdict(set)
        self._application_usage = defaultdict(set)
        self._applications = {}
        self._owners = defaultdict(list)

        team_descriptions = {team.name: team.description for team in graph.teams}
        application_names = {application.name for application in graph.applications}
        document_ids = {document.id for document in graph.documents}

        for document_link in graph.document_links:
            if document_link.document_id not in document_ids:
                raise RepositoryError(
                    f"Unknown document in document link mapping: {document_link.document_id}"
                )
            if document_link.service not in self._service_names:
                raise RepositoryError(
                    f"Unknown service in document link mapping: {document_link.service}"
                )
            self._document_links[document_link.document_id].add(document_link.service)
        for dependency in graph.service_dependencies:
            if dependency.source not in self._service_names:
                raise RepositoryError(
                    f"Unknown dependency source service: {dependency.source}"
                )
            if dependency.target not in self._service_names:
                raise RepositoryError(
                    f"Unknown dependency target service: {dependency.target}"
                )
            self._dependencies[dependency.source].add(dependency.target)
            self._reverse_dependencies[dependency.target].add(dependency.source)
        for usage in graph.application_usage:
            if usage.application not in application_names:
                raise RepositoryError(
                    f"Unknown application in usage mapping: {usage.application}"
                )
            if usage.service not in self._service_names:
                raise RepositoryError(
                    f"Unknown service in usage mapping: {usage.service}"
                )
            self._application_usage[usage.service].add(usage.application)
        for application in graph.applications:
            self._applications[application.name] = application
        for owner in graph.ownerships:
            if owner.team not in team_descriptions:
                raise RepositoryError(f"Unknown team in ownership mapping: {owner.team}")
            if owner.service not in self._service_names:
                raise RepositoryError(f"Unknown service in ownership mapping: {owner.service}")
            self._owners[owner.service].append(
                ServiceOwner(team=owner.team, description=team_descriptions[owner.team])
            )


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)
