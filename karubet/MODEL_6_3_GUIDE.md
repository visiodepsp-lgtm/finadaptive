# KARUBET 7.0 - motor original de probabilidades (v6.3)

## Modelo recuperado y verificado
Fuente privada aportada: KARUBET_Match_Centre_6_3_Colab.ipynb.
Se extrajeron y comprobaron 19 archivos del paquete embebido. Se mantienen los motores engine.py y form.py, model.joblib, form_model.joblib, labeled.csv, pa_calibration.csv, el histórico de secuencias de goles y los etiquetados.

Prueba offline con el BBETS_2026.zip original, corte temporal 2026-11-27 01:00 UTC: **1.204 encuentros**, 74 columnas; PA, Quasi PA (qpa), Doble PA (dpa) y Remontada (rem) completos, y jerarquía PA >= qpa >= dpa >= rem respetada.

## Primera carga privada en Supabase Storage
Bucket: karubet-bbets-input (privado).
Subir exactamente estos tres archivos:
- BBETS_DATA.zip (histórico, 35 MB), una vez; se actualiza sólo si hay correcciones.
- BBETS_2026.zip (fixture y resultados de la temporada), reemplazar semanalmente.
- KARUBET_MODELO_6_3_PRIVADO.zip (2 MB; fuente del modelo original), una vez.

SHA-256 del paquete del modelo:
06141a7fc956422e699fa59510e94759183daa62e08140cd2920978b4ea399df

El runner valida esta huella antes de cargar los modelos. Los formatos joblib/pickle sólo son seguros si provienen de una fuente de confianza; nunca ejecutar un fichero joblib desconocido.

## Operación semanal
En GitHub Actions ejecutar manualmente **KARUBET - probabilidades originales 6.3**.
El proceso primero importa datos nuevos de BBETS_2026 a la base, luego aplica engine.score y form.enhance originales, sin reentrenar pesos, y guarda todos los fixtures futuros en karubet_model_outputs con sus PA/Quasi/Doble/Rem, EWMA, H2H, Poisson y Elastic.
La automatización semanal de este modelo aún no está activada hasta comprobar una ejecución real de GitHub Actions.

Las predicciones se recalculan a partir de los nuevos partidos jugados, manteniendo el modelo original. No se debe incorporar el resultado futuro de un encuentro dentro de sus características prepartido.

## Integración futura con las dos hojas
- Hoja 1: último snapshot de probabilidades por fixture_id de Sportmonks.
- Hoja 2: cuotas L/E/V por partido enlazado y verificado a Apuesta Total; el mercado de cuotas no altera el PA.
- La tabla karubet_fixture_odds_links enlazará los partidos de fuentes diferentes, con revisión de alias y fecha.
- El timing ENTRAR/ESPERAR solo se activa con evidencia empírica y backtesting fuera de muestra.

**Protección:** no copiar las claves de Supabase a HTML ni al repositorio público. Todos los ZIP de datos/modelos permanecen privados.
