"""Tests de progreso: guardado atómico, recuperación, perfiles, racha, niveles."""
import json
import shutil
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from tortuscript import persistencia_local, progreso


class BaseTemporal(unittest.TestCase):
    def setUp(self):
        self._dir = Path(tempfile.mkdtemp())
        self._original = persistencia_local.DIRECTORIO
        self._perfil = persistencia_local.PERFIL_ACTUAL
        persistencia_local.DIRECTORIO = self._dir
        persistencia_local.PERFIL_ACTUAL = "default"

    def tearDown(self):
        persistencia_local.DIRECTORIO = self._original
        persistencia_local.PERFIL_ACTUAL = self._perfil
        shutil.rmtree(self._dir)


class TestGuardado(BaseTemporal):
    def test_ida_y_vuelta(self):
        p = persistencia_local.cargar_progreso()
        progreso.registrar_ejercicio(p, 0, 3, 30)
        self.assertTrue(persistencia_local.guardar_progreso(p))
        p2 = persistencia_local.cargar_progreso()
        self.assertEqual(p2["xp_total"], 30)
        self.assertEqual(p2["ejercicios"]["0"]["estrellas"], 3)

    def test_campos_internos_no_se_guardan(self):
        p = persistencia_local.cargar_progreso()
        persistencia_local.guardar_progreso(p)
        data = json.loads(persistencia_local.get_archivo_progreso().read_text(encoding="utf-8"))
        self.assertNotIn("_perfil", data)
        self.assertEqual(data["version"], progreso.VERSION_ESQUEMA)

    def test_json_corrupto_no_se_pierde_y_se_recupera_del_bak(self):
        # Bug P1: antes se arrancaba de cero y el siguiente guardado pisaba el archivo.
        p = persistencia_local.cargar_progreso()
        progreso.registrar_ejercicio(p, 0, 3, 30)
        self.assertTrue(persistencia_local.guardar_progreso(p))
        progreso.registrar_ejercicio(p, 1, 3, 30)          # crea el .bak con xp=30
        self.assertTrue(persistencia_local.guardar_progreso(p))
        archivo = persistencia_local.get_archivo_progreso()
        archivo.write_text("{ roto", encoding="utf-8")
        recuperado = persistencia_local.cargar_progreso()
        self.assertEqual(recuperado["xp_total"], 30)      # desde el .bak
        apartados = list(self._dir.glob("progreso_default.json.corrupto-*"))
        self.assertEqual(len(apartados), 1)
        self.assertEqual(apartados[0].read_text(encoding="utf-8"), "{ roto")

    def test_json_corrupto_sin_bak_arranca_de_cero_sin_borrar_el_danado(self):
        persistencia_local.get_archivo_progreso().write_text("[]", encoding="utf-8")
        p = persistencia_local.cargar_progreso()
        self.assertEqual(p["xp_total"], 0)
        self.assertTrue(list(self._dir.glob("*.corrupto-*")))

    def test_no_quedan_temporales(self):
        persistencia_local.guardar_progreso(persistencia_local.cargar_progreso())
        self.assertEqual(list(self._dir.glob("*.tmp")), [])

    def test_migra_archivo_viejo(self):
        persistencia_local.get_archivo_progreso().write_text(
            json.dumps({"xp_total": 10, "ejercicios": {}}), encoding="utf-8")
        p = persistencia_local.cargar_progreso()
        self.assertEqual(p["xp_total"], 10)
        self.assertIn("sesion_hoy", p)

    def test_migra_json_valido_con_tipos_anidados_danados(self):
        # Un JSON sintácticamente válido no debe romper el perfil por config/lecciones mal tipadas.
        persistencia_local.get_archivo_progreso().write_text(
            json.dumps({
                "xp_total": 17,
                "ejercicios": {},
                "config": {"ajustes": []},
                "lecciones": [],
                "xp_por_dia": None,
            }),
            encoding="utf-8",
        )
        p = persistencia_local.cargar_progreso()
        self.assertEqual(p["xp_total"], 17)
        self.assertIsInstance(p["config"], dict)
        self.assertIsInstance(p["config"]["ajustes"], dict)
        self.assertIsInstance(p["lecciones"], dict)
        self.assertIsInstance(p["xp_por_dia"], dict)
        self.assertEqual(p["config"]["ajustes"]["tam"], "normal")


class TestPerfiles(BaseTemporal):
    def test_ventana_abierta_no_mezcla_perfiles(self):
        # Bug P3: el progreso cargado con A se guardaba en el archivo de B.
        persistencia_local.set_perfil("ana")
        p_ana = persistencia_local.cargar_progreso()
        persistencia_local.set_perfil("beto")
        progreso.registrar_ejercicio(p_ana, 0, 3, 30)
        self.assertTrue(persistencia_local.guardar_progreso(p_ana))
        self.assertTrue(persistencia_local.get_archivo_progreso("ana").exists())
        self.assertFalse(persistencia_local.get_archivo_progreso("beto").exists())

    def test_sanitizar_perfil(self):
        self.assertEqual(progreso.sanitizar_perfil("../../Etc"), "etc")
        self.assertEqual(progreso.sanitizar_perfil("  Juan Pérez "), "juan_pérez")
        self.assertEqual(progreso.sanitizar_perfil("///"), "")

    def test_perfil_recordado(self):
        self.assertEqual(persistencia_local.perfil_recordado(), "default")
        persistencia_local.recordar_perfil("ana")
        self.assertEqual(persistencia_local.perfil_recordado(), "ana")

    def test_set_perfil_vacio_no_cambia(self):
        persistencia_local.set_perfil("ana")
        self.assertEqual(persistencia_local.set_perfil("***"), "ana")


class TestRachaYSesion(BaseTemporal):
    def test_racha_consecutiva_y_corte(self):
        p = persistencia_local.cargar_progreso()
        d = date(2026, 9, 1)
        progreso.actualizar_racha(p, d)
        progreso.actualizar_racha(p, d + timedelta(days=1))
        self.assertEqual(p["racha"], 2)
        progreso.actualizar_racha(p, d + timedelta(days=5))
        self.assertEqual(p["racha"], 1)
        self.assertEqual(p["racha_max"], 2)

    def test_racha_vigente_se_corta_al_mostrar(self):
        # Bug P5: se mostraba la racha vieja después de días sin jugar.
        p = {"racha": 5, "ultimo_dia": "2026-09-01"}
        self.assertEqual(progreso.racha_vigente(p, date(2026, 9, 2)), 5)
        self.assertEqual(progreso.racha_vigente(p, date(2026, 9, 4)), 0)

    def test_sesion_de_ayer_no_aparece_como_de_hoy(self):
        # Bug P6.
        p = persistencia_local.cargar_progreso()
        p.update({"ultimo_dia": "2026-09-01", "sesion_hoy": [0]})
        p["ejercicios"]["0"] = {"estrellas": 3, "xp": 30, "completado": True}
        ej = [{"titulo": "1", "nivel": 1}]
        self.assertEqual(progreso.resumen_sesion_hoy(p, ej, date(2026, 9, 2))["completados"], [])
        self.assertEqual(len(progreso.resumen_sesion_hoy(p, ej, date(2026, 9, 1))["completados"]), 1)

    def test_xp_solo_sube_si_mejora(self):
        p = persistencia_local.cargar_progreso()
        progreso.registrar_ejercicio(p, 0, 1, 10)
        progreso.registrar_ejercicio(p, 0, 3, 30)
        progreso.registrar_ejercicio(p, 0, 2, 20)
        self.assertEqual(p["xp_total"], 30)


class TestNiveles(unittest.TestCase):
    def test_nivel_maximo_alcanzable(self):
        # Bug P4: con 900 XP posibles no se pasaba del nivel 7. Ahora el máximo sale del curso entero.
        from tortuscript import contenido, leccion
        maximo = leccion.xp_maximo(contenido.cargar_curso())
        self.assertEqual(progreso.calcular_nivel(maximo)[0], 10)
        self.assertLess(progreso.calcular_nivel(maximo // 2)[0], 8)      # y no se llega a mitad del camino

    def test_barra_no_desborda(self):
        for xp in (0, 49, 50, 799, 800, 900, 5000):
            _, actual, total = progreso.calcular_nivel(xp)
            self.assertLessEqual(actual, total)
            self.assertGreaterEqual(actual, 0)


def _contraste_con_blanco(color):
    """Contraste WCAG entre un #rrggbb y el fondo blanco del lienzo."""
    canales = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lineales = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canales]
    luminancia = 0.2126 * lineales[0] + 0.7152 * lineales[1] + 0.0722 * lineales[2]
    return 1.05 / (luminancia + 0.05)


class TestColorDeLaTortuga(unittest.TestCase):
    def test_un_color_por_nivel_distinto_y_legible_sobre_el_lienzo(self):
        colores = [progreso.color_tortuga(n) for n in range(1, 11)]
        self.assertEqual(len(set(colores)), 10)
        for nivel, color in enumerate(colores, start=1):
            self.assertRegex(color, r"^#[0-9a-f]{6}$")
            self.assertGreaterEqual(_contraste_con_blanco(color), 3.0, f"nivel {nivel}: {color}")

    def test_el_nivel_1_es_el_verde_de_siempre_y_los_extremos_no_fallan(self):
        from tortuscript import tortuga
        self.assertEqual(progreso.color_tortuga(1), tortuga.COLOR_INICIAL)
        self.assertEqual(progreso.color_tortuga(0), progreso.color_tortuga(1))
        self.assertEqual(progreso.color_tortuga(99), progreso.color_tortuga(10))

    def test_el_lapiz_no_depende_del_nivel(self):
        """El cuerpo usa el color del nivel; el lápiz arranca siempre en verde (así no cambian los dibujos a comparar)."""
        js = (Path(__file__).resolve().parent.parent / "web/static/js/tortuga.js").read_text(encoding="utf-8")
        from tortuscript import tortuga
        self.assertIn(f'const VERDE = "{tortuga.COLOR_INICIAL}"', js)
        self.assertIn("color: VERDE", js)                         # estado inicial del lápiz
        self.assertIn("ctx.fillStyle = colorCuerpo()", js)        # el cuerpo no usa el color del lápiz
        self.assertEqual(tortuga.trazos([{"o": "avanzar", "v": 10}])[0][4], tortuga.COLOR_INICIAL)


class TestRegreso(unittest.TestCase):
    HOY = date(2026, 9, 26)

    def test_nada_que_contar_si_nunca_vino_o_ya_vino_hoy(self):
        self.assertIsNone(progreso.regreso({"ultimo_dia": None}, self.HOY))
        self.assertIsNone(progreso.regreso({"ultimo_dia": "2026-09-26"}, self.HOY))
        self.assertIsNone(progreso.regreso({"ultimo_dia": "cualquier cosa"}, self.HOY))

    def test_cuenta_desde_cuando_y_lo_que_gano_ese_dia(self):
        p = {"ultimo_dia": "2026-09-25", "xp_por_dia": {"2026-09-25": 40, "2026-09-20": 10}}
        self.assertEqual(progreso.regreso(p, self.HOY), {"dias": 1, "xp": 40})
        p["ultimo_dia"] = "2026-09-20"
        self.assertEqual(progreso.regreso(p, self.HOY), {"dias": 6, "xp": 10})
        self.assertEqual(progreso.regreso({"ultimo_dia": "2026-09-01"}, self.HOY), {"dias": 25, "xp": 0})


if __name__ == "__main__":
    unittest.main()
