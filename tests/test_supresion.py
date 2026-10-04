"""ADR-046 — supresión definitiva: perfiles archivados y cuenta con plazo de gracia."""
import hashlib
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tortuscript import pagos
from tortuscript.auth import AuthRepository
from tortuscript.cuentas import DIAS_DE_GRACIA_ELIMINACION, CuentaError, CuentaRepository
from tortuscript.en_curso import EnCurso, vacio
from tortuscript.progreso_childprofile import ProgresoChildProfile
from tortuscript.progreso_contrato import nuevo_snapshot
from web.app import create_app
from web.cuenta_routes import purgar_cuentas_vencidas

CLAVE = "una-clave-larga-123"
AHORA = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.db = self.tmp / "cuentas.sqlite3"
        self.progreso = self.tmp / "progreso_perfiles"
        self.app = create_app(token="t")
        self.app.config.update(TESTING=True, ACCOUNT_DB=self.db, PROGRESS_DIR=self.progreso,
                               ACCOUNT_EMAIL_SENDER=lambda **payload: None)
        self.c = self.app.test_client()
        self.cuentas = CuentaRepository(self.db)
        self.cuentas.ensure_schema()
        self.store = ProgresoChildProfile(self.progreso)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def adulto(self, email, cliente=None):
        cliente = cliente or self.c
        cliente.post("/cuenta/registrar", data={"email": email, "password": CLAVE, "responsable": "si"})
        cuenta = "acc_" + hashlib.sha256(email.encode()).hexdigest()[:24]
        AuthRepository(self.db).marcar_verificada(cuenta)
        self.assertEqual(cliente.post("/cuenta/login", data={"email": email, "password": CLAVE}).status_code, 302)
        return cuenta

    def csrf(self, cliente=None):
        return (cliente or self.c).get_cookie("tortu_csrf").value

    def perfil_con_archivos(self, cuenta, nombre):
        perfil = self.cuentas.crear_child_profile(cuenta, nombre).id
        self.store.guardar(nuevo_snapshot(perfil, {"xp": 10}))
        self.store.guardar(nuevo_snapshot(perfil, {"xp": 20}))          # deja además el .bak
        (self.progreso / f"progreso_{perfil}.json.corrupto-20261001-101010").write_text("{", encoding="utf-8")
        EnCurso(self.progreso).guardar(perfil, vacio())
        return perfil

    def archivos_de(self, perfil):
        return sorted(p.name for p in self.progreso.iterdir() if perfil in p.name)

    def tablas_con(self, cuenta):
        """Tablas de la base que todavía tienen alguna fila de la cuenta."""
        con_datos = []
        with closing(sqlite3.connect(self.db)) as con:
            for (tabla,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
                columnas = [c[1] for c in con.execute(f"PRAGMA table_info({tabla})")]
                columna = "account_id" if "account_id" in columnas else ("id" if tabla == "accounts" else None)
                if columna and con.execute(f"SELECT 1 FROM {tabla} WHERE {columna}=?", (cuenta,)).fetchone():
                    con_datos.append(tabla)
        return con_datos


class TestEliminarPerfil(Base):
    def setUp(self):
        super().setUp()
        self.cuenta = self.adulto("familia@example.com")
        self.perfil = self.perfil_con_archivos(self.cuenta, "Ana María")
        self.otro = self.perfil_con_archivos(self.cuenta, "Beto")

    def eliminar(self, perfil, nombre, cliente=None, **extra):
        cliente = cliente or self.c
        return cliente.post(f"/cuenta/perfiles/{perfil}/eliminar", data={"nombre": nombre, "csrf": self.csrf(cliente)}, **extra)

    def test_un_perfil_en_uso_no_se_puede_eliminar(self):
        r = self.eliminar(self.perfil, "Ana María")
        self.assertEqual(r.status_code, 400)
        self.assertIn("primero hay que archivarlo", r.get_data(as_text=True))
        self.assertEqual(len(self.archivos_de(self.perfil)), 4)

    def test_hay_que_escribir_el_nombre(self):
        self.cuentas.archivar_child_profile(self.cuenta, self.perfil)
        for nombre in ("", "Ana", "Beto", "x" * 200):
            with self.subTest(nombre=nombre):
                self.assertEqual(self.eliminar(self.perfil, nombre).status_code, 400)
        self.assertEqual(len(self.cuentas.listar_child_profiles(self.cuenta)), 2)
        self.assertEqual(len(self.archivos_de(self.perfil)), 4)

    def test_eliminar_borra_la_fila_y_todos_sus_archivos_y_nada_mas(self):
        self.cuentas.archivar_child_profile(self.cuenta, self.perfil)
        r = self.eliminar(self.perfil, "  ana   maría ")                # se compara como los nombres de perfil
        self.assertEqual(r.status_code, 302)
        self.assertIn("ok=eliminado", r.headers["Location"])
        self.assertEqual([p.id for p in self.cuentas.listar_child_profiles(self.cuenta)], [self.otro])
        self.assertEqual(self.archivos_de(self.perfil), [])
        self.assertEqual(len(self.archivos_de(self.otro)), 4)           # el hermano queda intacto
        self.assertEqual(self.store.cargar(self.otro).data["xp"], 20)
        self.assertEqual(self.eliminar(self.perfil, "Ana María").status_code, 400)   # ya no existe

    def test_la_pagina_ofrece_eliminar_solo_los_archivados(self):
        pagina = self.c.get("/cuenta/configuracion").get_data(as_text=True)
        self.assertNotIn("/eliminar\"", pagina.split("Eliminar la cuenta")[0])
        self.cuentas.archivar_child_profile(self.cuenta, self.perfil)
        pagina = self.c.get("/cuenta/configuracion").get_data(as_text=True)
        self.assertIn(f"/cuenta/perfiles/{self.perfil}/eliminar", pagina)
        self.assertNotIn(f"/cuenta/perfiles/{self.otro}/eliminar", pagina)

    def test_otra_cuenta_no_puede_eliminar_el_perfil_ni_sin_csrf(self):
        self.cuentas.archivar_child_profile(self.cuenta, self.perfil)
        intruso = self.app.test_client()
        self.adulto("intruso@example.com", intruso)
        self.assertEqual(self.eliminar(self.perfil, "Ana María", intruso).status_code, 400)
        self.assertEqual(self.c.post(f"/cuenta/perfiles/{self.perfil}/eliminar", data={"nombre": "Ana María"}).status_code, 403)
        self.assertEqual(self.app.test_client().post(f"/cuenta/perfiles/{self.perfil}/eliminar", json={"nombre": "Ana María"}).status_code, 401)
        self.assertEqual(len(self.archivos_de(self.perfil)), 4)

    def test_un_identificador_inventado_no_rompe_nada(self):
        for perfil in ("child_000000000000000000000000", "..%2F..%2Fcuentas", "x"):
            with self.subTest(perfil=perfil):
                r = self.c.post(f"/cuenta/perfiles/{perfil}/eliminar", json={"nombre": "x"},
                                headers={"X-Tortu-CSRF": self.csrf()})
                self.assertIn(r.status_code, (400, 404))
        self.assertEqual(len(self.cuentas.listar_child_profiles(self.cuenta)), 2)


class TestEliminarCuenta(Base):
    def setUp(self):
        super().setUp()
        self.cuenta = self.adulto("familia@example.com")
        self.perfil = self.perfil_con_archivos(self.cuenta, "Ana")

    def pedir(self, password=CLAVE, cliente=None):
        cliente = cliente or self.c
        return cliente.post("/cuenta/eliminar", data={"password": password, "csrf": self.csrf(cliente)})

    def test_pide_la_contrasena_y_csrf(self):
        for password in ("otra-clave-larga-999", ""):
            r = self.pedir(password)
            self.assertEqual(r.status_code, 400)
            self.assertIn("La contraseña no es correcta", r.get_data(as_text=True))
        self.assertEqual(self.c.post("/cuenta/eliminar", data={"password": CLAVE}).status_code, 403)
        self.assertEqual(self.app.test_client().post("/cuenta/eliminar", json={"password": CLAVE}).status_code, 401)
        self.assertEqual(self.c.post("/cuenta/eliminar", json={"password": ["x"]}, headers={"X-Tortu-CSRF": self.csrf()}).status_code, 400)
        self.assertIsNone(self.cuentas.eliminacion_pendiente(self.cuenta))

    def test_el_pedido_cierra_las_sesiones_y_no_borra_nada_todavia(self):
        otra_sesion = self.app.test_client()
        otra_sesion.post("/cuenta/login", data={"email": "familia@example.com", "password": CLAVE})
        r = self.pedir()
        self.assertEqual(r.status_code, 200)
        self.assertIn("La cuenta se va a eliminar el", r.get_data(as_text=True))
        for cliente in (self.c, otra_sesion):
            self.assertEqual(cliente.get("/cuenta/me").status_code, 401)
        self.assertIsNotNone(self.cuentas.obtener_account(self.cuenta))
        self.assertEqual(len(self.archivos_de(self.perfil)), 4)
        plazo = self.cuentas.eliminacion_pendiente(self.cuenta) - datetime.now(timezone.utc)
        self.assertAlmostEqual(plazo.total_seconds(), DIAS_DE_GRACIA_ELIMINACION * 86400, delta=60)

    def test_ingresar_dentro_del_plazo_cancela_el_pedido(self):
        self.pedir()
        r = self.c.post("/cuenta/login", data={"email": "familia@example.com", "password": CLAVE})
        self.assertEqual(r.status_code, 302)
        self.assertIn("ok=reactivada", r.headers["Location"])
        self.assertIn("Cancelamos el pedido de eliminación", self.c.get(r.headers["Location"]).get_data(as_text=True))
        self.assertIsNone(self.cuentas.eliminacion_pendiente(self.cuenta))
        with self.app.app_context():
            self.assertEqual(purgar_cuentas_vencidas(datetime.now(timezone.utc) + timedelta(days=365)), 0)
        self.assertEqual(self.store.cargar(self.perfil).data["xp"], 20)

    def test_una_contrasena_equivocada_no_reactiva(self):
        self.pedir()
        self.assertEqual(self.c.post("/cuenta/login", data={"email": "familia@example.com", "password": "otra-clave-larga-999"}).status_code, 401)
        self.assertIsNotNone(self.cuentas.eliminacion_pendiente(self.cuenta))

    def test_pedirlo_de_nuevo_no_reinicia_el_plazo(self):
        primera = self.cuentas.solicitar_eliminacion(self.cuenta, AHORA)
        self.assertEqual(self.cuentas.solicitar_eliminacion(self.cuenta, AHORA + timedelta(days=5)), primera)

    def test_vencido_el_plazo_se_borra_todo_y_queda_una_constancia_sin_datos(self):
        otra = self.cuentas.crear_account("vecinos@example.com").id
        perfil_ajeno = self.perfil_con_archivos(otra, "Ana")
        self.cuentas.registrar_consentimiento(self.cuenta, "tutor_ia", "2026-10-04", True)
        servicio = pagos.ServicioPagos(self.db)
        servicio.ensure_schema()
        servicio.confirmar_orden(servicio.crear_orden(self.cuenta, "tortuscript-premium", "transferencia", 100, "ARS", 30)["id"])
        servicio.crear_orden(self.cuenta, "tortuscript-premium", "transferencia", 100, "ARS", 30)
        self.assertGreaterEqual(len(self.tablas_con(self.cuenta)), 6)

        self.pedir()
        pedido = self.cuentas.eliminacion_pendiente(self.cuenta)
        with self.app.app_context():
            self.assertEqual(purgar_cuentas_vencidas(pedido - timedelta(minutes=1)), 0)     # todavía en plazo
            self.assertIsNotNone(self.cuentas.obtener_account(self.cuenta))
            self.assertEqual(purgar_cuentas_vencidas(pedido + timedelta(minutes=1)), 1)
            self.assertEqual(purgar_cuentas_vencidas(pedido + timedelta(minutes=1)), 0)     # no hay nada más que borrar
        self.assertIsNone(self.cuentas.obtener_account(self.cuenta))
        self.assertEqual(self.tablas_con(self.cuenta), [])
        self.assertEqual(self.archivos_de(self.perfil), [])
        # La otra familia no se entera.
        self.assertIsNotNone(self.cuentas.obtener_account(otra))
        self.assertEqual(len(self.archivos_de(perfil_ajeno)), 4)
        with closing(sqlite3.connect(self.db)) as con:
            (constancia,) = con.execute("SELECT deleted_at, account_hash FROM account_deletions").fetchall()
            volcado = "\n".join(con.iterdump())
        self.assertRegex(constancia[1], r"^[0-9a-f]{64}$")
        self.assertNotIn("familia@example.com", volcado)
        self.assertNotIn(self.cuenta, volcado)
        self.assertNotIn(self.perfil, volcado)
        # El evento del pago sigue registrado (no se puede volver a aplicar), ya sin dueño.
        self.assertIn("payment_succeeded", volcado)

    def test_ingresar_despues_del_plazo_borra_la_cuenta_y_no_deja_entrar(self):
        self.cuentas.solicitar_eliminacion(self.cuenta, datetime.now(timezone.utc) - timedelta(days=DIAS_DE_GRACIA_ELIMINACION + 1))
        r = self.c.post("/cuenta/login", data={"email": "familia@example.com", "password": CLAVE})
        self.assertEqual(r.status_code, 401)
        self.assertIsNone(self.cuentas.obtener_account(self.cuenta))
        self.assertEqual(self.archivos_de(self.perfil), [])

    def test_no_se_puede_purgar_una_cuenta_sin_pedido_ni_antes_de_tiempo(self):
        with self.assertRaises(CuentaError):
            self.cuentas.purgar_account(self.cuenta)
        self.cuentas.solicitar_eliminacion(self.cuenta, AHORA)
        with self.assertRaises(CuentaError):
            self.cuentas.purgar_account(self.cuenta, AHORA + timedelta(days=DIAS_DE_GRACIA_ELIMINACION - 1))
        self.assertIsNotNone(self.cuentas.obtener_account(self.cuenta))

    def test_una_suscripcion_que_se_renueva_sola_bloquea_el_pedido(self):
        servicio = pagos.ServicioPagos(self.db)
        servicio.ensure_schema()
        servicio.aplicar(pagos.EventoPago("prueba", "evt_1", "payment_succeeded", self.cuenta, "tortuscript-premium",
                                          "sub_1", AHORA, AHORA + timedelta(days=30)))
        r = self.pedir()
        self.assertEqual(r.status_code, 400)
        self.assertIn("se renueva sola", r.get_data(as_text=True))
        servicio.aplicar(pagos.EventoPago("prueba", "evt_2", "subscription_canceled", self.cuenta, "tortuscript-premium",
                                          "sub_1", AHORA + timedelta(seconds=1)))
        self.assertEqual(self.pedir().status_code, 200)

    def test_una_suscripcion_por_transferencia_no_bloquea(self):
        servicio = pagos.ServicioPagos(self.db)
        servicio.ensure_schema()
        servicio.confirmar_orden(servicio.crear_orden(self.cuenta, "tortuscript-premium", "transferencia", 100, "ARS", 30)["id"])
        self.assertEqual(self.pedir().status_code, 200)

    def test_la_purga_al_arrancar_no_impide_iniciar_si_falla(self):
        import iniciar_web
        self.app.config["ACCOUNT_DB"] = self.tmp                       # una carpeta, no una base: la purga falla
        with self.assertLogs(level="ERROR"):
            self.assertEqual(iniciar_web.purgar_cuentas_vencidas(self.app), 0)


if __name__ == "__main__":
    unittest.main()
