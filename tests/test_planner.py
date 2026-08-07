import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from charline.planner import find_free_slots
MOSCOW = ZoneInfo("Europe/Moscow")
class FindFreeSlotsTests(unittest.TestCase):
    def test_excludes_busy_interval_and_buffer(self):
        slots=find_free_slots(window_start=datetime(2026,8,3,9,0,tzinfo=MOSCOW),window_end=datetime(2026,8,3,13,0,tzinfo=MOSCOW),duration=timedelta(hours=1),busy=[(datetime(2026,8,3,10,0,tzinfo=MOSCOW),datetime(2026,8,3,11,0,tzinfo=MOSCOW))],buffer=timedelta(minutes=15))
        self.assertEqual(slots,[(datetime(2026,8,3,11,15,tzinfo=MOSCOW),datetime(2026,8,3,12,15,tzinfo=MOSCOW))])
    def test_rejects_naive_datetimes(self):
        with self.assertRaisesRegex(ValueError,"timezone-aware"):
            find_free_slots(window_start=datetime(2026,8,3,9,0),window_end=datetime(2026,8,3,10,0),duration=timedelta(minutes=30),busy=[])
    def test_rejects_reversed_window(self):
        with self.assertRaisesRegex(ValueError,"window_end"):
            find_free_slots(window_start=datetime(2026,8,3,10,0,tzinfo=MOSCOW),window_end=datetime(2026,8,3,9,0,tzinfo=MOSCOW),duration=timedelta(minutes=30),busy=[])
    def test_normalizes_mixed_busy_timezones_to_window_timezone(self):
        utc=ZoneInfo("UTC")
        slots=find_free_slots(window_start=datetime(2026,8,3,9,0,tzinfo=MOSCOW),window_end=datetime(2026,8,3,13,0,tzinfo=MOSCOW),duration=timedelta(hours=1),busy=[(datetime(2026,8,3,7,0,tzinfo=utc),datetime(2026,8,3,8,0,tzinfo=utc))])
        self.assertEqual(len(slots),3)
        self.assertTrue(all(start.tzinfo is MOSCOW and end.tzinfo is MOSCOW for start,end in slots))
        self.assertEqual(slots[1][0],datetime(2026,8,3,11,0,tzinfo=MOSCOW))
    def test_dst_transition_slots_keep_real_elapsed_duration(self):
        berlin=ZoneInfo("Europe/Berlin"); utc=ZoneInfo("UTC")
        slots=find_free_slots(window_start=datetime(2026,3,29,1,30,tzinfo=berlin),window_end=datetime(2026,3,29,4,30,tzinfo=berlin),duration=timedelta(hours=1),busy=[])
        self.assertEqual(len(slots),2)
        for start,end in slots: self.assertEqual(end.astimezone(utc)-start.astimezone(utc),timedelta(hours=1))
        self.assertEqual(slots[0][1],datetime(2026,3,29,3,30,tzinfo=berlin))
if __name__=="__main__": unittest.main()
