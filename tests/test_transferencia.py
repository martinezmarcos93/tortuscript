import unittest

from tortuscript import contenido, leccion
from tortuscript.evaluacion import normalizar_salida
from tortuscript.validacion import ERROR, _correr, validar_curso


class TestReglaTransferencia(unittest.TestCase):
    def curso(self, transferencia):
        return {"id": "sintetico", "secciones": [{"id": "s", "lecciones": [{
            "id": "reto", "pasos": [], "transferencia": transferencia,
        }]}]}

    def errores(self, transferencia):
        return [h.mensaje for h in validar_curso(self.curso(transferencia), {
            "unidades": {"u1": {"tipo": "lecciones"}, "u2": {"tipo": "lecciones"},
                         "proyecto": {"tipo": "proyecto"}},
        }) if h.nivel == ERROR]

    def test_menos_de_dos_conceptos(self):
        self.assertIn("transferencia necesita al menos 2 conceptos",
                      self.errores({"conceptos": ["u1"], "asistencia": "guiada"}))

    def test_concepto_que_no_es_unidad_lecciones(self):
        self.assertIn("transferencia contiene un concepto que no es unidad lecciones del mapa",
                      self.errores({"conceptos": ["u1", "proyecto"], "asistencia": "guiada"}))

    def test_asistencia_invalida(self):
        self.assertIn("transferencia.asistencia debe ser «guiada» o «autonoma»",
                      self.errores({"conceptos": ["u1", "u2"], "asistencia": "libre"}))

    def test_transferencia_valida(self):
        self.assertEqual([], self.errores({"conceptos": ["u1", "u2"], "asistencia": "autonoma"}))


class TestCursosDeTransferencia(unittest.TestCase):
    ESPERADAS = {
        "mensaje-en-ronda": ("Hola Luz\nHola Luz\nHola Luz", []),
        "puntos-del-juego": ("¡Nivel nuevo!", []),
        "clave-secreta": ("Adelante", ["mate"]),
        "tabla-relampago": ("3\n6\n9\n12\n15", []),
        "saludo-de-equipo": ("Vamos, Tortugas\nVamos, Tortugas\nVamos, Tortugas", ["Tortugas"]),
        "doble-o-nada": ("12", ["6"]),
        "filtro-de-nombres": ("Luna\nTomi", []),
        "funcion-de-puntos": ("16", []),
    }

    def test_cursos_al_final_del_orden_y_requisitos(self):
        ids = ["desafios-tortuscript", "desafios-python"]
        self.assertEqual(ids, list(contenido.ORDEN_CURSOS[-2:]))
        cursos = [contenido.cargar_curso(i) for i in ids]
        self.assertEqual(["primeros-pasos", "python-real"], [c["requiere"]["curso"] for c in cursos])
        cursos_reales = contenido.todos_los_cursos()
        indice = {}
        for c in cursos_reales:
            for _, lec in contenido.lecciones(c):
                indice[lec["id"]] = [0]
        for curso in cursos:
            requisito = curso["requiere"]["curso"]
            estado = leccion.estado_cursos(cursos_reales, {}, indice)
            por_id = {c["id"]: c for c in estado}
            self.assertFalse(por_id[curso["id"]]["abierto"])
            progreso = {"lecciones": {l["id"]: {"completada": True}
                         for _, l in contenido.lecciones(contenido.cargar_curso(requisito))}}
            estado = leccion.estado_cursos(cursos_reales, progreso, indice)
            self.assertTrue({c["id"]: c for c in estado}[curso["id"]]["abierto"])

    def test_todas_las_lecciones_y_soluciones(self):
        for curso_id in ("desafios-tortuscript", "desafios-python"):
            curso = contenido.cargar_curso(curso_id)
            for _, reto in contenido.lecciones(curso):
                with self.subTest(curso=curso_id, leccion=reto["id"]):
                    transfer = reto["transferencia"]
                    self.assertGreaterEqual(len(transfer["conceptos"]), 2)
                    self.assertIn(transfer["asistencia"], ("guiada", "autonoma"))
                    self.assertIn(reto["id"], self.ESPERADAS)
                    escribir = [p for p in reto["pasos"] if p["tipo"] == "escribir"]
                    self.assertTrue(escribir)
                    for paso in escribir:
                        salida, error, _ = _correr(paso["solucion"], paso.get("entradas_prueba"), paso.get("lenguaje"))
                        self.assertFalse(error)
                        esperada, entradas = self.ESPERADAS[reto["id"]]
                        self.assertEqual(normalizar_salida(esperada), normalizar_salida(salida))
                        self.assertEqual(entradas, paso.get("entradas_prueba", []))

    def test_minimo_y_asistencias_por_curso(self):
        for curso_id in ("desafios-tortuscript", "desafios-python"):
            lecciones = contenido.lecciones(contenido.cargar_curso(curso_id))
            asistencias = [l["transferencia"]["asistencia"] for _, l in lecciones]
            self.assertGreaterEqual(len(asistencias), 4)
            self.assertGreaterEqual(asistencias.count("guiada"), 1)
            self.assertGreaterEqual(asistencias.count("autonoma"), 2)


if __name__ == "__main__":
    unittest.main()
