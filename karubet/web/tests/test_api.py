"""Pruebas sin red de la API privada de KARUBET Market Centre."""
import importlib.util
import pathlib
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

HERE = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("karubet_api", HERE / "api" / "data.py")
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


class ReadOnlyApiTests(unittest.TestCase):
    def test_fixture_predictions_join_by_exact_id(self):
        future = datetime.now(timezone.utc) + timedelta(days=1)
        fixtures = [{
            "fixture_id": 88, "competition": "epl", "home_team": "A",
            "away_team": "B", "kickoff_at": future.isoformat(),
            "status": "unplayed", "phase": None,
        }]
        scores = [{
            "fixture_id": 88, "probabilities": {
                "pa": .55, "qpa": .2, "dpa": .04, "rem": .01
            }, "generated_at": datetime.now(timezone.utc).isoformat(),
        }]
        with patch.object(api, "get_json", side_effect=[fixtures, scores]):
            data = api.fixtures({"days": ["4"], "limit": ["20"], "offset": ["0"]})
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["model_count"], 1)
        self.assertEqual(data["items"][0]["model"]["probabilities"]["pa"], .55)
        self.assertFalse(data["page_full"])

    def test_market_latest_keeps_only_last_observation(self):
        now = datetime.now(timezone.utc).isoformat()
        old = {
            "id": 1, "league_code": "74", "home_team": "A",
            "away_team": "B", "kickoff_at": "2027-01-01T10:00:00+00:00",
            "captured_at": now, "odd_home": 2.4,
        }
        newer = dict(old, id=2, odd_home=2.7)
        with patch.object(api, "get_json", return_value=[newer, old]):
            data = api.markets()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["items"][0]["odd_home"], 2.7)

    def test_history_rejects_unscoped_request(self):
        with self.assertRaises(ValueError):
            api.history({"home":["A"],"away":["B"]})
        with self.assertRaises(ValueError):
            api.history({"league":["1 OR 1=1"],"home":["A"],"away":["B"]})

    def test_original_context_joins_by_exact_fixture_id(self):
        original = [{
            "fixture_id": 19722093,
            "source_snapshot_date": "2026-11-22",
            "context": {
                "home":"Arsenal", "away":"Manchester City", "competition":"epl",
                "home_recent":[{"opponent":"Newcastle United","result":"D"}],
                "h2h_matches":[{"date":"2026-04-19","score":"2–1"}],
                "h_gf_5": 1.4
            }
        }]
        with patch.object(api,"get_json",return_value=original) as request:
            data=api.contexts({"ids":["19722093"]})
        self.assertEqual(data["count"],1)
        self.assertEqual(data["items"][0]["context"]["home_recent"][0]["opponent"],
                         "Newcastle United")
        self.assertEqual(data["items"][0]["context"]["h_gf_5"],1.4)
        self.assertEqual(data["snapshot_date"],"2026-11-22")
        self.assertEqual(request.call_args[0][0],"karubet_fixture_context_original")
        self.assertEqual(request.call_args[0][1]["fixture_id"],"in.(19722093)")

    def test_context_input_is_strictly_limited(self):
        with patch.object(api,"get_json") as db:
            for ids in ("", "19722093);DROP TABLE matches", "abc",
                        ",".join(["19722093"] * 81)):
                with self.assertRaises(ValueError):
                    api.contexts({"ids":[ids]})
            db.assert_not_called()

    def test_unauthorized_table_is_blocked(self):
        with self.assertRaises(RuntimeError):
            # Will fail closed on missing server credentials before network.
            with patch.dict("os.environ", {"SUPABASE_URL":"", "SUPABASE_SECRET_KEY":""}):
                api.get_json("users", {})


if __name__ == "__main__":
    unittest.main()
