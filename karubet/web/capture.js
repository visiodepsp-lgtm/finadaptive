/* KARUBET Market Centre · orden de captura segura, no descarga secretos de GitHub. */
"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const TEN_MIN = 10 * 60 * 1000;
  let captureKey = "";
  let busy = false;
  let nextTimer = null;
  let monitorTimer = null;
  let newestCapture = 0;
  let pendingAfter = 0;

  function status(message, mode = "") {
    const element = $("captureStatus");
    if (!element) return;
    element.textContent = message;
    element.dataset.mode = mode;
  }

  function cancelNext() {
    if (nextTimer !== null) clearTimeout(nextTimer);
    nextTimer = null;
    $("captureNext").textContent = "Ciclo detenido · no se ejecutará con la pestaña cerrada.";
  }

  function planNext() {
    if (!$("captureLoop").checked) {
      cancelNext();
      return;
    }
    if (nextTimer !== null) clearTimeout(nextTimer);
    const next = new Date(Date.now() + TEN_MIN);
    $("captureNext").textContent = "Próximo intento: " +
      new Intl.DateTimeFormat("es-PE", {
        timeZone:"America/Lima", hour:"2-digit", minute:"2-digit"
      }).format(next) + " (tiene que seguir abierta esta pestaña).";
    nextTimer = setTimeout(() => {
      nextTimer = null;
      if ($("captureLoop").checked) captureNow(true);
    }, TEN_MIN);
  }

  function stopMonitor() {
    if (monitorTimer !== null) clearInterval(monitorTimer);
    monitorTimer = null;
    pendingAfter = 0;
  }

  function startMonitor() {
    stopMonitor();
    // Si aún no hay datos, exigir un registro posterior al envío.
    pendingAfter = newestCapture || (Date.now() - 30000);
    const started = Date.now();
    let loading = false;
    monitorTimer = setInterval(async () => {
      if (Date.now() - started > 8 * 60000) {
        stopMonitor();
        status("Sin nuevas cuotas tras 8 min. Comprueba GitHub Actions; el envío no equivale a una captura.", "error");
        return;
      }
      if (loading || document.hidden) return;
      loading = true;
      try {
        if (typeof window.loadMarkets === "function") await window.loadMarkets();
      } finally {
        loading = false;
      }
    }, 25000);
  }

  document.addEventListener("karubet:markets-loaded", event => {
    const value = Number(event.detail?.lastCapturedAt) || 0;
    newestCapture = Math.max(newestCapture, value);
    if (pendingAfter && value > pendingAfter) {
      stopMonitor();
      status("✓ Nuevas cuotas confirmadas en Supabase y sincronizadas en Market Centre.", "success");
    }
  });

  async function captureNow(fromCycle = false) {
    if (busy) return;
    if (!captureKey) {
      if (fromCycle) {
        cancelNext();
        status("Ciclo detenido: vuelve a introducir la clave de captura.", "error");
        return;
      }
      const entered = window.prompt("Clave privada de captura KARUBET (definida en Vercel). No es el token de GitHub:");
      if (entered === null || !entered.trim()) {
        status("Captura cancelada. No se envió ninguna solicitud.");
        return;
      }
      captureKey = entered;
    }

    busy = true;
    $("captureNow").disabled = true;
    status("Enviando orden segura a GitHub Actions...");
    try {
      const response = await fetch("/api/capture", {
        method: "POST",
        headers: {"X-Karubet-Capture-Key": captureKey},
        cache: "no-store",
        credentials: "same-origin"
      });
      const result = await response.json().catch(() => ({}));
      if (response.status === 401) captureKey = "";
      if (response.status === 429) {
        status("GitHub ya tiene una ejecución reciente. No se lanzó otra; las cuotas se consultarán normalmente.");
        if ($("captureLoop").checked) planNext();
        return;
      }
      if (!response.ok) {
        status(result.message || "No se pudo enviar la solicitud de captura.", "error");
        if (response.status === 401 || response.status === 503) cancelNext();
        return;
      }
      if (response.status !== 202) throw new Error("Respuesta inesperada del servidor.");
      status("✓ Solicitud aceptada. GitHub ejecutará el recolector; comprobando Supabase…", "success");
      startMonitor();
      if ($("captureLoop").checked) planNext();
    } catch (error) {
      status("Error de conexión al solicitar la captura: " + error.message, "error");
    } finally {
      busy = false;
      $("captureNow").disabled = false;
    }
  }

  async function init() {
    const button = $("captureNow");
    if (!button) return;
    button.addEventListener("click", () => captureNow(false));
    $("captureLoop").addEventListener("change", () => {
      if (!$("captureLoop").checked) cancelNext();
      else if (captureKey && nextTimer === null) {
        status("Modo 10 min activo; pulsa CAPTURAR CUOTAS AHORA para iniciar el ciclo.");
      }
    });
    try {
      const response = await fetch("/api/capture", {cache: "no-store"});
      const result = await response.json();
      if (response.ok && result.ready) {
        button.disabled = false;
        status("Captura disponible. Pulsa el botón para obtener nuevas cuotas desde Apuesta Total.");
      } else {
        button.disabled = true;
        status(result.message || "Captura pendiente de configuración privada en Vercel.", "error");
      }
    } catch {
      button.disabled = true;
      status("No se pudo consultar la función de captura. Verifica el despliegue en Vercel.", "error");
    }
    $("captureNext").textContent = "Repetición 10 min: activa tras pulsar el botón; requiere pestaña abierta.";
  }

  document.addEventListener("DOMContentLoaded", init);
})();
