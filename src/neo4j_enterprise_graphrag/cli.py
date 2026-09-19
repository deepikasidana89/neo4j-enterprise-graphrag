from __future__ import annotations

import argparse
import json
import sys

from .config import ConfigurationError, Neo4jConfig, configure_logging
from .repository import EntityNotFoundError, Neo4jGraphRepository, RepositoryError
from .service import EnterpriseGraphRAGService, InputValidationError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="neo4j-graphrag",
        description="Enterprise GraphRAG reference implementation for Neo4j.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-graph", help="Initialize the sample enterprise graph.")
    init_parser.add_argument("--reset", action="store_true", help="Delete existing sample nodes before loading.")

    service_parser = subparsers.add_parser("service", help="Describe a service and its dependencies.")
    service_parser.add_argument("--name", required=True, help="Service name.")
    service_parser.add_argument("--max-depth", type=int, default=4, help="Traversal depth from 1-6.")

    impact_parser = subparsers.add_parser("impact", help="Find customer-facing applications impacted by a service outage.")
    impact_parser.add_argument("--name", required=True, help="Service name.")
    impact_parser.add_argument("--max-depth", type=int, default=4, help="Traversal depth from 1-6.")

    path_parser = subparsers.add_parser("paths", help="Find dependency paths between two services.")
    path_parser.add_argument("--source", required=True, help="Upstream service name.")
    path_parser.add_argument("--target", required=True, help="Dependency service name.")
    path_parser.add_argument("--max-depth", type=int, default=4, help="Traversal depth from 1-6.")
    path_parser.add_argument("--limit", type=int, default=10, help="Maximum paths to return.")

    owner_parser = subparsers.add_parser("owners", help="Look up owning teams for a service.")
    owner_parser.add_argument("--name", required=True, help="Service name.")

    retrieve_parser = subparsers.add_parser("retrieve", help="Run the GraphRAG retrieval demo.")
    retrieve_parser.add_argument("--question", required=True, help="Natural language question.")
    retrieve_parser.add_argument("--service", help="Optional service hint for graph expansion.")
    retrieve_parser.add_argument("--limit", type=int, default=3, help="Maximum supporting documents to return.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = Neo4jConfig.from_env()
        configure_logging(config.log_level)
        repository = Neo4jGraphRepository(config)
        service = EnterpriseGraphRAGService(repository)
        try:
            if args.command == "init-graph":
                payload = service.initialize_sample_graph(reset=args.reset)
            elif args.command == "service":
                payload = service.describe_service(args.name, max_depth=args.max_depth)
            elif args.command == "impact":
                payload = service.get_impacted_applications(args.name, max_depth=args.max_depth)
            elif args.command == "paths":
                payload = service.find_dependency_paths(
                    args.source,
                    args.target,
                    max_depth=args.max_depth,
                    limit=args.limit,
                )
            elif args.command == "owners":
                payload = service.get_service_owners(args.name)
            else:
                payload = service.retrieve(args.question, service_name=args.service, limit=args.limit)
        finally:
            repository.close()
    except (ConfigurationError, InputValidationError, EntityNotFoundError, RepositoryError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, indent=2), file=sys.stderr)
        return 1

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
