from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
import uuid
from contextlib import closing
from dataclasses import dataclass
from typing import Iterator

import pytest

from neo4j_enterprise_graphrag.config import Neo4jConfig
from neo4j_enterprise_graphrag.models import (
    Application,
    ApplicationUsage,
    Document,
    DocumentLink,
    EnterpriseGraph,
    Ownership,
    Service,
    ServiceDependency,
    Team,
)
from neo4j_enterprise_graphrag.repository import Neo4jGraphRepository
from neo4j_enterprise_graphrag.sample_data import SAMPLE_GRAPH_SOURCE, build_sample_graph
from neo4j_enterprise_graphrag.service import EnterpriseGraphRAGService


pytestmark = pytest.mark.integration


@dataclass(frozen=True)
class IntegrationContext:
    repository: Neo4jGraphRepository
    config: Neo4jConfig


@dataclass(frozen=True)
class ManagedContainer:
    name: str


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(
        ["docker", "info"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


@pytest.fixture(scope="module")
def integration_context() -> Iterator[IntegrationContext]:
    if os.getenv("RUN_NEO4J_INTEGRATION") != "1":
        pytest.skip("Set RUN_NEO4J_INTEGRATION=1 to run Neo4j integration tests.")

    external_context = _external_integration_context()
    if external_context is not None:
        repository, config = external_context
        try:
            yield IntegrationContext(repository=repository, config=config)
        finally:
            repository.close()
        return

    if not _docker_available():
        pytest.skip("Docker is not available for disposable Neo4j integration tests.")

    repository, config, container = _start_disposable_neo4j()
    try:
        yield IntegrationContext(repository=repository, config=config)
    finally:
        repository.close()
        subprocess.run(["docker", "rm", "-f", container.name], check=False)


def _external_integration_context() -> tuple[Neo4jGraphRepository, Neo4jConfig] | None:
    uri = os.getenv("NEO4J_TEST_URI")
    if not uri:
        return None

    config = Neo4jConfig(
        uri,
        os.getenv("NEO4J_TEST_USERNAME", "neo4j"),
        os.getenv("NEO4J_TEST_PASSWORD", "test-password"),
        os.getenv("NEO4J_TEST_DATABASE", "neo4j"),
        os.getenv("NEO4J_TEST_LOG_LEVEL", "INFO"),
        os.getenv("NEO4J_TEST_GRAPH_SOURCE", SAMPLE_GRAPH_SOURCE),
    )
    repository = Neo4jGraphRepository(config)
    _wait_for_connectivity(repository)
    return repository, config


def _start_disposable_neo4j() -> tuple[Neo4jGraphRepository, Neo4jConfig, ManagedContainer]:
    bolt_port = _free_port()
    http_port = _free_port()
    container_name = f"neo4j-graphrag-test-{uuid.uuid4().hex[:8]}"
    password = "test-password"

    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-d",
            "--name",
            container_name,
            "-p",
            f"{bolt_port}:7687",
            "-p",
            f"{http_port}:7474",
            "-e",
            f"NEO4J_AUTH=neo4j/{password}",
            "neo4j:5",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    config = Neo4jConfig(f"bolt://127.0.0.1:{bolt_port}", "neo4j", password, "neo4j")
    repository = Neo4jGraphRepository(config)
    _wait_for_connectivity(repository)
    return repository, config, ManagedContainer(name=container_name)


def _wait_for_connectivity(repository: Neo4jGraphRepository) -> None:
    deadline = time.time() + 90
    while True:
        try:
            repository._driver.verify_connectivity()
            return
        except Exception:
            if time.time() >= deadline:
                raise AssertionError("Timed out waiting for Neo4j integration test database.")
            time.sleep(2)


def test_neo4j_seeding_loads_isolated_sample_graph(
    integration_context: IntegrationContext,
) -> None:
    neo4j_repository = integration_context.repository
    neo4j_repository.initialize_graph(build_sample_graph(), reset=True)
    neo4j_repository.initialize_graph(build_sample_graph(), reset=False)

    services = neo4j_repository.list_services()
    direct_dependencies = neo4j_repository.get_direct_dependencies("Customer API").value

    assert "Customer API" in services
    assert direct_dependencies == [
        "Billing Service",
        "Identity Service",
        "Order Service",
    ]


def test_neo4j_impact_query_returns_dependency_paths(
    integration_context: IntegrationContext,
) -> None:
    neo4j_repository = integration_context.repository
    neo4j_repository.initialize_graph(build_sample_graph(), reset=True)
    service = EnterpriseGraphRAGService(neo4j_repository)

    result = service.get_impacted_applications("Identity Service", max_depth=4)

    assert result["impacted_applications"] == [
        {
            "application": "Customer Web Portal",
            "dependent_service": "Customer API",
            "service_path": ["Customer API", "Identity Service"],
            "dependency_paths": [
                ["Customer API", "Identity Service"],
                ["Customer API", "Billing Service", "Identity Service"],
                [
                    "Customer API",
                    "Order Service",
                    "Notification Service",
                    "Identity Service",
                ],
            ],
            "hops": 1,
        },
        {
            "application": "Mobile App",
            "dependent_service": "Customer API",
            "service_path": ["Customer API", "Identity Service"],
            "dependency_paths": [
                ["Customer API", "Identity Service"],
                ["Customer API", "Billing Service", "Identity Service"],
                [
                    "Customer API",
                    "Order Service",
                    "Notification Service",
                    "Identity Service",
                ],
            ],
            "hops": 1,
        },
        {
            "application": "Mobile App",
            "dependent_service": "Search Service",
            "service_path": ["Search Service", "Identity Service"],
            "dependency_paths": [["Search Service", "Identity Service"]],
            "hops": 1,
        },
        {
            "application": "Partner Dashboard",
            "dependent_service": "Billing Service",
            "service_path": ["Billing Service", "Identity Service"],
            "dependency_paths": [["Billing Service", "Identity Service"]],
            "hops": 1,
        },
    ]

    assert SAMPLE_GRAPH_SOURCE == "neo4j-enterprise-graphrag-sample"


def test_neo4j_graph_source_isolation_hides_other_seeded_datasets(
    integration_context: IntegrationContext,
) -> None:
    neo4j_repository = integration_context.repository
    alternate_repository = Neo4jGraphRepository(
        Neo4jConfig(
            integration_context.config.uri,
            integration_context.config.username,
            integration_context.config.password,
            integration_context.config.database,
            integration_context.config.log_level,
            "alternate-graph-source",
        )
    )
    alternate_graph = EnterpriseGraph(
        services=[
            Service(name="Alternate Service", description="Alt", tier="edge"),
            Service(name="Shared Downstream", description="Downstream", tier="domain"),
        ],
        applications=[
            Application(name="Alternate App", description="Alt app", customer_facing=True),
        ],
        teams=[Team(name="Alternate Team", description="Alt team")],
        documents=[Document(id="alt-doc", title="Alt doc", content="Alt content")],
        service_dependencies=[
            ServiceDependency(source="Alternate Service", target="Shared Downstream"),
        ],
        application_usage=[
            ApplicationUsage(application="Alternate App", service="Alternate Service"),
        ],
        ownerships=[Ownership(team="Alternate Team", service="Alternate Service")],
        document_links=[DocumentLink(document_id="alt-doc", service="Alternate Service")],
    )

    try:
        neo4j_repository.initialize_graph(build_sample_graph(), reset=True)
        alternate_repository.initialize_graph(alternate_graph, reset=True)

        assert "Alternate Service" not in neo4j_repository.list_services()
        assert alternate_repository.list_services() == [
            "Alternate Service",
            "Shared Downstream",
        ]
    finally:
        alternate_repository.close()
