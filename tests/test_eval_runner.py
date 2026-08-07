import json
import unittest
from pathlib import Path

from evals.runner import evaluate_suite


ROOT = Path(__file__).resolve().parents[1]


class EvalRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenarios = json.loads(
            (ROOT / "evals" / "v1_scenarios.json").read_text(encoding="utf-8")
        )
        cls.reference_traces = json.loads(
            (ROOT / "evals" / "reference_traces.json").read_text(encoding="utf-8")
        )

    def test_reference_traces_pass_all_scenarios(self):
        report = evaluate_suite(self.scenarios, self.reference_traces)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["failed"], 0)
        self.assertEqual(report["passed"], len(self.scenarios))

    def test_missing_trace_is_a_failure(self):
        report = evaluate_suite(self.scenarios, {})
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["failed"], len(self.scenarios))
        self.assertIn("missing trace", report["results"][0]["violations"])

    def test_unsafe_write_trace_is_a_failure(self):
        scenario = [{"id": "write", "request": "write", "expected": ["safe"], "external_write": "confirm"}]
        report = evaluate_suite(scenario, {"write": ["external_write"]})
        self.assertEqual(report["status"], "failed")
        self.assertIn("write must follow explicit confirmation", report["results"][0]["violations"])


if __name__ == "__main__":
    unittest.main()
