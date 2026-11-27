# KARUBET 7.0 - BBETS histórico, 2026/27 y cuotas

## Archivos verificados (26 de noviembre de 2026)

- BBETS_DATA.zip: 45 ficheros fixtures.csv, 5 ligas, temporadas
  2017-2025; 16.111 resultados históricos.
  Incluye además 405.363 tiros, 478.431 apariciones y 24.612
  estadísticas de jugador en los CSV originales.
- BBETS_2026.zip: 6 ficheros fixtures.csv, 1.986 encuentros
  de temporada 2026/27; incluye Bundesliga y Champions League.
  1.279 encuentros estaban marcados unplayed en esta versión.
- Apuesta Total: capturas L/E/V cada 15 minutos, sin apuestas.

## Primera carga

1. Abrir la consola Supabase de KARUBET:
   https://supabase.com/dashboard/project/pryrwgpfunxcwfifsaei/storage/buckets
2. Abrir el bucket privado karubet-bbets-input.
3. Subir exactamente BBETS_DATA.zip (una vez) y
   BBETS_2026.zip (temporada actual). No poner estos ZIP
   en un repositorio público ni cambiar sus nombres.
4. En GitHub Actions ejecutar manualmente
   KARUBET - actualizar BBETS semanal, seleccionar dataset=all.
5. Revisar la ejecución; los datos quedarán en
   public.karubet_historical_matches y public.karubet_fixtures_2026.

**Importante:** subir archivos en ChatGPT no los copia
automáticamente al bucket de Supabase. Hasta subir esos ZIP e
importarlos, las tablas permanecerán vacías.

## Actualización semanal

- Cada semana reemplazar en el bucket BBETS_2026.zip.
- Si cambian las temporadas anteriores, reemplazar también
  BBETS_DATA.zip.
- La tarea de GitHub está programada para los lunes a las 07:17 UTC
  y permite ejecución manual.
- El importador karubet/import_bbets.py lee el bucket privado
  mediante GitHub Secrets, compara cada row_hash con el fixture_id
  de la BD, e inserta solo filas nuevas o modificadas.
- Cada importación queda auditada en karubet_data_imports.
- Si un ZIP es incompleto, aborta sin borrar filas anteriores.
- No se reentrena automáticamente el modelo PA hasta integrar
  el pipeline original y verificar el backtesting.
- Los ZIP originales permanecen en Storage para reproducibilidad
  y entrenamiento con datos de disparos y jugadores.

## Integración de los dos paneles

- Probabilidades: histórico Understat + fixtures Sportmonks
  + predicciones PA/Quasi PA/Doble PA en karubet_model_outputs.
- Market Centre: snapshots 1X2 de Apuesta Total.
- La tabla karubet_fixture_odds_links enlazará los dos mundos
  por identidad verificada de partido, fecha y equipos.
- No igualar IDs de Understat, Sportmonks y Apuesta Total.
- Apuesta Total cubre Ligue 1, Serie A, EPL, La Liga y Champions.
  Bundesliga está en fixtures, pero no en estos cinco enlaces
  originales de Apuesta Total.

## Control de filtración de información

Nunca usar resultados, goles ni xG realizados del partido
que vamos a predecir. Los features para un encuentro futuro
solo deben incluir partidos anteriores al corte temporal.
En copas, evaluar el mercado 1X2 a 90 minutos, sin penalizaciones.
Las tendencias de cuota deben entrenarse y comprobarse
walk-forward, usando únicamente snapshots previos.
