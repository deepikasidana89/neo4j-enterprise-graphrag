from __future__ import annotations

import argparse
import re

from .analysis import find_impacted_applications
from .config import Neo4jConfig
from .cypher import CONSTRAINT_STATEMENTS, DEPENDENCY_PATHS_QUERY, IMPACTED_APPLICATIONS_QUERY
from .neo4j_client import Neo4jGraphClient
from .sample_data import SAMPLE_GRAPH

QUESTION_PATTERNS = (
    re.compile(r"which applications are impacted if (?P<service>.+?) fails\??", re.IGNORECASE),
    re.compile(r"what applications depend on (?P<service>.+?)\??", re.IGNORECASE),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Enterprise GraphRAG reference CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    impacted = subparsers.add_parser("impacted-apps", help="List applications impacted by a failed service.")
    impacted.add_argument("--service", required=True, help="Service name to analyze.")
    impacted.add_argument(
        "--backend",
        choices=("memory", "neo4j"),
        default="memory",
        help="Use the built-in sample graph or query a live Neo4j database.",
    )

    ask = subparsers.add_parser("ask", help="Answer a supported natural-language dependency question.")
    ask.add_argument("question", help='Example: "Which applications are impacted if Identity Service fails?"')
    ask.add_argument("--backend", choices=("memory", "neo4j"), default="memory")

    subparsers.add_parser("show-cypher", help="Print the bundled Cypher queries.")
    subparsers.add_parser("seed-neo4j", help="Load the sample dataset into Neo4j using environment variables.")
    return parser


def answer_impacted_apps(service_name: str, backend: str) -> list[str]:
    if backend == "memory":
        return find_impacted_applications(SAMPLE_GRAPH, service_name)

    client = Neo4jGraphClient(Neo4jConfig.from_env())
    try:
        return client.impacted_applications(service_name)
    finally:
        client.close()


def parse_supported_question(question: str) -> str:
    normalized = question.strip()
    for pattern in QUESTION_PATTERNS:
        match = pattern.fullmatch(normalized)
        if match:
            return match.group("service").strip().rstrip("?")
    raise ValueError(
        "Unsupported question. Try: 'Which applications are impacted if Identity Service fails?'"
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "show-cypher":
        print("Constraints:")
        for statement in CONSTRAINT_STATEMENTS:
            print(f"- {statement}")
        print("\nImpacted applications query:")
        print(IMPACTED_APPLICATIONS_QUERY)
        print("\nDependency paths query:")
        print(DEPENDENCY_PATHS_QUERY)
        return 0

    if args.command == "seed-neo4j":
        client = Neo4jGraphClient(Neo4jConfig.from_env())
        try:
            client.seed_sample_graph()
        finally:
            client.close()
        print("Sample enterprise graph loaded into Neo4j.")
        return 0

    try:
        if args.command == "ask":
            service_name = parse_supported_question(args.question)
            impacted = answer_impacted_apps(service_name, args.backend)
        else:
            impacted = answer_impacted_apps(args.service, args.backend)
            service_name = args.service
    except ValueError as exc:
        parser.error(str(exc))
    except RuntimeError as exc:
        parser.error(str(exc))

    if impacted:
        print(f"Applications impacted by {service_name}:")
        for name in impacted:
            print(f"- {name}")
    else:
        print(f"No applications are impacted by {service_name} in the sample graph.")
    return 0
