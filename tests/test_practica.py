"""Práctica del día: repaso espaciado e intercalado."""
import shutil
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from tortuscript import persistencia_local, contenido, practica, progreso

CURSOS = contenido.todos_los_cursos()
HOY = date(2026, 9, 25)


def con_pasos(*pares, fecha="2026-09-20"):
    """Progreso con pasos terminados: pares = (leccion, [índices])."""
    p = {"lecciones": {}, "repaso": {}}
    for leccion_id, indices in pares:
        p["lecciones"][leccion_id] = {"pasos": {str(i): {"xp": 5, "perfecto": True, "fecha": fecha} for i in indices},
                                      "completada": True}
    return p


class TestCandidatos(unittest.TestCase):
    def test_solo_pasos_rapidos_de_lecciones_con_pasos_hechos(self):
        # hola-mundo: 0 explicación, 1 elegir, 2 completar, 3 ordenar, 4 predecir, 5 escribir
        p = con_pasos(("hola-mundo", [0, 1, 2, 3, 4, 5]))
        pasos = sorted(c["paso"] for c in practica.candidatos(p, CURSOS, HOY))
        self.assertEqual(pasos, [1, 2, 3, 4])                       # ni la explicación ni el 'escribir'

    def test_una_tarjeta_nueva_toca_al_dia_siguiente(self):
        p = con_pasos(("hola-mundo", [1]), fecha=str(HOY))
        self.assertEqual(practica.candidatos(p, CURSOS, HOY), [])
        self.assertEqual(len(practica.candidatos(p, CURSOS, HOY + timedelta(days=1))), 1)

    def test_progreso_viejo_sin_fecha_ya_toca(self):
        p = con_pasos(("hola-mundo", [1]))
        del p["lecciones"]["hola-mundo"]["pasos"]["1"]["fecha"]
        self.assertEqual(len(practica.candidatos(p, CURSOS, HOY)), 1)

    def test_lo_programado_manda_sobre_la_fecha(self):
        p = con_pasos(("hola-mundo", [1]))
        p["repaso"]["hola-mundo:1"] = {"caja": 2, "proximo": str(HOY + timedelta(days=3))}
        self.assertEqual(practica.candidatos(p, CURSOS, HOY), [])
        self.assertEqual(len(practica.candidatos(p, CURSOS, HOY + timedelta(days=3))), 1)

    def test_lecciones_o_pasos_que_ya_no_existen_se_ignoran(self):
        p = con_pasos(("no-existe", [1]), ("hola-mundo", [1, 99]))
        self.assertEqual([c["paso"] for c in practica.candidatos(p, CURSOS, HOY)], [1])

    def test_pendientes(self):
        p = con_pasos(("hola-mundo", [1, 2]), ("texto-o-cuenta", [1]))
        self.assertEqual(practica.pendientes(p, CURSOS, HOY), 3)


class TestElegir(unittest.TestCase):
    def test_intercala_lecciones_y_lo_mas_atrasado_va_primero(self):
        p = con_pasos(("hola-mundo", [1, 2, 3, 4], ), ("texto-o-cuenta", [1, 2, 3, 4]), fecha="2026-09-10")
        p["lecciones"]["hola-mundo"]["pasos"]["2"]["fecha"] = "2026-08-01"                 # el más atrasado
        elegidas = practica.elegir(p, CURSOS, HOY, cantidad=4)
        self.assertEqual(elegidas[0], ("hola-mundo", 2))
        self.assertEqual([l for l, _ in elegidas], ["hola-mundo", "texto-o-cuenta", "hola-mundo", "texto-o-cuenta"])
        self.assertEqual(len(set(elegidas)), 4)

    def test_a_lo_sumo_dos_por_leccion_si_hay_variedad(self):
        p = con_pasos(("hola-mundo", [1, 2, 3, 4]), ("texto-o-cuenta", [1, 2]), ("dos-lineas", [1, 2]))
        elegidas = practica.elegir(p, CURSOS, HOY, cantidad=6)
        self.assertEqual(len(elegidas), 6)
        for leccion_id in ("hola-mundo", "texto-o-cuenta", "dos-lineas"):
            self.assertEqual(sum(1 for l, _ in elegidas if l == leccion_id), 2)

    def test_con_una_sola_leccion_se_completa_la_sesion(self):
        p = con_pasos(("hola-mundo", [1, 2, 3, 4]))
        self.assertEqual(len(practica.elegir(p, CURSOS, HOY, cantidad=6)), 4)             # hay 4 en total
        self.assertEqual(len(practica.elegir(p, CURSOS, HOY, cantidad=3)), 3)

    def test_sin_nada_pendiente(self):
        self.assertEqual(practica.elegir({}, CURSOS, HOY), [])
        self.assertEqual(practica.elegir(con_pasos(("hola-mundo", [1]), fecha=str(HOY)), CURSOS, HOY), [])


class TestRegistrar(unittest.TestCase):
    def test_cajas_e_intervalos(self):
        p = {}
        esperado = [(1, 1), (2, 2), (3, 4), (4, 8), (5, 16), (5, 16)]                    # caja, días de espera
        for caja, dias in esperado:
            t = practica.registrar(p, "l", 1, True, HOY)
            self.assertEqual((t["caja"], t["proximo"]), (caja, str(HOY + timedelta(days=dias))))
        self.assertEqual(p["repaso"]["l:1"]["aciertos"], 6)

    def test_un_error_vuelve_a_la_caja_1_y_toca_mañana(self):
        p = {}
        for _ in range(3):
            practica.registrar(p, "l", 1, True, HOY)
        t = practica.registrar(p, "l", 1, False, HOY)
        self.assertEqual((t["caja"], t["proximo"], t["fallos"]), (1, str(HOY + timedelta(days=1)), 1))

    def test_las_tarjetas_son_independientes(self):
        p = {}
        practica.registrar(p, "l", 1, True, HOY)
        practica.registrar(p, "l", 2, False, HOY)
        self.assertEqual((p["repaso"]["l:1"]["caja"], p["repaso"]["l:2"]["caja"]), (1, 1))
        practica.registrar(p, "l", 1, True, HOY)
        self.assertEqual(p["repaso"]["l:1"]["caja"], 2)


class TestProgresoPractica(unittest.TestCase):
    def setUp(self):
        self._dir = Path(tempfile.mkdtemp())
        self._orig = (persistencia_local.DIRECTORIO, persistencia_local.PERFIL_ACTUAL)
        persistencia_local.DIRECTORIO = self._dir
        persistencia_local.PERFIL_ACTUAL = "default"

    def tearDown(self):
        persistencia_local.DIRECTORIO, persistencia_local.PERFIL_ACTUAL = self._orig
        shutil.rmtree(self._dir)

    def test_acierto_da_xp_con_tope_diario_y_cuenta_para_la_racha(self):
        p = persistencia_local.cargar_progreso()
        ganado = [progreso.registrar_practica(p, "hola-mundo", 1 + i % 4, True, HOY) for i in range(8)]
        self.assertEqual(ganado, [2] * 6 + [0, 0])                                       # tope de 12 XP por día
        self.assertEqual((p["xp_total"], p["racha"]), (12, 1))
        self.assertEqual(progreso.xp_de_hoy(p, HOY), 12)

    def test_error_no_da_xp_pero_reprograma(self):
        p = persistencia_local.cargar_progreso()
        self.assertEqual(progreso.registrar_practica(p, "hola-mundo", 1, False, HOY), 0)
        self.assertEqual(p["repaso"]["hola-mundo:1"]["caja"], 1)
        self.assertEqual(p["xp_total"], 0)

    def test_se_guarda_y_los_pasos_de_leccion_recuerdan_la_fecha(self):
        p = persistencia_local.cargar_progreso()
        progreso.registrar_practica(p, "hola-mundo", 1, True, HOY)
        self.assertTrue(persistencia_local.guardar_progreso(p))
        self.assertIn("hola-mundo:1", persistencia_local.cargar_progreso()["repaso"])
        progreso.registrar_paso_leccion(p, "hola-mundo", 1, 5, True, 6)
        fecha = p["lecciones"]["hola-mundo"]["pasos"]["1"]["fecha"]
        progreso.registrar_paso_leccion(p, "hola-mundo", 1, 5, True, 6)
        self.assertEqual(p["lecciones"]["hola-mundo"]["pasos"]["1"]["fecha"], fecha)      # no se pisa

    def test_perfil_viejo_se_migra(self):
        (self._dir / "progreso_default.json").write_text(
            '{"version": 5, "xp_total": 10, "ejercicios": {}}', encoding="utf-8")
        p = persistencia_local.cargar_progreso()
        self.assertEqual((p["repaso"], p["xp_practica"]), ({}, {}))


if __name__ == "__main__":
    unittest.main()
