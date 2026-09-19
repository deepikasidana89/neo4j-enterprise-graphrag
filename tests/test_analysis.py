import unittest

from enterprise_graphrag.analysis import find_impacted_applications
from enterprise_graphrag.sample_data import SAMPLE_GRAPH


class AnalysisTests(unittest.TestCase):
    def test_identity_service_failure_impacts_multiple_applications(self) -> None:
        self.assertEqual(
            find_impacted_applications(SAMPLE_GRAPH, "Identity Service"),
            ["Finance Dashboard", "Sales Portal", "Support Hub"],
        )

    def test_notification_service_failure_only_impacts_finance_dashboard(self) -> None:
        self.assertEqual(
            find_impacted_applications(SAMPLE_GRAPH, "Notification Service"),
            ["Finance Dashboard"],
        )

    def test_unknown_service_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown service"):
            find_impacted_applications(SAMPLE_GRAPH, "Missing Service")
