CREATE_CONSTRAINTS = [
    "CREATE CONSTRAINT service_name_unique IF NOT EXISTS FOR (s:Service) REQUIRE s.name IS UNIQUE",
    "CREATE CONSTRAINT application_name_unique IF NOT EXISTS FOR (a:Application) REQUIRE a.name IS UNIQUE",
    "CREATE CONSTRAINT team_name_unique IF NOT EXISTS FOR (t:Team) REQUIRE t.name IS UNIQUE",
    "CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
]

DELETE_SAMPLE_GRAPH = """
MATCH (n)
WHERE any(label IN labels(n) WHERE label IN ['Service', 'Application', 'Team', 'Document'])
DETACH DELETE n
"""

UPSERT_SERVICES = """
UNWIND $services AS service
MERGE (s:Service {name: service.name})
SET s.description = service.description,
    s.tier = service.tier
"""

UPSERT_APPLICATIONS = """
UNWIND $applications AS application
MERGE (a:Application {name: application.name})
SET a.description = application.description,
    a.customer_facing = application.customer_facing
"""

UPSERT_TEAMS = """
UNWIND $teams AS team
MERGE (t:Team {name: team.name})
SET t.description = team.description
"""

UPSERT_DOCUMENTS = """
UNWIND $documents AS document
MERGE (d:Document {id: document.id})
SET d.title = document.title,
    d.content = document.content
"""

UPSERT_SERVICE_DEPENDENCIES = """
UNWIND $service_dependencies AS rel
MATCH (source:Service {name: rel.source})
MATCH (target:Service {name: rel.target})
MERGE (source)-[:DEPENDS_ON]->(target)
"""

UPSERT_APPLICATION_USAGE = """
UNWIND $application_usage AS rel
MATCH (application:Application {name: rel.application})
MATCH (service:Service {name: rel.service})
MERGE (application)-[:USES_SERVICE]->(service)
"""

UPSERT_OWNERSHIPS = """
UNWIND $ownerships AS rel
MATCH (team:Team {name: rel.team})
MATCH (service:Service {name: rel.service})
MERGE (team)-[:OWNS]->(service)
"""

UPSERT_DOCUMENT_LINKS = """
UNWIND $document_links AS rel
MATCH (document:Document {id: rel.document_id})
MATCH (service:Service {name: rel.service})
MERGE (document)-[:DESCRIBES]->(service)
"""

LIST_SERVICES = """
MATCH (service:Service)
RETURN service.name AS name
ORDER BY name
"""

SERVICE_EXISTS = """
MATCH (service:Service {name: $service_name})
RETURN count(service) > 0 AS exists
"""

DIRECT_DEPENDENCIES = """
MATCH (:Service {name: $service_name})-[:DEPENDS_ON]->(dependency:Service)
RETURN dependency.name AS dependency
ORDER BY dependency
"""

MULTI_HOP_DEPENDENCIES = """
MATCH path = (:Service {name: $service_name})-[:DEPENDS_ON*1..6]->(dependency:Service)
WHERE length(path) <= $max_depth
WITH dependency, min(length(path)) AS hops
RETURN dependency.name AS dependency, hops
ORDER BY hops, dependency
"""

DOWNSTREAM_APPLICATION_IMPACT = """
MATCH path = (:Service {name: $service_name})<-[:DEPENDS_ON*0..6]-(dependent:Service)
WHERE length(path) <= $max_depth
MATCH (application:Application)-[:USES_SERVICE]->(dependent)
WHERE application.customer_facing = true
RETURN DISTINCT
  application.name AS application,
  dependent.name AS dependent_service,
  [node IN nodes(path) | node.name] AS service_path,
  length(path) AS hops
ORDER BY application, hops, dependent_service
"""

DEPENDENCY_PATH_DISCOVERY = """
MATCH path = (:Service {name: $source_name})-[:DEPENDS_ON*1..6]->(:Service {name: $target_name})
WHERE length(path) <= $max_depth
RETURN [node IN nodes(path) | node.name] AS path, length(path) AS hops
ORDER BY hops
LIMIT $limit
"""

SERVICE_OWNERSHIP_LOOKUP = """
MATCH (team:Team)-[:OWNS]->(:Service {name: $service_name})
RETURN team.name AS team, team.description AS description
ORDER BY team
"""

DOCUMENT_SEARCH = """
MATCH (document:Document)
WITH document, [
  token IN $tokens
  WHERE token <> '' AND toLower(document.title + ' ' + document.content) CONTAINS token
] AS matches
WITH document, matches, size(matches) AS score
WHERE score > 0
OPTIONAL MATCH (document)-[:DESCRIBES]->(service:Service)
RETURN
  document.id AS id,
  document.title AS title,
  document.content AS content,
  score,
  collect(DISTINCT service.name) AS related_services
ORDER BY score DESC, title ASC
LIMIT $limit
"""
