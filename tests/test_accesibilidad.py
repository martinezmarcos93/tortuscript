"""Accesibilidad: ajustes por perfil (letra, contraste, movimiento, voz) y marcas de la página."""
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tortuscript import persistencia_local, progreso

try:
    import flask  # noqa: F401
    HAY_FLASK = True
except ImportError:
    HAY_FLASK = False


class Base(unittest.TestCase):
    def setUp(self):
        self._dir = Path(tempfile.mkdtemp())
        self._orig = (persistencia_local.DIRECTORIO, persistencia_local.PERFIL_ACTUAL)
        persistencia_local.DIRECTORIO = self._dir
        persistencia_local.PERFIL_ACTUAL = "default"

    def tearDown(self):
        persistencia_local.DIRECTORIO, persistencia_local.PERFIL_ACTUAL = self._orig
        shutil.rmtree(self._dir)


class TestAjustes(Base):
    def test_de_fabrica(self):
        p = persistencia_local.cargar_progreso()
        self.assertEqual(progreso.ajustes_de(p), {"tam": "normal", "contraste": "normal", "movimiento": "normal",
                                                  "letra": "normal", "voz": "no", "velocidad": "normal"})

    def test_guardar_y_recordar(self):
        p = persistencia_local.cargar_progreso()
        self.assertTrue(progreso.guardar_ajustes(p, tam="grande", contraste="alto", voz="si"))
        self.assertTrue(persistencia_local.guardar_progreso(p))
        again = progreso.ajustes_de(persistencia_local.cargar_progreso())
        self.assertEqual((again["tam"], again["contraste"], again["voz"], again["letra"]), ("grande", "alto", "si", "normal"))

    def test_valores_invalidos_no_cambian_nada(self):
        p = persistencia_local.cargar_progreso()
        for cambios in ({"tam": "gigante"}, {"inventado": "x"}, {"tam": "grande", "contraste": "medio"}):
            with self.subTest(cambios=cambios):
                self.assertFalse(progreso.guardar_ajustes(p, **cambios))
        self.assertEqual(progreso.ajustes_de(p)["tam"], "normal")                      # ni siquiera el válido del último

    def test_valor_dañado_en_el_archivo_se_ignora(self):
        (self._dir / "progreso_default.json").write_text(
            '{"version": 7, "xp_total": 0, "ejercicios": {}, "config": {"ajustes": {"tam": "gigante", "voz": "si"}}}', encoding="utf-8")
        a = progreso.ajustes_de(persistencia_local.cargar_progreso())
        self.assertEqual((a["tam"], a["voz"]), ("normal", "si"))

    def test_perfil_viejo_sin_ajustes_se_migra(self):
        (self._dir / "progreso_default.json").write_text(
            '{"version": 7, "xp_total": 5, "ejercicios": {}, "config": {"onboarding": true, "meta_min": 5}}', encoding="utf-8")
        p = persistencia_local.cargar_progreso()
        self.assertEqual(p["config"]["meta_min"], 5)
        self.assertEqual(p["config"]["ajustes"]["contraste"], "normal")
        self.assertEqual(p["version"], progreso.VERSION_ESQUEMA)

    def test_cada_perfil_tiene_los_suyos(self):
        a = persistencia_local.cargar_progreso("lua")
        progreso.guardar_ajustes(a, tam="enorme")
        self.assertTrue(persistencia_local.guardar_progreso(a))
        self.assertEqual(progreso.ajustes_de(persistencia_local.cargar_progreso("lua"))["tam"], "enorme")
        self.assertEqual(progreso.ajustes_de(persistencia_local.cargar_progreso("tomi"))["tam"], "normal")

    def test_los_valores_de_fabrica_son_validos(self):
        for nombre, valores in progreso.AJUSTES.items():
            self.assertIn(progreso.PROGRESO_INICIAL["config"]["ajustes"][nombre], valores)


@unittest.skipUnless(HAY_FLASK, "Flask no instalado")
class TestPaginas(Base):
    def setUp(self):
        super().setUp()
        from web.app import create_app
        app = create_app(token="t")
        app.config.update(
            TESTING=True,
            ACCOUNT_DB=self._dir / "cuentas.sqlite3",
            ACCOUNT_COOKIE_SECURE=False,
            PROGRESS_DIR=self._dir / "progreso_perfiles",
        )
        self.c = app.test_client()
        self.h = {"X-Tortu-Token": "t"}
        from fixtures_cuenta import preparar_sesion_educativa
        preparar_sesion_educativa(app, self.c, email="accesibilidad@example.com", nombre="Ana", token="t")

    def post(self, ruta, datos=None):
        return self.c.post(ruta, json=datos or {}, headers=self.h)

    def test_los_ajustes_llegan_como_atributos_del_html(self):
        html = self.c.get("/").get_data(as_text=True)
        self.assertRegex(html, r'<html lang="es"[^>]*data-tam="normal"')
        self.assertIn('data-contraste="normal"', html)
        r = self.post("/api/ajustes", {"tam": "grande", "contraste": "alto", "movimiento": "reducido", "letra": "legible"}).get_json()
        self.assertTrue(r["ok"])
        html = self.c.get("/").get_data(as_text=True)
        for esperado in ('data-tam="grande"', 'data-contraste="alto"', 'data-movimiento="reducido"', 'data-letra="legible"'):
            self.assertIn(esperado, html)

    def test_api_rechaza_valores_invalidos_y_pide_token(self):
        self.assertEqual(self.post("/api/ajustes", {"tam": "gigante"}).status_code, 400)
        self.assertEqual(self.c.post("/api/ajustes", json={"tam": "grande"}).status_code, 403)
        self.assertEqual(self.post("/api/ajustes", {"velocidad": "rapida"}).get_json()["ajustes"]["velocidad"], "rapida")

    def test_cada_pagina_tiene_salto_al_contenido_y_marcas(self):
        for ruta in ("/", "/referencia", "/mapa", "/experimentar", "/tortuga", "/liga", "/logros", "/proyectos", "/resumen", "/leccion/hola-mundo"):
            with self.subTest(ruta=ruta):
                html = self.c.get(ruta).get_data(as_text=True)
                self.assertIn('<a class="saltar" href="#contenido">', html)
                self.assertIn('<main id="contenido"', html)
                self.assertIn('<nav class="nav" aria-label="Principal">', html)
                self.assertIn('id="modal-ajustes"', html)
                self.assertEqual(html.count("<main"), 1)

    def test_el_modal_de_ajustes_marca_lo_elegido_y_tiene_roles(self):
        self.post("/api/ajustes", {"tam": "enorme"})
        html = self.c.get("/").get_data(as_text=True)
        self.assertRegex(html, r'role="radio" data-valor="enorme" aria-checked="true"')
        self.assertRegex(html, r'role="radio" data-valor="normal" aria-checked="false"')
        self.assertEqual(html.count('role="radiogroup"'), 6)

    def test_ventanas_con_rol_dialogo_y_etiqueta(self):
        html = self.c.get("/").get_data(as_text=True)
        for modal in re.findall(r'<div class="modal"[^>]*>', html):
            self.assertIn('role="dialog"', modal)
            self.assertIn("aria-modal", modal)
            self.assertIn("aria-labelledby", modal)

    def test_los_botones_de_solo_icono_tienen_nombre(self):
        html = self.c.get("/").get_data(as_text=True)
        for boton in re.findall(r'<button[^>]*id="(?:btn-sonido|btn-ajustes)"[^>]*>', html):
            self.assertIn("aria-label", boton)

    def test_el_feedback_de_las_lecciones_se_anuncia(self):
        html = self.c.get("/leccion/hola-mundo").get_data(as_text=True)
        self.assertIn('id="lec-mensaje" role="status" aria-live="polite"', html)

    def test_hay_estilos_para_cada_ajuste(self):
        with self.c.get("/static/css/tortu.css") as r:
            css = r.get_data(as_text=True)
        for regla in ('html[data-tam="grande"]', 'html[data-tam="enorme"]', 'html[data-contraste="alto"]',
                      'html[data-movimiento="reducido"]', 'html[data-letra="legible"]', ":focus-visible", ".saltar"):
            self.assertIn(regla, css)


if __name__ == "__main__":
    unittest.main()
