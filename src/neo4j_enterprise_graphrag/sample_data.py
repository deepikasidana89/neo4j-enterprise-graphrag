from __future__ import annotations

from .models import (
    Application,
    ApplicationUsage,
    Document,
    DocumentLink,
    EnterpriseGraph,
    Ownership,
    Service,
    ServiceDependency,
    Team,
)


def build_sample_graph() -> EnterpriseGraph:
    return EnterpriseGraph(
        services=[
            Service(
                name="Identity Service",
                description="Authenticates users and brokers customer session tokens.",
                tier="platform",
            ),
            Service(
                name="Billing Service",
                description="Calculates invoices and payment events for customer transactions.",
                tier="domain",
            ),
            Service(
                name="Notification Service",
                description="Sends customer alerts for billing and order status changes.",
                tier="shared",
            ),
            Service(
                name="Inventory Service",
                description="Tracks sellable inventory and warehouse availability.",
                tier="domain",
            ),
            Service(
                name="Order Service",
                description="Coordinates order placement and fulfillment workflows.",
                tier="domain",
            ),
            Service(
                name="Customer API",
                description="Customer-facing API gateway used by external applications.",
                tier="edge",
            ),
            Service(
                name="Search Service",
                description="Provides product catalog search and recommendation lookups.",
                tier="edge",
            ),
        ],
        applications=[
            Application(
                name="Customer Web Portal",
                description="Primary self-service customer portal for web users.",
                customer_facing=True,
            ),
            Application(
                name="Mobile App",
                description="Mobile channel for account access, ordering, and notifications.",
                customer_facing=True,
            ),
            Application(
                name="Partner Dashboard",
                description="Partner-facing billing and order visibility experience.",
                customer_facing=True,
            ),
            Application(
                name="Operations Console",
                description="Internal tooling for support and incident response.",
                customer_facing=False,
            ),
        ],
        teams=[
            Team(
                name="Platform Team",
                description="Owns identity and shared platform capabilities.",
            ),
            Team(
                name="Commerce Team",
                description="Owns billing, inventory, and order domain services.",
            ),
            Team(
                name="Experience Team",
                description="Owns edge services exposed to customer applications.",
            ),
        ],
        documents=[
            Document(
                id="doc-identity-runbook",
                title="Identity Service Runbook",
                content=(
                    "Identity Service issues tokens for Customer API, Billing Service, "
                    "Notification Service, and Search Service."
                ),
            ),
            Document(
                id="doc-customer-api-dependencies",
                title="Customer API Dependency Overview",
                content=(
                    "Customer API depends on Identity Service, Billing Service, and Order Service "
                    "to serve customer applications."
                ),
            ),
            Document(
                id="doc-billing-impact",
                title="Billing Service Business Impact",
                content=(
                    "Billing Service supports Partner Dashboard and Customer Web Portal "
                    "checkout and account history experiences."
                ),
            ),
            Document(
                id="doc-order-fulfillment",
                title="Order Fulfillment Dependency Notes",
                content=(
                    "Order Service depends on Inventory Service and Notification Service "
                    "during customer order processing."
                ),
            ),
        ],
        service_dependencies=[
            ServiceDependency(source="Billing Service", target="Identity Service"),
            ServiceDependency(source="Notification Service", target="Identity Service"),
            ServiceDependency(source="Order Service", target="Inventory Service"),
            ServiceDependency(source="Order Service", target="Notification Service"),
            ServiceDependency(source="Customer API", target="Identity Service"),
            ServiceDependency(source="Customer API", target="Billing Service"),
            ServiceDependency(source="Customer API", target="Order Service"),
            ServiceDependency(source="Search Service", target="Identity Service"),
        ],
        application_usage=[
            ApplicationUsage(application="Customer Web Portal", service="Customer API"),
            ApplicationUsage(application="Mobile App", service="Customer API"),
            ApplicationUsage(application="Mobile App", service="Search Service"),
            ApplicationUsage(application="Partner Dashboard", service="Billing Service"),
            ApplicationUsage(application="Operations Console", service="Notification Service"),
        ],
        ownerships=[
            Ownership(team="Platform Team", service="Identity Service"),
            Ownership(team="Platform Team", service="Notification Service"),
            Ownership(team="Commerce Team", service="Billing Service"),
            Ownership(team="Commerce Team", service="Inventory Service"),
            Ownership(team="Commerce Team", service="Order Service"),
            Ownership(team="Experience Team", service="Customer API"),
            Ownership(team="Experience Team", service="Search Service"),
        ],
        document_links=[
            DocumentLink(document_id="doc-identity-runbook", service="Identity Service"),
            DocumentLink(document_id="doc-customer-api-dependencies", service="Customer API"),
            DocumentLink(document_id="doc-billing-impact", service="Billing Service"),
            DocumentLink(document_id="doc-order-fulfillment", service="Order Service"),
        ],
    )
