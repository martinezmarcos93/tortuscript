/* Página de Juegos: pide el árbol al servidor, lo corre en un Web Worker (intérprete TortuGame) y anima el registro.
 * El código del chico nunca se ejecuta en esta página: solo en el Worker, que no ve la página ni la red. */
"use strict";
(() => {
  const EJEMPLOS = [
    ["⚔️ Combate", 'escena("bosque")\nh es heroe("Tharok", 30, 5)\nb es enemigo("Bug", 20, 2)\nmision("Vencé al Bug del bosque")\n' +
      'mientras vivo(b) y vivo(h):\n    atacar(h, b)\n    si vivo(b):\n        atacar(b, h)\nsi vivo(h):\n    ganar("¡Salvaste el bosque!")\n' +
      'sino:\n    perder("El Bug ganó esta vez")'],
    ["❓ Decisiones", 'escena("cueva")\nh es heroe("Lua", 20, 4)\nd es enemigo("Dragón", 40, 6)\n' +
      'respuesta es preguntar("¿Peleás o huís? ")\nsi respuesta == "peleo":\n    mientras vivo(d) y vivo(h):\n        atacar(h, d)\n' +
      '        atacar(d, h)\n    si vivo(h):\n        ganar("¡Venciste al dragón!")\n    sino:\n        perder("El dragón era muy fuerte")\n' +
      'sino:\n    decir(h, "Mejor vuelvo otro día")\n    ganar("Huiste a tiempo")'],
    ["🎒 Inventario", 'escena("aldea")\nh es heroe("Kira", 25, 3)\nmision("Juntá la llave y el mapa")\ndar(h, "llave")\n' +
      'dar(h, "mapa")\nmover(h, 5, 1)\nsi tiene(h, "llave") y tiene(h, "mapa"):\n    decir(h, "¡Tengo todo!")\n    ganar("¡Misión cumplida!")'],
  ];
  const TIEMPO_MAX = 3000;                                        // después, el Worker se termina (modelo de amenazas A7)
  const config = JSON.parse(document.getElementById("juego-config").textContent);
  const canvas = document.getElementById("escena");
  const escena = Escena.crear(canvas, document.getElementById("registro-juego"));
  const { editor } = Tortu.crearEditores(jugar);
  Proyectos.iniciar("juego", editor);
  const btn = document.getElementById("btn-ejecutar");
  const btnDetener = document.getElementById("btn-detener");
  let worker = null, lineaMarcada = null;

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
  function terminarWorker() { if (worker) { worker.terminate(); worker = null; } }

  /** Corre el árbol en un Worker nuevo, con tope de tiempo. */
  function correr(arbol, semilla, entradas) {
    return new Promise((resolver) => {
      terminarWorker();
      worker = new Worker(config.worker);
      const reloj = setTimeout(() => {
        terminarWorker();
        resolver({ eventos: [], error: true, mensaje: "⏱️ Tu juego tardó demasiado y lo frenamos\n\n💡 ¿Hay un mientras que no termina?", linea: null, pregunta: null });
      }, TIEMPO_MAX);
      worker.onmessage = (ev) => { clearTimeout(reloj); terminarWorker(); resolver(ev.data); };
      worker.onerror = () => { clearTimeout(reloj); terminarWorker();
        resolver({ eventos: [], error: true, mensaje: "😵 El juego se trabó. Probá de nuevo.", linea: null, pregunta: null }); };
      worker.postMessage({ arbol, semilla, entradas });
    });
  }

  async function jugar() {
    if (btn.disabled) return;
    Tortu.limpiarResultado(); marcarLinea(null);
    const codigo = editor.getValue();
    if (!codigo.trim()) { Tortu.veredicto("info", "⚠️ Escribí tu juego primero", [["mensaje", "Probá con un ejemplo de arriba."]]); return; }
    btn.disabled = true; btnDetener.disabled = false;
    try {
      const r = await Tortu.api("/api/juego/arbol", { codigo });
      if (!r.ok) { marcarLinea(r.linea); Tortu.veredicto("error", "🔧 Hay algo para arreglar", [["mensaje", r.mensaje]]); Tortu.tocar("error"); return; }
      const semilla = Math.floor(Math.random() * 2 ** 31);          // otra partida cada vez; la misma si pregunta algo
      const entradas = [];
      let resultado;
      for (let vuelta = 0; vuelta < 30; vuelta++) {
        resultado = await correr(r.arbol, semilla, entradas);
        if (resultado.pregunta === null || resultado.pregunta === undefined || resultado.error) break;
        const respuesta = await Tortu.pedirRespuesta(resultado.pregunta);
        if (respuesta === null) { Tortu.veredicto("info", "✋ Cancelaste la pregunta", []); return; }
        entradas.push(respuesta);
      }
      const rapido = document.documentElement.dataset.movimiento === "reducido";
      const termino = await escena.reproducir(resultado.eventos, { rapido });
      if (!termino) { Tortu.veredicto("info", "⏹ Frenaste el juego", []); return; }
      if (resultado.error) { marcarLinea(resultado.linea); Tortu.veredicto("error", "🔧 Hay algo para arreglar", [["mensaje", resultado.mensaje]]); Tortu.tocar("error"); return; }
      const fin = resultado.eventos.find((e) => e.t === "fin");
      if (fin && fin.gano) { Tortu.veredicto("bien", `🏆 ${fin.texto}`, []); Tortu.tocar("success"); Tortu.celebrar(true); }
      else if (fin) Tortu.veredicto("info", `💀 ${fin.texto}`, [["mensaje", "¡Probá otra vez o cambiá tu estrategia!"]]);
      else Tortu.veredicto("info", "✅ Tu juego terminó", [["mensaje", "Tip: usá ganar(\"…\") o perder(\"…\") para ponerle un final."]]);
    } catch (e) {
      Tortu.veredicto("error", "😵 No pude comunicarme con TortuScript", [["mensaje", (e?.datos?.mensaje || "Revisá tu conexión e intentá nuevamente.")]]);
    } finally {
      btn.disabled = false; btnDetener.disabled = true;
    }
  }

  btn.addEventListener("click", jugar);
  btnDetener.addEventListener("click", () => { terminarWorker(); escena.detener(); });
  escena.reiniciar();
})();
