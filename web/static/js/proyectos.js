/* Mis proyectos: guardar el código de Experimentar o de la Zona Tortuga, y la lista para abrir, duplicar o borrar. */
"use strict";
const Proyectos = (() => {
  /** Pide un nombre en la ventana de la página. Devuelve la promesa con el texto o null si se cancela. */
  function pedirNombre() {
    const modal = document.getElementById("modal-nombre");
    const campo = document.getElementById("nm-campo");
    const error = document.getElementById("nm-error");
    campo.value = ""; error.textContent = ""; modal.hidden = false;
    setTimeout(() => campo.focus(), 30);
    return new Promise((resolver) => {
      const ok = document.getElementById("nm-ok"), cancelar = document.getElementById("nm-cancelar");
      const cerrar = (valor) => {
        modal.hidden = true;
        ok.onclick = cancelar.onclick = campo.onkeydown = null;
        resolver(valor);
      };
      ok.onclick = () => {
        if (!campo.value.trim()) { error.textContent = "Ponele un nombre a tu proyecto."; return; }
        cerrar(campo.value.trim());
      };
      cancelar.onclick = () => cerrar(null);
      campo.onkeydown = (ev) => {
        if (ev.key === "Enter") { ev.preventDefault(); ok.click(); }
        else if (ev.key === "Escape") { ev.preventDefault(); cerrar(null); }
      };
    });
  }

  function mensaje(titulo, detalle) {
    Tortu.avisos([{ tipo: "mensaje", titulo, detalle }]);
  }

  /** Conecta el botón Guardar de una página con su editor. */
  function iniciar(tipo, editor) {
    const nodo = document.getElementById("proyecto-actual");
    const actual = nodo ? JSON.parse(nodo.textContent) : null;
    let id = actual ? actual.id : null;
    let nombre = actual ? actual.nombre : null;
    if (actual) editor.setValue(actual.codigo);
    const boton = document.getElementById("btn-guardar");
    const etiqueta = document.getElementById("proyecto-nombre");

    function pintarNombre() {
      etiqueta.textContent = "";
      if (!nombre) return;
      etiqueta.append("Proyecto: ");
      const b = document.createElement("b"); b.textContent = nombre; etiqueta.appendChild(b);
    }

    async function guardar(nombreElegido) {
      boton.disabled = true;
      try {
        const r = await Tortu.api("/api/proyectos", { id, nombre: nombreElegido || nombre, tipo, codigo: editor.getValue() });
        id = r.id; nombre = nombreElegido || nombre;
        pintarNombre();
        history.replaceState(null, "", `?proyecto=${id}`);
        Tortu.actualizarEstado(r.estado_juego);
        mensaje("💾 ¡Guardado!", nombre);
        Tortu.avisos(r.avisos);
      } catch (e) {
        mensaje("😵 No se pudo guardar", e?.datos?.mensaje || "Revisá tu conexión e intentá nuevamente.");
      } finally { boton.disabled = false; }
    }

    boton.addEventListener("click", async () => {
      if (id) { await guardar(); return; }
      const elegido = await pedirNombre();
      if (elegido) await guardar(elegido);
    });
    document.addEventListener("keydown", (ev) => {           // Ctrl+S guarda, como en cualquier editor
      if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === "s") { ev.preventDefault(); boton.click(); }
    });
    pintarNombre();
  }

  /** La lista de /proyectos: duplicar y borrar. */
  function iniciarLista() {
    for (const b of document.querySelectorAll("[data-accion]")) {
      b.addEventListener("click", async () => {
        const { accion, id, nombre } = b.dataset;
        if (accion === "borrar" && !window.confirm(`¿Borrar «${nombre}»? No se puede deshacer.`)) return;
        try {
          await Tortu.api(`/api/proyectos/${id}/${accion}`, {});
          location.reload();
        } catch (e) {
          mensaje("😵 No se pudo", e?.datos?.mensaje || "Revisá tu conexión e intentá nuevamente.");
        }
      });
    }
  }

  if (document.querySelector("[data-lista-proyectos]")) iniciarLista();   // página /proyectos (sin script inline)
  return { iniciar, iniciarLista };
})();
