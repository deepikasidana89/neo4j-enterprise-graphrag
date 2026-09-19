from __future__ import annotations

from .models import GraphDataset, Node, Relationship

SAMPLE_GRAPH = GraphDataset(
    nodes=(
        Node("Team", "Platform Engineering", {"domain": "Shared Services"}),
        Node("Team", "Revenue Systems", {"domain": "Sales"}),
        Node("Team", "Customer Experience", {"domain": "Support"}),
        Node("Application", "Sales Portal", {"criticality": "high"}),
        Node("Application", "Support Hub", {"criticality": "medium"}),
        Node("Application", "Finance Dashboard", {"criticality": "high"}),
        Node("Service", "Identity Service", {"tier": "platform"}),
        Node("Service", "Customer Profile Service", {"tier": "domain"}),
        Node("Service", "Billing Service", {"tier": "domain"}),
        Node("Service", "Notification Service", {"tier": "platform"}),
        Node("Service", "Reporting Service", {"tier": "analytics"}),
    ),
    relationships=(
        Relationship("Application", "Sales Portal", "DEPENDS_ON", "Service", "Customer Profile Service"),
        Relationship("Application", "Support Hub", "DEPENDS_ON", "Service", "Customer Profile Service"),
        Relationship("Application", "Finance Dashboard", "DEPENDS_ON", "Service", "Billing Service"),
        Relationship("Application", "Finance Dashboard", "DEPENDS_ON", "Service", "Reporting Service"),
        Relationship("Service", "Customer Profile Service", "DEPENDS_ON", "Service", "Identity Service"),
        Relationship("Service", "Billing Service", "DEPENDS_ON", "Service", "Identity Service"),
        Relationship("Service", "Billing Service", "DEPENDS_ON", "Service", "Notification Service"),
        Relationship("Service", "Reporting Service", "DEPENDS_ON", "Service", "Billing Service"),
        Relationship("Team", "Platform Engineering", "OWNS", "Service", "Identity Service"),
        Relationship("Team", "Platform Engineering", "OWNS", "Service", "Notification Service"),
        Relationship("Team", "Revenue Systems", "OWNS", "Application", "Sales Portal"),
        Relationship("Team", "Revenue Systems", "OWNS", "Service", "Billing Service"),
        Relationship("Team", "Customer Experience", "OWNS", "Application", "Support Hub"),
        Relationship("Team", "Customer Experience", "OWNS", "Service", "Customer Profile Service"),
        Relationship("Team", "Revenue Systems", "OWNS", "Application", "Finance Dashboard"),
        Relationship("Team", "Revenue Systems", "OWNS", "Service", "Reporting Service"),
    ),
)
