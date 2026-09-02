import unittest
from datetime import datetime, timedelta, timezone
from live_selection import CompleteField, decide_publication

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
        from live_selection import select_nearest_usable
        self.assertEqual(newer, select_nearest_usable([older, newer], now))
