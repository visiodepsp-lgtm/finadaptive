"""Pruebas offline del control de captura; sin llamadas reales a GitHub."""
import importlib.util
import pathlib
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("capture_api", HERE / "api" / "capture.py")
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


class CaptureApiTests(unittest.TestCase):
    def test_refuses_missing_or_weak_credentials(self):
        with patch.dict("os.environ", {"GITHUB_ACTIONS_TOKEN": "", "KARUBET_CAPTURE_KEY": ""}):
            self.assertFalse(api.ready())
            self.assertFalse(api.authorized(""))
        with patch.dict("os.environ", {"GITHUB_ACTIONS_TOKEN": "ghp_example",
                                            "KARUBET_CAPTURE_KEY": "short"}):
            self.assertFalse(api.ready())
            self.assertFalse(api.authorized("short"))

    def test_secret_only_authorizes_exact_match(self):
        key = "a-long-unpredictable-capture-access-key"
        with patch.dict("os.environ", {"GITHUB_ACTIONS_TOKEN": "example",
                                            "KARUBET_CAPTURE_KEY": key}):
            self.assertTrue(api.ready())
            self.assertTrue(api.authorized(key))
            self.assertFalse(api.authorized(key + "wrong"))
            self.assertFalse(api.authorized(""))

    def test_recent_run_blocks_duplicate_but_failed_run_does_not(self):
        now = datetime(2026, 11, 27, 18, 0, tzinfo=timezone.utc)
        recent = (now - timedelta(minutes=3)).isoformat()
        run = {"event": "workflow_dispatch", "created_at": recent,
               "status": "in_progress", "conclusion": None}
        self.assertGreater(api.recent_run_wait({"workflow_runs": [run]}, now), 200)
        run["conclusion"] = "failure"
        self.assertEqual(api.recent_run_wait({"workflow_runs": [run]}, now), 0)

    def test_old_run_and_other_events_not_blocking(self):
        now = datetime(2026, 11, 27, 18, 0, tzinfo=timezone.utc)
        old = (now - timedelta(minutes=11)).isoformat()
        run = {"event": "schedule", "created_at": old, "conclusion": "success"}
        self.assertEqual(api.recent_run_wait({"workflow_runs": [run]}, now), 0)
        run = {"event": "push", "created_at": now.isoformat(), "conclusion": None}
        self.assertEqual(api.recent_run_wait({"workflow_runs": [run]}, now), 0)


if __name__ == "__main__":
    unittest.main()
