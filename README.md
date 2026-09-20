# neo4j-enterprise-graphrag

Educational enterprise GraphRAG reference implementations built with Python and Neo4j. The repository models teams, applications, services, and supporting documents in a synthetic knowledge graph so you can explore multi-hop dependency analysis and relationship-aware retrieval without proprietary data or a paid LLM API.

## What is included

This repository currently contains two complementary educational implementations:

- `src/enterprise_graphrag`: a minimal, beginner-friendly CLI that can answer impact questions in memory and optionally query Neo4j
- `src/neo4j_enterprise_graphrag`: a richer Neo4j-focused service and CLI with graph initialization, dependency traversal, ownership lookup, and retrieval demos
- Sample synthetic enterprise graph data
- Reusable Cypher queries for multi-hop dependency analysis
- Unit tests plus optional Docker-backed Neo4j integration tests

## Repository layout

```text
.
├── .env.example
├── pyproject.toml
├── src/enterprise_graphrag
│   ├── analysis.py
│   ├── cli.py
│   ├── config.py
│   ├── cypher.py
│   ├── models.py
│   ├── neo4j_client.py
│   └── sample_data.py
├── src/neo4j_enterprise_graphrag
│   ├── cli.py
│   ├── config.py
│   ├── cypher.py
│   ├── models.py
│   ├── repository.py
│   ├── sample_data.py
│   └── service.py
└── tests
```

## Knowledge graph concepts

Across the two examples, the synthetic graph uses these core node types:

- `Team`
- `Application`
- `Service`
- `Document`

And these relationship types:

- `(:Application)-[:DEPENDS_ON]->(:Service)` in the minimal implementation
- `(:Application)-[:USES_SERVICE]->(:Service)` in the richer Neo4j implementation
- `(:Service)-[:DEPENDS_ON]->(:Service)`
- `(:Team)-[:OWNS]->(:Application|:Service)`
- `(:Document)-[:DESCRIBES]->(:Service)`

Representative questions include:

- Which applications are impacted if `Identity Service` fails?
- Which services depend on `Billing Service` within three hops?
- Which teams own the services in a dependency path?
- Which documents provide supporting evidence for a retrieval answer?

## Prerequisites

- Python 3.11+
- Optional: a running Neo4j instance for live graph loading and queries
- Optional: Docker for disposable integration tests

## Setup

### 1. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install the project

```bash
pip install -e .
pip install -e .[dev]
```

### 3. Optional: configure Neo4j

Copy the sample environment file and update it for your local Neo4j instance:

```bash
cp .env.example .env
set -a
source .env
set +a
```

Environment variables used by the Neo4j-backed examples:

- `NEO4J_URI`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`
- `NEO4J_DATABASE` (defaults to `neo4j`)
- `NEO4J_LOG_LEVEL` (used by `neo4j_enterprise_graphrag`)
- `NEO4J_GRAPH_SOURCE` (used to isolate seeded sample graphs in Neo4j)

> The minimal `enterprise_graphrag` demo works without Neo4j because it can analyze the bundled synthetic graph in memory.

### 4. Optional: run Neo4j locally with Docker

```bash
docker run \
  --name neo4j-graphrag \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/please-change-me \
  neo4j:5
```

## CLI usage

### Minimal beginner-friendly CLI

Analyze impact in memory:

```bash
python -m enterprise_graphrag impacted-apps --service "Identity Service"
```

Ask a supported natural-language-style question:

```bash
python -m enterprise_graphrag ask "Which applications are impacted if Notification Service fails?"
```

Load the synthetic graph into Neo4j:

```bash
python -m enterprise_graphrag seed-neo4j
```

Show the bundled Cypher queries:

```bash
python -m enterprise_graphrag show-cypher
```

### Rich Neo4j-oriented CLI

Initialize the graph:

```bash
python -m neo4j_enterprise_graphrag init-graph --reset
```

Inspect service dependencies:

```bash
python -m neo4j_enterprise_graphrag service --name "Customer API" --max-depth 4
```

Find impacted applications:

```bash
python -m neo4j_enterprise_graphrag impact --name "Identity Service" --max-depth 4
```

Run the retrieval demo:

```bash
python -m neo4j_enterprise_graphrag retrieve --question "What breaks if Identity Service is down?"
```

## Key Cypher query

One core impact-analysis query follows dependency paths of any length:

```cypher
MATCH (failed:Service {name: $service_name})
MATCH path = (application:Application)-[:DEPENDS_ON*1..]->(failed)
RETURN DISTINCT application.name AS application, length(path) AS hops
ORDER BY hops, application
```

## Testing

Run the minimal implementation's unit tests with the standard library:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Run the pytest-based suite for the richer implementation:

```bash
pytest
```

Run optional disposable Neo4j integration tests:

```bash
RUN_NEO4J_INTEGRATION=1 pytest -m integration
```

## Educational goals

This repository is intentionally modular so contributors can extend it with:

- More Cypher templates for service impact analysis
- Additional node types such as databases, APIs, or business capabilities
- Retrieval strategies that combine graph context with local or open-source language models
- UI, notebook, or tutorial walkthroughs for GraphRAG experimentation
