# neo4j-enterprise-graphrag

A beginner-friendly enterprise GraphRAG reference implementation built with Python and Neo4j. It models teams, applications, services, and their dependencies in a small synthetic knowledge graph so you can explore multi-hop impact analysis without needing proprietary data or a paid LLM API.

## What is included

- Synthetic enterprise graph data for teams, applications, and services
- Reusable Cypher queries for multi-hop dependency analysis
- A Python CLI for natural-language-style dependency questions
- Optional Neo4j loading and querying through the official Python driver
- Focused unit tests using the standard library

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
└── tests
```

## Data model

The sample graph uses three node types:

- `Team`
- `Application`
- `Service`

And two relationship types:

- `(:Application)-[:DEPENDS_ON]->(:Service)`
- `(:Service)-[:DEPENDS_ON]->(:Service)`
- `(:Team)-[:OWNS]->(:Application|:Service)`

This lets you answer questions such as:

- Which applications are impacted if `Identity Service` fails?
- Which dependency paths connect an application to a shared platform service?
- Which teams own the applications and services in a dependency chain?

## Setup

### 1. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install the project

```bash
pip install -e .
```

### 3. Optional: configure Neo4j

Copy the sample environment file and update it for your local Neo4j instance:

```bash
cp .env.example .env
```

Environment variables used by the CLI:

- `NEO4J_URI`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`
- `NEO4J_DATABASE` (defaults to `neo4j`)

> The basic demo works without Neo4j because the CLI can analyze the bundled synthetic graph in memory.

## CLI usage

### Analyze impact in memory

```bash
python -m enterprise_graphrag impacted-apps --service "Identity Service"
```

Example output:

```text
Applications impacted by Identity Service:
- Finance Dashboard
- Sales Portal
- Support Hub
```

### Ask a natural-language-style question

```bash
python -m enterprise_graphrag ask "Which applications are impacted if Notification Service fails?"
```

### Load the synthetic graph into Neo4j

```bash
python -m enterprise_graphrag seed-neo4j
```

### Query Neo4j instead of the in-memory graph

```bash
python -m enterprise_graphrag impacted-apps --service "Identity Service" --backend neo4j
```

### Show the bundled Cypher queries

```bash
python -m enterprise_graphrag show-cypher
```

## Key Cypher query

The core impact-analysis query follows dependency paths of any length:

```cypher
MATCH (failed:Service {name: $service_name})
MATCH path = (application:Application)-[:DEPENDS_ON*1..]->(failed)
RETURN DISTINCT application.name AS application, length(path) AS hops
ORDER BY hops, application
```

## Testing

Run the focused unit tests with:

```bash
python -m unittest discover -s tests -v
```

## Educational goals

This project is intentionally small and modular so it is easy to extend with:

- Retrieval pipelines that ground answers in graph evidence
- Additional Cypher templates
- More node types such as databases, APIs, or business capabilities
- A UI or notebook walkthrough for GraphRAG experimentation
