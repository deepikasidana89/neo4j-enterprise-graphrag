from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Node:
    label: str
    name: str
    properties: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Relationship:
    start_label: str
    start_name: str
    rel_type: str
    end_label: str
    end_name: str


@dataclass(frozen=True)
class GraphDataset:
    nodes: tuple[Node, ...]
    relationships: tuple[Relationship, ...]
