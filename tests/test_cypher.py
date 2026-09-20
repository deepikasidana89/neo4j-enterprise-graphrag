import unittest

from enterprise_graphrag.cypher import DEPENDENCY_PATHS_QUERY, IMPACTED_APPLICATIONS_QUERY, seed_query
from enterprise_graphrag.sample_data import SAMPLE_GRAPH


class CypherTests(unittest.TestCase):
    def test_queries_reference_variable_length_dependencies(self) -> None:
        self.assertIn("[:DEPENDS_ON*1..]", IMPACTED_APPLICATIONS_QUERY)
        self.assertIn("[:DEPENDS_ON*1..]", DEPENDENCY_PATHS_QUERY)

    def test_seed_query_contains_sample_payload(self) -> None:
        _, parameters = seed_query(SAMPLE_GRAPH)
        self.assertGreaterEqual(len(parameters["nodes"]), 5)
        self.assertTrue(
            any(node["name"] == "Identity Service" for node in parameters["nodes"])
        )
