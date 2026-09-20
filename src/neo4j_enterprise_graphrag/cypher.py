CREATE_CONSTRAINTS = [
    "CREATE CONSTRAINT service_identity_unique IF NOT EXISTS FOR (s:Service) REQUIRE (s.graph_source, s.name) IS UNIQUE",
    "CREATE CONSTRAINT application_identity_unique IF NOT EXISTS FOR (a:Application) REQUIRE (a.graph_source, a.name) IS UNIQUE",
    "CREATE CONSTRAINT team_identity_unique IF NOT EXISTS FOR (t:Team) REQUIRE (t.graph_source, t.name) IS UNIQUE",
    "CREATE CONSTRAINT document_identity_unique IF NOT EXISTS FOR (d:Document) REQUIRE (d.graph_source, d.id) IS UNIQUE",
]

DELETE_SAMPLE_GRAPH = """
MATCH (n {graph_source: $graph_source})
WHERE any(label IN labels(n) WHERE label IN ['Service', 'Application', 'Team', 'Document'])
DETACH DELETE n
"""

UPSERT_SERVICES = """
UNWIND $services AS service
MERGE (s:Service {graph_source: $graph_source, name: service.name})
SET s.description = service.description,
    s.tier = service.tier
"""

UPSERT_APPLICATIONS = """
UNWIND $applications AS application
MERGE (a:Application {graph_source: $graph_source, name: application.name})
SET a.description = application.description,
    a.customer_facing = application.customer_facing
"""

UPSERT_TEAMS = """
UNWIND $teams AS team
MERGE (t:Team {graph_source: $graph_source, name: team.name})
SET t.description = team.description
"""

UPSERT_DOCUMENTS = """
UNWIND $documents AS document
MERGE (d:Document {graph_source: $graph_source, id: document.id})
SET d.title = document.title,
    d.content = document.content
"""

UPSERT_SERVICE_DEPENDENCIES = """
UNWIND $service_dependencies AS rel
MATCH (source:Service {name: rel.source, graph_source: $graph_source})
MATCH (target:Service {name: rel.target, graph_source: $graph_source})
MERGE (source)-[:DEPENDS_ON {graph_source: $graph_source}]->(target)
"""

UPSERT_APPLICATION_USAGE = """
UNWIND $application_usage AS rel
MATCH (application:Application {name: rel.application, graph_source: $graph_source})
MATCH (service:Service {name: rel.service, graph_source: $graph_source})
MERGE (application)-[:USES_SERVICE {graph_source: $graph_source}]->(service)
"""

UPSERT_OWNERSHIPS = """
UNWIND $ownerships AS rel
MATCH (team:Team {name: rel.team, graph_source: $graph_source})
MATCH (service:Service {name: rel.service, graph_source: $graph_source})
MERGE (team)-[:OWNS {graph_source: $graph_source}]->(service)
"""

UPSERT_DOCUMENT_LINKS = """
UNWIND $document_links AS rel
MATCH (document:Document {id: rel.document_id, graph_source: $graph_source})
MATCH (service:Service {name: rel.service, graph_source: $graph_source})
MERGE (document)-[:DESCRIBES {graph_source: $graph_source}]->(service)
"""

LIST_SERVICES = """
MATCH (service:Service {graph_source: $graph_source})
RETURN service.name AS name
ORDER BY name
"""

SERVICE_EXISTS = """
MATCH (service:Service {name: $service_name, graph_source: $graph_source})
RETURN count(service) > 0 AS exists
"""

DIRECT_DEPENDENCIES = """
MATCH (:Service {name: $service_name, graph_source: $graph_source})-[:DEPENDS_ON {graph_source: $graph_source}]->(dependency:Service {graph_source: $graph_source})
RETURN dependency.name AS dependency
ORDER BY dependency
"""

MULTI_HOP_DEPENDENCIES = """
MATCH path = (:Service {name: $service_name, graph_source: $graph_source})-[:DEPENDS_ON*1..MAX_DEPTH]->(dependency:Service {graph_source: $graph_source})
WHERE dependency.name <> $service_name
  AND all(rel IN relationships(path) WHERE rel.graph_source = $graph_source)
WITH dependency, min(length(path)) AS hops
RETURN dependency.name AS dependency, hops
ORDER BY hops, dependency
"""

DOWNSTREAM_APPLICATION_IMPACT = """
MATCH path = (:Service {name: $service_name, graph_source: $graph_source})<-[:DEPENDS_ON*0..MAX_DEPTH]-(dependent:Service {graph_source: $graph_source})
MATCH (application:Application {graph_source: $graph_source})-[:USES_SERVICE {graph_source: $graph_source}]->(dependent)
WHERE application.customer_facing = true
  AND all(rel IN relationships(path) WHERE rel.graph_source = $graph_source)
WITH application, dependent, collect(DISTINCT reverse([node IN nodes(path) | node.name])) AS raw_paths
UNWIND raw_paths AS service_path
WITH application, dependent, service_path
ORDER BY size(service_path), service_path
WITH application, dependent, collect(service_path) AS dependency_paths
RETURN
  application.name AS application,
  dependent.name AS dependent_service,
  dependency_paths[0] AS service_path,
  dependency_paths AS dependency_paths,
  size(dependency_paths[0]) - 1 AS hops
ORDER BY application, hops, dependent_service
"""
DEPENDENCY_PATH_DISCOVERY = """
MATCH path = (:Service {name: $source_name, graph_source: $graph_source})-[:DEPENDS_ON*1..MAX_DEPTH]->(:Service {name: $target_name, graph_source: $graph_source})
WHERE all(rel IN relationships(path) WHERE rel.graph_source = $graph_source)
RETURN [node IN nodes(path) | node.name] AS path, length(path) AS hops
ORDER BY hops
LIMIT $limit
"""

SERVICE_OWNERSHIP_LOOKUP = """
MATCH (team:Team {graph_source: $graph_source})-[:OWNS {graph_source: $graph_source}]->(:Service {name: $service_name, graph_source: $graph_source})
RETURN team.name AS team, team.description AS description
ORDER BY team
"""

DOCUMENT_SEARCH = """
MATCH (document:Document {graph_source: $graph_source})
WITH document, [
  token IN $tokens
  WHERE token <> '' AND toLower(document.title + ' ' + document.content) CONTAINS token
] AS matches
WITH document, matches, size(matches) AS score
WHERE score > 0
OPTIONAL MATCH (document)-[:DESCRIBES {graph_source: $graph_source}]->(service:Service {graph_source: $graph_source})
RETURN
  document.id AS id,
  document.title AS title,
  document.content AS content,
  score,
  collect(DISTINCT service.name) AS related_services
ORDER BY score DESC, title ASC
LIMIT $limit
"""


def render_bounded_query(template: str, max_depth: int) -> str:
    if max_depth < 1 or max_depth > 6:
        raise ValueError("max_depth must be between 1 and 6.")
    return template.replace("MAX_DEPTH", str(max_depth))
