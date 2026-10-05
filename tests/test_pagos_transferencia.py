"""Suscripción por transferencia (ADR-047): la orden, el aviso del adulto y la confirmación de quien opera."""
import contextlib
import hashlib
import io
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from herramientas import gestionar_pagos
from tortuscript import pagos
from tortuscript.auth import AuthRepository
from tortuscript.cuentas import CuentaRepository
from web.app import create_app

CLAVE = "una-clave-larga-123"
PREMIUM = "tortuscript-premium"
OFERTA = pagos.ConfiguracionPagos(alias="tortu.alias.prueba", titular="Titular de Prueba", importe_centavos=950000, dias=30)
T0 = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


class TestConfiguracion(unittest.TestCase):
    def test_sin_variables_los_pagos_quedan_apagados(self):
        self.assertFalse(pagos.configuracion_desde_entorno({}).habilitado)
        self.assertFalse(create_app(token="t").config["PAGOS"].habilitado)

    def test_alias_e_importe_la_habilitan(self):
        oferta = pagos.configuracion_desde_entorno(
            {"TORTU_PAGO_ALIAS": " mi.alias ", "TORTU_PAGO_IMPORTE": "9500,50", "TORTU_PAGO_DIAS": "60"})
        self.assertTrue(oferta.habilitado)
        self.assertEqual((oferta.alias, oferta.importe_centavos, oferta.dias, oferta.moneda), ("mi.alias", 950050, 60, "ARS"))
        self.assertEqual(oferta.importe_legible, "$ 9.500,50")
        self.assertEqual(pagos.importe_legible(950000), "$ 9.500")

    def test_una_configuracion_a_medias_o_mal_escrita_se_rechaza(self):
        for entorno in ({"TORTU_PAGO_ALIAS": "mi.alias"}, {"TORTU_PAGO_IMPORTE": "9500"},
                        {"TORTU_PAGO_ALIAS": "a", "TORTU_PAGO_IMPORTE": "gratis"},
                        {"TORTU_PAGO_ALIAS": "a", "TORTU_PAGO_IMPORTE": "0"},
                        {"TORTU_PAGO_ALIAS": "a", "TORTU_PAGO_IMPORTE": "10", "TORTU_PAGO_DIAS": "0"}):
            with self.subTest(entorno=entorno), self.assertRaises(pagos.PagoError):
                pagos.configuracion_desde_entorno(entorno)

    def test_la_tarjeta_figura_pero_no_esta_disponible(self):
        medios = {m["id"]: m["disponible"] for m in pagos.MEDIOS_DE_PAGO}
        self.assertEqual(medios, {"transferencia": True, "tarjeta": False})


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.db = self.tmp / "cuentas.sqlite3"
        self.cuentas = CuentaRepository(self.db)
        self.cuentas.ensure_schema()
        AuthRepository(self.db).ensure_schema()
        self.servicio = pagos.ServicioPagos(self.db)
        self.servicio.ensure_schema()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def orden(self, cuenta, **cambios):
        datos = dict(producto=PREMIUM, medio="transferencia", importe_centavos=950000, moneda="ARS", dias=30)
        datos.update(cambios)
        return self.servicio.crear_orden(cuenta, datos["producto"], datos["medio"], datos["importe_centavos"],
                                         datos["moneda"], datos["dias"], ahora=T0)


class TestOrdenes(Base):
    def setUp(self):
        super().setUp()
        self.cuenta = self.cuentas.crear_account("familia@example.com").id

    def test_crear_una_orden_no_da_acceso(self):
        orden = self.orden(self.cuenta)
        self.assertEqual(orden["estado"], "pendiente")
        self.assertRegex(orden["referencia"], r"^TS-[A-HJ-NP-Z2-9]{6}$")
        self.assertFalse(self.cuentas.tiene_entitlement(self.cuenta, PREMIUM))

    def test_pedirla_dos_veces_devuelve_la_misma(self):
        self.assertEqual(self.orden(self.cuenta)["id"], self.orden(self.cuenta)["id"])
        self.assertEqual(len(self.servicio.listar_ordenes(self.cuenta)), 1)

    def test_medios_productos_e_importes_invalidos(self):
        for cambios in ({"medio": "tarjeta"}, {"medio": "efectivo"}, {"medio": None}, {"producto": "otro"},
                        {"importe_centavos": 0}, {"importe_centavos": "950000"}, {"dias": 0}):
            with self.subTest(cambios=cambios), self.assertRaises(pagos.PagoError):
                self.orden(self.cuenta, **cambios)
        with self.assertRaises(pagos.PagoError):
            self.orden("acc_inexistente")
        self.assertEqual(self.servicio.listar_ordenes(self.cuenta), [])

    def test_avisar_no_da_acceso_y_la_nota_se_recorta(self):
        orden = self.orden(self.cuenta)
        informada = self.servicio.informar_orden(self.cuenta, orden["id"], "  Ana   Pérez  " + "x" * 300, ahora=T0)
        self.assertEqual(informada["estado"], "informada")
        self.assertTrue(informada["nota"].startswith("Ana Pérez x"))
        self.assertEqual(len(informada["nota"]), pagos.MAX_NOTA)
        self.assertFalse(self.cuentas.tiene_entitlement(self.cuenta, PREMIUM))
        with self.assertRaises(pagos.PagoError):                     # ya avisó
            self.servicio.informar_orden(self.cuenta, orden["id"])

    def test_otra_cuenta_no_puede_tocar_la_orden(self):
        orden = self.orden(self.cuenta)
        otra = self.cuentas.crear_account("otra@example.com").id
        for operacion in (self.servicio.informar_orden, self.servicio.cancelar_orden):
            with self.assertRaises(pagos.PagoError):
                operacion(otra, orden["id"])
        self.assertEqual(self.servicio.listar_ordenes(otra), [])
        self.assertEqual(self.servicio.listar_ordenes(self.cuenta)[0]["estado"], "pendiente")

    def test_confirmar_da_acceso_por_el_periodo_y_la_gracia(self):
        orden = self.orden(self.cuenta)
        self.assertEqual(self.servicio.confirmar_orden(orden["id"], ahora=T0)["estado"], "confirmada")
        self.assertTrue(self.cuentas.tiene_entitlement(self.cuenta, PREMIUM))
        (sub,) = self.servicio.listar_suscripciones(self.cuenta)
        self.assertEqual((sub["estado"], sub["proveedor"]), ("active", "transferencia"))
        self.assertEqual(datetime.fromisoformat(sub["periodo_hasta"]), T0 + timedelta(days=30))

    def test_confirmar_dos_veces_no_suma_dias(self):
        orden = self.orden(self.cuenta)
        self.servicio.confirmar_orden(orden["id"], ahora=T0)
        self.servicio.confirmar_orden(orden["id"], ahora=T0 + timedelta(days=3))
        (sub,) = self.servicio.listar_suscripciones(self.cuenta)
        self.assertEqual(datetime.fromisoformat(sub["periodo_hasta"]), T0 + timedelta(days=30))

    def test_renovar_antes_de_vencer_extiende_desde_el_fin_del_periodo(self):
        self.servicio.confirmar_orden(self.orden(self.cuenta)["id"], ahora=T0)
        segunda = self.orden(self.cuenta)
        self.servicio.confirmar_orden(segunda["id"], ahora=T0 + timedelta(days=10))
        (sub,) = self.servicio.listar_suscripciones(self.cuenta)
        self.assertEqual(datetime.fromisoformat(sub["periodo_hasta"]), T0 + timedelta(days=60))

    def test_renovar_despues_de_vencer_arranca_desde_el_pago(self):
        self.servicio.confirmar_orden(self.orden(self.cuenta)["id"], ahora=T0)
        tarde = T0 + timedelta(days=90)
        self.servicio.confirmar_orden(self.orden(self.cuenta)["id"], ahora=tarde)
        (sub,) = self.servicio.listar_suscripciones(self.cuenta)
        self.assertEqual(datetime.fromisoformat(sub["periodo_hasta"]), tarde + timedelta(days=30))

    def test_un_periodo_vencido_se_informa_como_vencido_y_no_da_acceso(self):
        self.servicio.confirmar_orden(self.orden(self.cuenta)["id"], ahora=datetime(2020, 1, 1, tzinfo=timezone.utc))
        (sub,) = self.servicio.listar_suscripciones(self.cuenta)
        self.assertTrue(sub["vencida"])
        self.assertFalse(self.cuentas.tiene_entitlement(self.cuenta, PREMIUM))

    def test_rechazar_y_cancelar_cierran_la_orden_sin_dar_acceso(self):
        rechazada = self.servicio.rechazar_orden(self.orden(self.cuenta)["id"], "no llegó la transferencia", ahora=T0)
        self.assertEqual((rechazada["estado"], rechazada["nota_operador"]), ("rechazada", "no llegó la transferencia"))
        cancelada = self.servicio.cancelar_orden(self.cuenta, self.orden(self.cuenta)["id"], ahora=T0)
        self.assertEqual(cancelada["estado"], "cancelada")
        for cerrada in (rechazada, cancelada):
            with self.assertRaises(pagos.PagoError):
                self.servicio.confirmar_orden(cerrada["id"], ahora=T0)
        self.assertFalse(self.cuentas.tiene_entitlement(self.cuenta, PREMIUM))
        self.assertEqual(self.servicio.listar_ordenes_abiertas(), [])

    def test_un_acceso_concedido_a_mano_no_lo_recorta_un_pago(self):
        self.cuentas.establecer_entitlement(self.cuenta, PREMIUM, True, "soporte")
        self.servicio.confirmar_orden(self.orden(self.cuenta)["id"], ahora=datetime(2020, 1, 1, tzinfo=timezone.utc))
        self.assertTrue(self.cuentas.tiene_entitlement(self.cuenta, PREMIUM))

    def test_las_abiertas_muestran_primero_las_informadas(self):
        otra = self.cuentas.crear_account("otra@example.com").id
        self.orden(self.cuenta)
        informada = self.orden(otra)
        self.servicio.informar_orden(otra, informada["id"], ahora=T0)
        self.assertEqual([o["estado"] for o in self.servicio.listar_ordenes_abiertas()], ["informada", "pendiente"])
        self.assertEqual(self.servicio.buscar_orden(informada["referencia"].lower())["id"], informada["id"])
        self.assertIsNone(self.servicio.buscar_orden("TS-NOEXISTE"))


class TestHerramienta(Base):
    def correr(self, *args):
        salida, errores = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(errores):
            codigo = gestionar_pagos.main(["--db", str(self.db), *args])
        return codigo, salida.getvalue() + errores.getvalue()

    def test_listar_confirmar_y_rechazar(self):
        cuenta = self.cuentas.crear_account("familia@example.com").id
        self.assertEqual(self.correr()[0], 0)                       # nada abierto
        orden = self.orden(cuenta)
        codigo, texto = self.correr()
        self.assertEqual(codigo, 0)                                 # pendiente: todavía nadie dijo que pagó
        self.assertIn(orden["referencia"], texto)
        self.assertIn("familia@example.com", texto)
        self.servicio.informar_orden(cuenta, orden["id"], "Ana Pérez")
        self.assertEqual(self.correr()[0], 2)                       # hay una informada esperando
        codigo, texto = self.correr("confirmar", orden["referencia"])
        self.assertEqual(codigo, 0)
        self.assertIn("confirmada", texto)
        self.assertTrue(self.cuentas.tiene_entitlement(cuenta, PREMIUM))
        self.assertEqual(self.correr("rechazar", orden["referencia"])[0], 1)   # ya confirmada
        self.assertEqual(self.correr("confirmar", "TS-NOEXISTE")[0], 1)
        otra = self.orden(cuenta)
        self.assertEqual(self.correr("rechazar", otra["id"], "--nota", "no llegó")[0], 0)
        self.assertEqual(self.servicio.listar_ordenes(cuenta)[0]["nota_operador"], "no llegó")

    def test_sin_base_de_cuentas(self):
        self.assertEqual(gestionar_pagos.main(["--db", str(self.tmp / "no-existe.sqlite3")]), 1)


class TestPlanes(unittest.TestCase):
    """Un plan por producto: TortuScript Premium y el nivel avanzado (Croco-Script)."""

    def test_planes_segun_los_importes_configurados(self):
        dos = pagos.configuracion_desde_entorno({"TORTU_PAGO_ALIAS": "a.b", "TORTU_PAGO_IMPORTE": "9500", "TORTU_PAGO_IMPORTE_CROCO": "15000,50"})
        self.assertEqual([(p["producto"], p["importe_centavos"]) for p in dos.planes()],
                         [(PREMIUM, 950000), ("croco-script", 1500050)])
        self.assertEqual(dos.plan("croco-script")["importe_legible"], "$ 15.000,50")
        solo_croco = pagos.configuracion_desde_entorno({"TORTU_PAGO_ALIAS": "a.b", "TORTU_PAGO_IMPORTE_CROCO": "15000"})
        self.assertTrue(solo_croco.habilitado)
        self.assertEqual([p["producto"] for p in solo_croco.planes()], ["croco-script"])
        self.assertIsNone(solo_croco.plan(PREMIUM))
        self.assertIsNone(solo_croco.plan("inventado"))

    def test_importes_invalidos_del_plan_avanzado(self):
        for entorno in ({"TORTU_PAGO_IMPORTE_CROCO": "15000"},
                        {"TORTU_PAGO_ALIAS": "a", "TORTU_PAGO_IMPORTE_CROCO": "mucho"},
                        {"TORTU_PAGO_ALIAS": "a", "TORTU_PAGO_IMPORTE_CROCO": "-5"},
                        {"TORTU_PAGO_ALIAS": "a", "TORTU_PAGO_IMPORTE": "0", "TORTU_PAGO_IMPORTE_CROCO": "0"}):
            with self.subTest(entorno=entorno), self.assertRaises(pagos.PagoError):
                pagos.configuracion_desde_entorno(entorno)


class TestHTTP(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.db = self.tmp / "cuentas.sqlite3"
        self.app = create_app(token="t")
        self.app.config.update(TESTING=True, ACCOUNT_DB=self.db, PROGRESS_DIR=self.tmp / "progreso_perfiles",
                               ACCOUNT_EMAIL_SENDER=lambda **payload: None, PAGOS=OFERTA)
        self.c, self.cuenta = self.adulto("paga@example.com")
        self.servicio = pagos.ServicioPagos(self.db)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def adulto(self, email):
        cliente = self.app.test_client()
        cliente.post("/cuenta/registrar", data={"email": email, "password": CLAVE, "responsable": "si"})
        cuenta = "acc_" + hashlib.sha256(email.encode()).hexdigest()[:24]
        AuthRepository(self.db).marcar_verificada(cuenta)
        cliente.post("/cuenta/login", data={"email": email, "password": CLAVE})
        return cliente, cuenta

    def csrf(self, cliente=None):
        return (cliente or self.c).get_cookie("tortu_csrf").value

    def test_sin_sesion_la_pagina_pide_ingresar(self):
        r = self.app.test_client().get("/cuenta/suscripcion")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/cuenta/ingresar", r.headers["Location"])
        self.assertEqual(self.app.test_client().post("/cuenta/suscripcion/orden", json={"medio": "transferencia"}).status_code, 401)

    def test_la_pagina_muestra_los_medios_y_el_alias_solo_con_una_orden(self):
        pagina = self.c.get("/cuenta/suscripcion").get_data(as_text=True)
        self.assertIn("Transferencia", pagina)
        self.assertIn("próximamente", pagina)                        # la tarjeta figura, deshabilitada
        self.assertIn("$ 9.500", pagina)
        self.assertNotIn(OFERTA.alias, pagina)                       # el alias aparece recién al armar la orden
        r = self.c.post("/cuenta/suscripcion/orden", data={"medio": "transferencia", "csrf": self.csrf()})
        self.assertEqual(r.status_code, 302)
        pagina = self.c.get("/cuenta/suscripcion").get_data(as_text=True)
        (orden,) = self.servicio.listar_ordenes(self.cuenta)
        for texto in (OFERTA.alias, OFERTA.titular, orden["referencia"], "Ya hice la transferencia"):
            self.assertIn(texto, pagina)

    def test_el_importe_lo_fija_el_servidor(self):
        r = self.c.post("/cuenta/suscripcion/orden", headers={"X-Tortu-CSRF": self.csrf()},
                        json={"medio": "transferencia", "importe_centavos": 1, "dias": 9999})
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.json["orden"]["importe_centavos"], r.json["orden"]["dias"], r.json["orden"]["producto"]),
                         (950000, 30, PREMIUM))

    def test_no_se_puede_pedir_un_plan_que_no_se_ofrece(self):
        cabeceras = {"X-Tortu-CSRF": self.csrf()}
        for producto in ("croco-script", "inventado", "", ["croco-script"], 7):
            with self.subTest(producto=producto):
                r = self.c.post("/cuenta/suscripcion/orden", headers=cabeceras, json={"medio": "transferencia", "producto": producto})
                self.assertEqual(r.status_code, 400)
        self.assertEqual(self.servicio.listar_ordenes(self.cuenta), [])

    def test_circuito_completo_hasta_el_acceso(self):
        cabeceras = {"X-Tortu-CSRF": self.csrf()}
        perfil = self.c.post("/cuenta/perfiles", json={"nombre": "Ana"}, headers=cabeceras).json["perfil"]["id"]
        self.c.post("/cuenta/perfil", json={"perfil_id": perfil}, headers=cabeceras)
        acceso = lambda: self.c.get(f"/cuenta/acceso?producto={PREMIUM}").json["permitido"]   # noqa: E731
        orden = self.c.post("/cuenta/suscripcion/orden", json={"medio": "transferencia"}, headers=cabeceras).json["orden"]
        r = self.c.post(f"/cuenta/suscripcion/orden/{orden['id']}/informar", data={"nota": "Ana Pérez", "csrf": self.csrf()})
        self.assertEqual(r.status_code, 302)
        self.assertIn("Estamos confirmando el pago", self.c.get("/cuenta/suscripcion").get_data(as_text=True))
        self.assertFalse(acceso())                                   # avisar no alcanza
        self.servicio.confirmar_orden(orden["id"])
        self.assertTrue(acceso())
        pagina = self.c.get("/cuenta/suscripcion").get_data(as_text=True)
        self.assertIn("tiene acceso a TortuScript Premium", pagina)
        self.assertIn("Renovar", pagina)
        exportado = self.c.get("/cuenta/datos/exportar").json
        self.assertEqual(exportado["ordenes_de_pago"][0]["estado"], "confirmada")
        self.assertNotIn(OFERTA.alias, str(exportado))

    def test_medio_no_disponible_csrf_y_orden_ajena(self):
        cabeceras = {"X-Tortu-CSRF": self.csrf()}
        self.assertEqual(self.c.post("/cuenta/suscripcion/orden", json={"medio": "tarjeta"}, headers=cabeceras).status_code, 400)
        self.assertEqual(self.c.post("/cuenta/suscripcion/orden", json=["transferencia"], headers=cabeceras).status_code, 400)
        self.assertEqual(self.c.post("/cuenta/suscripcion/orden", json={"medio": "transferencia"}).status_code, 403)
        r = self.c.post("/cuenta/suscripcion/orden", data={"medio": "tarjeta", "csrf": self.csrf()})
        self.assertEqual(r.status_code, 400)
        self.assertIn("todavía no está disponible", r.get_data(as_text=True))
        orden = self.c.post("/cuenta/suscripcion/orden", json={"medio": "transferencia"}, headers=cabeceras).json["orden"]
        intruso, _ = self.adulto("intruso@example.com")
        ajeno = {"X-Tortu-CSRF": self.csrf(intruso)}
        for accion in ("informar", "cancelar"):
            self.assertEqual(intruso.post(f"/cuenta/suscripcion/orden/{orden['id']}/{accion}", json={}, headers=ajeno).status_code, 400)
        self.assertEqual(self.servicio.listar_ordenes(self.cuenta)[0]["estado"], "pendiente")
        r = self.c.post(f"/cuenta/suscripcion/orden/{orden['id']}/cancelar", data={"csrf": self.csrf()})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.servicio.listar_ordenes(self.cuenta)[0]["estado"], "cancelada")

    def test_la_cuenta_administradora_ve_que_ya_tiene_acceso(self):
        self.assertIn("todavía no tiene acceso", self.c.get("/cuenta/suscripcion").get_data(as_text=True))
        CuentaRepository(self.db).establecer_role(self.cuenta, "admin")
        pagina = self.c.get("/cuenta/suscripcion").get_data(as_text=True)
        self.assertIn("cuenta administradora", pagina)
        self.assertNotIn("todavía no tiene acceso", pagina)
        self.assertIn("Continuar", pagina)                           # igual puede probar el circuito

    def test_dos_planes_se_contratan_por_separado(self):
        self.app.config["PAGOS"] = pagos.ConfiguracionPagos(alias="tortu.alias.prueba", importe_centavos=950000,
                                                             importe_croco_centavos=1500000, dias=30)
        pagina = self.c.get("/cuenta/suscripcion").get_data(as_text=True)
        for texto in ("TortuScript Premium", "Croco-Script", "$ 9.500", "$ 15.000", 'id="plan-croco-script"'):
            self.assertIn(texto, pagina)
        cabeceras = {"X-Tortu-CSRF": self.csrf()}
        croco = self.c.post("/cuenta/suscripcion/orden", json={"medio": "transferencia", "producto": "croco-script"}, headers=cabeceras).json["orden"]
        premium = self.c.post("/cuenta/suscripcion/orden", json={"medio": "transferencia", "producto": PREMIUM}, headers=cabeceras).json["orden"]
        self.assertEqual((croco["producto"], croco["importe_centavos"]), ("croco-script", 1500000))
        self.assertEqual((premium["producto"], premium["importe_centavos"]), (PREMIUM, 950000))
        self.assertNotEqual(croco["referencia"], premium["referencia"])
        self.servicio.confirmar_orden(croco["id"])
        cuentas = CuentaRepository(self.db)
        self.assertTrue(cuentas.tiene_entitlement(self.cuenta, "croco-script"))
        self.assertFalse(cuentas.tiene_entitlement(self.cuenta, PREMIUM))       # pagar uno no da el otro
        pagina = self.c.get("/cuenta/suscripcion").get_data(as_text=True)
        self.assertIn("tiene acceso a Croco-Script", pagina)
        self.assertIn("todavía no tiene acceso a TortuScript Premium", pagina)
        self.assertIn(premium["referencia"], pagina)                              # la otra orden sigue abierta

    def test_sin_oferta_configurada_no_se_puede_contratar(self):
        self.app.config["PAGOS"] = pagos.ConfiguracionPagos()
        pagina = self.c.get("/cuenta/suscripcion").get_data(as_text=True)
        self.assertIn("todavía no está disponible en esta instalación", pagina)
        r = self.c.post("/cuenta/suscripcion/orden", json={"medio": "transferencia"}, headers={"X-Tortu-CSRF": self.csrf()})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.servicio.listar_ordenes(self.cuenta), [])


if __name__ == "__main__":
    unittest.main()
