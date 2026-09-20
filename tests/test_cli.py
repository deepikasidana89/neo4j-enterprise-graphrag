import contextlib
import io
import unittest

from enterprise_graphrag.cli import main, parse_supported_question


class CliTests(unittest.TestCase):
    def test_parse_supported_question(self) -> None:
        self.assertEqual(
            parse_supported_question("Which applications are impacted if Identity Service fails?"),
            "Identity Service",
        )

    def test_impacted_apps_command(self) -> None:
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            exit_code = main(["impacted-apps", "--service", "Identity Service"])
        self.assertEqual(exit_code, 0)
        self.assertIn("Sales Portal", stream.getvalue())
        self.assertIn("Support Hub", stream.getvalue())

    def test_ask_command(self) -> None:
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            exit_code = main(["ask", "Which applications are impacted if Notification Service fails?"])
        self.assertEqual(exit_code, 0)
        self.assertIn("Finance Dashboard", stream.getvalue())
