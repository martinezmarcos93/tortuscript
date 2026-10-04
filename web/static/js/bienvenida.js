/* Bienvenida: nombre → experiencia (y, si ya programó, dónde empezar) → meta diaria. Un POST al final. */
"use strict";
(() => {
  const paso = (n) => document.querySelector(`.paso-bv[data-paso="${n}"]`);
  const nombre = document.getElementById("bv-nombre");
  const error = document.getElementById("bv-error");
  const errorFinal = document.getElementById("bv-error-final");
  const respuestas = { experiencia: null, entrada: "", meta_min: 10 };
  const bloqueEntrada = document.getElementById("bv-entrada");
  const bloquePrueba = document.getElementById("bv-prueba");
  const opcionPrueba = bloqueEntrada.querySelector("[data-prueba]");
  const textoPrueba = opcionPrueba.innerHTML;
  const prueba = [];                     // respuestas de la prueba de nivel (ADR-004), por pregunta

  function elegir(grupo, boton) {
    for (const x of grupo.querySelectorAll(".opcion-paso")) {
      x.classList.toggle("elegida", x === boton);
      x.setAttribute("aria-checked", String(x === boton));
    }
  }

  /** Quien ya programó puede elegir empezar más adelante (ADR-004); "desde el principio" queda elegido. */
  function mostrarEntrada(experiencia) {
    const opcion = bloqueEntrada.querySelector(`[data-para="${experiencia}"]:not([data-prueba])`);
    for (const b of bloqueEntrada.querySelectorAll("[data-para]")) b.hidden = b.dataset.para !== experiencia;
    bloqueEntrada.hidden = !opcion;
    bloquePrueba.hidden = true;
    opcionPrueba.dataset.valor = ""; opcionPrueba.innerHTML = textoPrueba;
    elegir(bloqueEntrada.querySelector('[role="radiogroup"]'), bloqueEntrada.querySelector('[data-valor=""]'));
    respuestas.entrada = "";
  }

  function ir(n) {
    for (const i of [1, 2, 3]) paso(i).hidden = i !== n;
    document.getElementById("bv-barra").style.width = `${Math.round(100 * n / 3)}%`;
    document.getElementById("bv-contador").textContent = `${n} / 3`;
    document.getElementById("bv-progreso").setAttribute("aria-valuenow", String(n));
    const foco = paso(n).querySelector("input, .opcion-paso[aria-checked='true'], .opcion-paso");
    if (foco) foco.focus();
  }

  // opciones tipo radio: una sola elegida por grupo
  for (const grupo of document.querySelectorAll('[role="radiogroup"]')) {
    grupo.addEventListener("click", (ev) => {
      const b = ev.target.closest(".opcion-paso");
      if (!b) return;
      elegir(grupo, b);
      const campo = grupo.dataset.campo;
      if (campo === "experiencia") {
        respuestas.experiencia = b.dataset.valor; document.getElementById("bv-sig-2").disabled = false;
        mostrarEntrada(b.dataset.valor);
      } else if (campo === "entrada") {
        respuestas.entrada = b.dataset.valor;
        bloquePrueba.hidden = !b.hasAttribute("data-prueba") || Boolean(b.dataset.valor);
      } else if (campo === "prueba") {
        prueba[Number(grupo.dataset.indice)] = b.dataset.valor;
        const total = bloquePrueba.querySelectorAll('[data-campo="prueba"]').length;
        document.getElementById("bv-corregir").disabled = prueba.filter((x) => x !== undefined).length < total;
      } else respuestas.meta_min = Number(b.dataset.valor);
    });
  }
  document.querySelector('[data-campo="meta_min"] [data-valor="10"]').classList.add("elegida");

  document.getElementById("bv-sig-1").addEventListener("click", () => {
    error.textContent = "";
    if (nombre.value.trim() && !/[A-Za-z0-9ñáéíóúüÑÁÉÍÓÚÜ]/.test(nombre.value)) {
      error.textContent = "Usá letras o números para el nombre."; return;
    }
    ir(2);
  });
  nombre.addEventListener("keydown", (ev) => { if (ev.key === "Enter") document.getElementById("bv-sig-1").click(); });
  document.getElementById("bv-corregir").addEventListener("click", async () => {
    const resultado = document.getElementById("bv-resultado");
    try {
      const r = await Tortu.api("/api/diagnostico", { respuestas: prueba });
      opcionPrueba.dataset.valor = r.entrada;
      opcionPrueba.textContent = `⏩ En «${r.seccion}» (lección ${r.numero}, según tu prueba)`;
      respuestas.entrada = r.entrada;
      bloquePrueba.hidden = true;
      resultado.textContent = "";
    } catch (e) { resultado.textContent = "No se pudo corregir la prueba. Podés empezar desde el principio."; }
  });
  document.getElementById("bv-sig-2").addEventListener("click", () => ir(3));

  document.getElementById("bv-empezar").addEventListener("click", async () => {
    const boton = document.getElementById("bv-empezar");
    boton.disabled = true; errorFinal.textContent = "";
    try {
      const r = await Tortu.api("/api/onboarding", {
        nombre: nombre.value.trim(), experiencia: respuestas.experiencia, meta_min: respuestas.meta_min,
        entrada: respuestas.entrada || undefined,
      });
      if (r.ok) {
        location.href = "/";
      } else {
        errorFinal.textContent = r.mensaje || "No pude guardar tus respuestas. Revisá los datos y probá de nuevo.";
        boton.disabled = false;
      }
    } catch (e) {
      const mensaje = e?.datos?.mensaje || "No pude guardar tus respuestas. Revisá el nombre y probá de nuevo.";
      errorFinal.textContent = mensaje;
      boton.disabled = false;
      ir(3);
    }
  });
  nombre.focus();
})();
