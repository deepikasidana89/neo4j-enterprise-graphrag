from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
import uuid
from contextlib import closing

import pytest

from neo4j_enterprise_graphrag.config import Neo4jConfig
from neo4j_enterprise_graphrag.repository import Neo4jGraphRepository
from neo4j_enterprise_graphrag.sample_data import SAMPLE_GRAPH_SOURCE, build_sample_graph
from neo4j_enterprise_graphrag.service import EnterpriseGraphRAGService


pytestmark = pytest.mark.integration


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
def neo4j_repository() -> Neo4jGraphRepository:
    if os.getenv("RUN_NEO4J_INTEGRATION") != "1":
        pytest.skip("Set RUN_NEO4J_INTEGRATION=1 to run disposable Neo4j integration tests.")
    if not _docker_available():
        pytest.skip("Docker is not available for disposable Neo4j integration tests.")

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

    repository = Neo4jGraphRepository(
        Neo4jConfig(f"bolt://127.0.0.1:{bolt_port}", "neo4j", password, "neo4j")
    )

    deadline = time.time() + 90
    while True:
        try:
            repository._driver.verify_connectivity()
            break
        except Exception:
            if time.time() >= deadline:
                repository.close()
                subprocess.run(["docker", "rm", "-f", container_name], check=False)
                pytest.fail("Timed out waiting for disposable Neo4j test container.")
            time.sleep(2)

    try:
        yield repository
    finally:
        repository.close()
        subprocess.run(["docker", "rm", "-f", container_name], check=False)


def test_neo4j_seeding_loads_isolated_sample_graph(neo4j_repository: Neo4jGraphRepository) -> None:
    neo4j_repository.initialize_graph(build_sample_graph(), reset=True)

    services = neo4j_repository.list_services()
    direct_dependencies = neo4j_repository.get_direct_dependencies("Customer API").value

    assert "Customer API" in services
    assert direct_dependencies == [
        "Billing Service",
        "Identity Service",
        "Order Service",
    ]


def test_neo4j_impact_query_returns_dependency_paths(
    neo4j_repository: Neo4jGraphRepository,
) -> None:
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

    cleanup_result = neo4j_repository._run_query(
        """
        MATCH (n {graph_source: $graph_source})
        RETURN count(n) AS nodes
        """,
    )
    assert cleanup_result[0]["nodes"] > 0
    assert SAMPLE_GRAPH_SOURCE == "neo4j-enterprise-graphrag-sample"
