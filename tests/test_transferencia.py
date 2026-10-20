import unittest

from tortuscript import catalogo_producto, contenido, leccion
from tortuscript.evaluacion import normalizar_salida
from tortuscript.validacion import ERROR, _correr, validar_transferencias


class TestReglaTransferencia(unittest.TestCase):
    def cursos(self, transferencia, anterior="hola-mundo"):
        curso = lambda cid, lid, transfer=None: {"id": cid, "secciones": [{"id": "s", "lecciones": [
            {"id": lid, "pasos": [], **({"transferencia": transfer} if transfer is not None else {})}
        ]}]}
        base = curso("primeros-pasos", anterior)
        base["secciones"][0]["lecciones"].append({"id": "tu-primera-variable", "pasos": []})
        return [base, curso("desafios-tortuscript", "reto", transferencia)]

    def errores(self, transferencia, anterior="hola-mundo"):
        return [h.mensaje for h in validar_transferencias(self.cursos(transferencia, anterior)) if h.nivel == ERROR]

    def test_menos_de_dos_conceptos(self):
        self.assertIn("transferencia necesita al menos 2 conceptos distintos",
                      self.errores({"conceptos": ["hola-mundo", "hola-mundo"], "asistencia": "guiada"}))

    def test_concepto_que_no_es_unidad_lecciones(self):
        self.assertTrue(self.errores({"conceptos": ["hola-mundo", "inventada"], "asistencia": "guiada"}))

    def test_concepto_del_mismo_curso_o_posterior(self):
        self.assertTrue(self.errores({"conceptos": ["hola-mundo", "reto"], "asistencia": "guiada"}))
        self.assertTrue(self.errores({"conceptos": ["hola-mundo", "py-print"], "asistencia": "guiada"}))

    def test_asistencia_invalida(self):
        self.assertIn("transferencia.asistencia debe ser «guiada» o «autonoma»",
                      self.errores({"conceptos": ["u1", "u2"], "asistencia": "libre"}))

    def test_transferencia_valida(self):
        self.assertEqual([], self.errores({"conceptos": ["hola-mundo", "tu-primera-variable"], "asistencia": "autonoma"}))


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
                    self.assertEqual([], [h for h in validar_transferencias(contenido.todos_los_cursos())
                                          if h.nivel == ERROR])

    def test_minimo_y_asistencias_por_curso(self):
        for curso_id in ("desafios-tortuscript", "desafios-python"):
            lecciones = contenido.lecciones(contenido.cargar_curso(curso_id))
            asistencias = [l["transferencia"]["asistencia"] for _, l in lecciones]
            self.assertGreaterEqual(len(asistencias), 4)
            self.assertGreaterEqual(asistencias.count("guiada"), 1)
            self.assertGreaterEqual(asistencias.count("autonoma"), 2)


class TestUnidadDeCobro(unittest.TestCase):
    def test_unidad_de_leccion_del_mapa(self):
        self.assertEqual(catalogo_producto.unidad_de_leccion("py-if"), catalogo_producto.unidad_de_cobro("py-if"))

    def test_leccion_fuera_del_mapa_sin_conceptos(self):
        self.assertIsNone(catalogo_producto.unidad_de_cobro("tortuga-avanzar"))

    def test_desafios_tortuscript_son_gratis(self):
        for _, reto in contenido.lecciones(contenido.cargar_curso("desafios-tortuscript")):
            self.assertIsNone(catalogo_producto.unidad_de_cobro(reto["id"]))

    def test_conceptos_gratuitos_no_cobran_y_premium_si(self):
        from unittest.mock import patch
        def reto(conceptos):
            return {"id": "reto-sintetico", "transferencia": {"conceptos": conceptos}, "pasos": []}
        curso = {"id": "sintetico", "secciones": [{"id": "s", "lecciones": [reto(["hola-mundo", "tu-primera-variable"])]}]}
        limpiar = catalogo_producto._conceptos_declarados.cache_clear      # el índice se cachea: el contenido no cambia
        self.addCleanup(limpiar)
        with patch.object(contenido, "todos_los_cursos", return_value=[curso]):
            limpiar()
            self.assertIsNone(catalogo_producto.unidad_de_cobro("reto-sintetico"))
            curso["secciones"][0]["lecciones"] = [reto(["py-if", "py-for"])]
            limpiar()
            self.assertEqual("python-control", catalogo_producto.unidad_de_cobro("reto-sintetico"))


if __name__ == "__main__":
    unittest.main()
