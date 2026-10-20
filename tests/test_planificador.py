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


class PlanificadorBordesTests(unittest.TestCase):
    """Bordes agregados por el director tras la prueba de mutación."""

    def test_tope_exacto_de_dos_por_concepto_en_la_primera_pasada(self):
        p, c, m = fixture()
        m = {"ua": {"tipo": "lecciones", "curso": "c", "lecciones": ["a", "b"]},
             "uc": {"tipo": "lecciones", "curso": "c", "lecciones": ["c", "x"]}}
        with patch.object(dominio, "dominio", return_value={"ua": {"nivel": 1}, "uc": {"nivel": 4}}):
            res = planificador.elegir(p, c, date(2026, 10, 19), m, 4)
        # Dos de cada concepto aunque el de nivel 1 tenga más tarjetas.
        self.assertEqual(res, [("a", 0), ("c", 0), ("a", 1), ("c", 1)])

    def test_leccion_en_dos_unidades_usa_la_primera_del_mapa(self):
        p, c, _ = fixture()
        p["lecciones"] = {"a": p["lecciones"]["a"], "c": p["lecciones"]["c"]}
        m = {"u1": {"tipo": "lecciones", "curso": "c", "lecciones": ["a"]},
             "u2": {"tipo": "lecciones", "curso": "c", "lecciones": ["a", "c"]}}
        with patch.object(dominio, "dominio", return_value={"u1": {"nivel": 0}, "u2": {"nivel": 5}}):
            res = planificador.elegir(p, c, date(2026, 10, 19), m, 1)
        self.assertEqual(res, [("a", 0)])
        with patch.object(dominio, "dominio", return_value={"u1": {"nivel": 5}, "u2": {"nivel": 0}}):
            res = planificador.elegir(p, c, date(2026, 10, 19), m, 1)
        self.assertEqual(res, [("c", 0)])

    def test_apagado_no_usa_el_planificador_aunque_den_distinto(self):
        p, c, m = fixture()
        hoy = date(2026, 10, 19)
        with patch.object(dominio, "dominio", return_value={"ua": {"nivel": 5}, "uc": {"nivel": 0}}):
            adaptativo = planificador.elegir_sesion(p, c, hoy, m, {"TORTU_PLANIFICADOR": "adaptativo"}, 1)
            apagado = planificador.elegir_sesion(p, c, hoy, m, {}, 1)
        self.assertEqual(adaptativo, [("c", 0)])
        self.assertEqual(apagado, practica.elegir(p, c, hoy, 1))
        self.assertNotEqual(adaptativo, apagado)

    def test_una_sola_leccion_vencida_llena_la_sesion_como_practica(self):
        cursos = [{"id": "c", "secciones": [{"lecciones": [{"id": "a", "pasos": [{"tipo": "elegir"}] * 6}]}]}]
        p = {"lecciones": {"a": {"pasos": {str(i): {"fecha": "2026-10-01"} for i in range(6)}}}, "repaso": {}}
        m = {"ua": {"tipo": "lecciones", "curso": "c", "lecciones": ["a"]}}
        hoy = date(2026, 10, 19)
        res = planificador.elegir(p, cursos, hoy, m)
        self.assertEqual(len(res), len(practica.elegir(p, cursos, hoy)))
        self.assertEqual(len(res), 6)
