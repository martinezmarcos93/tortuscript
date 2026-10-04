"""Barrido 3 — el recorrido completo de una familia, de punta a punta y por HTTP.

Registro con enlace de correo → verificación → ingreso → perfil → bienvenida → lección con
error, pista y reintento → XP y cierre → mapa y lección siguiente → abandono y regreso →
segundo perfil aislado → exportación. Nada se siembra por fuera de la API pública: si este
test pasa, el flujo que usa una familia real funciona.
"""
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from tortuscript import contenido, correo, persistencia_local
from tortuscript import leccion as motor
from web.app import create_app

CLAVE = "una-clave-larga-123"
BASE = "http://localhost"


class TestCicloCompletoDelAlumno(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._orig = persistencia_local.DIRECTORIO
        persistencia_local.DIRECTORIO = self.tmp
        self.correos = []
        self.app = self._nueva_app()
        self.c = self.app.test_client()
        self.h = {"X-Tortu-Token": "t"}
        self.curso = contenido.cargar_curso()
        self.lecciones = [lec for _, lec in contenido.lecciones(self.curso)]

    def tearDown(self):
        persistencia_local.DIRECTORIO = self._orig
        shutil.rmtree(self.tmp)

    def _nueva_app(self):
        """Una app sobre los mismos datos: sirve también para simular que el servidor se reinició."""
        app = create_app(token="t")
        app.config.update(
            TESTING=True, ACCOUNT_DB=self.tmp / "instance" / "cuentas.sqlite3",
            PROGRESS_DIR=self.tmp / "instance" / "progreso_perfiles",
            # El enviador real de consola: el enlace sale armado como lo recibiría el adulto.
            ACCOUNT_EMAIL_SENDER=correo.EnviadorConsola(BASE, salida=self.correos.append),
        )
        return app

    # ── piezas del recorrido ──
    def _enlace_del_ultimo_correo(self):
        url = re.search(r"https?://\S+", self.correos[-1]).group(0)
        partes = urlsplit(url)
        return partes.path + "?" + partes.query, parse_qs(partes.query)["token"][0]

    def _csrf(self, cliente=None):
        return (cliente or self.c).get_cookie("tortu_csrf").value

    def _registrar_y_verificar(self, email):
        r = self.c.post("/cuenta/registrar", data={"email": email, "password": CLAVE})
        self.assertEqual(r.status_code, 202)
        self.assertIn("Verificá tu correo", r.get_data(as_text=True))
        # Sin verificar no se puede entrar.
        self.assertEqual(self.c.post("/cuenta/login", data={"email": email, "password": CLAVE}).status_code, 401)
        ruta, token = self._enlace_del_ultimo_correo()
        confirmar = self.c.get(ruta)
        self.assertEqual(confirmar.status_code, 200)
        self.assertIn("Confirmar correo", confirmar.get_data(as_text=True))
        ok = self.c.post("/cuenta/verificar-email", data={"token": token})
        self.assertEqual(ok.status_code, 200)
        self.assertIn("Correo verificado", ok.get_data(as_text=True))

    def _ingresar(self, email, cliente=None):
        cliente = cliente or self.c
        r = cliente.post("/cuenta/login", data={"email": email, "password": CLAVE})
        self.assertEqual(r.status_code, 302)
        return r

    def _crear_perfil_y_entrar(self, nombre):
        r = self.c.post("/cuenta/perfiles", data={"nombre": nombre, "csrf": self._csrf()})
        self.assertEqual(r.status_code, 302)
        me = self.c.get("/cuenta/me").json
        return next(p["id"] for p in me["perfiles"] if p["nombre"] == nombre)

    def _elegir_perfil(self, perfil_id):
        r = self.c.post("/cuenta/perfil", data={"perfil_id": perfil_id, "csrf": self._csrf()})
        self.assertEqual(r.status_code, 302)

    def _bienvenida(self, nombre):
        # Un perfil nuevo siempre pasa primero por la bienvenida.
        r = self.c.get("/")
        self.assertEqual((r.status_code, r.headers["Location"]), (302, "/bienvenida"))
        self.assertEqual(self.c.get("/bienvenida").status_code, 200)
        r = self.c.post("/api/onboarding", json={"nombre": nombre, "experiencia": "nunca", "meta_min": 10},
                        headers=self.h)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.c.get("/").status_code, 200)

    def _estado(self):
        return self.c.get("/api/estado", headers=self.h).json

    def _paso(self, leccion_id, i, respuesta):
        return self.c.post(f"/api/lecciones/{leccion_id}/pasos/{i}/comprobar", json={"respuesta": respuesta},
                           headers=self.h)

    def _respuesta_mala(self, paso):
        """Una respuesta incorrecta pero bien formada para el tipo de paso."""
        if paso["tipo"] in ("elegir", "predecir"):
            return str(next(o for n, o in enumerate(paso["opciones"]) if n != paso["correcta"]))
        if paso["tipo"] == "completar":
            return ["zzz"] * len(paso["respuesta"])
        return list(reversed(paso["lineas"]))                       # ordenar

    def _hacer_leccion(self, lec, con_tropiezos=False):
        """Recorre todos los pasos de una lección. Con tropiezos: se equivoca una vez en cada paso
        corregible y pide una pista antes de escribir. Devuelve el resumen del último paso."""
        self.assertEqual(self.c.get(f"/leccion/{lec['id']}").status_code, 200)
        ultimo = None
        for i, paso in enumerate(lec["pasos"]):
            if paso["tipo"] == "explicacion":
                ultimo = self._paso(lec["id"], i, True).json
            elif paso["tipo"] == "escribir":
                if con_tropiezos:
                    mal = self.c.post(f"/api/lecciones/{lec['id']}/pasos/{i}/evaluar",
                                      json={"codigo": 'mostrar "otra cosa distinta"'}, headers=self.h).json
                    self.assertNotEqual(mal["evaluacion"]["estado"], "correcto")
                    self.assertNotIn("premio", mal)
                    pista = self.c.post(f"/api/lecciones/{lec['id']}/pasos/{i}/pista", headers=self.h).json
                    self.assertEqual(pista["nivel"], 1)
                ultimo = self.c.post(f"/api/lecciones/{lec['id']}/pasos/{i}/evaluar",
                                     json={"codigo": paso["solucion"]}, headers=self.h).json
                self.assertEqual(ultimo["evaluacion"]["estado"], "correcto", ultimo)
                self.assertEqual(ultimo["premio"]["estrellas"], 2 if con_tropiezos else 3)
            else:
                if con_tropiezos and paso["tipo"] != "ordenar":
                    mal = self._paso(lec["id"], i, self._respuesta_mala(paso)).json
                    self.assertFalse(mal["ok"])
                    self.assertTrue(mal["pista"])
                ultimo = self._paso(lec["id"], i, motor.respuesta_correcta(paso)).json
                self.assertTrue(ultimo["ok"], (lec["id"], i, ultimo))
        return ultimo

    # ── el recorrido ──
    def test_recorrido_completo_con_dos_perfiles(self):
        email = "familia@example.com"
        primera, segunda = self.lecciones[0], self.lecciones[1]

        # 1. Sin sesión no hay nada educativo a la vista.
        r = self.c.get("/mapa")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/cuenta/ingresar", r.headers["Location"])
        self.assertEqual(self.c.get("/api/estado", headers=self.h).status_code, 401)

        # 2. Registro, verificación por enlace e ingreso.
        self._registrar_y_verificar(email)
        self._ingresar(email)
        # Con cuenta pero sin perfil elegido tampoco se entra al contenido.
        r = self.c.get("/mapa")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/cuenta/seleccionar-perfil", r.headers["Location"])

        # 3. Primer perfil y bienvenida.
        ana = self._crear_perfil_y_entrar("Ana")
        self._bienvenida("Ana")
        inicial = self._estado()
        self.assertEqual((inicial["nombre"], inicial["xp"], inicial["lecciones_hechas"]), ("Ana", 0, 0))

        # 4. La segunda lección está cerrada hasta terminar la primera.
        r = self.c.get(f"/leccion/{segunda['id']}")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self._paso(segunda["id"], 0, True).status_code, 403)

        # 5. Primera lección con errores, pista y reintentos: gana XP, pero no es perfecta.
        fin = self._hacer_leccion(primera, con_tropiezos=True)
        self.assertTrue(fin["leccion"]["completa"])
        self.assertTrue(fin["leccion"]["recien_completa"])
        self.assertFalse(fin["leccion"]["perfecta"])
        self.assertEqual(fin["leccion"]["siguiente"], segunda["id"])
        tras_primera = self._estado()
        self.assertGreater(tras_primera["xp"], 0)
        self.assertEqual(tras_primera["lecciones_hechas"], 1)
        self.assertGreaterEqual(tras_primera["racha"], 1)
        self.assertEqual(tras_primera["xp_hoy"], tras_primera["xp"])

        # 6. El mapa y el inicio reflejan el avance, y «seguir» lleva a la lección que toca.
        self.assertEqual(self.c.get("/mapa").status_code, 200)
        # («Seguir» propone la lección pendiente del camino completo, que empieza por el Nivel 0.)
        seguir = self.c.get("/aprender").headers["Location"]
        self.assertEqual(self.c.get(seguir).status_code, 200)
        self.assertEqual(self.c.get(f"/leccion/{segunda['id']}").status_code, 200)   # ya está abierta
        self.assertEqual(self.c.get("/resumen").status_code, 200)
        self.assertEqual(self.c.get("/logros").status_code, 200)

        # 7. Empieza la segunda y la abandona a mitad de camino.
        self.assertEqual(self.c.get(f"/leccion/{segunda['id']}").status_code, 200)
        self.assertTrue(self._paso(segunda["id"], 0, True).json["ok"])
        xp_al_abandonar = self._estado()["xp"]

        # 8. Cierra sesión: nada educativo queda accesible con las cookies viejas.
        sesion_vieja = self.c.get_cookie("tortu_session").value
        r = self.c.post("/cuenta/logout", data={"csrf": self._csrf()})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.c.get("/mapa").status_code, 302)
        self.c.set_cookie("tortu_session", sesion_vieja)
        self.assertEqual(self.c.get("/api/estado", headers=self.h).status_code, 401)
        self.c.delete_cookie("tortu_session")

        # 9. Otro día: se reinicia el servidor, vuelve a ingresar y retoma donde dejó.
        self.app = self._nueva_app()
        self.c = self.app.test_client()
        self._ingresar(email)
        self._elegir_perfil(ana)
        retomado = self._estado()
        self.assertEqual((retomado["nombre"], retomado["xp"], retomado["lecciones_hechas"]),
                         ("Ana", xp_al_abandonar, 1))
        self.assertEqual(self.c.get("/").status_code, 200)            # no repite la bienvenida
        self.assertEqual(self.c.get("/aprender").headers["Location"], seguir)
        fin = self._hacer_leccion(segunda)
        self.assertTrue(fin["leccion"]["completa"])
        self.assertTrue(fin["leccion"]["perfecta"])                   # sin tropiezos esta vez
        xp_ana = self._estado()["xp"]
        self.assertGreater(xp_ana, xp_al_abandonar)

        # 10. Segundo perfil de la misma cuenta: empieza de cero y con su propia bienvenida.
        bruno = self._crear_perfil_y_entrar("Bruno")
        self._bienvenida("Bruno")
        estado_bruno = self._estado()
        self.assertEqual((estado_bruno["nombre"], estado_bruno["xp"], estado_bruno["lecciones_hechas"]), ("Bruno", 0, 0))
        self.assertEqual(self._paso(segunda["id"], 0, True).status_code, 403)   # lo de Ana no le abre nada
        self._hacer_leccion(primera)
        xp_bruno = self._estado()["xp"]
        self.assertNotEqual(xp_bruno, xp_ana)

        # 11. Un proyecto guardado por Bruno no aparece en el perfil de Ana.
        r = self.c.post("/api/proyectos", json={"nombre": "Dibujo de Bruno", "tipo": "experimentar",
                                                "codigo": 'mostrar "hola"'}, headers=self.h)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertIn("Dibujo de Bruno", self.c.get("/proyectos").get_data(as_text=True))

        # 12. Volver a Ana: todo lo suyo intacto, nada de Bruno.
        self._elegir_perfil(ana)
        ana_final = self._estado()
        self.assertEqual((ana_final["nombre"], ana_final["xp"], ana_final["lecciones_hechas"]), ("Ana", xp_ana, 2))
        self.assertNotIn("Dibujo de Bruno", self.c.get("/proyectos").get_data(as_text=True))

        # 13. Exportación: cada perfil se lleva solo lo suyo.
        exportado = self.c.get("/api/perfil/exportar", headers=self.h).json
        self.assertEqual(exportado["datos"]["perfil"], "Ana")
        self.assertEqual(exportado["datos"]["progreso"]["xp_total"], xp_ana)
        self.assertEqual(exportado["datos"]["progreso"].get("proyectos", {}), {})
        self.assertNotIn("Bruno", str(exportado))
        self.assertNotIn(email, str(exportado))                       # ni el correo del adulto

        # 14. En disco: un archivo por perfil, con su identificador opaco y sin el nombre visible en la ruta.
        archivos = sorted(p.name for p in (self.tmp / "instance" / "progreso_perfiles").glob("progreso_child_*.json"))
        self.assertEqual(archivos, sorted(f"progreso_{pid}.json" for pid in (ana, bruno)))

    def test_otra_familia_no_ve_ni_puede_elegir_perfiles_ajenos(self):
        self._registrar_y_verificar("uno@example.com")
        self._ingresar("uno@example.com")
        ana = self._crear_perfil_y_entrar("Ana")
        self._bienvenida("Ana")
        self._hacer_leccion(self.lecciones[0])
        xp_ana = self._estado()["xp"]

        otra = self.app.test_client()
        self.c, propia = otra, self.c
        self._registrar_y_verificar("dos@example.com")
        self._ingresar("dos@example.com")
        self.assertEqual(self.c.get("/cuenta/me").json["perfiles"], [])
        # Conocer el identificador de un perfil ajeno no alcanza para entrar.
        r = self.c.post("/cuenta/perfil", json={"perfil_id": ana}, headers={"X-Tortu-CSRF": self._csrf()})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.c.get("/api/estado", headers=self.h).status_code, 401)
        # El mismo nombre en otra familia es otro perfil, vacío.
        self._crear_perfil_y_entrar("Ana")
        self._bienvenida("Ana")
        self.assertEqual(self._estado()["xp"], 0)
        self.c = propia
        self.assertEqual(self._estado()["xp"], xp_ana)


if __name__ == "__main__":
    unittest.main()
