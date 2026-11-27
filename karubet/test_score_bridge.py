"""Pruebas de integridad para el puente de probabilidades original KARUBET 6.3."""
import unittest
from score_weekly import make_rows


class BridgeTest(unittest.TestCase):
    def row(self):
        return {
            "fixture_id": 19722085, "competition": "epl",
            "home": "Nottingham Forest", "away": "Chelsea",
            "dia": "2026-11-27", "hora": "15:00",
            "hora_confirmada": True,
            "pa": .49, "qpa": .15, "dpa": .04, "rem": .01,
            "h2h_count": 2, "h2h_evidence": 1.2,
        }

    def test_nested_probabilities_are_preserved(self):
        import pandas as pd
        values = make_rows(pd.DataFrame([self.row()]), "2026-11-27T01:00:00+00:00")
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0]["fixture_id"], 19722085)
        self.assertEqual(values[0]["probabilities"]["qpa"], .15)
        self.assertEqual(values[0]["probabilities"]["rem"], .01)
        self.assertIsNone(values[0]["probabilities"]["ewma"]["pa"])

    def test_impossible_hierarchy_rejected(self):
        import pandas as pd
        row = self.row()
        row["dpa"] = .2
        with self.assertRaises(RuntimeError):
            make_rows(pd.DataFrame([row]), "2026-11-27T01:00:00+00:00")

    def test_missing_pa_rejected(self):
        import pandas as pd
        row = self.row()
        row["pa"] = float("nan")
        with self.assertRaises(RuntimeError):
            make_rows(pd.DataFrame([row]), "2026-11-27T01:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
