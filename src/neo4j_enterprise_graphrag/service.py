from __future__ import annotations

import logging
import re
from dataclasses import asdict
from typing import Any

from .repository import EntityNotFoundError, GraphRepository
from .sample_data import build_sample_graph

LOGGER = logging.getLogger(__name__)
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


class InputValidationError(ValueError):
    """Raised when CLI or service input is invalid."""


class EnterpriseGraphRAGService:
    def __init__(self, repository: GraphRepository) -> None:
        self._repository = repository

    def initialize_sample_graph(self, reset: bool = False) -> dict[str, Any]:
        duration_ms = self._repository.initialize_graph(build_sample_graph(), reset=reset)
        return {
            "status": "ok",
            "operation": "initialize_sample_graph",
            "reset": reset,
            "duration_ms": duration_ms,
        }

    def describe_service(self, service_name: str, max_depth: int = 4) -> dict[str, Any]:
        name = _validate_name(service_name)
        depth = _validate_depth(max_depth)
        direct = self._repository.get_direct_dependencies(name)
        multi_hop = self._repository.get_multi_hop_dependencies(name, depth)
        impact = self._repository.get_impacted_applications(name, depth)
        owners = self._repository.get_service_owners(name)

        return {
            "service": name,
            "owner_teams": [asdict(owner) for owner in owners.value],
            "direct_dependencies": direct.value,
            "multi_hop_dependencies": multi_hop.value,
            "impacted_applications": [asdict(item) for item in impact.value],
            "timing_ms": {
                "direct_dependencies": direct.duration_ms,
                "multi_hop_dependencies": multi_hop.duration_ms,
                "impacted_applications": impact.duration_ms,
                "service_ownership": owners.duration_ms,
            },
        }

    def get_impacted_applications(self, service_name: str, max_depth: int = 4) -> dict[str, Any]:
        name = _validate_name(service_name)
        depth = _validate_depth(max_depth)
        impact = self._repository.get_impacted_applications(name, depth)

        return {
            "service": name,
            "impacted_applications": [asdict(item) for item in impact.value],
            "duration_ms": impact.duration_ms,
        }

    def find_dependency_paths(
        self, source_name: str, target_name: str, max_depth: int = 4, limit: int = 10
    ) -> dict[str, Any]:
        source = _validate_name(source_name)
        target = _validate_name(target_name)
        depth = _validate_depth(max_depth)
        capped_limit = _validate_limit(limit)
        paths = self._repository.find_dependency_paths(source, target, depth, capped_limit)

        return {
            "source_service": source,
            "target_service": target,
            "paths": [asdict(path) for path in paths.value],
            "duration_ms": paths.duration_ms,
        }

    def get_service_owners(self, service_name: str) -> dict[str, Any]:
        name = _validate_name(service_name)
        owners = self._repository.get_service_owners(name)
        return {
            "service": name,
            "owners": [asdict(owner) for owner in owners.value],
            "duration_ms": owners.duration_ms,
        }

    def retrieve(self, question: str, service_name: str | None = None, limit: int = 3) -> dict[str, Any]:
        normalized_question = question.strip()
        if not normalized_question:
            raise InputValidationError("Question must not be empty.")

        capped_limit = _validate_limit(limit)
        provided_service = _validate_name(service_name) if service_name else None
        tokens = _tokenize(normalized_question)
        documents = self._repository.search_documents(tokens, capped_limit)

        candidate_services = set()
        if provided_service:
            candidate_services.add(provided_service)
        else:
            lowered_question = normalized_question.lower()
            for known_service in self._repository.list_services():
                if known_service.lower() in lowered_question:
                    candidate_services.add(known_service)

        for document in documents.value:
            candidate_services.update(document.related_services)

        graph_context = []
        for matched_service in sorted(candidate_services):
            try:
                graph_context.append(self.describe_service(matched_service, max_depth=4))
            except EntityNotFoundError:
                LOGGER.warning("Skipping missing service while retrieving graph context: %s", matched_service)

        return {
            "question": normalized_question,
            "matched_services": sorted(candidate_services),
            "documents": [asdict(document) for document in documents.value],
            "graph_context": graph_context,
            "retrieval_notes": [
                "Documents are retrieved first using local keyword overlap.",
                "Graph traversal then expands to owners, dependencies, and impacted applications.",
                "This demonstrates how graph retrieval adds relationship-aware evidence beyond standalone document matches.",
            ],
            "timing_ms": {
                "document_search": documents.duration_ms,
            },
        }


def _validate_name(value: str | None) -> str:
    if value is None:
        raise InputValidationError("A service name is required.")
    normalized = value.strip()
    if not normalized:
        raise InputValidationError("A service name is required.")
    return normalized


def _validate_depth(value: int) -> int:
    if value < 1 or value > 6:
        raise InputValidationError("max_depth must be between 1 and 6.")
    return value


def _validate_limit(value: int) -> int:
    if value < 1 or value > 20:
        raise InputValidationError("limit must be between 1 and 20.")
    return value


def _tokenize(text: str) -> list[str]:
    return sorted(set(TOKEN_PATTERN.findall(text.lower())))
