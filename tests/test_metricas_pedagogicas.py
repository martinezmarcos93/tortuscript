"""Métricas pedagógicas locales (P6, docs/ESPECIFICACION_P1_P6.md)."""
import copy
import unittest

from tortuscript import contenido, dominio, metricas_pedagogicas as mp

CURSOS = [{"id": "c", "secciones": [{"id": "s", "lecciones": [
    {"id": "l1", "pasos": [{"tipo": "explicacion"}, {"tipo": "elegir"}, {"tipo": "predecir"},
                           {"tipo": "completar"}, {"tipo": "ordenar"}, {"tipo": "elegir"}]},
    {"id": "l2", "pasos": [{"tipo": "escribir"}, {"tipo": "escribir"}, {"tipo": "escribir"}, {"tipo": "escribir"}]},
    {"id": "l3", "pasos": [{"tipo": "elegir"}, {"tipo": "escribir"}]},
]}]}]
MAPA = {
    "u1": {"tipo": "lecciones", "curso": "c", "lecciones": ["l1"]},
    "u2": {"tipo": "lecciones", "curso": "c", "lecciones": ["l2"]},
    "u3": {"tipo": "lecciones", "curso": "c", "lecciones": ["l3"]},
    "p": {"tipo": "proyecto", "proyecto": "x"},
}


def progreso(pasos_l1=None, pasos_l2=None, repaso=None):
    lecciones = {}
    if pasos_l1 is not None:
        lecciones["l1"] = {"pasos": pasos_l1}
    if pasos_l2 is not None:
        lecciones["l2"] = {"pasos": pasos_l2}
    return {"lecciones": lecciones, "repaso": repaso or {}}


def m(p, cursos=CURSOS, mapa=MAPA):
    return mp.metricas(p, cursos, mapa)


class FormaTests(unittest.TestCase):
    def test_claves(self):
        r = m(progreso())
        self.assertEqual(set(r), {"pasos_rapidos", "escribir", "repaso", "conceptos", "recomendaciones", "datos_danados"})
        self.assertEqual(set(r["pasos_rapidos"]), {"total", "primer_intento", "con_reintentos", "ayudados"})
        self.assertEqual(set(r["escribir"]), {"total", "autonomos", "con_ayuda"})
        self.assertEqual(set(r["repaso"]), {"tarjetas", "aciertos", "fallos", "tasa_acierto", "retenidas"})
        self.assertEqual(list(r["conceptos"]), list(dominio.ESTADOS))

    def test_progreso_vacio_o_raro_da_ceros(self):
        for p in ({}, None, [], "x", {"lecciones": "x", "repaso": 3}):
            with self.subTest(p=p):
                r = m(p)
                self.assertEqual(r["pasos_rapidos"], {"total": 0, "primer_intento": 0, "con_reintentos": 0, "ayudados": 0})
                self.assertEqual(r["escribir"], {"total": 0, "autonomos": 0, "con_ayuda": 0})
                self.assertEqual(r["repaso"], {"tarjetas": 0, "aciertos": 0, "fallos": 0, "tasa_acierto": None, "retenidas": 0})
                self.assertEqual(r["conceptos"]["sin_evidencia"], 3)
                self.assertEqual(r["datos_danados"], 0)


class PasosTests(unittest.TestCase):
    def test_pasos_rapidos_por_xp(self):
        # índices de l1: 1 elegir, 2 predecir, 3 completar, 4 ordenar, 5 elegir; 0 es explicación
        r = m(progreso({"0": {"xp": 0}, "1": {"xp": 5}, "2": {"xp": 4}, "3": {"xp": 1}, "4": {"xp": 0}, "5": {"xp": -1}}))
        self.assertEqual(r["pasos_rapidos"], {"total": 5, "primer_intento": 1, "con_reintentos": 2, "ayudados": 2})

    def test_escribir_por_estrellas_o_perfecto(self):
        r = m(progreso(pasos_l2={"0": {"estrellas": 3, "xp": 30}, "1": {"estrellas": 2, "xp": 20},
                                 "2": {"perfecto": True}, "3": {"perfecto": False}}))
        self.assertEqual(r["escribir"], {"total": 4, "autonomos": 2, "con_ayuda": 2})
        r = m(progreso(pasos_l2={"0": {"estrellas": 0}, "1": {"estrellas": 1}}))
        self.assertEqual(r["escribir"], {"total": 2, "autonomos": 0, "con_ayuda": 2})

    def test_indices_fuera_de_rango_o_lecciones_desconocidas_no_cuentan(self):
        p = progreso({"9": {"xp": 5}, "1": {"xp": 5}})
        p["lecciones"]["no-existe"] = {"pasos": {"0": {"xp": 5}}}
        self.assertEqual(m(p)["pasos_rapidos"]["total"], 1)

    def test_datos_danados_se_cuentan_y_no_lanzan(self):
        p = progreso({"1": "x", "2": {"xp": "5"}, "3": {"xp": True}, "4": {"xp": None}, "5": {"xp": 5}})
        r = m(p)
        self.assertEqual(r["pasos_rapidos"]["total"], 1)
        self.assertEqual(r["datos_danados"], 4)


class RepasoTests(unittest.TestCase):
    def test_suma_y_tasa(self):
        r = m(progreso(repaso={"l1:1": {"caja": 1, "aciertos": 2, "fallos": 1}, "l1:2": {"caja": 2, "aciertos": 0, "fallos": 0}}))
        self.assertEqual(r["repaso"], {"tarjetas": 2, "aciertos": 2, "fallos": 1, "tasa_acierto": 0.667, "retenidas": 0})

    def test_tasa_none_sin_respuestas(self):
        self.assertIsNone(m(progreso(repaso={"l1:1": {"caja": 0, "aciertos": 0, "fallos": 0}}))["repaso"]["tasa_acierto"])

    def test_retenidas_bordes(self):
        repaso = {"a:0": {"caja": 3, "aciertos": 2}, "a:1": {"caja": 2, "aciertos": 5},
                  "a:2": {"caja": 5, "aciertos": 1}, "a:3": {"caja": 4, "aciertos": 3}}
        self.assertEqual(m(progreso(repaso=repaso))["repaso"]["retenidas"], 2)

    def test_tarjetas_danadas(self):
        repaso = {"a:0": "x", "a:1": {"caja": 1, "aciertos": "2", "fallos": 1}, "a:2": {"caja": 1, "aciertos": 1, "fallos": 1}}
        r = m(progreso(repaso=repaso))
        self.assertEqual((r["repaso"]["tarjetas"], r["repaso"]["aciertos"], r["repaso"]["fallos"]), (1, 1, 1))
        self.assertEqual(r["datos_danados"], 2)


class ConceptosTests(unittest.TestCase):
    def test_conteo_por_estado(self):
        # u1: todas sus categorías fuertes → autónomo; u2: un escribir con ayuda → visto; u3: nada.
        p = progreso({"1": {"xp": 5}, "2": {"xp": 5}, "3": {"xp": 5}}, {"0": {"estrellas": 1}})
        r = m(p)
        self.assertEqual(r["conceptos"]["autonomo"], 1)
        self.assertEqual(r["conceptos"]["visto"], 1)
        self.assertEqual(r["conceptos"]["sin_evidencia"], 1)
        self.assertEqual(sum(r["conceptos"].values()), 3)

    def test_recomendaciones(self):
        p = progreso({"1": {"xp": 5}, "2": {"xp": 5}, "3": {"xp": 5}}, {"0": {"estrellas": 1}})
        r = m(p)
        self.assertEqual(r["recomendaciones"], {"u1": "repaso", "u2": "produccion", "u3": "reconocimiento"})

    def test_consolidado_no_recomienda(self):
        p = progreso({"1": {"xp": 5}, "2": {"xp": 5}, "3": {"xp": 5}},
                     repaso={"l1:1": {"caja": 3, "aciertos": 2, "fallos": 0}})
        self.assertNotIn("u1", m(p)["recomendaciones"])


class GarantiasTests(unittest.TestCase):
    def test_no_muta_el_progreso(self):
        p = progreso({"1": {"xp": 5}, "2": "x"}, {"0": {"estrellas": 3}}, {"l1:1": {"caja": 3, "aciertos": 2}})
        original = copy.deepcopy(p)
        m(p)
        self.assertEqual(p, original)

    def test_datos_reales_con_progreso_vacio(self):
        mapa = dominio.cargar_mapa()
        r = mp.metricas({}, contenido.todos_los_cursos(), mapa)
        self.assertEqual(r["conceptos"]["sin_evidencia"], sum(1 for u in mapa.values() if u.get("tipo") == "lecciones"))
        self.assertEqual(r["pasos_rapidos"]["total"], 0)


if __name__ == "__main__":
    unittest.main()
