import sys
"""TortuGame: API de referencia (Python), árbol con lista blanca y CONFORMIDAD con el intérprete JS.

La conformidad corre los mismos programas en Python (tortuscript/tortugame.py) y en JS (web/static/js/tortugame/
interprete.js, con Node) y exige el mismo registro de eventos, el mismo error y la misma pregunta pendiente.
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

from tortuscript.executor import CodigoNoPermitido
from tortuscript.juego_ast import arbol_del_juego
from tortuscript.tortugame import Azar, Partida, correr_juego, sin_lineas

RAIZ = Path(__file__).resolve().parent.parent

# Programas de conformidad: (fuente, semilla, entradas). Cubren la API y las reglas de Python que imita el intérprete.
CORPUS = [
    ('escena("bosque")\nh es heroe("Tharok", 30, 5)\nb es enemigo("Bug", 20, 2)\nmision("Vencé al Bug")\n'
     'mientras vivo(b):\n    atacar(h, b)\n    si vivo(b):\n        atacar(b, h)\nsi vivo(h):\n    ganar("¡Salvaste el bosque!")\n'
     'sino:\n    perder("El Bug ganó")\nmostrar "esto no aparece"', 2026, []),
    ('h es heroe("Lua", 10, 1)\nrepetir 5 veces:\n    mostrar dado(6), dado(20), dado()', 7, []),
    ('h es heroe("Lua", 50, 1)\nh.vida es h.vida - 45\ncurar(h, 100)\nmostrar h.vida, h.vida_max\nh.vida es 80\nmostrar h.vida_max', 1, []),
    ('h es heroe("Ana", 10, 3)\ndar(h, "espada")\ndar(h, "poción")\nmostrar h.inventario, tiene(h, "espada"), tiene(h, "arco")\n'
     'h.inventario.append("mapa")\nmostrar len(h.inventario), h.inventario.pop(), h.inventario.pop(0)', 1, []),
    ('h es heroe("Kim", 10, 1)\nmover(h, 7, 4)\nmover(h, 0, 0)\ndecir(h, "¡Hola!")\nh.nombre es "Kimi"\nmostrar h', 3, []),
    ('funcion golpe(a, b):\n    d es atacar(a, b)\n    si d > 7:\n        devolver "fuerte"\n    devolver "suave"\n\n'
     'h es heroe("Ro", 40, 4)\ne es enemigo("Orco", 40, 3)\nrepetir 4 veces:\n    mostrar golpe(h, e), e.vida', 11, []),
    ('mostrar 7 / 2, 6 / 2, 7 // 2, -7 // 2, 7 % 3, -7 % 3, 2 ** 10, 2 ** -1, 0.1 + 0.2, 1 / 3', 1, []),
    ('mostrar 1e-05, 0.0001, 1e16, 123456789.5, -0.5, 3 * 1.5, 10 - 2.5, round(2.5), round(3.5), round(2.6)', 1, []),
    ('mostrar abs(-3), abs(-2.5), min(4, 2, 8), max([3, 9, 1]), sum([1, 2, 3]), sum([0.5, 1]), int("42"), int(3.9), float(2)', 1, []),
    ('a es [1, 2] + [3]\nb es [0] * 3\nmostrar "ab" + "cd", "ja" * 3, a, b', 1, []),
    ('print("a" in "casa", 2 in [1, 2], 5 not in [1, 2], "z" in "casa")', 1, []),         # Python: `en` no es TortuScript
    ('mostrar 1 < 2 < 3, 3 > 2 > 5, "a" < "b", 1 == 1.0, verdadero == 1, [1, 2] == [1, 2], 2 != 3', 1, []),
    ('mostrar 0 o "x", "" o 0, 3 y 4, 0 y 5, no 0, no [1]', 1, []),
    ('l es [5, 3, 8]\nl[0] es 1\nl[-1] es 9\nmostrar l, l[1], l[-2], len("hola")\npara x en "ab":\n    mostrar x', 1, []),
    ('total es 0\npara n en range(1, 11):\n    si n % 2 == 0:\n        seguir\n    si n > 7:\n        cortar\n    total es total + n\n'
     'mostrar total, range(3), range(10, 0, -3)', 1, []),
    ('a es [1, "a", verdadero, 2.0]\nb es ["it\'s"]\nc es ["x\\ny"]\nmostrar a, b, c', 1, []),
    ('nombre es preguntar("¿Tu nombre? ")\nh es heroe(nombre, 20, 2)\nmostrar "Hola", h', 5, ["Lua"]),
    ('nombre es preguntar("¿Tu nombre? ")\nh es heroe(nombre, 20, 2)', 5, []),
    ('a es preguntar("¿Atacás? ")\nh es heroe("H", 20, 2)\ne es enemigo("E", 10, 1)\nsi a == "si":\n    atacar(h, e)\nmostrar e.vida',
     9, ["si"]),
    ('h es heroe("A", 10, 1)\nh2 es heroe("B", 10, 1)', 1, []),
    ('escena("luna")', 1, []),
    ('h es heroe("", 10, 1)', 1, []),
    ('h es heroe("A", 0, 1)', 1, []),
    ('h es heroe("A", 10, 1)\nmover(h, 8, 0)', 1, []),
    ('h es heroe("A", 10, 1)\natacar(h, 5)', 1, []),
    ('mostrar x', 1, []),
    ('mostrar 1 / 0', 1, []),
    ('l es [1, 2]\nmostrar l[5]', 1, []),
    ('mostrar "a" + 1', 1, []),
    ('mostrar int("hola")', 1, []),
    ('vida es 10\nfuncion bajar():\n    vida es vida - 1\n\nbajar()', 1, []),
    ('funcion f(n):\n    devolver f(n + 1)\n\nf(0)', 1, []),
    ('h es heroe("A", 10, 1)\nh.vida es "mucha"', 1, []),
    ('h es heroe("A", 10, 1)\nmientras verdadero:\n    decir(h, "otra vez")', 1, []),
]


def js_disponible():
    return shutil.which("node") is not None


def correr_en_js(pedidos):
    r = subprocess.run(["node", str(RAIZ / "tests/js/correr_juegos.mjs")], input=json.dumps(pedidos),
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise AssertionError(r.stderr[-2000:])
    return json.loads(r.stdout)


@unittest.skipUnless(js_disponible(), "Node no está instalado")
class TestConformidadPythonJS(unittest.TestCase):
    """El juego se juega con el intérprete JS y se evalúa con Python: tienen que coincidir."""

    @classmethod
    def setUpClass(cls):
        cls.python = [correr_juego(f, s, e) for f, s, e in CORPUS]
        cls.js = correr_en_js([{"arbol": arbol_del_juego(f), "semilla": s, "entradas": e} for f, s, e in CORPUS])

    def test_mismo_registro_error_y_pregunta(self):
        for (fuente, _, _), py, js in zip(CORPUS, self.python, self.js):
            with self.subTest(fuente[:60]):
                self.assertEqual(sin_lineas(js["eventos"]), sin_lineas(py["eventos"]))
                self.assertEqual(js["error"], py["error"], (py["mensaje"][:120], js["mensaje"][:120]))
                self.assertEqual(js["pregunta"], py["pregunta"])

    def test_mismas_lineas_en_eventos_y_errores(self):
        """Los errores señalan la misma línea. En los eventos, una diferencia a propósito: después de que una función
        devuelve, JS marca la línea que la llamó (mejor para resaltar) y Python la última de adentro de la función
        (su rastreador solo avisa al empezar una línea). La evaluación no compara líneas."""
        for (fuente, _, _), py, js in zip(CORPUS, self.python, self.js):
            with self.subTest(fuente[:60]):
                if py["error"]:
                    if sys.version_info < (3, 10) and "RecursionError" in py["mensaje"]:
                        # CPython 3.9 puede atribuir el límite de recursión a la línea de definición
                        # en vez de la llamada recursiva; la diferencia esperable es como máximo 1 línea.
                        self.assertLessEqual(abs(js["linea"] - py["linea"]), 1)
                    else:
                        self.assertEqual(js["linea"], py["linea"])
                if "funcion" not in fuente:
                    self.assertEqual([e["l"] for e in js["eventos"]], [e["l"] for e in py["eventos"]])

    def test_el_corpus_prueba_errores_y_preguntas(self):
        self.assertGreaterEqual(sum(r["error"] for r in self.python), 10)
        self.assertTrue(any(r["pregunta"] for r in self.python))


class TestReferencia(unittest.TestCase):
    def test_azar_determinista(self):
        a, b = Azar(2026), Azar(2026)
        self.assertEqual([a.dado(6) for _ in range(20)], [b.dado(6) for _ in range(20)])
        self.assertTrue(all(1 <= Azar(s).dado(6) <= 6 for s in range(200)))

    def test_ganar_termina_el_registro(self):
        r = correr_juego('ganar("¡Bien!")\nmostrar "no"', 1)
        self.assertEqual(sin_lineas(r["eventos"]), [{"t": "fin", "gano": True, "texto": "¡Bien!"}])

    def test_topes(self):
        self.assertTrue(correr_juego('repetir 60 veces:\n    enemigo("E", 1, 1)', 1)["error"])
        r = correr_juego('h es heroe("A", 10, 1)\nmientras verdadero:\n    decir(h, "x")', 1)
        self.assertTrue(r["error"])
        self.assertIn("demasiadas cosas", r["mensaje"])

    def test_lo_interno_del_personaje_no_se_toca(self):
        for mal in ('h es heroe("A", 10, 1)\nmostrar h._partida', 'h es heroe("A", 10, 1)\nh._vida es 999'):
            self.assertTrue(correr_juego(mal, 1)["error"])

    def test_una_partida_nueva_empieza_vacia(self):
        self.assertEqual(Partida(1).eventos, [])


class TestArbol(unittest.TestCase):
    def test_rechaza_lo_que_no_es_de_un_juego(self):
        for mal in ("import os", "x.__class__", "h.constructor", "h.x es 3", "mostrar [1, 2][0:1]",
                    "mostrar f(a=1)", "mostrar lambda: 1", "clase A:\n    pass",
                    "funcion a():\n    funcion b():\n        pass", "d es {1: 2}", "mostrar mostrar.__name__"):
            with self.subTest(mal):
                with self.assertRaises((CodigoNoPermitido, SyntaxError)):
                    arbol_del_juego(mal)

    def test_el_arbol_solo_tiene_tipos_conocidos(self):
        conocidos = {"programa", "expr", "asignar", "asignar_op", "si", "mientras", "para", "funcion", "devolver",
                     "cortar", "seguir", "nada", "num", "texto", "const", "var", "op", "unario", "logica",
                     "comparar", "llamar", "metodo", "attr", "indice", "lista", "si_expr"}
        vistos = set()

        def recorrer(x):
            if isinstance(x, dict):
                if "k" in x:
                    vistos.add(x["k"])
                for v in x.values():
                    recorrer(v)
            elif isinstance(x, list):
                for v in x:
                    recorrer(v)
        for fuente, _, _ in CORPUS:
            recorrer(arbol_del_juego(fuente))
        self.assertLessEqual(vistos, conocidos)


if __name__ == "__main__":
    unittest.main()
