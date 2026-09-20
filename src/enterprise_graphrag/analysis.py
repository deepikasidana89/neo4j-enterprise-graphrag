from __future__ import annotations

from collections import defaultdict, deque

from .models import GraphDataset


def _dependency_reverse_graph(dataset: GraphDataset) -> dict[str, set[str]]:
    reverse_graph: dict[str, set[str]] = defaultdict(set)
    for relationship in dataset.relationships:
        if relationship.rel_type == "DEPENDS_ON":
            reverse_graph[relationship.end_name].add(relationship.start_name)
    return reverse_graph


def _node_labels(dataset: GraphDataset) -> dict[str, str]:
    return {node.name: node.label for node in dataset.nodes}


def find_impacted_applications(dataset: GraphDataset, failed_service: str) -> list[str]:
    labels = _node_labels(dataset)
    if labels.get(failed_service) != "Service":
        raise ValueError(f"Unknown service: {failed_service}")

    reverse_graph = _dependency_reverse_graph(dataset)
    queue = deque([failed_service])
    visited = {failed_service}
    impacted: set[str] = set()

    while queue:
        current = queue.popleft()
        for dependent in reverse_graph.get(current, set()):
            if dependent in visited:
                continue
            visited.add(dependent)
            queue.append(dependent)
            if labels.get(dependent) == "Application":
                impacted.add(dependent)

    return sorted(impacted)
