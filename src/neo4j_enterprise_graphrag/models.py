from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Service:
    name: str
    description: str
    tier: str


@dataclass(frozen=True)
class Application:
    name: str
    description: str
    customer_facing: bool = True


@dataclass(frozen=True)
class Team:
    name: str
    description: str


@dataclass(frozen=True)
class Document:
    id: str
    title: str
    content: str


@dataclass(frozen=True)
class ServiceDependency:
    source: str
    target: str


@dataclass(frozen=True)
class ApplicationUsage:
    application: str
    service: str


@dataclass(frozen=True)
class Ownership:
    team: str
    service: str


@dataclass(frozen=True)
class DocumentLink:
    document_id: str
    service: str


@dataclass(frozen=True)
class EnterpriseGraph:
    services: list[Service]
    applications: list[Application]
    teams: list[Team]
    documents: list[Document]
    service_dependencies: list[ServiceDependency]
    application_usage: list[ApplicationUsage]
    ownerships: list[Ownership]
    document_links: list[DocumentLink]

    def to_payload(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "services": [asdict(item) for item in self.services],
            "applications": [asdict(item) for item in self.applications],
            "teams": [asdict(item) for item in self.teams],
            "documents": [asdict(item) for item in self.documents],
            "service_dependencies": [asdict(item) for item in self.service_dependencies],
            "application_usage": [asdict(item) for item in self.application_usage],
            "ownerships": [asdict(item) for item in self.ownerships],
            "document_links": [asdict(item) for item in self.document_links],
        }


@dataclass(frozen=True)
class ImpactRecord:
    application: str
    dependent_service: str
    service_path: list[str]
    hops: int


@dataclass(frozen=True)
class DependencyPath:
    path: list[str]
    hops: int


@dataclass(frozen=True)
class RetrievedDocument:
    id: str
    title: str
    content: str
    score: int
    related_services: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ServiceOwner:
    team: str
    description: str
