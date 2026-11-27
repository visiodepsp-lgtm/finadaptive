# KARUBET 7.0 - web independiente con datos de Supabase

**Ubicación:** karubet/web/ dentro del repositorio FinAdaptive.
**Despliegue:** otro proyecto Vercel, con Root Directory: karubet/web.
No reemplaza ni modifica el index.html ni el despliegue actual de FinAdaptive.

## Hojas
1. Probabilidades 6.3: PA, Quasi PA, Doble PA, Remontada, componentes
   EWMA/H2H/Poisson/Elastic y goles esperados desde karubet_model_outputs.
2. Market Centre: cuota L/E/V, rolling 3/6/12/24 capturas, volatilidad,
   máximos y mínimos y banda +/-2 desviaciones.
   Cuando no existen snapshots, muestra 'sin capturas'.
   No genera recomendaciones de inversión sin un backtesting válido.

## Seguridad
- Todas las solicitudes a Supabase se hacen desde la función privada
  api/data.py; la clave sb_secret_ se mantiene exclusivamente en Vercel.
- El frontend solicita un token de acceso largo, guardado sólo en
  sessionStorage y enviado a /api/data en el encabezado Authorization.
- Si falta alguna variable privada, el backend devuelve HTTP 503,
  sin filtrar datos.
- La API es solo lectura y dispone de lista estricta de tablas
  autorizadas, sin ejecución SQL ni escrituras.
- RLS sigue activada en Supabase; anon no puede leer esas tablas.

## Variables Vercel (Production, Preview)
- SUPABASE_URL = https://pryrwgpfunxcwfifsaei.supabase.co (config)
- SUPABASE_SECRET_KEY = clave sb_secret_ del proyecto (SECRET)
- KARUBET_ACCESS_TOKEN = token aleatorio de longitud >= 20 (SECRET)
Los secretos del repositorio GitHub Actions NO se copian automáticamente
a Vercel. Nunca compartirlos en GitHub ni en el HTML.
Tras crear/actualizar variables, hacer un redeploy.

## Datos actuales
- Hoja 1: 1.204 predicciones originales 6.3 en Supabase (al 27/11/2026).
- Hoja 2: 0 snapshots 1X2 guardados al iniciar esta fase.
  Revisar Github Actions, capturas válidas y fixture-alias antes
  de automatizar las señales.
- Para vincular Hoja 1 y Hoja 2 se utiliza la tabla
  karubet_fixture_odds_links, sólo con enlaces revisados.

## API
- GET /api/data?kind=fixtures&days=210&limit=250&offset=0
- GET /api/data?kind=markets
- GET /api/data?kind=history&league=24&home=Chelsea&away=Arsenal&kickoff=...
- GET /api/data?kind=linked&fixture_id=123
Todas exigen encabezado Authorization: Bearer <KARUBET_ACCESS_TOKEN>.

No utilizar estos indicadores para invertir dinero real hasta que
un modelo de timing sea validado fuera de muestra.
