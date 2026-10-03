"use strict";

(() => {
  const catalogo = document.querySelector("[data-iniciar-proyecto]");
  if (catalogo) {
    for (const boton of document.querySelectorAll("[data-iniciar-proyecto]")) {
      boton.addEventListener("click", async () => {
        boton.disabled = true;
        try {
          const r = await Tortu.api("/api/proyectos-integradores/" + encodeURIComponent(boton.dataset.iniciarProyecto), { });
          location.href = r.url;
        } catch (e) {
          boton.disabled = false;
          Tortu.avisos([{ tipo: "mensaje", titulo: "No se pudo empezar", detalle: e?.datos?.mensaje || "Revisá tu conexión e intentá nuevamente." }]);
        }
      });
    }
  }

  const datos = document.getElementById("datos-proyecto");
  if (!datos) return;
  const proyecto = JSON.parse(datos.textContent);

  function mensaje(texto, clase) {
    const nodo = document.getElementById("integrador-mensaje");
    if (!nodo) return;
    nodo.className = "resultado veredicto " + (clase || "info");
    nodo.textContent = texto;
  }

  for (const boton of document.querySelectorAll("[data-guardar-archivo]")) {
    boton.addEventListener("click", async () => {
      const nombre = boton.dataset.guardarArchivo;
      const editor = document.querySelector('[data-editor="' + CSS.escape(nombre) + '"]');
      boton.disabled = true;
      try {
        await Tortu.api("/api/proyectos-integradores/" + encodeURIComponent(proyecto.id) + "/archivo", {
          nombre, codigo: editor.value
        });
        mensaje("✓ Guardé " + nombre + ".", "bien");
      } catch (e) {
        mensaje(e?.datos?.mensaje || "Revisá tu conexión e intentá nuevamente.", "error");
      } finally { boton.disabled = false; }
    });
  }

  for (const boton of document.querySelectorAll("[data-validar-etapa]")) {
    boton.addEventListener("click", async () => {
      boton.disabled = true;
      try {
        const r = await Tortu.api("/api/proyectos-integradores/" + encodeURIComponent(proyecto.id) + "/etapas/" + encodeURIComponent(boton.dataset.validarEtapa), {});
        mensaje(r.completado ? "🎉 ¡Proyecto completado! Ya podés descargarlo." : "✓ Etapa completada. Seguimos con la siguiente.", "bien");
        setTimeout(() => location.reload(), 700);
      } catch (e) {
        mensaje(e?.datos?.mensaje || "Todavía falta algo en esta etapa.", "error");
        boton.disabled = false;
      }
    });
  }

  for (const boton of document.querySelectorAll("[data-ayuda]")) {
    boton.addEventListener("click", async () => {
      boton.disabled = true;
      try {
        const r = await Tortu.api("/api/proyectos-integradores/" + encodeURIComponent(proyecto.id) + "/ayudas/" + encodeURIComponent(boton.dataset.ayuda), {});
        const texto = document.querySelector('[data-ayuda-texto="' + CSS.escape(boton.dataset.ayuda) + '"]');
        texto.textContent = r.texto;
        texto.hidden = false;
      } catch (e) {
        mensaje(e?.datos?.mensaje || "Revisá tu conexión e intentá nuevamente.", "error");
      } finally { boton.disabled = false; }
    });
  }

  const exportar = document.getElementById("btn-exportar-integrador");
  if (exportar && !exportar.disabled) {
    exportar.addEventListener("click", async () => {
      exportar.disabled = true;
      try {
        const r = await Tortu.api("/api/proyectos-integradores/" + encodeURIComponent(proyecto.id) + "/exportar", {});
        const bin = atob(r.archivo);\n        const bytes = new Uint8Array(bin.length);\n        for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);\n        const blob = new Blob([bytes], { type: "application/zip" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url; a.download = r.nombre; a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      } catch (e) {
        mensaje(e?.datos?.mensaje || "Revisá tu conexión e intentá nuevamente.", "error");
      } finally { exportar.disabled = false; }
    });
  }
})();
