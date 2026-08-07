import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from charline.availability import AvailabilityValidationError, plan_availability


class AvailabilityContractTests(unittest.TestCase):
    def base_request(self):
        return {
            "window_start": "2026-08-07T09:00:00+03:00",
            "window_end": "2026-08-07T13:00:00+03:00",
            "current_time": "2026-08-07T10:15:00+03:00",
            "duration_minutes": 30,
            "buffer_minutes": 0,
            "limit": 3,
            "busy": [],
        }

    def test_clamps_current_day_window_to_current_time(self):
        result = plan_availability(self.base_request())
        self.assertEqual(result["slots"][0]["start"], "2026-08-07T10:15:00+03:00")
        self.assertEqual(len(result["slots"]), 3)

    def test_returns_no_slots_when_window_is_already_past(self):
        request = self.base_request()
        request["current_time"] = "2026-08-07T14:00:00+03:00"
        self.assertEqual(plan_availability(request)["slots"], [])

    def test_applies_busy_intervals_and_buffer(self):
        request = self.base_request()
        request["current_time"] = "2026-08-07T09:00:00+03:00"
        request["buffer_minutes"] = 15
        request["busy"] = [
            {
                "start": "2026-08-07T10:00:00+03:00",
                "end": "2026-08-07T11:00:00+03:00",
            }
        ]
        result = plan_availability(request)
        self.assertEqual(result["slots"][1]["start"], "2026-08-07T11:15:00+03:00")

    def test_rejects_naive_current_time(self):
        request = self.base_request()
        request["current_time"] = "2026-08-07T10:15:00"
        with self.assertRaisesRegex(AvailabilityValidationError, "timezone-aware"):
            plan_availability(request)


if __name__ == "__main__":
    unittest.main()
