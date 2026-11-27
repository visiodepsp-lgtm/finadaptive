# KARUBET · Captura 1X2 (versión piloto)

Este módulo está separado de FinAdaptive. **No modifica** el \`index.html\` ni el notebook original.
Captura las columnas de apuestas **Local / Empate / Visita** de los cinco enlaces de
Apuesta Total configurados en \`catalogo.py\`, sin abrir cada evento.

## Primera prueba segura

1. Revisa y fusiona el PR \`karubet-automation-v1\` a \`main\`.
2. En **Actions**, abre **KARUBET - prueba cuotas 1X2**.
3. Pulsa **Run workflow** y **deja desmarcado** \`save_to_db\` (por defecto).
4. En la ejecución, baja el artifact \`karubet-diagnostico-1x2\`.
5. Verifica los datos en \`cuotas_1x2.csv\`, \`diagnosticos.json\`, \`resumen.json\`
   y las capturas \`liga_XX.png\`.
6. Cuando comprobemos que la lectura corresponde a cada categoría, ejecuta
   de nuevo y activa \`save_to_db\` para insertar snapshots en Supabase.

**Todavía no hay ejecución automática por horario**. La agregaremos tras validar
la primera captura desde los runners de GitHub.

## Seguridad

Los dos secrets del repositorio son:
- \`SUPABASE_URL\`: URL HTTPS de Supabase.
- \`SUPABASE_SECRET_KEY\`: clave privada \`sb_secret_...\`, **nunca** se imprime ni se sube.

El recolector usa la API REST con el header \`apikey\` (no JWT Bearer).
No agregues estas claves a archivos, imágenes, ni al frontend público.

La base ya tiene las tablas:
- \`public.karubet_ingest_runs\`: auditoría y diagnósticos por ejecución.
- \`public.karubet_odds_1x2\`: historial por partido/captura.

Ambas usan RLS y no conceden lectura pública. Solo un backend autorizado
puede insertar datos mediante la Secret API key.

## Calidad de datos

- Se exige validar que la **cuota central sea EMPATE**, y el margen implícito
  del mercado debe tener un rango plausible.
- Los mismos encuentros detectados en varias categorías se excluyen.
- Si no se encuentra fecha, se guarda como NULL y se marca \`kickoff_missing\`.
  **No se debe cruzar directamente con el fixture hasta confirmar la fecha.**
- Si las cinco ligas devuelven exactamente la misma cantidad, se marca una alerta.
- Si el sitio cambia o restringe los navegadores automáticos, puede fallar:
  HTTP 200 no confirma que la extracción sea correcta.

**No son probabilidades del modelo**: \`market_p_*\` son probabilidades implícitas
normalizadas, calculadas únicamente a partir de las cuotas.

El histórico H2H, las estadísticas oficiales, el modelo Poisson y el
Match Centre 6.3 siguen separados: integración posterior, tras validar fechas
y ligas. No se envían apuestas ni se automatizan transacciones.

Respetar las condiciones de uso y límites de la fuente de datos. No intentar
eludir restricciones o CAPTCHAs.
