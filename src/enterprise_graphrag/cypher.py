from __future__ import annotations

from .models import GraphDataset

CONSTRAINT_STATEMENTS = (
    "CREATE CONSTRAINT team_name IF NOT EXISTS FOR (t:Team) REQUIRE t.name IS UNIQUE",
    "CREATE CONSTRAINT application_name IF NOT EXISTS FOR (a:Application) REQUIRE a.name IS UNIQUE",
    "CREATE CONSTRAINT service_name IF NOT EXISTS FOR (s:Service) REQUIRE s.name IS UNIQUE",
)

IMPACTED_APPLICATIONS_QUERY = """
MATCH (failed:Service {name: $service_name})
MATCH path = (application:Application)-[:DEPENDS_ON*1..]->(failed)
RETURN DISTINCT application.name AS application, length(path) AS hops
ORDER BY hops, application
""".strip()

DEPENDENCY_PATHS_QUERY = """
MATCH (failed:Service {name: $service_name})
MATCH path = (impacted)-[:DEPENDS_ON*1..]->(failed)
RETURN
  labels(impacted)[0] AS impacted_type,
  impacted.name AS impacted_name,
  [node IN nodes(path) | node.name] AS dependency_chain,
  length(path) AS hops
ORDER BY hops, impacted_name
""".strip()


def seed_query(dataset: GraphDataset) -> tuple[str, dict[str, list[dict[str, object]]]]:
    query = """
    UNWIND [node IN $nodes WHERE node.label = 'Team'] AS node
    MERGE (n:Team {name: node.name})
    SET n += node.properties
    WITH collect(n) AS _
    UNWIND [node IN $nodes WHERE node.label = 'Application'] AS node
    MERGE (n:Application {name: node.name})
    SET n += node.properties
    WITH collect(n) AS _
    UNWIND [node IN $nodes WHERE node.label = 'Service'] AS node
    MERGE (n:Service {name: node.name})
    SET n += node.properties
    WITH collect(n) AS _
    UNWIND [rel IN $relationships WHERE rel.start_label = 'Application' AND rel.end_label = 'Service'] AS rel
    MATCH (a:Application {name: rel.start_name}), (b:Service {name: rel.end_name})
    MERGE (a)-[:DEPENDS_ON]->(b)
    WITH count(*) AS _
    UNWIND [rel IN $relationships WHERE rel.start_label = 'Service' AND rel.end_label = 'Service'] AS rel
    MATCH (a:Service {name: rel.start_name}), (b:Service {name: rel.end_name})
    MERGE (a)-[:DEPENDS_ON]->(b)
    WITH count(*) AS _
    UNWIND [rel IN $relationships WHERE rel.start_label = 'Team' AND rel.end_label = 'Application'] AS rel
    MATCH (a:Team {name: rel.start_name}), (b:Application {name: rel.end_name})
    MERGE (a)-[:OWNS]->(b)
    WITH count(*) AS _
    UNWIND [rel IN $relationships WHERE rel.start_label = 'Team' AND rel.end_label = 'Service'] AS rel
    MATCH (a:Team {name: rel.start_name}), (b:Service {name: rel.end_name})
    MERGE (a)-[:OWNS]->(b)
    RETURN count(*) AS relationships_loaded
    """.strip()
    parameters = {
        "nodes": [
            {"label": node.label, "name": node.name, "properties": node.properties}
            for node in dataset.nodes
        ],
        "relationships": [
            {
                "start_label": rel.start_label,
                "start_name": rel.start_name,
                "rel_type": rel.rel_type,
                "end_label": rel.end_label,
                "end_name": rel.end_name,
            }
            for rel in dataset.relationships
        ],
    }
    return query, parameters
