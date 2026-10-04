/* Zona de experimentación: ejecutar sin evaluar. */
"use strict";
(() => {
  const EJEMPLOS = [
    ["Hola mundo", 'mostrar "Hola mundo"'],
    ["Variable", 'nombre es "Lua"\nmostrar nombre'],
    ["Suma", "a es 5\nb es 3\nmostrar a + b"],
    ["Pregunta", 'nombre es preguntar("¿Cómo te llamás? ")\nmostrar "Hola " + nombre'],
    ["Condicional", 'edad es 13\nsi edad > 10:\n    mostrar "Grande"\nsino:\n    mostrar "Chico"'],
    ["Repetir", 'repetir 5 veces:\n    mostrar "Hola"'],
    ["Función", 'funcion saludar(nombre):\n    mostrar "Hola " + nombre\n\nsaludar("Lua")'],
  ];
  const { editor, python } = Tortu.crearEditores(ejecutar);
  Proyectos.iniciar("experimentar", editor);
  const btn = document.getElementById("btn-ejecutar");
  const caja = document.getElementById("ejemplos");
  for (const [nombre, codigo] of EJEMPLOS) {
    const b = document.createElement("button");
    b.type = "button"; b.className = "boton chico celeste"; b.textContent = nombre;
    b.addEventListener("click", () => { editor.setValue(codigo); editor.focus(); });
    caja.appendChild(b);
  }

  async function ejecutar() {
    btn.disabled = true;
    Tortu.limpiarResultado();
    try {
      const r = await Tortu.ejecutarConPreguntas("/api/ejecutar", { codigo: editor.getValue() });
      Tortu.mostrarConsola(r);
      if (r.python) python.setValue(r.python);
      if (r.cancelado) Tortu.veredicto("info", "✋ Cancelaste la pregunta", []);
      else if (r.error) { Tortu.veredicto("error", "🔧 Hay algo para arreglar", [["mensaje", r.mensaje]]); Tortu.tocar("error"); }
      else if (r.tipo === "python") Tortu.veredicto("info", "🐍 Detecté Python directo: lo ejecuté sin traducir", []);
    } catch (e) {
      Tortu.veredicto("error", "😵 No pude comunicarme con TortuScript", [["mensaje", e?.datos?.mensaje || "Revisá tu conexión e intentá nuevamente."]]);
    } finally {
      btn.disabled = false;
    }
  }
  btn.addEventListener("click", ejecutar);
  document.getElementById("btn-limpiar").addEventListener("click", () => { editor.setValue(""); editor.focus(); });
})();
