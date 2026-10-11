"""Lo que TortuScript le responde y le pide a Croco-Script (ADR-037): Entitlement.v1, ProgressQuery.v1, Supresion.v1."""
import base64
import hashlib
import hmac
import io
import json
import shutil
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError

from tortuscript import catalogo_producto, federacion
from tortuscript.auth import AuthRepository
from tortuscript.cuentas import CuentaRepository
from tortuscript.federacion import FederacionError
from tortuscript.federacion_operaciones import OperacionesCroco
from tortuscript.progreso_childprofile import ProgresoChildProfile
from tortuscript.progreso_contrato import nuevo_snapshot
from web.app import create_app

RAIZ = Path(__file__).resolve().parent.parent
VECTORES = json.loads((RAIZ / "docs" / "contratos" / "supresion-v1.vectores.json").read_text(encoding="utf-8"))
CLAVE = "x" * 40
CONFIG = {"url": "https://croco.example/entrar", "clave": CLAVE, "kid": "k1"}


def firma_como_croco(clave, momento, producto, identificador):
    """La fórmula tal como la escribe Croco-Script en `acceso.py`/`progreso.py` (copia independiente del código de arriba)."""
    mensaje = f"{momento}.{producto}.{identificador}".encode("utf-8")
    return base64.urlsafe_b64encode(hmac.new(clave.encode("utf-8"), mensaje, hashlib.sha256).digest()).rstrip(b"=").decode("ascii")


def encabezado(identificador, clave=CLAVE, kid="k1", momento=None, producto="croco-script"):
    momento = int(time.time()) if momento is None else momento
    return {"Authorization": f"Croco-HMAC kid={kid}, ts={momento}, firma={firma_como_croco(clave, momento, producto, identificador)}"}


class TestFirmaDeConsulta(unittest.TestCase):
    def test_coincide_con_la_formula_de_croco_script(self):
        self.assertEqual(federacion.firma_de_consulta(CLAVE, 1793534400, "croco-script", "acc_1"),
                         firma_como_croco(CLAVE, 1793534400, "croco-script", "acc_1"))

    def test_valida_y_rechaza(self):
        ahora = datetime.fromtimestamp(1793534400, tz=timezone.utc)
        claves = {"k1": CLAVE}
        ok = encabezado("acc_1", momento=1793534400)["Authorization"]
        federacion.validar_consulta(ok, claves, "croco-script", "acc_1", ahora=ahora)
        malos = {
            "sin encabezado": (None, "acc_1", ahora),
            "otro esquema": ("Bearer abc", "acc_1", ahora),
            "otra identidad": (ok, "acc_2", ahora),
            "otra clave": (encabezado("acc_1", clave="y" * 40, momento=1793534400)["Authorization"], "acc_1", ahora),
            "kid desconocido": (encabezado("acc_1", kid="otro", momento=1793534400)["Authorization"], "acc_1", ahora),
            "vencida": (ok, "acc_1", ahora + timedelta(seconds=61)),
            "del futuro": (ok, "acc_1", ahora - timedelta(seconds=61)),
            "campo repetido": (ok + ", kid=k1", "acc_1", ahora),
            "ts no numérico": ("Croco-HMAC kid=k1, ts=abc, firma=x", "acc_1", ahora),
            "falta la firma": ("Croco-HMAC kid=k1, ts=1793534400", "acc_1", ahora),
            "otro producto": (encabezado("acc_1", momento=1793534400, producto="otro")["Authorization"], "acc_1", ahora),
        }
        for motivo, (cabecera, identificador, momento) in malos.items():
            with self.subTest(motivo=motivo), self.assertRaises(FederacionError):
                federacion.validar_consulta(cabecera, claves, "croco-script", identificador, ahora=momento)


class TestEmisorSupresion(unittest.TestCase):
    """El emisor reproduce, byte a byte, los vectores que Croco-Script acepta."""

    def test_reproduce_los_vectores_validos(self):
        for nombre, vector in VECTORES["validos"].items():
            d = vector["datos"]
            with self.subTest(vector=nombre):
                token = federacion.emitir_operacion(
                    VECTORES["clave"], VECTORES["kid"], VECTORES["destino"], d["act"], d["acc"], d.get("sub"),
                    ahora=datetime.fromtimestamp(d["iat"], tz=timezone.utc), jti=d["jti"])
                self.assertEqual(token, vector["token"])

    def test_no_se_emite_con_datos_incompletos_o_ajenos(self):
        casos = [dict(accion="borrar_todo", cuenta_id="acc_1", perfil_id="p"),
                 dict(accion="suprimir_perfil", cuenta_id="acc_1", perfil_id=None),
                 dict(accion="exportar_perfil", cuenta_id="acc_1", perfil_id=""),
                 dict(accion="suprimir_cuenta", cuenta_id="", perfil_id=None),
                 dict(accion="suprimir_cuenta", cuenta_id="acc_1", destino="otro")]
        for caso in casos:
            with self.subTest(caso=caso), self.assertRaises(FederacionError):
                federacion.emitir_operacion(CLAVE, "k1", caso.pop("destino", "croco-script"), **caso)

    def test_el_token_de_borrado_no_abre_sesion_y_el_de_entrada_no_borra(self):
        borrado = federacion.emitir_operacion(CLAVE, "k1", "croco-script", "suprimir_cuenta", "acc_1")
        with self.assertRaises(FederacionError):
            federacion.validar_autorizacion(borrado, {"k1": CLAVE}, "croco-script")
        cuerpo = json.loads(base64.urlsafe_b64decode(borrado.split(".")[1] + "=="))
        self.assertNotIn("ent", cuerpo)
        self.assertNotIn("sub", cuerpo)


class _Respuesta:
    def __init__(self, estado, cuerpo):
        self.status, self._cuerpo = estado, json.dumps(cuerpo).encode("utf-8")

    def read(self, n=-1):
        return self._cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http_error(codigo):
    return HTTPError("https://croco.example", codigo, "x", {}, io.BytesIO(b"{}"))


class TestOperaciones(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.pedidos = []
        self.salidas = []                                 # lo que responde el «servidor»: estado, excepción o cuerpo

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def abrir(self, pedido, timeout=None):
        self.pedidos.append(pedido)
        salida = self.salidas.pop(0) if self.salidas else _Respuesta(200, {"contrato": "Supresion.v1"})
        if isinstance(salida, Exception):
            raise salida
        return salida

    def ops(self, config=CONFIG):
        return OperacionesCroco(config, self.tmp, abrir=self.abrir)

    def test_sin_conexion_no_hace_nada(self):
        ops = self.ops(None)
        self.assertTrue(ops.solicitar("suprimir_perfil", "acc_1", "p1"))
        self.assertEqual(self.pedidos, [])
        self.assertEqual(ops.exportar_perfil("acc_1", "p1")["error"], "Croco-Script no está conectado.")

    def test_el_pedido_va_firmado_en_la_cabecera_y_no_en_la_url(self):
        self.assertTrue(self.ops().solicitar("suprimir_perfil", "acc_1", "p1"))
        pedido = self.pedidos[0]
        self.assertEqual((pedido.get_method(), pedido.full_url), ("POST", "https://croco.example/federacion/v1/operacion"))
        token = pedido.get_header("Authorization").removeprefix("Bearer ")
        self.assertNotIn(token, pedido.full_url)
        cuerpo = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))
        self.assertEqual((cuerpo["act"], cuerpo["acc"], cuerpo["sub"]), ("suprimir_perfil", "acc_1", "p1"))
        self.assertEqual(self.ops().pendientes(), [])

    def test_si_croco_no_responde_queda_en_cola_y_se_reintenta_con_token_nuevo(self):
        self.salidas = [OSError("sin red")]
        ops = self.ops()
        self.assertFalse(ops.solicitar("suprimir_cuenta", "acc_1"))
        pendientes = ops.pendientes()
        self.assertEqual([(e["accion"], e["cuenta"], e["perfil"], e["intentos"]) for e in pendientes],
                         [("suprimir_cuenta", "acc_1", None, 1)])
        self.assertNotIn("@", json.dumps(pendientes))                          # solo identificadores opacos
        self.assertEqual(ops.reintentar_pendientes(), 1)
        self.assertEqual(ops.pendientes(), [])
        tokens = {p.get_header("Authorization") for p in self.pedidos}
        self.assertEqual(len(tokens), 2)                                       # el reintento no reusa el jti

    def test_un_error_del_servidor_tambien_se_encola_y_los_intentos_suben(self):
        self.salidas = [_http_error(503), _http_error(503)]
        ops = self.ops()
        self.assertFalse(ops.solicitar("suprimir_perfil", "acc_1", "p1"))
        self.assertEqual(ops.reintentar_pendientes(), 0)
        self.assertEqual(ops.pendientes()[0]["intentos"], 2)

    def test_la_misma_operacion_no_se_encola_dos_veces(self):
        self.salidas = [OSError(), OSError()]
        ops = self.ops()
        ops.solicitar("suprimir_perfil", "acc_1", "p1")
        ops.solicitar("suprimir_perfil", "acc_1", "p1")
        self.assertEqual(len(ops.pendientes()), 1)

    def test_una_cola_danada_se_conserva_antes_de_encolar_nuevos_pedidos(self):
        for nombre, contenido in (("json-malformado", "{"), ("estructura-invalida", "{}")):
            with self.subTest(nombre=nombre):
                carpeta = self.tmp / nombre
                carpeta.mkdir()
                archivo = carpeta / "operaciones_pendientes.json"
                archivo.write_text(contenido, encoding="utf-8")
                self.salidas = [OSError("sin red")]
                ops = OperacionesCroco(CONFIG, carpeta, abrir=self.abrir)

                self.assertFalse(ops.solicitar("suprimir_cuenta", "acc_sintetica"))
                cuarentena = list(carpeta.glob("operaciones_pendientes.json.corrupto-*"))
                self.assertEqual(len(cuarentena), 1)
                self.assertEqual(cuarentena[0].read_text(encoding="utf-8"), contenido)
                pendientes = json.loads(archivo.read_text(encoding="utf-8"))
                self.assertEqual([(e["accion"], e["cuenta"]) for e in pendientes],
                                 [("suprimir_cuenta", "acc_sintetica")])

    def test_un_perfil_de_otra_cuenta_no_se_reintenta(self):
        self.salidas = [_http_error(409)]
        self.assertTrue(self.ops().solicitar("suprimir_perfil", "acc_1", "p1"))
        self.assertEqual(self.ops().pendientes(), [])

    def test_exportar_devuelve_los_datos_o_el_motivo(self):
        datos = {"formato": "crocoscript-datos-de-perfil", "version": 1, "entregas": []}
        self.salidas = [_Respuesta(200, {"contrato": "Supresion.v1", "accion": "exportar_perfil", "datos": datos}),
                        _http_error(404), OSError("caído"), _Respuesta(200, {"sin": "datos"})]
        ops = self.ops()
        self.assertEqual(ops.exportar_perfil("acc_1", "p1"), datos)
        self.assertIn("vacio", ops.exportar_perfil("acc_1", "p1"))
        self.assertIn("error", ops.exportar_perfil("acc_1", "p1"))
        self.assertIn("error", ops.exportar_perfil("acc_1", "p1"))
        self.assertEqual(ops.pendientes(), [])                                 # exportar nunca se encola


class _Base(unittest.TestCase):
    """Una app con una cuenta, un perfil activo y Croco-Script configurado."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.app = create_app(token="t")
        self.app.config.update(
            TESTING=True, ACCOUNT_DB=self.tmp / "cuentas.sqlite3", PROGRESS_DIR=self.tmp / "progreso_perfiles",
            ACCOUNT_EMAIL_SENDER=lambda **payload: None, FEDERACION={"croco-script": dict(CONFIG)})
        self.app.instance_path = str(self.tmp / "instancia")
        self.c = self.app.test_client()
        self.email = "familia@example.com"
        self.c.post("/cuenta/registrar", data={"email": self.email, "password": "una-clave-larga-123", "responsable": "si"})
        self.cuenta_id = "acc_" + hashlib.sha256(self.email.encode()).hexdigest()[:24]
        AuthRepository(self.tmp / "cuentas.sqlite3").marcar_verificada(self.cuenta_id)
        self.c.post("/cuenta/login", data={"email": self.email, "password": "una-clave-larga-123"})
        self.csrf = self.c.get_cookie("tortu_csrf").value
        self.perfil = self.c.post("/cuenta/perfiles", json={"nombre": "Ana"}, headers={"X-Tortu-CSRF": self.csrf}).json["perfil"]["id"]
        self.cuentas = CuentaRepository(self.tmp / "cuentas.sqlite3")
        self.anonimo = self.app.test_client()             # sin cookies: así llama un servidor

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def dar_acceso(self, activo=True):
        self.cuentas.establecer_entitlement(self.cuenta_id, "croco-script", activo, "prueba")


class TestEntitlementV1(_Base):
    def pedir(self, cuenta, **kw):
        return self.anonimo.get(f"/federacion/v1/acceso?cuenta={cuenta}&producto=croco-script", headers=encabezado(cuenta, **kw))

    def test_responde_el_estado_de_acceso_de_la_cuenta(self):
        r = self.pedir(self.cuenta_id)
        self.assertEqual((r.status_code, r.json["contrato"], r.json["producto"], r.json["activo"]), (200, "Entitlement.v1", "croco-script", False))
        self.assertEqual(r.headers["Cache-Control"], "no-store")
        self.dar_acceso()
        self.assertIs(self.pedir(self.cuenta_id).json["activo"], True)
        self.dar_acceso(False)
        self.assertIs(self.pedir(self.cuenta_id).json["activo"], False)

    def test_la_fecha_de_consulta_es_actual_y_con_zona_horaria(self):
        consultado = datetime.fromisoformat(self.pedir(self.cuenta_id).json["consultado"])
        self.assertLess(abs((datetime.now(timezone.utc) - consultado).total_seconds()), 10)

    def test_una_cuenta_desconocida_no_tiene_acceso(self):
        r = self.pedir("acc_inexistente")
        self.assertEqual((r.status_code, r.json["activo"]), (200, False))

    def test_un_admin_tiene_acceso_como_en_la_transicion(self):
        self.cuentas.establecer_role(self.cuenta_id, "admin")
        self.assertIs(self.pedir(self.cuenta_id).json["activo"], True)

    def test_sin_firma_valida_es_401_y_no_dice_por_que(self):
        casos = {
            "sin firma": self.anonimo.get(f"/federacion/v1/acceso?cuenta={self.cuenta_id}&producto=croco-script"),
            "firma de otra cuenta": self.anonimo.get(f"/federacion/v1/acceso?cuenta={self.cuenta_id}&producto=croco-script",
                                                     headers=encabezado("acc_otra")),
            "clave equivocada": self.pedir(self.cuenta_id, clave="z" * 40),
            "vencida": self.pedir(self.cuenta_id, momento=int(time.time()) - 600),
            "sin cuenta": self.anonimo.get("/federacion/v1/acceso?producto=croco-script", headers=encabezado("")),
            "identificador raro": self.anonimo.get("/federacion/v1/acceso?cuenta=../x&producto=croco-script", headers=encabezado("../x")),
        }
        for motivo, r in casos.items():
            with self.subTest(motivo=motivo):
                self.assertEqual((r.status_code, r.json), (401, {"error": "autorizacion_invalida"}))

    def test_sin_federacion_configurada_no_existe(self):
        self.app.config["FEDERACION"] = {}
        self.assertEqual(self.pedir(self.cuenta_id).status_code, 404)

    def test_otro_producto_no_se_consulta(self):
        r = self.anonimo.get(f"/federacion/v1/acceso?cuenta={self.cuenta_id}&producto=otro", headers=encabezado(self.cuenta_id, producto="otro"))
        self.assertEqual(r.status_code, 404)

    def test_no_pide_sesion_ni_redirige(self):
        r = self.anonimo.get(f"/federacion/v1/acceso?cuenta={self.cuenta_id}&producto=croco-script", headers=encabezado(self.cuenta_id))
        self.assertEqual(r.status_code, 200)


class TestProgressQueryV1(_Base):
    def pedir(self, perfil, **kw):
        return self.anonimo.get(f"/federacion/v1/progreso?perfil={perfil}&producto=croco-script", headers=encabezado(perfil, **kw))

    def guardar_progreso(self, data):
        ProgresoChildProfile(self.tmp / "progreso_perfiles").guardar(nuevo_snapshot(self.perfil, data))

    def test_un_perfil_con_acceso_recibe_su_progress_v1(self):
        self.dar_acceso()
        r = self.pedir(self.perfil)
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.json["contrato"], r.json["producto"], r.json["perfil"]), ("Progress.v1", "tortuscript", self.perfil))
        self.assertEqual(r.json["cursos"], [])                                  # sin actividad no figura ningún curso
        self.assertEqual(r.headers["Cache-Control"], "no-store")

    def test_lo_completado_aparece_con_los_identificadores_de_curriculum_v1(self):
        self.dar_acceso()
        mapa = catalogo_producto.cargar_mapa()["unidades"]
        unidad = next(u for u, e in mapa.items() if e.get("tipo") == "lecciones")
        lecciones = mapa[unidad]["lecciones"]
        self.guardar_progreso({"lecciones": {l: {"pasos": {"0": {"xp": 5, "perfecto": True}, "1": {"xp": 5, "perfecto": True}},
                                                 "completada": True, "perfecta": True} for l in lecciones}})
        cursos = self.pedir(self.perfil).json["cursos"]
        curriculo = catalogo_producto.curriculo_publicado()
        itinerario = next(i["id"] for i in curriculo["itinerarios"] if unidad in i["unidades"])
        curso = next(c for c in cursos if c["curso"] == itinerario)
        self.assertIn(unidad, curso["lecciones_completadas"])
        self.assertEqual(curso["ejercicios_completados"], 2 * len(lecciones))
        self.assertEqual(federacion.prerrequisitos_desconocidos_v1(curriculo, [curso["curso"], *curso["lecciones_completadas"]]), [])

    def test_no_lleva_datos_personales(self):
        self.dar_acceso()
        self.guardar_progreso({"config": {"nombre": "Ana Pérez"}, "xp_total": 40})
        cuerpo = self.pedir(self.perfil).get_data(as_text=True)
        for dato in ("Ana", "Pérez", self.email, self.cuenta_id, "xp_total"):
            self.assertNotIn(dato, cuerpo)

    def test_un_perfil_sin_acceso_se_trata_como_inexistente(self):
        r = self.pedir(self.perfil)
        self.assertEqual((r.status_code, r.json), (404, {"error": "perfil_inexistente"}))
        self.assertEqual(self.pedir("child_que_no_existe").status_code, 404)

    def test_un_perfil_archivado_no_se_responde(self):
        self.dar_acceso()
        self.c.post(f"/cuenta/perfiles/{self.perfil}/archivar", headers={"X-Tortu-CSRF": self.csrf})
        self.assertEqual(self.pedir(self.perfil).status_code, 404)

    def test_la_firma_es_obligatoria_y_es_del_perfil_pedido(self):
        self.dar_acceso()
        for motivo, r in {"sin firma": self.anonimo.get(f"/federacion/v1/progreso?perfil={self.perfil}&producto=croco-script"),
                          "firma de otro perfil": self.anonimo.get(f"/federacion/v1/progreso?perfil={self.perfil}&producto=croco-script",
                                                                   headers=encabezado("otro")),
                          "clave equivocada": self.pedir(self.perfil, clave="z" * 40)}.items():
            with self.subTest(motivo=motivo):
                self.assertEqual(r.status_code, 401)

    def test_croco_script_puede_leerlo_con_su_propio_cliente(self):
        """Ida y vuelta con la fórmula de firma de Croco-Script (no con la nuestra)."""
        self.dar_acceso()
        momento = int(time.time())
        cabecera = {"Authorization": f"Croco-HMAC kid=k1, ts={momento}, firma={firma_como_croco(CLAVE, momento, 'croco-script', self.perfil)}"}
        self.assertEqual(self.anonimo.get(f"/federacion/v1/progreso?perfil={self.perfil}&producto=croco-script", headers=cabecera).status_code, 200)


class TestBorradoYExportacionHaciaCroco(_Base):
    def setUp(self):
        super().setUp()
        self.pedidos = []
        self.salidas = []
        patrulla = mock.patch("tortuscript.federacion_operaciones.urllib.request.urlopen", side_effect=self._urlopen)
        patrulla.start()
        self.addCleanup(patrulla.stop)

    def _urlopen(self, pedido, timeout=None):
        self.pedidos.append(pedido)
        salida = self.salidas.pop(0) if self.salidas else _Respuesta(200, {"contrato": "Supresion.v1"})
        if isinstance(salida, Exception):
            raise salida
        return salida

    def acciones(self):
        return [json.loads(base64.urlsafe_b64decode(p.get_header("Authorization").split(".")[1] + "=="))["act"] for p in self.pedidos]

    def eliminar_perfil(self):
        self.c.post(f"/cuenta/perfiles/{self.perfil}/archivar", headers={"X-Tortu-CSRF": self.csrf})
        return self.c.post(f"/cuenta/perfiles/{self.perfil}/eliminar", json={"nombre": "Ana"}, headers={"X-Tortu-CSRF": self.csrf})

    def test_eliminar_un_perfil_le_avisa_a_croco_script(self):
        self.eliminar_perfil()
        self.assertEqual(self.acciones(), ["suprimir_perfil"])
        cuerpo = json.loads(base64.urlsafe_b64decode(self.pedidos[0].get_header("Authorization").split(".")[1] + "=="))
        self.assertEqual((cuerpo["acc"], cuerpo["sub"]), (self.cuenta_id, self.perfil))

    def test_si_croco_esta_caido_el_perfil_se_elimina_igual_y_el_aviso_queda_pendiente(self):
        self.salidas = [OSError("caído")]
        r = self.eliminar_perfil()
        self.assertTrue(r.json["ok"] if r.is_json else True)
        self.assertEqual(self.cuentas.listar_child_profiles(self.cuenta_id), [])
        pendientes = OperacionesCroco(CONFIG, Path(self.app.instance_path)).pendientes()
        self.assertEqual([(e["accion"], e["perfil"]) for e in pendientes], [("suprimir_perfil", self.perfil)])

    def test_sin_croco_configurado_eliminar_funciona_y_no_hay_pedidos(self):
        self.app.config["FEDERACION"] = {}
        self.eliminar_perfil()
        self.assertEqual(self.pedidos, [])
        self.assertEqual(self.cuentas.listar_child_profiles(self.cuenta_id), [])

    def test_purgar_una_cuenta_vencida_avisa_y_reintenta_lo_pendiente(self):
        from web.cuenta_routes import purgar_cuentas_vencidas
        OperacionesCroco(CONFIG, Path(self.app.instance_path))._encolar("suprimir_perfil", "acc_vieja", "child_viejo")
        self.cuentas.solicitar_eliminacion(self.cuenta_id, ahora=datetime.now(timezone.utc) - timedelta(days=400))
        with self.app.app_context():
            self.assertEqual(purgar_cuentas_vencidas(), 1)
        self.assertEqual(sorted(self.acciones()), ["suprimir_cuenta", "suprimir_perfil"])
        self.assertEqual(OperacionesCroco(CONFIG, Path(self.app.instance_path)).pendientes(), [])

    def test_la_descarga_de_datos_incluye_lo_que_guarda_croco_script(self):
        datos = {"formato": "crocoscript-datos-de-perfil", "version": 1, "entregas": [{"tarea": "t1"}]}
        self.salidas = [_Respuesta(200, {"contrato": "Supresion.v1", "accion": "exportar_perfil", "datos": datos})]
        documento = self.c.get("/cuenta/datos/exportar").json
        self.assertEqual(documento["perfiles"][0]["croco_script"], datos)
        self.assertEqual(self.acciones(), ["exportar_perfil"])

    def test_la_descarga_funciona_aunque_croco_script_no_responda(self):
        self.salidas = [OSError("caído")]
        documento = self.c.get("/cuenta/datos/exportar").json
        self.assertIn("error", documento["perfiles"][0]["croco_script"])
        self.assertEqual(documento["cuenta"]["id"], self.cuenta_id)

    def test_sin_croco_la_descarga_no_trae_esa_seccion(self):
        self.app.config["FEDERACION"] = {}
        self.assertNotIn("croco_script", self.c.get("/cuenta/datos/exportar").json["perfiles"][0])


if __name__ == "__main__":
    unittest.main()
