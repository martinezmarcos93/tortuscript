"""Casos ocultos para los pasos de escritura que reciben datos."""
import unittest

from tortuscript import contenido
from tortuscript.proceso import TrabajoInvalido, normalizar_pedido
from tortuscript.validacion import ERROR, validar_curso
from tortuscript.worker import atender


def curso_con(paso):
    return {"id": "c", "secciones": [{"id": "s", "lecciones": [
        {"id": "l", "titulo": "Prueba", "pasos": [paso]}]}]}


class TestNormalizarCasos(unittest.TestCase):
    def pedido(self, casos):
        return {"op": "evaluar", "fuente": "print('ok')", "casos": casos}

    def test_acepta_cinco_casos_y_normaliza_respuestas_numericas(self):
        limpio = normalizar_pedido(self.pedido([[1], ["a"], [], ["b"], ["c"]]))
        self.assertEqual(limpio["casos"], [["1"], ["a"], [], ["b"], ["c"]])

    def test_rechaza_cantidad_formato_tipo_y_limites_de_entrada(self):
        for casos in ([], [["x"]] * 6, "x", ["x"], [[True]], [["x"] * 101], [["x" * 1001]]):
            with self.subTest(casos=casos):
                with self.assertRaises(TrabajoInvalido):
                    normalizar_pedido(self.pedido(casos))


class TestEvaluacionConCasos(unittest.TestCase):
    def evaluar(self, fuente, solucion, entradas, casos=None):
        pedido = {"op": "evaluar", "fuente": fuente, "solucion": solucion, "entradas": entradas}
        if casos is not None:
            pedido["casos"] = casos
        return atender(normalizar_pedido(pedido))["evaluacion"]

    def test_siempre_adelante_pasa_sin_casos_y_falla_con_caso(self):
        solucion = 'clave es preguntar("Clave")\nsi clave == "mate":\n    mostrar "Adelante"\nsino:\n    mostrar "Probá otra vez"'
        trucha = 'preguntar("Clave")\nmostrar "Adelante"'
        self.assertEqual(self.evaluar(trucha, solucion, ["mate"])["estado"], "correcto")
        ev = self.evaluar(trucha, solucion, ["mate"], [["mate"], ["sol"]])
        self.assertEqual(ev["estado"], "incorrecto")
        self.assertEqual(ev["caso"], ["sol"])
        self.assertEqual(self.evaluar(solucion, solucion, ["mate"], [["mate"], ["sol"]])["estado"], "correcto")

    def test_error_del_alumno_en_un_caso_es_incorrecto(self):
        solucion = "n = int(input())\nprint(n * 2)"
        alumno = "n = int(input())\nprint(n * 2)"
        ev = self.evaluar(alumno, solucion, ["6"], [["6"], ["no es numero"]])
        self.assertEqual(ev["estado"], "incorrecto")
        self.assertEqual(ev["caso"], ["no es numero"])


class TestValidadorCasos(unittest.TestCase):
    def errores(self, paso):
        return [h.mensaje for h in validar_curso(curso_con(paso)) if h.nivel == ERROR]

    def test_rechaza_formato_paso_incompatible_y_error_de_solucion(self):
        base = {"tipo": "escribir", "solucion": "print('ok')"}
        for casos in ("mal", [], [[1]], [["x"]] * 6):
            with self.subTest(casos=casos):
                self.assertTrue(self.errores({**base, "casos_prueba": casos}))
        self.assertTrue(self.errores({"tipo": "elegir", "casos_prueba": [["x"]]}))
        self.assertTrue(self.errores({**base, "tortuga": True, "casos_prueba": [["x"]]}))
        self.assertTrue(self.errores({**base, "juego": True, "casos_prueba": [["x"]]}))
        self.assertTrue(self.errores({**base, "lenguaje": "sql", "casos_prueba": [["x"]]}))
        self.assertTrue(self.errores({**base, "web": {}, "casos_prueba": [["x"]]}))
        self.assertTrue(self.errores({**base, "lenguaje": "python", "solucion": "int(input())", "casos_prueba": [["no"]]}))

    def test_acepta_caso_valido(self):
        paso = {"tipo": "escribir", "lenguaje": "python", "solucion": "nombre = input()\nprint(nombre)",
                "casos_prueba": [["Ada"]]}
        self.assertEqual(self.errores(paso), [])


class TestDesafiosConCasos(unittest.TestCase):
    def test_soluciones_reales_pasan_y_truchas_fallan(self):
        curso_ts = contenido.cargar_curso("desafios-tortuscript")
        curso_py = contenido.cargar_curso("desafios-python")
        pasos = {p.get("id"): next(x for x in p["pasos"] if x["tipo"] == "escribir")
                 for c in (curso_ts, curso_py) for _, p in contenido.lecciones(c)
                 if p.get("id") in {"clave-secreta", "saludo-de-equipo", "doble-o-nada"}}
        truchas = {"clave-secreta": 'preguntar("Clave")\nmostrar "Adelante"',
                   "saludo-de-equipo": 'equipo = input()\nprint("Vamos, Tortugas")\nprint("Vamos, Tortugas")\nprint("Vamos, Tortugas")',
                   "doble-o-nada": "fichas = input()\nprint(12)"}
        for id_paso, paso in pasos.items():
            entradas = paso.get("entradas_prueba", [])
            pedido = {"op": "evaluar", "fuente": paso["solucion"], "solucion": paso["solucion"],
                      "entradas": entradas, "casos": paso["casos_prueba"]}
            with self.subTest(paso=id_paso):
                self.assertEqual(atender(normalizar_pedido(pedido))["evaluacion"]["estado"], "correcto")
                pedido["fuente"] = truchas[id_paso]
                self.assertEqual(atender(normalizar_pedido(pedido))["evaluacion"]["estado"], "incorrecto")


if __name__ == "__main__":
    unittest.main()
