"""Pistas graduadas (P4, docs/ESPECIFICACION_P1_P6.md).

Contrato con el validador: todo hallazgo sobre el campo `pistas` es de nivel ERROR y su mensaje contiene «pistas».
"""
import unittest

from tortuscript import leccion, validacion

TRES = ["Mirá la segunda línea.", "Recordá qué hace repetir.", "Contá las vueltas: van tres."]


def elegir(**extra):
    return {"tipo": "elegir", "pregunta": "¿Cuál?", "opciones": ["uno", "dos", "tres"], "correcta": 1,
            "pista": "Pista de siempre.", **extra}


def completar(**extra):
    return {"tipo": "completar", "codigo": "mostrar ___", "fichas": ["1", "2"], "respuesta": ["1"],
            "pista": "Pista de siempre.", **extra}


def ordenar(**extra):
    return {"tipo": "ordenar", "lineas": ["a es 1", "mostrar a"], "pista": "Pista de siempre.", **extra}


def predecir(**extra):
    return {"tipo": "predecir", "codigo": "mostrar 2", "opciones": ["1", "2"], "correcta": 1,
            "pista": "Pista de siempre.", **extra}


class MotorTests(unittest.TestCase):
    def test_elegir_gradua_segun_errores_previos(self):
        paso = elegir(pistas=TRES)
        for errores, esperada in ((0, TRES[0]), (1, TRES[1]), (2, TRES[2]), (5, TRES[2])):
            with self.subTest(errores=errores):
                self.assertEqual(leccion.comprobar(paso, "uno", errores_previos=errores)["pista"], esperada)

    def test_sin_errores_previos_es_la_primera(self):
        self.assertEqual(leccion.comprobar(elegir(pistas=TRES), "uno")["pista"], TRES[0])

    def test_una_sola_pista_siempre_esa(self):
        for errores in (0, 1, 7):
            self.assertEqual(leccion.comprobar(elegir(pistas=["Única."]), "uno", errores_previos=errores)["pista"], "Única.")

    def test_sin_pistas_usa_pista_y_sin_pista_la_generica(self):
        self.assertEqual(leccion.comprobar(elegir(), "uno", errores_previos=1)["pista"], "Pista de siempre.")
        paso = elegir()
        del paso["pista"]
        self.assertEqual(leccion.comprobar(paso, "uno", errores_previos=1)["pista"], leccion.PISTAS_GENERICAS["elegir"])

    def test_pistas_invalidas_usan_la_pista_de_siempre(self):
        for pistas in ([], "texto", [""], [3], None):
            with self.subTest(pistas=pistas):
                r = leccion.comprobar(elegir(pistas=pistas), "uno", errores_previos=1)
                self.assertEqual(r["pista"], "Pista de siempre.")

    def test_errores_previos_raros_cuentan_como_cero(self):
        for errores in (-1, True, "2", None, 1.5):
            with self.subTest(errores=errores):
                self.assertEqual(leccion.comprobar(elegir(pistas=TRES), "uno", errores_previos=errores)["pista"], TRES[0])

    def test_respuesta_correcta_no_cambia(self):
        self.assertEqual(leccion.comprobar(elegir(pistas=TRES), "dos", errores_previos=2),
                         {"ok": True, "pista": None, "malos": None})

    def test_pistas_fijas_de_forma_no_cambian(self):
        r = leccion.comprobar(completar(pistas=TRES), [], errores_previos=2)
        self.assertEqual(r["pista"], "Todavía quedan huecos sin completar.")
        r = leccion.comprobar(ordenar(pistas=TRES), ["a es 1"], errores_previos=2)
        self.assertEqual(r["pista"], "Todavía faltan líneas por ubicar.")

    def test_completar_ordenar_y_predecir_graduan_y_conservan_malos(self):
        r = leccion.comprobar(completar(pistas=TRES), ["2"], errores_previos=1)
        self.assertEqual((r["ok"], r["pista"], r["malos"]), (False, TRES[1], [0]))
        r = leccion.comprobar(ordenar(pistas=TRES), ["mostrar a", "a es 1"], errores_previos=2)
        self.assertEqual((r["ok"], r["pista"], r["malos"]), (False, TRES[2], [0, 1]))
        r = leccion.comprobar(predecir(pistas=TRES), "1", errores_previos=0)
        self.assertEqual((r["ok"], r["pista"], r["malos"]), (False, TRES[0], None))

    def test_la_forma_del_resultado_no_cambia(self):
        self.assertEqual(set(leccion.comprobar(elegir(pistas=TRES), "uno", errores_previos=1)), {"ok", "pista", "malos"})


def curso_con(paso):
    return {"id": "c", "titulo": "C", "secciones": [{"id": "s", "titulo": "S", "lecciones": [
        {"id": "l", "titulo": "1. L", "pasos": [{"tipo": "explicacion", "texto": "Hola."}, paso]}]}]}


def errores_de_pistas(paso):
    return [h for h in validacion.validar_curso(curso_con(paso)) if h.nivel == validacion.ERROR and "pistas" in h.mensaje]


class ValidadorTests(unittest.TestCase):
    def test_pistas_validas_no_dan_error(self):
        for paso in (elegir(pistas=TRES[:2]), completar(pistas=["Una."]), ordenar(pistas=TRES), predecir(pistas=TRES)):
            with self.subTest(tipo=paso["tipo"]):
                self.assertEqual(errores_de_pistas(paso), [])

    def test_sin_pistas_no_da_error(self):
        self.assertEqual(errores_de_pistas(elegir()), [])

    def test_formas_invalidas_dan_error(self):
        casos = {"vacía": [], "cuatro": TRES + ["Otra."], "texto vacío": ["Bien.", ""], "repetidas": ["Igual.", "Igual."],
                 "no es lista": "Mirá.", "no son textos": [1, 2]}
        for nombre, pistas in casos.items():
            with self.subTest(caso=nombre):
                self.assertTrue(errores_de_pistas(elegir(pistas=pistas)))

    def test_tipos_que_no_las_usan_dan_error(self):
        explicacion = {"tipo": "explicacion", "texto": "Hola.", "pistas": ["Mirá."]}
        self.assertTrue(errores_de_pistas(explicacion))
        escribir = {"tipo": "escribir", "consigna": "Mostrá hola.", "solucion": "mostrar \"hola\"", "pistas": ["Mirá."]}
        self.assertTrue(errores_de_pistas(escribir))

    def test_pista_que_contiene_la_opcion_correcta_da_error(self):
        self.assertTrue(errores_de_pistas(elegir(pistas=["Mirá bien.", "Es la que dice dos, claro."])))
        self.assertTrue(errores_de_pistas(predecir(opciones=["uno", "cuatro"], pistas=["Da cuatro."])))

    def test_opcion_correcta_corta_no_se_busca_en_las_pistas(self):
        # «2» tiene menos de 3 caracteres: aparecer en una pista no es error.
        self.assertEqual(errores_de_pistas(predecir(pistas=["Mirá el 2 que se muestra."])), [])


if __name__ == "__main__":
    unittest.main()
