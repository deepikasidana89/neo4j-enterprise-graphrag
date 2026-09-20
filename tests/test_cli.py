import contextlib
import io

from neo4j_enterprise_graphrag import cli
from neo4j_enterprise_graphrag.repository import EntityNotFoundError


class FakeConfig:
    log_level = "INFO"


class FakeRepository:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeService:
    def __init__(self, repository: FakeRepository) -> None:
        self.repository = repository

    def initialize_sample_graph(self, reset: bool = False):
        return {"command": "init-graph", "reset": reset}

    def describe_service(self, name: str, max_depth: int = 4):
        return {"command": "service", "name": name, "max_depth": max_depth}

    def get_impacted_applications(self, name: str, max_depth: int = 4):
        return {"command": "impact", "name": name, "max_depth": max_depth}

    def find_dependency_paths(self, source: str, target: str, max_depth: int = 4, limit: int = 10):
        return {
            "command": "paths",
            "source": source,
            "target": target,
            "max_depth": max_depth,
            "limit": limit,
        }

    def get_service_owners(self, name: str):
        return {"command": "owners", "name": name}

    def retrieve(self, question: str, service_name: str | None = None, limit: int = 3, max_depth: int = 4):
        return {
            "command": "retrieve",
            "question": question,
            "service_name": service_name,
            "limit": limit,
            "max_depth": max_depth,
        }


class ErrorService(FakeService):
    def describe_service(self, name: str, max_depth: int = 4):
        raise EntityNotFoundError(f"Service not found: {name}")


def _run_main(monkeypatch, argv, service_type=FakeService):
    repository = FakeRepository()
    monkeypatch.setattr(cli.Neo4jConfig, "from_env", staticmethod(lambda: FakeConfig()))
    monkeypatch.setattr(cli, "configure_logging", lambda level: None)
    monkeypatch.setattr(cli, "Neo4jGraphRepository", lambda config: repository)
    monkeypatch.setattr(cli, "EnterpriseGraphRAGService", service_type)
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = cli.main(argv)
    return exit_code, stdout.getvalue(), stderr.getvalue(), repository


def test_init_graph_command(monkeypatch) -> None:
    exit_code, stdout, _, repository = _run_main(monkeypatch, ["init-graph", "--reset"])

    assert exit_code == 0
    assert '"command": "init-graph"' in stdout
    assert '"reset": true' in stdout
    assert repository.closed is True


def test_service_command(monkeypatch) -> None:
    exit_code, stdout, _, repository = _run_main(
        monkeypatch,
        ["service", "--name", "Customer API", "--max-depth", "5"],
    )

    assert exit_code == 0
    assert '"command": "service"' in stdout
    assert '"name": "Customer API"' in stdout
    assert '"max_depth": 5' in stdout
    assert repository.closed is True


def test_impact_command(monkeypatch) -> None:
    exit_code, stdout, _, _ = _run_main(
        monkeypatch,
        ["impact", "--name", "Identity Service", "--max-depth", "3"],
    )

    assert exit_code == 0
    assert '"command": "impact"' in stdout
    assert '"name": "Identity Service"' in stdout
    assert '"max_depth": 3' in stdout


def test_paths_command(monkeypatch) -> None:
    exit_code, stdout, _, _ = _run_main(
        monkeypatch,
        [
            "paths",
            "--source",
            "Customer API",
            "--target",
            "Identity Service",
            "--max-depth",
            "4",
            "--limit",
            "7",
        ],
    )

    assert exit_code == 0
    assert '"command": "paths"' in stdout
    assert '"source": "Customer API"' in stdout
    assert '"target": "Identity Service"' in stdout
    assert '"limit": 7' in stdout


def test_owners_command(monkeypatch) -> None:
    exit_code, stdout, _, _ = _run_main(monkeypatch, ["owners", "--name", "Identity Service"])

    assert exit_code == 0
    assert '"command": "owners"' in stdout
    assert '"name": "Identity Service"' in stdout


def test_retrieve_command(monkeypatch) -> None:
    exit_code, stdout, _, _ = _run_main(
        monkeypatch,
        [
            "retrieve",
            "--question",
            "What breaks if Identity Service is down?",
            "--service",
            "Customer API",
            "--limit",
            "2",
            "--max-depth",
            "2",
        ],
    )

    assert exit_code == 0
    assert '"command": "retrieve"' in stdout
    assert '"question": "What breaks if Identity Service is down?"' in stdout
    assert '"service_name": "Customer API"' in stdout
    assert '"limit": 2' in stdout
    assert '"max_depth": 2' in stdout


def test_cli_returns_json_error_payload(monkeypatch) -> None:
    exit_code, _, stderr, repository = _run_main(
        monkeypatch,
        ["service", "--name", "Missing Service"],
        service_type=ErrorService,
    )

    assert exit_code == 1
    assert '"status": "error"' in stderr
    assert '"message": "Service not found: Missing Service"' in stderr
    assert repository.closed is True
