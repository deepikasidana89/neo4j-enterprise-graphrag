from neo4j_enterprise_graphrag.repository import EntityNotFoundError, InMemoryGraphRepository
from neo4j_enterprise_graphrag.sample_data import build_sample_graph
from neo4j_enterprise_graphrag.service import EnterpriseGraphRAGService
from neo4j_enterprise_graphrag.models import EnterpriseGraph, Service, ServiceDependency, Application, ApplicationUsage, Team, Ownership, Document, DocumentLink


def build_service() -> EnterpriseGraphRAGService:
    return EnterpriseGraphRAGService(InMemoryGraphRepository(build_sample_graph()))


def test_direct_dependencies_are_returned() -> None:
    service = build_service()

    result = service.describe_service("Customer API", max_depth=4)

    assert result["direct_dependencies"] == [
        "Billing Service",
        "Identity Service",
        "Order Service",
    ]


def test_multi_hop_dependencies_include_transitive_services() -> None:
    service = build_service()

    result = service.describe_service("Customer API", max_depth=4)

    assert result["multi_hop_dependencies"] == [
        {"dependency": "Billing Service", "hops": 1},
        {"dependency": "Identity Service", "hops": 1},
        {"dependency": "Order Service", "hops": 1},
        {"dependency": "Inventory Service", "hops": 2},
        {"dependency": "Notification Service", "hops": 2},
    ]


def test_missing_services_raise_a_clear_error() -> None:
    service = build_service()

    try:
        service.describe_service("Missing Service", max_depth=2)
    except EntityNotFoundError as exc:
        assert "Service not found" in str(exc)
    else:
        raise AssertionError("Expected EntityNotFoundError")


def test_cyclic_dependencies_do_not_loop_forever() -> None:
    graph = EnterpriseGraph(
        services=[
            Service(name="Service A", description="A", tier="domain"),
            Service(name="Service B", description="B", tier="domain"),
            Service(name="Service C", description="C", tier="domain"),
        ],
        applications=[
            Application(name="Customer App", description="App", customer_facing=True),
        ],
        teams=[Team(name="Core Team", description="Core ownership")],
        documents=[Document(id="doc-1", title="Cycle", content="Service A and Service B")],
        service_dependencies=[
            ServiceDependency(source="Service A", target="Service B"),
            ServiceDependency(source="Service B", target="Service C"),
            ServiceDependency(source="Service C", target="Service A"),
        ],
        application_usage=[ApplicationUsage(application="Customer App", service="Service A")],
        ownerships=[Ownership(team="Core Team", service="Service A")],
        document_links=[DocumentLink(document_id="doc-1", service="Service A")],
    )
    service = EnterpriseGraphRAGService(InMemoryGraphRepository(graph))

    result = service.describe_service("Service A", max_depth=4)

    assert result["multi_hop_dependencies"] == [
        {"dependency": "Service B", "hops": 1},
        {"dependency": "Service C", "hops": 2},
    ]


def test_duplicate_relationships_are_deduplicated() -> None:
    graph = EnterpriseGraph(
        services=[
            Service(name="Service A", description="A", tier="domain"),
            Service(name="Service B", description="B", tier="domain"),
        ],
        applications=[
            Application(name="Customer App", description="App", customer_facing=True),
        ],
        teams=[Team(name="Core Team", description="Core ownership")],
        documents=[Document(id="doc-1", title="Duplicate", content="Service A")],
        service_dependencies=[
            ServiceDependency(source="Service A", target="Service B"),
            ServiceDependency(source="Service A", target="Service B"),
        ],
        application_usage=[
            ApplicationUsage(application="Customer App", service="Service A"),
            ApplicationUsage(application="Customer App", service="Service A"),
        ],
        ownerships=[Ownership(team="Core Team", service="Service A")],
        document_links=[DocumentLink(document_id="doc-1", service="Service A")],
    )
    service = EnterpriseGraphRAGService(InMemoryGraphRepository(graph))

    result = service.describe_service("Service A", max_depth=2)

    assert result["direct_dependencies"] == ["Service B"]
    assert result["impacted_applications"] == [
        {
            "application": "Customer App",
            "dependent_service": "Service A",
            "service_path": ["Service A"],
            "hops": 0,
        }
    ]


def test_application_impact_results_include_upstream_dependents() -> None:
    service = build_service()

    result = service.get_impacted_applications("Identity Service", max_depth=4)

    impacted_pairs = [
        (
            row["application"],
            row["dependent_service"],
            tuple(row["service_path"]),
            row["hops"],
        )
        for row in result["impacted_applications"]
    ]
    assert impacted_pairs == [
        ("Customer Web Portal", "Customer API", ("Customer API", "Identity Service"), 1),
        ("Mobile App", "Customer API", ("Customer API", "Identity Service"), 1),
        ("Mobile App", "Search Service", ("Search Service", "Identity Service"), 1),
        ("Partner Dashboard", "Billing Service", ("Billing Service", "Identity Service"), 1),
    ]


def test_application_impact_includes_zero_hop_direct_usage_paths() -> None:
    service = build_service()

    result = service.get_impacted_applications("Customer API", max_depth=4)

    assert result["impacted_applications"] == [
        {
            "application": "Customer Web Portal",
            "dependent_service": "Customer API",
            "service_path": ["Customer API"],
            "hops": 0,
        },
        {
            "application": "Mobile App",
            "dependent_service": "Customer API",
            "service_path": ["Customer API"],
            "hops": 0,
        },
    ]


def test_retrieve_infers_service_name_from_question() -> None:
    service = build_service()

    result = service.retrieve(
        "Which customer-facing applications are affected if Identity Service fails?",
        max_depth=2,
    )

    assert "Identity Service" in result["matched_services"]
    assert result["documents"]
    assert any(item["service"] == "Identity Service" for item in result["graph_context"])


def test_retrieve_uses_explicit_service_hint_for_graph_expansion() -> None:
    service = build_service()

    result = service.retrieve(
        "Show outage evidence.",
        service_name="Customer API",
        limit=2,
        max_depth=1,
    )

    assert result["matched_services"] == ["Customer API"]
    assert result["graph_context"][0]["service"] == "Customer API"
    assert result["graph_context"][0]["multi_hop_dependencies"] == [
        {"dependency": "Billing Service", "hops": 1},
        {"dependency": "Identity Service", "hops": 1},
        {"dependency": "Order Service", "hops": 1},
    ]
