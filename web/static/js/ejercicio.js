/* Página de un ejercicio. */
"use strict";
(() => {
  const cab = document.querySelector(".cabecera-ej");
  const n = Number(cab.dataset.n);
  const total = Number(cab.dataset.total);
  let completado = cab.dataset.completado === "si";
  let pistas = 0;
  const { editor, python } = Tortu.crearEditores(ejecutar);
  const botonVoz = document.getElementById("btn-voz");
  if (botonVoz && Tortu.hayVoz) {                            // escuchar la consigna
    const consigna = () => document.querySelector(".consigna").textContent.replace("📋", "").trim();
    botonVoz.hidden = false;
    botonVoz.addEventListener("click", () => Tortu.leer(consigna()));
    if (Tortu.leerSolo()) Tortu.leer(consigna());
  }
  const btnEjecutar = document.getElementById("btn-ejecutar");

  async function ejecutar() {
    btnEjecutar.disabled = true;
    Tortu.limpiarResultado();
    try {
      const r = await Tortu.ejecutarConPreguntas(`/api/ejercicios/${n}/evaluar`, { codigo: editor.getValue() });
      Tortu.mostrarConsola(r);
      if (r.python !== undefined && r.python !== "") python.setValue(r.python);
      mostrarVeredicto(r);
      Tortu.actualizarEstado(r.estado_juego);
      Tortu.avisos(r.avisos);
    } catch (e) {
      Tortu.veredicto("error", "😵 No pude comunicarme con TortuScript", [["mensaje", String(e)]]);
    } finally {
      btnEjecutar.disabled = false;
    }
  }

  function mostrarVeredicto(r) {
    if (r.cancelado) {
      Tortu.veredicto("info", "✋ Cancelaste la pregunta", [["mensaje", "Tocá Ejecutar para volver a empezar."]]);
      return;
    }
    if (r.error) {
      Tortu.veredicto("error", "🔧 Hay algo para arreglar", [["mensaje", r.mensaje]]);
      Tortu.tocar("error");
      return;
    }
    const ev = r.evaluacion || {};
    if (ev.estado === "falta_preguntar") {
      Tortu.veredicto("info", "✏️ Este ejercicio pide usar preguntar", [["mensaje", "Así la persona que usa tu programa puede escribir el dato."]]);
    } else if (ev.estado === "sin_salida") {
      Tortu.veredicto("info", "🤫 Tu programa no mostró nada", [["mensaje", "Recordá usar mostrar para ver el resultado."]]);
    } else if (ev.estado === "incorrecto") {
      Tortu.tocar("error");
      Tortu.veredicto("casi", "🤔 ¡Casi! Tu programa corre, pero muestra otra cosa", [
        ["mensaje", "Se esperaba:"], ["codigo", ev.esperado],
        ["mensaje", "Compará línea por línea con lo que mostró tu programa (arriba). Mayúsculas, tildes y espacios entre palabras cuentan."],
      ]);
    } else if (ev.estado === "correcto") {
      const p = r.premio || {};
      const partes = [];
      if (p.mejora) partes.push(["premio", `${"⭐".repeat(p.estrellas)}${"☆".repeat(3 - p.estrellas)}  +${p.xp} XP`]);
      else partes.push(["mensaje", "Ya tenías este resultado guardado. ¡Igual, bien hecho!"]);
      if (p.sube_nivel) partes.push(["premio", `🎉 ¡Subiste a ${r.estado_juego.titulo}!`]);
      if (n < total) partes.push(["mensaje", "Tocá Siguiente ➡ para seguir."]);
      Tortu.veredicto("bien", "✅ ¡Correcto! Es justo lo que pedía el ejercicio", partes);
      if (p.mejora) {
        document.getElementById("estrellas-ej").textContent = "⭐".repeat(p.estrellas) + "☆".repeat(3 - p.estrellas);
        Tortu.celebrar(p.sube_nivel);
        Tortu.tocar(p.sube_nivel ? "level_up" : "success");
      }
      completado = true;
    }
  }

  async function pista() {
    const botonPista = document.getElementById("btn-pista");
    botonPista.disabled = true;
    try {
      const r = await Tortu.api(`/api/ejercicios/${n}/pista`, {});
      pistas = r.nivel;
      const caja = document.getElementById("pista-caja");
      caja.textContent = "";
      const div = document.createElement("div");
      div.className = "veredicto info pista-caja";
      const h = document.createElement("h3");
      h.textContent = `💡 Pista ${r.nivel}: ${r.titulo}`;
      div.appendChild(h);
      for (const [clave, tipo] of [["texto", "div"], ["codigo", "pre"], ["python", "pre"]]) {
        if (!r[clave]) continue;
        if (clave === "python") { const t = document.createElement("div"); t.textContent = "🐍 En Python:"; div.appendChild(t); }
        const el = document.createElement(tipo);
        el.textContent = r[clave];
        div.appendChild(el);
      }
      const aviso = document.createElement("div");
      aviso.className = "tenue";
      aviso.textContent = r.nivel >= 3 ? "Con la solución a la vista, este ejercicio vale 1 estrella."
                                       : "Cada pista que ves vale una estrella menos.";
      div.appendChild(aviso);
      caja.appendChild(div);
      document.getElementById("pista-n").textContent = r.nivel >= 3 ? "(vista)" : `(${r.nivel + 1}/3)`;
    } catch (e) {
      Tortu.veredicto("error", "No se pudo cargar la pista", [[
        "mensaje", e?.datos?.mensaje || "Revisá tu conexión e intentá nuevamente."
      ]]);
    } finally {
      botonPista.disabled = pistas >= 3;
    }
  }

  btnEjecutar.addEventListener("click", ejecutar);
  document.getElementById("btn-pista").addEventListener("click", pista);
  document.getElementById("btn-limpiar").addEventListener("click", () => { editor.setValue(""); editor.focus(); });
  const sig = document.getElementById("btn-siguiente");
  if (sig) sig.addEventListener("click", (ev) => {
    if (!completado) {
      ev.preventDefault();
      Tortu.veredicto("info", "🔒 Primero resolvé este ejercicio", [["mensaje", "Cuando tu programa muestre lo que pide la consigna, se desbloquea el siguiente."]]);
    }
  });
})();
