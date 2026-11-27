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
- El panel es público de solo lectura y no exige contraseña.
- Cualquier persona que conozca la URL puede consultar partidos, cuotas
  históricas y predicciones mostradas por esta API. No usar para material privado.
- La clave de Supabase nunca se entrega al navegador.
- Si falta la clave privada del servidor, el backend devuelve HTTP 503.
- La API es solo lectura y dispone de lista estricta de tablas
  autorizadas, sin ejecución SQL ni escrituras.
- RLS sigue activada en Supabase; anon no puede leer esas tablas.

## Variables Vercel (Production, Preview)
- SUPABASE_URL = https://pryrwgpfunxcwfifsaei.supabase.co (config)
- SUPABASE_SECRET_KEY = clave sb_secret_ del proyecto (SECRET)
- KARUBET_ACCESS_TOKEN ya no se utiliza (opcional eliminarla en Vercel).
Los secretos del repositorio GitHub Actions NO se copian automáticamente
a Vercel. Nunca compartirlos en GitHub ni en el HTML.
Tras crear/actualizar variables, hacer un redeploy.

## Datos actuales
- Hoja 1: 1.204 predicciones originales 6.3 en Supabase (al 27/11/2026).
- Hoja 2: 78 snapshots en 39 partidos, dos capturas verificadas
  al 27/11/2026, sujeto a actualización por cron programado cada 10 min.
  Las ejecuciones programadas de GitHub pueden demorarse u omitirse.\n  La barra de Market Centre muestra la hora de la última captura y alerta\n  si han pasado más de 25 minutos sin snapshots nuevos.
- Market Centre: watchlist densa con filtros de liga y autocompletado
  de equipos, gráfico con cursor, MA rolling, banda, estadísticas y tape.
- Escudos de 96 clubes 2026/27 procedentes del proyecto público
  luukhopman/football-logos. Los logos de las cinco ligas provienen de\n  Sachawd/wc26-assets. Las marcas son de sus respectivos titulares;
  se muestra fallback textual cuando no existe correspondencia revisada.
- Para vincular Hoja 1 y Hoja 2 se utiliza la tabla
  karubet_fixture_odds_links, sólo con enlaces revisados.

## API
- GET /api/data?kind=fixtures&days=210&limit=250&offset=0
- GET /api/data?kind=markets
- GET /api/data?kind=history&league=24&home=Chelsea&away=Arsenal&kickoff=...
- GET /api/data?kind=linked&fixture_id=123
No exigen un encabezado Authorization. Su uso es público y de solo lectura;
los parámetros, tablas, campos y límites están restringidos por el backend.

No utilizar estos indicadores para invertir dinero real hasta que
un modelo de timing sea validado fuera de muestra.

## Match Centre 6.3: restauración del contexto histórico
- Tabla `karubet_fixture_context_original`: 1.207 filas restauradas de
  `KARUBET_Match_Centre_6_3_limpio (2).html`, snapshot del 22/11/2026.
- Enlaza por `fixture_id` y valida también nombre de ambos equipos y liga.
- Forma de ambos equipos y factores observados disponibles en 1.204 de
  1.204 predicciones; H2H disponibles en 1.126 de esas predicciones.
- El frontend solicita el contexto en tandas de hasta 75 IDs a
  `GET /api/data?kind=contexts&ids=ID1,ID2,...` sin exponer claves.
- No se alteró el objeto de probabilidades del modelo 6.3.
- Importante: se trata de una foto histórica, no de un recálculo de
  forma/H2H posterior al 22/11/2026. La actualización semanal de estas
  fichas exige regenerarlas desde el motor original y subir una nueva versión.

## Captura manual y ciclo de 10 minutos (Market Centre)

El botón `CAPTURAR CUOTAS AHORA` no ejecuta Playwright dentro del navegador:
`POST /api/capture` autoriza una solicitud **en el servidor** y despacha
`.github/workflows/karubet-1x2.yml` con `save_to_db=true`. GitHub Actions
ejecuta el recolector y guarda snapshots en Supabase; Market Centre consulta
automáticamente las novedades cada 25 segundos después de una solicitud.
El botón `SINCRONIZAR` solo refresca las lecturas, no obtiene cuotas nuevas.

**Configuración necesaria en Vercel, proyecto finadaptive-web (Production):**

1. `GITHUB_ACTIONS_TOKEN`: token GitHub *fine-grained* limitado al repositorio
   `visiodepsp-lgtm/finadaptive`, permiso **Actions: Read and write**.
   No debe ponerse en GitHub ni en el HTML.
2. `KARUBET_CAPTURE_KEY`: frase secreta larga y aleatoria (mínimo 24
   caracteres), distinta del token GitHub. Se introduce en el prompt del
   botón; permanece **solo en memoria de la pestaña** hasta cerrarla.

Tras configurar ambas variables, redeployar el proyecto web. Nunca pegar
ninguna clave en un chat o un commit. El endpoint rechaza llamadas sin la
frase correcta y limita los disparos cuando hay una ejecución reciente en
GitHub. La página pública sigue siendo de consulta de datos, pero **el POST
de captura está protegido**. Si faltan claves, el botón queda deshabilitado.

La casilla `REPETIR 10 MIN` está marcada inicialmente: al pulsar el botón,
la página solicita una captura y programa nuevos intentos cada diez minutos.
**El ciclo de navegador termina al cerrar la pestaña** y puede retrasarse si
el navegador suspende pestañas inactivas. GitHub Actions conserva su cron
independiente para la recogida de fondo (sus ejecuciones tampoco tienen
garantía de puntualidad). El servidor evita enviar otra solicitud si detecta
una ejecución reciente, para no duplicar cuotas. El estado `ENVIADA` no
implica captura terminada: se confirma solo al observar snapshots más nuevos
en Supabase.


## Bundesliga
- La primera Bundesliga de Alemania se encontró directamente en Apuesta Total:
  `/es-pe/spbkv3/sports/1/category?region=54&league=110`.
- El recolector consulta **seis** competiciones (incluidas Bundesliga y UCL).
- En Market Centre el identificador de Bundesliga es `110`, con su insignia y
  escudos. Se exige confirmación explícita de la etiqueta "Bundesliga" y se
  rechaza "2ª Bundesliga" para evitar mezclar categorías.
- Los partidos aparecen en la Watchlist **solo cuando haya cuotas 1X2 verificadas
  y guardadas en Supabase**. No se inventan cuotas ni capturas previas.
- El workflow registra las cuotas automáticamente al actualizar el catálogo,
  además de conservar el cron; esto permite probar el alta de la liga.
