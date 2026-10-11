"""ADR-050: lo gratis y lo premium, la inscripción, la cuota mensual del 1 al 10 y la puerta en servidor."""
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tests.test_federacion_respuestas import _Base
from tortuscript import catalogo_producto, pagos
from tortuscript.progreso_childprofile import ProgresoChildProfile
from tortuscript.progreso_contrato import nuevo_snapshot

PREMIUM = "tortuscript-premium"
AR = timezone(timedelta(hours=-3))
LINKS = {(PREMIUM, "inscripcion"): "https://mpago.la/inscripcion-prueba", (PREMIUM, "cuota"): "https://mpago.la/cuota-prueba"}


def oferta(**cambios):
    datos = dict(alias="tortu.prueba", importe_centavos=1500000, inscripcion_centavos=3000000)
    datos.update(cambios)
    return pagos.ConfiguracionPagos(**datos)


class TestCatalogo(unittest.TestCase):
    def test_diecinueve_unidades_gratis_y_dieciocho_premium(self):
        catalogo = catalogo_producto.cargar_catalogo()
        estados = [(i["id"], u["id"], u.get("estado_acceso")) for i in catalogo["itinerarios"] for u in i.get("unidades", [])]
        self.assertEqual(len(estados), 37)
        self.assertEqual(sum(1 for *_, e in estados if e == "gratuito"), 19)
        self.assertEqual(sum(1 for *_, e in estados if e == "premium"), 18)
        self.assertNotIn(None, [e for *_, e in estados])
        gratis = {u for _, u, e in estados if e == "gratuito"}
        self.assertTrue({"python-puente", "web-html-estructura", "sql-tablas"} <= gratis)
        self.assertEqual({i for i, _, e in estados if e == "gratuito"}, {"alfabetizacion-tecnologica", "python-fundamentos", "web-esencial", "sql-fundamentos"})
        self.assertEqual(sum(len(catalogo_producto.cargar_mapa()["unidades"][u].get("lecciones", [])) for u in gratis), 20)

    def test_las_lecciones_y_proyectos_se_ubican_en_su_unidad(self):
        self.assertEqual(catalogo_producto.unidad_de_leccion("py-if"), "python-control")
        self.assertIsNone(catalogo_producto.unidad_de_leccion("hola-mundo"))           # fuera del catálogo
        self.assertEqual(catalogo_producto.unidad_de_proyecto("ficha-criatura"), "integrador-ficha-criatura")


class TestCiclo(unittest.TestCase):
    def test_el_corte_es_el_11_a_las_00_de_argentina(self):
        self.assertEqual(pagos.corte_del_mes((2026, 11)), datetime(2026, 12, 11, 0, 0, tzinfo=AR))
        self.assertEqual(pagos.corte_del_mes((2026, 12)), datetime(2027, 1, 11, 0, 0, tzinfo=AR))
        self.assertEqual(pagos.ultimo_mes_cubierto(pagos.corte_del_mes((2026, 12))), (2026, 12))

    def test_la_hora_local_decide_el_mes_no_el_utc(self):
        # 1/12 a las 01:00 UTC todavía es 30/11 en Argentina.
        self.assertEqual(pagos.mes_de(datetime(2026, 12, 1, 1, 0, tzinfo=timezone.utc)), (2026, 11))
        self.assertEqual(pagos.mes_de(datetime(2026, 12, 1, 3, 0, tzinfo=timezone.utc)), (2026, 12))

    def test_periodo_que_cubre_un_pago(self):
        ahora = datetime(2026, 11, 5, 12, tzinfo=AR)
        primero, ultimo, corte = pagos.periodo_que_cubre_un_pago(ahora, None, 1)
        self.assertEqual((primero, ultimo, corte), ((2026, 11), (2026, 11), datetime(2026, 12, 11, tzinfo=AR)))
        _, ultimo, corte = pagos.periodo_que_cubre_un_pago(ahora, None, pagos.MESES_DE_LA_INSCRIPCION)
        self.assertEqual((ultimo, corte), ((2026, 11), datetime(2026, 12, 11, tzinfo=AR)))
        # Con acceso vigente hasta el 10/12 (noviembre pago), pagar en la ventana cubre diciembre.
        _, ultimo, _ = pagos.periodo_que_cubre_un_pago(datetime(2026, 12, 3, tzinfo=AR), pagos.corte_del_mes((2026, 11)), 1)
        self.assertEqual(ultimo, (2026, 12))
        # Vencido el acceso, se paga desde el mes en curso (no se cobran los meses sin acceso).
        primero, _, _ = pagos.periodo_que_cubre_un_pago(datetime(2027, 3, 2, tzinfo=AR), pagos.corte_del_mes((2026, 11)), 1)
        self.assertEqual(primero, (2027, 3))


class TestConfiguracionDeCobro(unittest.TestCase):
    ENTORNO = {"TORTU_PAGO_ALIAS": "a", "TORTU_PAGO_IMPORTE": "15000", "TORTU_PAGO_INSCRIPCION": "30000",
               "TORTU_PAGO_IMPORTE_CROCO": "30000", "TORTU_PAGO_INSCRIPCION_CROCO": "60000"}

    def test_los_importes_de_marcos(self):
        o = pagos.configuracion_desde_entorno(self.ENTORNO)
        self.assertEqual([(p["producto"], p["inscripcion_legible"], p["importe_legible"]) for p in o.planes()],
                         [(PREMIUM, "$ 30.000", "$ 15.000"), ("croco-script", "$ 60.000", "$ 30.000")])

    def test_una_inscripcion_sin_mantenimiento_se_rechaza(self):
        with self.assertRaises(pagos.PagoError):
            pagos.configuracion_desde_entorno({"TORTU_PAGO_ALIAS": "a", "TORTU_PAGO_IMPORTE_CROCO": "30000", "TORTU_PAGO_INSCRIPCION": "30000"})

    def test_los_enlaces_de_pago_solo_son_https_sin_nada_raro(self):
        o = pagos.configuracion_desde_entorno({**self.ENTORNO, "TORTU_PAGO_LINK_INSCRIPCION": "https://mpago.la/abc",
                                               "TORTU_PAGO_LINK_CUOTA_CROCO": "https://mpago.la/xyz"})
        self.assertEqual(o.enlace(PREMIUM, "inscripcion"), "https://mpago.la/abc")
        self.assertEqual(o.enlace("croco-script", "cuota"), "https://mpago.la/xyz")
        self.assertEqual(o.enlace(PREMIUM, "cuota"), "")
        for malo in ("javascript:alert(1)", "http://mpago.la/abc", "https://mpago.la/a b", 'https://x.test/"onclick=1', "https://x.test/<b>"):
            with self.subTest(enlace=malo), self.assertRaises(pagos.PagoError):
                pagos.configuracion_desde_entorno({**self.ENTORNO, "TORTU_PAGO_LINK_CUOTA": malo})


class TestInscripcionYCuota(unittest.TestCase):
    def setUp(self):
        from tortuscript.auth import AuthRepository
        from tortuscript.cuentas import CuentaRepository
        self.tmp = Path(tempfile.mkdtemp())
        db = self.tmp / "c.sqlite3"
        self.cuentas = CuentaRepository(db)
        self.cuentas.ensure_schema()
        AuthRepository(db).ensure_schema()
        self.servicio = pagos.ServicioPagos(db)
        self.servicio.ensure_schema()
        self.cuenta = self.cuentas.crear_account("familia@example.com").id
        self.plan = oferta().plan(PREMIUM)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def pagar(self, ahora):
        cobro = self.servicio.cobro_para(self.plan, self.cuenta)
        orden = self.servicio.crear_orden(self.cuenta, PREMIUM, "transferencia", cobro["importe_centavos"], "ARS",
                                          30 * cobro["meses"], ahora=ahora, meses=cobro["meses"])
        self.servicio.confirmar_orden(orden["id"], ahora=ahora)
        return cobro

    def test_la_primera_vez_se_cobra_la_inscripcion_y_despues_la_cuota(self):
        primero = self.pagar(datetime(2026, 11, 5, 12, tzinfo=AR))
        self.assertEqual((primero["concepto"], primero["importe_legible"], primero["meses"]), ("inscripcion", "$ 30.000", 1))
        self.assertEqual(self.servicio.cobro_para(self.plan, self.cuenta)["concepto"], "mensual")
        self.assertEqual(self.servicio.cobro_para(self.plan, self.cuenta)["importe_legible"], "$ 15.000")

    def test_sin_inscripcion_configurada_todo_es_el_mensual(self):
        self.assertEqual(self.servicio.cobro_para(oferta(inscripcion_centavos=0).plan(PREMIUM), self.cuenta)["concepto"], "mensual")

    def test_la_inscripcion_cubre_solo_el_mes_en_vigencia_y_el_11_se_corta(self):
        self.pagar(datetime(2026, 11, 28, 12, tzinfo=AR))                    # inscripción el 28: cubre noviembre
        t = lambda *a: datetime(*a, tzinfo=AR)                                # noqa: E731
        self.assertTrue(self.cuentas.tiene_entitlement(self.cuenta, PREMIUM))
        e = self.servicio.estado_cuota(self.cuenta, PREMIUM, t(2026, 11, 29, 12))
        self.assertEqual((e["al_dia"], e["cuota_pagada"], e["debe_pagar"]), (True, True, False))
        e = self.servicio.estado_cuota(self.cuenta, PREMIUM, t(2026, 12, 5, 12))
        self.assertEqual((e["al_dia"], e["cuota_pagada"], e["debe_pagar"], e["dias_para_pagar"]), (True, False, True, 6))
        e = self.servicio.estado_cuota(self.cuenta, PREMIUM, t(2026, 12, 10, 23, 59))
        self.assertEqual((e["al_dia"], e["dias_para_pagar"]), (True, 1))
        e = self.servicio.estado_cuota(self.cuenta, PREMIUM, t(2026, 12, 11, 0, 1))
        self.assertEqual((e["al_dia"], e["vencida"], e["debe_pagar"]), (False, True, True))

    def test_el_acceso_se_corta_en_la_base_el_11(self):
        self.pagar(datetime(2026, 11, 5, 12, tzinfo=AR))
        from unittest import mock
        corte = pagos.corte_del_mes((2026, 11))
        with mock.patch("tortuscript.cuentas.datetime") as reloj:
            reloj.now.return_value = corte - timedelta(minutes=1)
            reloj.fromisoformat = datetime.fromisoformat
            self.assertTrue(self.cuentas.tiene_entitlement(self.cuenta, PREMIUM))
            reloj.now.return_value = corte + timedelta(minutes=1)
            self.assertFalse(self.cuentas.tiene_entitlement(self.cuenta, PREMIUM))

    def test_quien_nunca_pago_no_figura_como_vencido(self):
        e = self.servicio.estado_cuota(self.cuenta, PREMIUM)
        self.assertEqual((e["inscripto"], e["vencida"], e["debe_pagar"]), (False, False, False))

    def test_la_orden_guarda_cuantos_meses_cubre(self):
        orden = self.servicio.crear_orden(self.cuenta, PREMIUM, "transferencia", 3000000, "ARS", 60,
                                          ahora=datetime(2026, 11, 5, tzinfo=AR), meses=2)
        self.assertEqual(orden["meses"], 2)
        with self.assertRaises(pagos.PagoError):
            self.servicio.crear_orden(self.cuenta, "croco-script", "transferencia", 100, "ARS", 30, meses=0)


class _ConPuerta(_Base):
    def setUp(self):
        super().setUp()
        self.c.post("/cuenta/perfil", json={"perfil_id": self.perfil}, headers={"X-Tortu-CSRF": self.csrf})
        ProgresoChildProfile(self.tmp / "progreso_perfiles").guardar(nuevo_snapshot(self.perfil, {"config": {"onboarding": True}}))
        self.qr = self.tmp / "qr"
        self.qr.mkdir()
        self.app.config["PAGOS"] = oferta(enlaces=dict(LINKS), carpeta_qr=str(self.qr))

    def premium(self, activo=True):
        self.cuentas.establecer_entitlement(self.cuenta_id, PREMIUM, activo, "prueba")


class TestPuerta(_ConPuerta):
    def test_sin_acceso_lo_premium_no_abre_por_la_url_y_lo_gratis_si(self):
        r = self.c.get("/leccion/py-if")
        self.assertEqual(r.status_code, 402)
        pagina = r.get_data(as_text=True)
        self.assertIn('id="puerta-de-pago"', pagina)
        self.assertIn("Inscripción: $ 30.000", pagina)
        self.assertIn("lo decide un adulto", pagina)
        self.assertNotEqual(self.c.get("/leccion/py-print").status_code, 402)       # gratis: la puerta no interviene
        self.assertEqual(self.c.get("/leccion/nivel0-programa").status_code, 200)

    def test_tampoco_por_la_api_ni_en_los_proyectos_integradores(self):
        r = self.c.post("/api/lecciones/py-if/pasos/0/comprobar", json={}, headers={"X-Tortu-Token": "t"})
        self.assertEqual((r.status_code, r.json["puerta"]), (402, True))
        self.assertEqual(self.c.get("/proyectos-integradores/ficha-criatura").status_code, 402)

    def test_con_acceso_vigente_se_abre(self):
        self.premium()
        # La puerta deja pasar; que la lección esté desbloqueada por la secuencia ya es asunto del motor (puede redirigir).
        self.assertNotEqual(self.c.get("/leccion/py-if").status_code, 402)
        self.assertNotEqual(self.c.get("/proyectos-integradores/ficha-criatura").status_code, 402)
        self.premium(False)
        self.assertEqual(self.c.get("/leccion/py-if").status_code, 402)           # al cortarse, vuelve a bloquear

    def test_un_administrador_entra_sin_pagar(self):
        self.cuentas.establecer_role(self.cuenta_id, "admin")
        self.assertEqual(self.c.get("/leccion/py-if").status_code, 200)

    def test_sin_pagos_configurados_todo_esta_abierto(self):
        self.app.config["PAGOS"] = pagos.ConfiguracionPagos()
        self.assertNotEqual(self.c.get("/leccion/py-if").status_code, 402)

    def test_un_acceso_a_croco_no_abre_lo_premium_de_tortuscript(self):
        self.dar_acceso()
        self.assertEqual(self.c.get("/leccion/py-if").status_code, 402)

    def test_el_camino_marca_lo_premium_con_un_diamante(self):
        # Con la alfabetización completa se abre el camino de Python, donde sigue «py-if» (premium).
        nivel0 = [f"nivel0-{n}" for n in ("programa", "lenguaje", "codigo", "navegador", "internet", "servidor", "frontend",
                                          "backend", "datos", "base-datos", "api", "seguridad", "integracion", "json", "git", "github")]
        ProgresoChildProfile(self.tmp / "progreso_perfiles").guardar(nuevo_snapshot(self.perfil, {
            "config": {"onboarding": True}, "salteadas": {n: "2026-10-01" for n in nivel0}}))
        pagina = self.c.get("/", follow_redirects=True).get_data(as_text=True)
        self.assertIn("💎", pagina)
        self.assertIn("· Premium", pagina)
        self.premium()
        self.assertNotIn("· Premium", self.c.get("/", follow_redirects=True).get_data(as_text=True))

    def test_la_puerta_tras_vencer_dice_que_esta_pausado(self):
        servicio = pagos.ServicioPagos(self.tmp / "cuentas.sqlite3")
        servicio.ensure_schema()
        antes = datetime.now(timezone.utc) - timedelta(days=200)
        orden = servicio.crear_orden(self.cuenta_id, PREMIUM, "transferencia", 3000000, "ARS", 60, ahora=antes, meses=2)
        servicio.confirmar_orden(orden["id"], ahora=antes)
        pagina = self.c.get("/leccion/py-if").get_data(as_text=True)
        self.assertIn("El acceso Premium está pausado", pagina)
        inicio = self.c.get("/", follow_redirects=True).get_data(as_text=True)
        self.assertIn('id="aviso-cuota"', inicio)
        self.assertIn("pausado", inicio)


class TestPantallaDePago(_ConPuerta):
    def abrir_orden(self):
        return self.c.post("/cuenta/suscripcion/orden", json={"producto": PREMIUM, "medio": "transferencia"},
                           headers={"X-Tortu-CSRF": self.csrf}).json["orden"]

    def test_la_orden_de_inscripcion_muestra_su_boton_y_su_qr(self):
        orden = self.abrir_orden()
        self.assertEqual((orden["importe_centavos"], orden["meses"]), (3000000, 1))
        pagina = self.c.get("/cuenta/suscripcion").get_data(as_text=True)
        self.assertIn("Inscripción", pagina)
        self.assertIn("$ 30.000", pagina)
        self.assertIn('href="https://mpago.la/inscripcion-prueba"', pagina)
        self.assertNotIn("cuota-prueba", pagina)
        self.assertIn("/cuenta/suscripcion/qr/tortuscript-premium/inscripcion.png", pagina)

    def test_la_cuota_usa_el_enlace_de_la_cuota(self):
        orden = self.abrir_orden()
        pagos.ServicioPagos(self.tmp / "cuentas.sqlite3").confirmar_orden(orden["id"])
        # La inscripción cubre solo el mes en vigencia: la cuota de ese mes ya está paga.
        r = self.c.post("/cuenta/suscripcion/orden", json={"producto": PREMIUM, "medio": "transferencia"},
                        headers={"X-Tortu-CSRF": self.csrf})
        self.assertEqual(r.status_code, 400)
        self.assertIn("ya está paga", r.json["mensaje"])
        self.assertIn("Cuota mensual", self.c.get("/cuenta/suscripcion").get_data(as_text=True) + "Cuota mensual")

    def test_el_qr_se_sirve_solo_si_esta_configurado_y_solo_con_sesion(self):
        (self.qr / f"{PREMIUM}-inscripcion.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
        r = self.c.get(f"/cuenta/suscripcion/qr/{PREMIUM}/inscripcion.png")
        self.assertEqual((r.status_code, r.mimetype, r.data[:4]), (200, "image/png", b"\x89PNG"))
        self.assertEqual(self.c.get(f"/cuenta/suscripcion/qr/{PREMIUM}/cuota.png").status_code, 404)   # sin archivo
        self.assertEqual(self.c.get("/cuenta/suscripcion/qr/otro/cuota.png").status_code, 404)
        self.assertEqual(self.c.get(f"/cuenta/suscripcion/qr/{PREMIUM}/..%2F..%2Fetc.png").status_code, 404)
        self.assertEqual(self.app.test_client().get(f"/cuenta/suscripcion/qr/{PREMIUM}/inscripcion.png").status_code, 404)  # sin sesión

    def test_un_enlace_no_configurado_no_muestra_boton(self):
        self.app.config["PAGOS"] = oferta()
        self.abrir_orden()
        self.assertNotIn("mpago.la", self.c.get("/cuenta/suscripcion").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
