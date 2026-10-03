/* Zona Tortuga: el servidor devuelve la lista de órdenes; acá se animan en un <canvas>. */
"use strict";
const Lienzo = (() => {
  const VERDE = "#16a34a";
  const TAM = 600;
  const VISTA_INICIAL = Object.freeze({ escala: 1, cx: 0, cy: 0 });
  const GRIS_PARED = "#6b7280";
  const RADIO_SALIDA = 20;                  // igual que tortuscript/tortuga.py

  /** Estado puro de la tortuga (0° = arriba, giro a la derecha = horario). Sin DOM: testeable. */
  function nuevoEstado() {
    return { x: 0, y: 0, rumbo: 0, lapiz: true, color: VERDE, trazos: [] };
  }
  function destino(e, distancia) {
    const r = (e.rumbo * Math.PI) / 180;
    return { x: e.x + Math.sin(r) * distancia, y: e.y - Math.cos(r) * distancia };
  }
  /** Aplica una orden completa (sin animar). */
  function aplicar(e, orden) {
    switch (orden.o) {
      case "avanzar": case "retroceder": {
        const d = orden.o === "avanzar" ? orden.v : -orden.v;
        const p = destino(e, d);
        if (e.lapiz) e.trazos.push({ x1: e.x, y1: e.y, x2: p.x, y2: p.y, color: e.color });
        e.x = p.x; e.y = p.y;
        break;
      }
      case "girar_der": e.rumbo = (e.rumbo + orden.v) % 360; break;
      case "girar_izq": e.rumbo = (e.rumbo - orden.v) % 360; break;
      case "color": e.color = orden.v; break;
      case "bajar_lapiz": e.lapiz = true; break;
      case "subir_lapiz": e.lapiz = false; break;
    }
    return e;
  }

  /** Encuadre que hace entrar todos los dibujos (listas de órdenes) con un margen, sin pasarse de 2.4x
   *  (así una raya corta no se ve gigante). Incluye siempre el punto de partida. */
  function vistaPara(...listas) {
    let minX = 0, maxX = 0, minY = 0, maxY = 0;
    for (const ordenes of listas) {
      const e = nuevoEstado();
      for (const o of ordenes || []) aplicar(e, o);
      for (const t of e.trazos) {
        minX = Math.min(minX, t.x1, t.x2); maxX = Math.max(maxX, t.x1, t.x2);
        minY = Math.min(minY, t.y1, t.y2); maxY = Math.max(maxY, t.y1, t.y2);
      }
    }
    const extension = Math.max(maxX - minX, maxY - minY);
    if (extension <= 0) return VISTA_INICIAL;
    return { escala: Math.max(0.4, Math.min(2.4, 480 / extension)), cx: (minX + maxX) / 2, cy: (minY + maxY) / 2 };
  }

  /** Encuadre de un laberinto: entra entero, con margen (el mundo no cambia con el recorrido del chico). */
  function vistaLaberinto(lab) {
    let minX = 0, maxX = 0, minY = 0, maxY = 0;
    for (const [x1, y1, x2, y2] of lab.paredes) {
      minX = Math.min(minX, x1, x2); maxX = Math.max(maxX, x1, x2);
      minY = Math.min(minY, y1, y2); maxY = Math.max(maxY, y1, y2);
    }
    const extension = Math.max(maxX - minX, maxY - minY) || 1;
    return { escala: Math.max(0.4, Math.min(2.4, 480 / extension)), cx: (minX + maxX) / 2, cy: (minY + maxY) / 2 };
  }

  /** Paredes grises y la bandera de salida (ctx ya está en coordenadas del dibujo). */
  function dibujarLaberinto(ctx, lab, escala) {
    const [sx, sy] = lab.salida;
    ctx.fillStyle = "rgba(250, 204, 21, .35)";
    ctx.beginPath(); ctx.arc(sx, sy, RADIO_SALIDA, 0, 7); ctx.fill();
    ctx.strokeStyle = GRIS_PARED; ctx.lineWidth = 7 / escala; ctx.lineCap = "round";
    for (const [x1, y1, x2, y2] of lab.paredes) {
      ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
    }
    ctx.save(); ctx.translate(sx, sy); ctx.scale(1 / escala, 1 / escala);
    ctx.font = "44px sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";   // como la tortuga
    ctx.fillText("🏁", 0, 0);
    ctx.restore();
  }

  /** Color del cuerpo de la tortuga: el del nivel del chico (lo pone el servidor en <html>). El lápiz es otra cosa. */
  function colorCuerpo() {
    return document.documentElement.dataset.colorTortuga || VERDE;
  }

  /** La tortuga se dibuja con tamaño fijo en pantalla, sea cual sea el zoom (ctx ya está en coordenadas del dibujo). */
  function dibujarTortuga(ctx, e, escala) {
    ctx.save();
    ctx.translate(e.x, e.y);
    ctx.scale(1 / escala, 1 / escala);
    ctx.rotate((e.rumbo * Math.PI) / 180);
    ctx.fillStyle = colorCuerpo(); ctx.strokeStyle = "#0b3d1e"; ctx.lineWidth = 2;
    for (const [px, py] of [[-11, -9], [11, -9], [-11, 10], [11, 10]]) {   // patas
      ctx.beginPath(); ctx.arc(px, py, 5, 0, 7); ctx.fill(); ctx.stroke();
    }
    ctx.beginPath(); ctx.arc(0, -17, 6, 0, 7); ctx.fill(); ctx.stroke();      // cabeza
    ctx.beginPath(); ctx.ellipse(0, 0, 13, 17, 0, 0, 7); ctx.fill(); ctx.stroke();   // caparazón
    ctx.strokeStyle = "rgba(255,255,255,.55)"; ctx.beginPath();
    ctx.moveTo(-8, -4); ctx.lineTo(8, -4); ctx.moveTo(-8, 6); ctx.lineTo(8, 6); ctx.moveTo(0, -12); ctx.lineTo(0, 13); ctx.stroke();
    ctx.restore();
  }

  function crear(canvas) {
    const ctx = canvas.getContext("2d");
    let e = nuevoEstado();
    let vista = VISTA_INICIAL;
    let laberinto = null;                    // {paredes, salida} en los pasos de laberinto
    let ejecucion = 0;                       // se incrementa para cancelar una animación en curso

    function pintar(parcial) {
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, TAM, TAM);
      ctx.setTransform(vista.escala, 0, 0, vista.escala, TAM / 2 - vista.cx * vista.escala, TAM / 2 - vista.cy * vista.escala);
      if (laberinto) dibujarLaberinto(ctx, laberinto, vista.escala);
      ctx.lineCap = "round"; ctx.lineWidth = 3 / Math.max(1, vista.escala * 0.6 + 0.4);
      const trazos = parcial ? e.trazos.concat([parcial]) : e.trazos;
      for (const t of trazos) {
        ctx.strokeStyle = t.color; ctx.beginPath();
        ctx.moveTo(t.x1, t.y1); ctx.lineTo(t.x2, t.y2); ctx.stroke();
      }
      dibujarTortuga(ctx, e, vista.escala);
    }
    const esperar = (ms) => new Promise((r) => setTimeout(r, ms));
    function cuadro() { return new Promise((r) => requestAnimationFrame(r)); }

    /** Anima un movimiento o giro; `paso` = unidades por segundo. */
    async function animar(orden, vel, id) {
      const pxSeg = 60 + vel * vel * 40, gradosSeg = vel * 90;
      if (orden.o === "avanzar" || orden.o === "retroceder") {
        const total = Math.abs(orden.v), signo = orden.o === "avanzar" ? 1 : -1;
        const x0 = e.x, y0 = e.y, dur = (total / pxSeg) * 1000;
        const ini = performance.now();
        while (id === ejecucion) {
          const f = dur === 0 ? 1 : Math.min(1, (performance.now() - ini) / dur);
          const p = destino({ x: x0, y: y0, rumbo: e.rumbo }, signo * total * f);
          if (f >= 1) break;
          const guardado = [e.x, e.y]; e.x = p.x; e.y = p.y;
          pintar(e.lapiz ? { x1: x0, y1: y0, x2: p.x, y2: p.y, color: e.color } : null);
          e.x = guardado[0]; e.y = guardado[1];
          await cuadro();
        }
        if (id === ejecucion) aplicar(e, orden);
      } else if (orden.o === "girar_der" || orden.o === "girar_izq") {
        const signo = orden.o === "girar_der" ? 1 : -1, r0 = e.rumbo;
        const dur = (Math.abs(orden.v) / gradosSeg) * 1000, ini = performance.now();
        while (id === ejecucion) {
          const f = dur === 0 ? 1 : Math.min(1, (performance.now() - ini) / dur);
          if (f >= 1) break;
          e.rumbo = r0 + signo * orden.v * f; pintar(null);
          await cuadro();
        }
        e.rumbo = r0;
        if (id === ejecucion) aplicar(e, orden);
      } else {
        aplicar(e, orden);
      }
      if (id === ejecucion) pintar(null);
    }

    return {
      estado: () => e,
      /** Cambia el encuadre (ver vistaPara) y vuelve a pintar lo que hay. */
      usarVista(nueva) { vista = nueva || VISTA_INICIAL; pintar(null); },
      /** Muestra (o saca, con null) las paredes y la salida de un laberinto. */
      usarLaberinto(lab) { laberinto = lab || null; pintar(null); },
      /** Dibuja todas las órdenes de una vez (vista previa del objetivo). */
      dibujar(ordenes) {
        ejecucion++; e = nuevoEstado();
        for (const orden of ordenes) aplicar(e, orden);
        pintar(null);
      },
      reiniciar() { ejecucion++; e = nuevoEstado(); pintar(null); },
      detener() { ejecucion++; },
      /** Reproduce las órdenes. opciones: {velocidad 1-10, depurador, alLinea(n), alFinal()} */
      async reproducir(ordenes, opciones) {
        e = nuevoEstado();
        const id = ++ejecucion;
        const vel = opciones.velocidad || 5;
        pintar(null);
        for (const orden of ordenes) {
          if (id !== ejecucion) return false;
          if (opciones.depurador && opciones.alLinea) {
            opciones.alLinea(orden.l);
            await esperar(Math.max(60, 500 - vel * 45));
          }
          await animar(orden, vel, id);
        }
        if (id !== ejecucion) return false;
        if (opciones.alLinea) opciones.alLinea(null);
        return true;
      },
      pintar,
    };
  }

  return { crear, nuevoEstado, aplicar, destino, vistaPara, vistaLaberinto };
})();

(() => {
  if (!document.getElementById("lienzo")) return;
  const EJEMPLOS = [
    ["Cuadrado", "repetir 4 veces:\n    avanzar 100\n    girar_der 90"],
    ["Triángulo", 'color "azul"\nrepetir 3 veces:\n    avanzar 120\n    girar_der 120'],
    ["Estrella", 'color "naranja"\nrepetir 5 veces:\n    avanzar 150\n    girar_der 144'],
    ["Escalera", 'color "violeta"\nrepetir 6 veces:\n    avanzar 40\n    girar_izq 90\n    avanzar 40\n    girar_der 90'],
    ["Arcoíris", 'colores es ["rojo", "naranja", "amarillo", "verde", "celeste", "azul", "violeta"]\nlargo es 220\npara c en colores:\n    color c\n    avanzar largo\n    girar_der 90\n    largo es largo - 25'],
    ["Línea punteada", "repetir 8 veces:\n    avanzar 20\n    subir_lapiz\n    avanzar 20\n    bajar_lapiz"],
  ];
  const canvas = document.getElementById("lienzo");
  const lienzo = Lienzo.crear(canvas);
  window.lienzoTortuga = lienzo;
  const { editor } = Tortu.crearEditores(dibujar);
  Proyectos.iniciar("tortuga", editor);
  const btn = document.getElementById("btn-ejecutar");
  const btnDetener = document.getElementById("btn-detener");
  const chkDepurador = document.getElementById("chk-depurador");
  const velocidad = document.getElementById("velocidad");
  let lineaMarcada = null;

  const caja = document.getElementById("ejemplos");
  for (const [nombre, codigo] of EJEMPLOS) {
    const b = document.createElement("button");
    b.type = "button"; b.className = "boton chico celeste"; b.textContent = nombre;
    b.addEventListener("click", () => { editor.setValue(codigo); editor.focus(); });
    caja.appendChild(b);
  }

  function marcarLinea(n) {
    if (lineaMarcada !== null) editor.removeLineClass(lineaMarcada, "background", "linea-actual");
    lineaMarcada = null;
    if (n) { lineaMarcada = n - 1; editor.addLineClass(lineaMarcada, "background", "linea-actual"); }
  }

  function ocupado(si) {
    btn.disabled = si; btnDetener.disabled = !si;
  }

  async function dibujar() {
    if (btn.disabled) return;
    const codigo = editor.getValue();
    Tortu.limpiarResultado();
    if (!codigo.trim()) {
      Tortu.veredicto("info", "⚠️ Escribí algo primero", [["mensaje", "Probá con un ejemplo de arriba o escribí:  avanzar 100"]]);
      return;
    }
    ocupado(true);
    try {
      const r = await Tortu.ejecutarConPreguntas("/api/tortuga", { codigo });
      Tortu.mostrarConsola(r);
      if (r.cancelado) { Tortu.veredicto("info", "✋ Cancelaste la pregunta", []); return; }
      const terminó = await lienzo.reproducir(r.ordenes || [], {
        velocidad: Number(velocidad.value), depurador: chkDepurador.checked, alLinea: marcarLinea,
      });
      marcarLinea(null);
      if (!terminó) Tortu.veredicto("info", "⏹ Frenaste el dibujo", []);
      else if (r.error) { Tortu.veredicto("error", "🔧 Hay algo para arreglar", [["mensaje", r.mensaje]]); Tortu.tocar("error"); }
      else { Tortu.veredicto("bien", "✅ ¡Dibujo completado!", []); Tortu.tocar("success"); }
    } catch (e) {
      Tortu.veredicto("error", "😵 No pude comunicarme con TortuScript", [["mensaje", e?.datos?.mensaje || "Revisá tu conexión e intentá nuevamente."]]);
    } finally {
      ocupado(false);
    }
  }

  btn.addEventListener("click", dibujar);
  btnDetener.addEventListener("click", () => { lienzo.detener(); });
  document.getElementById("btn-limpiar").addEventListener("click", () => {
    lienzo.reiniciar(); marcarLinea(null);
    editor.setValue(""); Tortu.limpiarResultado();
    document.getElementById("consola").textContent = "";
    editor.focus();
  });
  lienzo.reiniciar();
})();
