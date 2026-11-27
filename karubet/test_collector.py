"""Pruebas locales del filtro de calidad; no hacen llamadas a red."""
import unittest
from collector import revisar_filas, probabilidades_mercado, completar_fecha


def fila(liga="74", home="Nottingham Forest", away="Chelsea", fecha=None,
         cuotas=(2.50, 3.32, 2.84)):
    return {
        "league_code": liga,
        "source_url": "https://www.apuestatotal.com/apuestas-en-vivo/?fpath=/es-pe/spbkv3/sports/1/category?league=" + liga,
        "home_team": home,
        "away_team": away,
        "kickoff_text": fecha,
        "odd_home": cuotas[0],
        "odd_draw": cuotas[1],
        "odd_away": cuotas[2],
        "verified_draw_label": True,
        "raw_excerpt": "Empate",
    }


class PruebasCalidad(unittest.TestCase):
    def test_probabilidad_mercado_suma_uno(self):
        p = probabilidades_mercado(2.5, 3.32, 2.84)
        self.assertAlmostEqual(sum(p), 1.0, places=3)

    def test_fila_sin_fecha_se_marca_y_no_se_inventa(self):
        validas, resumen = revisar_filas([fila()], [{"eventos_con_1x2": 1, "estado": "CUOTAS_1X2_DETECTADAS"}])
        self.assertEqual(len(validas), 1)
        self.assertIsNone(validas[0]["kickoff_text"])
        self.assertTrue(validas[0]["quality_flags"]["kickoff_missing"])
        self.assertEqual(resumen["sin_fecha"], 1)

    def test_no_duplicar_mismo_partido_en_dos_categorias(self):
        validas, resumen = revisar_filas(
            [fila(liga="25"), fila(liga="74")],
            [{"eventos_con_1x2": 1, "estado": "CUOTAS_1X2_DETECTADAS"}] * 2
        )
        self.assertEqual(len(validas), 0)
        self.assertEqual(resumen["solapados_entre_ligas"], 1)


    def test_fecha_y_competicion_extraidas_de_captura_real(self):
        r = fila(liga="24", fecha=None)
        r["raw_excerpt"] = (
            "27/11 • 15:00 Premier League Nottingham Forest Chelsea "
            "2.50 Nottingham Forest 3.32 Empate 2.84 Chelsea"
        )
        validas, resumen = revisar_filas(
            [r], [{"eventos_con_1x2": 1, "estado": "CUOTAS_1X2_DETECTADAS"}],
            "2026-11-27T01:05:15+00:00"
        )
        self.assertEqual(len(validas), 1)
        self.assertEqual(validas[0]["kickoff_text"], "27/11 15:00")
        self.assertEqual(validas[0]["kickoff_at"], "2026-11-27T20:00:00+00:00")
        self.assertEqual(resumen["sin_fecha"], 0)
        self.assertEqual(resumen["categoria_no_confirmada"], 0)

    def test_fecha_ya_normalizada_con_separador_punto(self):
        r = fila(liga="25", fecha="08/12 · 12:45")
        r["raw_excerpt"] = "08/12 • 12:45 Ligue 1 Brest Paris FC 3.30 Empate 3.40"
        completar_fecha(r, "2026-11-27T01:05:15+00:00")
        self.assertEqual(r["kickoff_at"], "2026-12-08T17:45:00+00:00")

    def test_rechazar_margen_inverosimil(self):
        validas, resumen = revisar_filas([fila(cuotas=(1.03, 1.04, 1.05))], [])
        self.assertEqual(len(validas), 0)
        self.assertEqual(resumen["partidos_rechazados"]["margen_1x2_atipico"], 1)


if __name__ == "__main__":
    unittest.main()
