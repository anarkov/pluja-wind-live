import unittest
from datetime import datetime, timedelta, timezone
from live_selection import CompleteField, decide_publication, select_nearest_usable

class LiveSelectionTest(unittest.TestCase):
    def field(self, valid): return CompleteField("2026090200", 3, valid, "u", "v", "t")
    def test_publication_policy(self):
        now = datetime(2026,9,2,12,tzinfo=timezone.utc); fresh=self.field(now+timedelta(minutes=30)); stale=self.field(now-timedelta(hours=3)); newer=self.field(now+timedelta(minutes=60))
        self.assertEqual("PUBLISH", decide_publication(stale, fresh, now).decision)
        self.assertEqual("KEEP_CURRENT", decide_publication(fresh, fresh, now).decision)
        self.assertEqual("REJECT_DOWNGRADE", decide_publication(newer, fresh, now).decision)
        self.assertEqual("PUBLISH", decide_publication(fresh, newer, now).decision)
        self.assertEqual("KEEP_CURRENT", decide_publication(fresh, None, now).decision)
        self.assertEqual("NO_VALID_CANDIDATE", decide_publication(stale, None, now).decision)
        self.assertEqual("KEEP_CURRENT", decide_publication(fresh, self.field(now + timedelta(hours=2)), now).decision)

    def test_same_valid_time_prefers_the_most_recent_model_run(self):
        now = datetime(2026, 9, 2, 12, tzinfo=timezone.utc)
        older = CompleteField("2026090121", 15, now + timedelta(minutes=30), "u", "v", "t")
        newer = CompleteField("2026090209", 3, now + timedelta(minutes=30), "u", "v", "t")
        self.assertEqual(newer, select_nearest_usable([older, newer], now))
        self.assertEqual("PUBLISH", decide_publication(older, newer, now).decision)

    def test_old_current_yields_to_later_forecast_hour_from_the_same_run(self):
        now = datetime(2026, 9, 3, 14, 20, tzinfo=timezone.utc)
        current = CompleteField("2026090306", 6, datetime(2026, 9, 3, 12, tzinfo=timezone.utc), "u", "v", "t")
        same_run_later = CompleteField("2026090306", 9, datetime(2026, 9, 3, 15, tzinfo=timezone.utc), "u", "v", "t")
        self.assertEqual(same_run_later, select_nearest_usable([current, same_run_later], now))
        self.assertEqual("PUBLISH", decide_publication(current, same_run_later, now).decision)

    def test_slightly_future_complete_field_beats_an_old_current_field(self):
        now = datetime(2026, 9, 3, 14, 20, tzinfo=timezone.utc)
        old_current = self.field(now - timedelta(minutes=110))
        future = self.field(now + timedelta(minutes=35))
        self.assertEqual(future, select_nearest_usable([old_current, future], now))
        self.assertEqual("PUBLISH", decide_publication(old_current, future, now).decision)

    def test_current_remains_when_it_is_closer_than_the_available_future_candidate(self):
        now = datetime(2026, 9, 3, 14, 20, tzinfo=timezone.utc)
        current = self.field(now - timedelta(minutes=10))
        future = self.field(now + timedelta(minutes=80))
        self.assertEqual(current, select_nearest_usable([current, future], now))
        self.assertEqual("KEEP_CURRENT", decide_publication(current, current, now).decision)

    def test_never_downgrades_valid_time(self):
        now = datetime(2026, 9, 3, 14, 20, tzinfo=timezone.utc)
        current = self.field(now + timedelta(minutes=50))
        older = self.field(now - timedelta(minutes=5))
        self.assertEqual("REJECT_DOWNGRADE", decide_publication(current, older, now).decision)
