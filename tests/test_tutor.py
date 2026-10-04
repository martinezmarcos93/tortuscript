"""Tortu-LLM (ADR-035): privacidad del contexto, control de revelación, límites, consentimiento y fallback.

No se llama a ningún modelo real: el proveedor es un doble que registra lo que recibiría.
"""
import hashlib
import shutil
import sys
import tempfile
import types
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from tortuscript import contenido, persistencia_local, tutor
from tortuscript.auth import AuthRepository
from tortuscript.tutor import TutorNoDisponible, TutorService
from web.app import create_app

HOY = date(2026, 12, 10)
PISTA = "Palabras clave a usar: mostrar"


class Doble:
    def __init__(self, respuesta="¿Qué palabra usás para que algo aparezca en la pantalla?"):
        self.respuesta, self.pedidos = respuesta, []

    def __call__(self, instrucciones, pedido):
        self.pedidos.append((instrucciones, pedido))
        if isinstance(self.respuesta, Exception):
            raise self.respuesta
        return self.respuesta


class TestContexto(unittest.TestCase):
    def test_el_pedido_lleva_solo_consigna_intento_error_y_nivel(self):
        pedido = tutor.armar_pedido("Mostrá Hola", 'mostrar "Hola', "Falta cerrar las comillas", 3)
        for parte in ("<consigna>", "Mostrá Hola", "<intento>", 'mostrar "Hola', "<error>", "Falta cerrar", "diagnóstico del error"):
            self.assertIn(parte, pedido)
        self.assertNotIn("<error>", tutor.armar_pedido("c", "x", "", 1))
        with self.assertRaises(ValueError):
            tutor.armar_pedido("c", "x", "", 9)

    def test_se_tachan_los_datos_de_contacto_que_escribio_el_chico(self):
        codigo = ('nombre es "ana.perez@example.com"\ntel es "+54 11 4321-9876"\n'
                  'web es "https://mi-escuela.example/alumnos/ana"\nedad es 11\nmostrar 12345')
        pedido = tutor.armar_pedido("c", codigo, "mirá www.sitio.example y escribime a x@y.zz", 1)
        for dato in ("ana.perez@example.com", "4321-9876", "mi-escuela.example", "www.sitio.example", "x@y.zz"):
            self.assertNotIn(dato, pedido)
        self.assertIn("edad es 11", pedido)                        # los números comunes del programa se conservan
        self.assertIn("mostrar 12345", pedido)

    def test_los_tamanos_estan_acotados(self):
        pedido = tutor.armar_pedido("c" * 9000, "x" * 9000, "e" * 9000, 1)
        self.assertLess(len(pedido), tutor.CONSIGNA_MAX + tutor.CODIGO_MAX + tutor.ERROR_MAX + 400)

    def test_las_instrucciones_piden_no_resolver_e_ignorar_ordenes_del_intento(self):
        for frase in ("nunca le das", "las ignorás", "datos personales"):
            self.assertIn(frase, tutor.INSTRUCCIONES)


class TestControlDeRevelacion(unittest.TestCase):
    def test_respuestas_que_resuelven_demasiado_se_descartan(self):
        malas = (
            "Acá va:\n```\nnombre es preguntar(\"?\")\nmostrar nombre\n```",
            "Hacé esto:\nnombre es \"Ana\"\nmostrar nombre\nmostrar \"chau\"",
            "x = 1\nprint(x)",
            "palabra " * 200,
            "", "   ", None, 7,
        )
        for texto in malas:
            with self.subTest(texto=str(texto)[:30]), self.assertRaises(TutorNoDisponible):
                tutor.revisar_respuesta(texto, 2)

    def test_ayudas_normales_pasan_y_el_ejemplo_parcial_admite_pocas_lineas(self):
        self.assertEqual(tutor.revisar_respuesta("  ¿Cerraste las comillas?  ", 2), "¿Cerraste las comillas?")
        self.assertTrue(tutor.revisar_respuesta("Acordate de usar mostrar para que algo aparezca.", 1))
        ejemplo = "Mirá este parecido:\nanimal es \"gato\"\nmostrar animal"
        self.assertTrue(tutor.revisar_respuesta(ejemplo, 4))
        with self.assertRaises(TutorNoDisponible):
            tutor.revisar_respuesta(ejemplo, 2)
        with self.assertRaises(TutorNoDisponible):
            tutor.revisar_respuesta(ejemplo + "\nmostrar 1\nmostrar 2", 4)


class TestServicio(unittest.TestCase):
    def ayudar(self, servicio, progreso, consentimiento=True, nivel=2, hoy=HOY):
        return servicio.ayudar(progreso, consentimiento, "Mostrá Hola", "mostar Hola", "", nivel, PISTA, hoy=hoy)

    def test_con_proveedor_y_consentimiento_responde_el_tutor_y_descuenta_un_uso(self):
        doble, p = Doble(), {}
        ayuda = self.ayudar(TutorService(doble), p)
        self.assertEqual((ayuda.origen, ayuda.restantes), ("tutor", tutor.USOS_POR_DIA - 1))
        self.assertEqual(p["tutor"], {"dia": "2026-12-10", "usos": 1})
        self.assertEqual(len(doble.pedidos), 1)

    def test_sin_consentimiento_o_sin_proveedor_no_sale_nada_hacia_afuera(self):
        doble, p = Doble(), {}
        self.assertEqual(self.ayudar(TutorService(doble), p, consentimiento=False).origen, "pista")
        self.assertEqual(self.ayudar(TutorService(None), p).texto, PISTA)
        self.assertEqual(doble.pedidos, [])
        self.assertNotIn("tutor", p)

    def test_cupo_diario_por_perfil_y_se_renueva_al_dia_siguiente(self):
        doble, p = Doble(), {}
        servicio = TutorService(doble, usos_por_dia=2)
        self.assertEqual([self.ayudar(servicio, p).origen for _ in range(3)], ["tutor", "tutor", "pista"])
        self.assertEqual(len(doble.pedidos), 2)                     # el tercero no llegó al proveedor
        self.assertEqual(self.ayudar(servicio, p, hoy=date(2026, 12, 11)).origen, "tutor")

    def test_un_contador_manipulado_no_regala_usos(self):
        servicio = TutorService(Doble(), usos_por_dia=2)
        for manipulado in ({"dia": "2026-12-10", "usos": -50}, {"dia": "2026-12-10", "usos": "0"}, {"dia": "2026-12-10", "usos": None}):
            self.assertLessEqual(servicio.restantes({"tutor": manipulado}, HOY), 2)
        self.assertEqual(servicio.restantes({"tutor": {"dia": "2026-12-10", "usos": "0"}}, HOY), 0)
        self.assertEqual(servicio.restantes({"tutor": "roto"}, HOY), 2)

    def test_fallas_y_respuestas_inaceptables_devuelven_la_pista_sin_gastar_uso(self):
        for respuesta in (RuntimeError("sin red"), TutorNoDisponible("rechazo"), "```\na es 1\nmostrar a\n```", ""):
            with self.subTest(respuesta=str(respuesta)[:20]):
                p = {}
                with self.assertLogs("tortuscript.tutor", "WARNING") as logs:
                    ayuda = self.ayudar(TutorService(Doble(respuesta)), p)
                self.assertEqual((ayuda.origen, ayuda.texto), ("pista", PISTA))
                self.assertNotIn("tutor", p)
                self.assertNotIn("mostar Hola", "\n".join(logs.output))    # el intento del chico no va al log

    def test_nivel_desconocido_baja_al_primero(self):
        doble = Doble()
        self.assertEqual(self.ayudar(TutorService(doble), {}, nivel=99).nivel, 1)
        self.assertIn("pista conceptual", doble.pedidos[0][1])


class TestAdaptadorClaude(unittest.TestCase):
    """El SDK `anthropic` es opcional: se prueba el adaptador con un módulo de mentira con la misma forma."""

    def _sdk(self, respuesta=None, error=None):
        sdk = types.ModuleType("anthropic")

        class APIStatusError(Exception):
            status_code = 500

        class RateLimitError(APIStatusError):
            status_code = 429

        class APIConnectionError(Exception):
            pass

        llamadas = []

        class Mensajes:
            def create(self, **kwargs):
                llamadas.append(kwargs)
                if error:
                    raise error(sdk)
                return respuesta

        class Anthropic:
            def __init__(self, **kwargs):
                self.opciones, self.messages = kwargs, Mensajes()

        sdk.Anthropic, sdk.APIStatusError, sdk.RateLimitError, sdk.APIConnectionError = \
            Anthropic, APIStatusError, RateLimitError, APIConnectionError
        return sdk, llamadas

    def _respuesta(self, stop="end_turn", bloques=(("thinking", ""), ("text", "¿Probaste con mostrar?"))):
        return types.SimpleNamespace(stop_reason=stop, content=[
            types.SimpleNamespace(type=t, text=x, thinking=x) for t, x in bloques])

    def test_pide_con_el_modelo_por_defecto_y_devuelve_solo_el_texto(self):
        sdk, llamadas = self._sdk(self._respuesta())
        with mock.patch.dict(sys.modules, {"anthropic": sdk}):
            proveedor = tutor.proveedor_desde_entorno({"TORTU_TUTOR": "claude"})
            self.assertEqual(proveedor("instrucciones", "pedido"), "¿Probaste con mostrar?")
        pedido = llamadas[0]
        self.assertEqual(pedido["model"], "claude-opus-5-5")
        self.assertEqual(pedido["system"], "instrucciones")
        self.assertEqual(pedido["messages"], [{"role": "user", "content": "pedido"}])
        self.assertEqual(pedido["output_config"], {"effort": "low"})
        for obsoleto in ("temperature", "top_p", "tool_choice"):
            self.assertNotIn(obsoleto, pedido)
        self.assertNotIn("budget_tokens", str(pedido))

    def test_rechazos_cortes_y_errores_del_proveedor_son_tutor_no_disponible(self):
        casos = [dict(respuesta=self._respuesta(stop="refusal")), dict(respuesta=self._respuesta(stop="max_tokens")),
                 dict(error=lambda sdk: sdk.RateLimitError()), dict(error=lambda sdk: sdk.APIStatusError()),
                 dict(error=lambda sdk: sdk.APIConnectionError())]
        for caso in casos:
            sdk, _ = self._sdk(**caso)
            with self.subTest(caso=str(caso)[:40]), mock.patch.dict(sys.modules, {"anthropic": sdk}):
                with self.assertRaises(TutorNoDisponible):
                    tutor.ProveedorClaude()("i", "p")

    def test_apagado_por_defecto_y_si_falta_el_paquete(self):
        self.assertIsNone(tutor.proveedor_desde_entorno({}))
        self.assertIsNone(tutor.proveedor_desde_entorno({"TORTU_TUTOR": "otro"}))
        with mock.patch.dict(sys.modules, {"anthropic": None}), self.assertLogs("tortuscript.tutor", "ERROR"):
            self.assertIsNone(tutor.proveedor_desde_entorno({"TORTU_TUTOR": "claude"}))

    def test_otro_modelo_por_configuracion(self):
        sdk, _ = self._sdk(self._respuesta())
        with mock.patch.dict(sys.modules, {"anthropic": sdk}):
            self.assertEqual(tutor.proveedor_desde_entorno({"TORTU_TUTOR": "claude", "TORTU_TUTOR_MODELO": "claude-haiku-4-5"}).modelo,
                             "claude-haiku-4-5")


class TestHTTP(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._orig = persistencia_local.DIRECTORIO
        persistencia_local.DIRECTORIO = self.tmp
        self.doble = Doble()
        self.app = create_app(token="t")
        self.app.config.update(TESTING=True, ACCOUNT_DB=self.tmp / "cuentas.sqlite3",
                               PROGRESS_DIR=self.tmp / "progreso_perfiles",
                               ACCOUNT_EMAIL_SENDER=lambda **payload: None, TUTOR_PROVEEDOR=self.doble)
        self.c = self.app.test_client()
        self.h = {"X-Tortu-Token": "t"}
        self.email = "tutor@example.com"
        self.c.post("/cuenta/registrar", data={"email": self.email, "password": "una-clave-larga-123", "responsable": "si"})
        cuenta_id = "acc_" + hashlib.sha256(self.email.encode()).hexdigest()[:24]
        AuthRepository(self.tmp / "cuentas.sqlite3").marcar_verificada(cuenta_id)
        self.c.post("/cuenta/login", data={"email": self.email, "password": "una-clave-larga-123"})
        self.csrf = self.c.get_cookie("tortu_csrf").value
        perfil = self.c.post("/cuenta/perfiles", json={"nombre": "Ana Secreta"}, headers={"X-Tortu-CSRF": self.csrf}).json["perfil"]["id"]
        self.c.post("/cuenta/perfil", json={"perfil_id": perfil}, headers={"X-Tortu-CSRF": self.csrf})
        self.c.post("/api/onboarding", json={"nombre": "Ana Secreta", "experiencia": "nunca", "meta_min": 10}, headers=self.h)
        leccion = contenido.lecciones(contenido.cargar_curso())[0][1]
        self.leccion = leccion["id"]
        self.i = next(n for n, paso in enumerate(leccion["pasos"]) if paso["tipo"] == "escribir")
        self.paso = leccion["pasos"][self.i]
        self.ruta = f"/api/lecciones/{self.leccion}/pasos/{self.i}"

    def tearDown(self):
        persistencia_local.DIRECTORIO = self._orig
        shutil.rmtree(self.tmp)

    def consentir(self, decision="aceptar"):
        return self.c.post("/cuenta/consentimiento", data={"csrf": self.csrf, "finalidad": "tutor_ia", "decision": decision})

    def pedir(self, **datos):
        return self.c.post(self.ruta + "/tutor", json={"codigo": "mostar hola", "error": "", "nivel": 1, **datos}, headers=self.h)

    def test_sin_que_el_adulto_acepte_no_se_envia_nada_y_no_hay_boton(self):
        r = self.pedir()
        self.assertEqual((r.status_code, r.json["origen"]), (200, "pista"))
        self.assertEqual(self.doble.pedidos, [])
        self.assertIn('"tutor": false', self.c.get(f"/leccion/{self.leccion}").get_data(as_text=True))

    def test_con_aceptacion_responde_el_tutor_sin_identidad_ni_solucion_en_el_pedido(self):
        html = self.c.get("/cuenta/configuracion").get_data(as_text=True)
        self.assertIn("Qué se envía", html)
        self.assertIn("desactivada", html)
        self.assertEqual(self.consentir().status_code, 302)
        self.assertIn('"tutor": true', self.c.get(f"/leccion/{self.leccion}").get_data(as_text=True))
        r = self.pedir(error="Nombre desconocido")
        self.assertEqual((r.json["origen"], r.json["restantes"]), ("tutor", tutor.USOS_POR_DIA - 1))
        instrucciones, pedido = self.doble.pedidos[0]
        enviado = instrucciones + pedido
        for privado in (self.email, "Ana Secreta", "child_", "acc_", self.paso["solucion"].strip()):
            self.assertNotIn(privado, enviado)
        self.assertIn("mostar hola", pedido)
        self.assertIn(self.paso["consigna"][:20], pedido)

    def test_revocar_corta_el_envio_de_inmediato_y_queda_en_la_bitacora(self):
        self.consentir()
        self.pedir()
        self.consentir("revocar")
        self.assertEqual(self.pedir().json["origen"], "pista")
        self.assertEqual(len(self.doble.pedidos), 1)
        exportado = self.c.get("/cuenta/datos/exportar").json["consentimientos"]
        self.assertEqual([(c["finalidad"], c["otorgado"]) for c in exportado if c["finalidad"] == "tutor_ia"],
                         [("tutor_ia", True), ("tutor_ia", False)])

    def test_pedir_ayuda_cuenta_como_pista_y_no_aprueba_el_ejercicio(self):
        self.consentir()
        self.pedir()
        self.assertEqual(self.c.get("/api/estado", headers=self.h).json["lecciones_hechas"], 0)
        r = self.c.post(self.ruta + "/evaluar", json={"codigo": self.paso["solucion"]}, headers=self.h).json
        self.assertEqual(r["evaluacion"]["estado"], "correcto")
        self.assertEqual(r["premio"]["estrellas"], 2)               # como con una pista

    def test_sin_proveedor_la_seccion_no_aparece_y_la_ruta_da_la_pista(self):
        self.app.config["TUTOR_PROVEEDOR"] = None
        self.assertNotIn("inteligencia artificial", self.c.get("/cuenta/configuracion").get_data(as_text=True))
        self.consentir()
        self.assertEqual(self.pedir().json["origen"], "pista")

    def test_validaciones_de_la_ruta(self):
        self.assertEqual(self.pedir(codigo=["x"]).status_code, 400)
        self.assertEqual(self.pedir(nivel="2").status_code, 400)
        self.assertEqual(self.c.post(f"/api/lecciones/{self.leccion}/pasos/0/tutor", json={}, headers=self.h).status_code, 400)
        self.assertEqual(self.c.post("/cuenta/consentimiento", data={"csrf": self.csrf, "finalidad": "analitica", "decision": "aceptar"}).status_code, 400)
        self.assertEqual(self.c.post("/cuenta/consentimiento", data={"finalidad": "tutor_ia", "decision": "aceptar"}).status_code, 403)

    def test_el_cupo_diario_se_guarda_en_el_progreso_del_perfil(self):
        self.consentir()
        with mock.patch.object(tutor, "USOS_POR_DIA", 2), mock.patch.object(TutorService.__init__, "__defaults__", (None, 2)):
            origenes = [self.pedir().json["origen"] for _ in range(3)]
        self.assertEqual(origenes, ["tutor", "tutor", "pista"])


if __name__ == "__main__":
    unittest.main()
