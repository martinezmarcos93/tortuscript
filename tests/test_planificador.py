import copy
import unittest
from datetime import date
from unittest.mock import patch

from tortuscript import contenido, dominio, planificador, practica


def fixture():
    cursos = [{"id": "c", "secciones": [{"lecciones": [
        {"id": lid, "pasos": [{"tipo": "elegir"} for _ in range(3)]}
        for lid in ("a", "b", "c", "x")]}]}]
    mapa = {
        "ua": {"tipo": "lecciones", "curso": "c", "lecciones": ["a", "b"]},
        "uc": {"tipo": "lecciones", "curso": "c", "lecciones": ["c"]},
    }
    progreso = {"lecciones": {lid: {"pasos": {str(i): {"fecha": "2026-10-01"} for i in range(3)}}
                              for lid in ("a", "b", "c", "x")}, "repaso": {}}
    return progreso, cursos, mapa


class PlanificadorTests(unittest.TestCase):
    def test_interruptor_y_apagado_usa_practica(self):
        for entorno, esperado in (({}, False), ({"TORTU_PLANIFICADOR": "si"}, False),
                                  ({"TORTU_PLANIFICADOR": ""}, False),
                                  ({"TORTU_PLANIFICADOR": "ADAPTATIVO "}, True)):
            self.assertEqual(planificador.activo(entorno), esperado)
        p, c, _ = fixture()
        hoy = date(2026, 10, 19)
        self.assertEqual(planificador.elegir_sesion(p, c, hoy), practica.elegir(p, c, hoy))

    def test_nivel_empate_pool_topes_y_relleno(self):
        p, c, m = fixture()
        p["repaso"]["c:0"] = {"caja": 1, "proximo": "2026-10-19"}
        niveles = {"ua": {"nivel": 1}, "uc": {"nivel": 4}}
        with patch.object(dominio, "dominio", return_value=niveles):
            res = planificador.elegir(p, c, date(2026, 10, 19), m, 6)
        self.assertEqual(res, [("a", 0), ("x", 0), ("c", 1), ("a", 1), ("x", 1), ("c", 2)])
        pool = {(t["leccion"], t["paso"]) for t in practica.candidatos(p, c, date(2026, 10, 19))}
        self.assertTrue(set(res) <= pool)
        self.assertEqual(len(res), len(set(res)))
        self.assertLessEqual(len(res), 6)
        self.assertLessEqual(sum(l == "a" for l, _ in res), 2)
        self.assertEqual(planificador.elegir(p, c, date(2026, 10, 19), m, 0), [])
        self.assertEqual(planificador.elegir(p, c, date(2026, 10, 19), m, -1), [])

    def test_empate_mas_atrasado_primero_y_determinismo_no_mutacion(self):
        p, c, m = fixture()
        p["repaso"]["a:0"] = {"caja": 1, "proximo": "2026-10-18"}
        original = copy.deepcopy(p)
        with patch.object(dominio, "dominio", return_value={"ua": {"nivel": 2}, "uc": {"nivel": 2}}):
            a = planificador.elegir(p, c, date(2026, 10, 19), m, 4)
            b = planificador.elegir(p, c, date(2026, 10, 19), m, 4)
        self.assertEqual(a, b)
        self.assertEqual(a[0], ("a", 1))
        self.assertEqual(p, original)

    def test_relleno_con_un_solo_concepto(self):
        p, c, m = fixture()
        c[0]["secciones"][0]["lecciones"] = c[0]["secciones"][0]["lecciones"][:2]
        p["lecciones"] = {k: v for k, v in p["lecciones"].items() if k in ("a", "b")}
        with patch.object(dominio, "dominio", return_value={"ua": {"nivel": 2}}):
            resultado = planificador.elegir(p, c, date(2026, 10, 19), {"ua": m["ua"]}, 4)
        self.assertEqual(resultado, [("a", 0), ("a", 1), ("b", 0), ("b", 1)])

    def test_sin_concepto_nivel_tres_y_fallback(self):
        p, c, m = fixture()
        niveles = {"ua": {"nivel": 1}, "uc": {"nivel": 5}}
        with patch.object(dominio, "dominio", return_value=niveles):
            resultado = planificador.elegir(p, c, date(2026, 10, 19), m, 2)
        self.assertEqual(resultado, [("a", 0), ("x", 0)])
        with patch.object(dominio, "dominio", side_effect=RuntimeError("fallo")):
            with self.assertLogs(planificador.logger, level="ERROR"):
                sesion = planificador.elegir_sesion(p, c, date(2026, 10, 19), m,
                                                    {"TORTU_PLANIFICADOR": "adaptativo"})
        self.assertEqual(sesion, practica.elegir(p, c, date(2026, 10, 19)))

    def test_recomendar(self):
        self.assertEqual(planificador.recomendar({"disponibles": ["produccion", "reconocimiento"], "fuertes": []}), "reconocimiento")
        self.assertEqual(planificador.recomendar({"disponibles": ["reconocimiento", "prediccion"], "fuertes": ["reconocimiento"]}), "prediccion")
        self.assertEqual(planificador.recomendar({"disponibles": ["reconocimiento"], "fuertes": ["reconocimiento"], "estado": "aplicado", "retencion": False}), "repaso")
        self.assertIsNone(planificador.recomendar({"disponibles": ["reconocimiento"], "fuertes": ["reconocimiento"], "estado": "aplicado", "retencion": True}))
        self.assertIsNone(planificador.recomendar({"disponibles": [], "fuertes": []}))
        self.assertIsNone(planificador.recomendar({"disponibles": ["reconocimiento"], "fuertes": ["reconocimiento"], "estado": "consolidado", "retencion": True}))

    def test_datos_reales(self):
        cursos = contenido.todos_los_cursos()
        mapa = dominio.cargar_mapa()
        p = {"lecciones": {}, "repaso": {}}
        lecciones = [lec for curso in cursos for seccion in curso["secciones"] for lec in seccion["lecciones"]]
        for lec in lecciones[:4]:
            pasos = {str(i): {"fecha": "2026-10-01"} for i, paso in enumerate(lec["pasos"])
                     if paso.get("tipo") in practica.TIPOS}
            if pasos:
                p["lecciones"][lec["id"]] = {"pasos": pasos}
        resultado = planificador.elegir(p, cursos, date(2026, 10, 19), mapa)
        pool = {(t["leccion"], t["paso"]) for t in practica.candidatos(p, cursos, date(2026, 10, 19))}
        self.assertTrue(set(resultado) <= pool)
        self.assertLessEqual(len(resultado), practica.POR_SESION)


if __name__ == "__main__":
    unittest.main()
