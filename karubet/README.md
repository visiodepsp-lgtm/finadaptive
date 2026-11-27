# KARUBET · Captura 1X2 automatizada y observatorio de cuotas

Este módulo es independiente de FinAdaptive. **No modifica** el `index.html`
ni el notebook original de KARUBET Match Centre.

## Programación

GitHub Actions ejecuta `.github/workflows/karubet-1x2.yml` a los minutos
**07, 22, 37 y 52 UTC** de cada hora: hasta 96 ejecuciones programadas por día
(*best effort*: GitHub puede retrasar u omitir ejecuciones).
- Ejecución programada: guarda snapshots en Supabase sólo si el encuentro empieza
  durante las siguientes **96 horas** (4 días), tiene liga y fecha verificadas,
  y todavía no comenzó.
- Aunque la lectura sigue consultando las cinco páginas web, sólo se escriben
  partidos dentro de la ventana. Integrar el fixture maestro permitirá optimizar
  posteriormente qué páginas se abren.
- Ejecución manual `Run workflow`: por defecto es **solo lectura**.
- Ejecución manual con `save_to_db=true`: guarda en Supabase.
- Se puede pausar desde GitHub Actions → workflow → menú ⋯ → Disable workflow.

Se mantienen **cuotas iguales en capturas distintas** para reconstruir series
de tiempo sin sesgo de selección por cambio de precio.

## Protección de datos

Credenciales guardadas como GitHub Repository Secrets:
- `SUPABASE_URL`: URL HTTPS de KARUBET.
- `SUPABASE_SECRET_KEY`: clave privada `sb_secret_...`, nunca en frontend.

Datos en PostgreSQL:
- `public.karubet_ingest_runs`: auditoría y diagnósticos por ejecución.
- `public.karubet_odds_1x2`: snapshot de cada partido prepartido
  (competición, fecha de juego, captura, cuota L/E/V, probabilidades de mercado).
- `karubet_analytics.ultimos_movimientos_1x2`: vista privada que calcula
  diferencia con última captura, cambio de probabilidad en puntos porcentuales,
  media y z-score en una ventana de 12 observaciones.

Solo los partidos con fecha, liga y cuotas verificadas, **dentro de las 96 horas antes del inicio**,
se guardan en la base. Los datos dudosos se conservan en diagnósticos locales
sin contaminar el historial. No se fabrican cuotas, fechas o equipos.
Se evita relacionar partidos que aparecen en varias categorías.

El proceso genera `alertas_movimientos.json` y un resumen en GitHub Actions
cuando encuentra una variación de cuota ≥3% o un movimiento de probabilidad
implícita ≥1 punto porcentual. Son **alertas descriptivas**, no apuestas.

## Acceder a los resultados

- **Actions → KARUBET - cuotas 1X2 cada 15 min → Run → Summary**.
- Los artifacts de diagnósticos se suben en ejecuciones manuales o fallidas.
- El archivador diario `.github/workflows/karubet-archive.yml` consolida
  **todos los partidos iniciados** en `public.karubet_event_archive`, con apertura,
  cierre, mínimos, máximos, número de capturas y serie temporal completa de cuotas
  como JSONB. Incluye campos vacíos para completar después el marcador real.
- Por ahora se conservan también los snapshots originales. **No se eliminan
  filas automáticamente** sin comprobar antes la integridad del archivo.
- En el futuro, tras verificar la copia, podemos purgar datos crudos antiguos
  o pasarlos a almacenamiento comprimido; no se guardarán únicamente ganadores.

## Investigación y siguientes etapas

- Hipótesis iniciales: momentum, reversión a la media, cambios bruscos,
  cierre de cuota y discrepancia de cuota respecto al modelo KARUBET.
- No considerar la cuota de una sola casa como un activo que se pueda
  comprar y vender sin costes. En un bookmaker la apuesta suele ser
  fija; el valor de cash-out o la cobertura depende de condiciones.
- Validar señales por partido y *walk-forward* con resultados realizados;
  separar ligas, controlar comisiones/margen, no introducir información futura.
- Una disminución de cuota ≠ prueba de ventaja predictiva.
- GitHub Actions puede consumir minutos y Supabase almacenamiento según
  su plan. Revisar consumo periódicamente.
- Nunca se envían apuestas ni se automatizan pagos.

Uso sujeto a los términos del proveedor de cuotas; si bloquea automatización,
el recolector falla sin intentar eludir restricciones.
