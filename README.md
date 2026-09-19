# neo4j-enterprise-graphrag

Reference implementation of enterprise GraphRAG with Neo4j for relationship-aware retrieval, service dependency analysis, and evidence-backed impact assessment.

## Project overview

This project demonstrates how a knowledge graph helps answer enterprise questions that require multi-hop reasoning, not just document similarity.

Primary use case:

> Which customer-facing applications could be affected if a service becomes unavailable?

The implementation ships with:

- a synthetic enterprise knowledge graph
- parameterized Neo4j Cypher queries
- a Python CLI for graph initialization and analysis
- a graph-based retrieval demo that works without a paid LLM API
- automated tests for dependency and impact scenarios

## Architecture

```mermaid
flowchart TD
    CLI[Python CLI] --> Service[EnterpriseGraphRAGService]
    Service --> Repo[Neo4jGraphRepository]
    Service --> MemoryRepo[InMemoryGraphRepository for tests]
    Repo --> Neo4j[(Neo4j Database)]
    Service --> Retrieval[Keyword document retrieval + graph traversal]
    Retrieval --> Docs[Document nodes]
    Retrieval --> Graph[Service, Application, Team nodes]
```

## Knowledge graph schema

### Node labels

- `Service` - enterprise services and APIs
- `Application` - consuming applications
- `Team` - owning teams
- `Document` - supporting operational or architecture documents

### Relationships

- `(:Service)-[:DEPENDS_ON]->(:Service)`
- `(:Application)-[:USES_SERVICE]->(:Service)`
- `(:Team)-[:OWNS]->(:Service)`
- `(:Document)-[:DESCRIBES]->(:Service)`

## Repository layout

```text
src/neo4j_enterprise_graphrag/
  cli.py
  config.py
  cypher.py
  models.py
  repository.py
  sample_data.py
  service.py
tests/
  test_service.py
```

## Prerequisites

- Python 3.11+
- A running Neo4j 5.x instance

## Neo4j setup instructions

You can run Neo4j locally with Docker:

```bash
docker run \
  --name neo4j-graphrag \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/please-change-me \
  neo4j:5
```

Set environment variables:

```bash
cp .env.example .env
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USERNAME=neo4j
export NEO4J_PASSWORD=please-change-me
export NEO4J_DATABASE=neo4j
```

## Installation instructions

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Local run instructions

1. Start Neo4j.
2. Set the `NEO4J_*` environment variables.
3. Initialize the sample graph:

   ```bash
   neo4j-graphrag init-graph --reset
   ```

4. Run example queries:

   ```bash
   neo4j-graphrag service --name "Customer API"
   neo4j-graphrag impact --name "Identity Service"
   neo4j-graphrag paths --source "Customer API" --target "Identity Service"
   neo4j-graphrag owners --name "Billing Service"
   neo4j-graphrag retrieve --question "Which customer-facing applications are affected if Identity Service fails?"
   ```

## Example commands

```bash
neo4j-graphrag init-graph --reset
neo4j-graphrag service --name "Customer API" --max-depth 4
neo4j-graphrag impact --name "Identity Service" --max-depth 4
neo4j-graphrag paths --source "Customer API" --target "Notification Service"
neo4j-graphrag retrieve --question "Show documents and graph evidence for Identity Service outage impact."
```

## Example output

```json
{
  "service": "Identity Service",
  "impacted_applications": [
    {
      "application": "Customer Web Portal",
      "dependent_service": "Customer API",
      "service_path": ["Customer API", "Identity Service"],
      "hops": 1
    },
    {
      "application": "Partner Dashboard",
      "dependent_service": "Billing Service",
      "service_path": ["Billing Service", "Identity Service"],
      "hops": 1
    }
  ],
  "duration_ms": 3.2
}
```

## Implemented Cypher queries

- Direct dependencies
- Multi-hop dependencies
- Downstream application impact analysis
- Dependency path discovery
- Service ownership lookup
- Document retrieval with graph expansion

All queries are defined in `src/neo4j_enterprise_graphrag/cypher.py` and executed with parameters.

## GraphRAG vs traditional vector RAG

Traditional vector RAG can retrieve documents that mention a service outage, but it does not naturally explain transitive impact across application and service relationships.

This project demonstrates a graph-first retrieval workflow:

1. retrieve supporting documents by local keyword overlap
2. identify related service nodes
3. traverse the knowledge graph for owners, dependencies, and impacted applications
4. return evidence paths that explain why an application is affected

This makes relationship paths explicit and auditable, which is critical for dependency analysis and operational decision support.

## Reliability and engineering considerations

- Neo4j configuration is provided through environment variables
- all Cypher execution uses parameters
- CLI and service inputs are validated
- missing services return clear errors
- empty query results are returned explicitly instead of failing
- execution timing is returned for query operations
- logging is configurable with `NEO4J_LOG_LEVEL`
- sample graph loading is idempotent because node and relationship creation uses `MERGE`

## Automated tests

Run:

```bash
pytest
```

The tests use the in-memory repository to validate traversal logic without requiring a running Neo4j instance. Neo4j-backed CLI commands still require a live database and could not be verified end-to-end in this agent environment.

## Known limitations

- The CLI does not infer complex entities beyond exact service-name matches in questions.
- The retrieval demo uses keyword overlap rather than embeddings.
- The provided tests validate traversal logic, not a live Neo4j deployment.

## Future enhancements

- optional vector indexing and embedding-based retrieval
- richer natural language entity extraction
- graph visualization output for impact paths
- integration tests against a disposable Neo4j instance

## Security and data hygiene

- The repository uses synthetic enterprise entities only.
- No proprietary company references or credentials are included.
- `.env` files are ignored; use `.env.example` as the template.
