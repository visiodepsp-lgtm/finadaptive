"""Pruebas locales del filtro de calidad; no hacen llamadas a red."""
import unittest
from collector import revisar_filas, probabilidades_mercado


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

    def test_rechazar_margen_inverosimil(self):
        validas, resumen = revisar_filas([fila(cuotas=(1.03, 1.04, 1.05))], [])
        self.assertEqual(len(validas), 0)
        self.assertEqual(resumen["partidos_rechazados"]["margen_1x2_atipico"], 1)


if __name__ == "__main__":
    unittest.main()
