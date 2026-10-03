/* Resumen: cambiar la meta diaria. */
"use strict";
(() => {
  for (const b of document.querySelectorAll("[data-meta]")) {
    b.addEventListener("click", async () => {
      const estabaDeshabilitado = b.disabled;
      b.disabled = true;
      try {
        const r = await Tortu.api("/api/config", { meta_min: Number(b.dataset.meta) });
        if (r.ok) {
          location.reload();
          return;
        }
        throw new Error(r.mensaje || "El servidor no confirmó el cambio.");
      } catch (e) {
        Tortu.avisos([{
          tipo: "mensaje",
          titulo: "No se pudo cambiar la meta diaria",
          detalle: e?.datos?.mensaje || e.message || "Revisá tu conexión e intentá nuevamente.",
        }]);
      } finally {
        b.disabled = estabaDeshabilitado;
      }
    });
  }
})();
