"""Registros de progreso que son JSON válido pero tienen datos internos dañados (repaso espaciado).

Contrato (ver docs/audits/ROBUSTEZ_REGISTROS_PROGRESO.md): un registro dañado se AISLA, no bloquea el resto.
- No se interpreta con una suposición: ni fecha de vencimiento inventada, ni caja "corregida", ni tarjeta nueva.
- Lo válido de al lado se conserva y sigue funcionando; el perfil no se descarta ni se reescribe al leerlo.
- Los intervalos (1, 2, 4, 8, 16 días) y la elegibilidad de las tarjetas sanas no cambian.
"""
import copy
import shutil
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from tortuscript import catalogo_producto, contenido, persistencia_local, practica, progreso

import test_camino
from test_practica import CURSOS, HOY, con_pasos

try:
    import flask  # noqa: F401
    HAY_FLASK = True
except ImportError:
    HAY_FLASK = False

# hola-mundo: pasos rápidos 1..4. texto-o-cuenta: 1..4. Todos con fecha 2026-09-20 → vencidos el 2026-09-25.
SANAS = [("texto-o-cuenta", 1), ("texto-o-cuenta", 2), ("dos-lineas", 1)]


def perfil(*extra_pasos):
    """Perfil con tarjetas sanas y vencidas + los pasos extra (leccion, [índices])."""
    return con_pasos(("texto-o-cuenta", [1, 2]), ("dos-lineas", [1]), *extra_pasos)


def ids(candidatos):
    return sorted((c["leccion"], c["paso"]) for c in candidatos)


class TestClaveDePasoDanada(unittest.TestCase):
    CLAVES_MALAS = ("abc", "", "-1", "1.5", " 2", "01", "+1", "1e0", "٣", "None")     # "٣" es un dígito unicode

    def test_una_clave_que_no_es_un_indice_canonico_se_ignora_y_lo_sano_sigue(self):
        for mala in self.CLAVES_MALAS:
            with self.subTest(clave=mala):
                p = perfil(("hola-mundo", [1]))
                p["lecciones"]["hola-mundo"]["pasos"][mala] = {"xp": 5, "perfecto": True, "fecha": "2026-09-20"}
                self.assertEqual(ids(practica.candidatos(p, CURSOS, HOY)),
                                 sorted(SANAS + [("hola-mundo", 1)]))

    def test_menos_uno_no_se_interpreta_como_el_ultimo_paso(self):
        # int("-1") valía y apuntaba al último paso de la lección: una tarjeta que nadie hizo.
        p = con_pasos(("hola-mundo", [1]))
        p["lecciones"]["hola-mundo"]["pasos"]["-1"] = {"xp": 5, "perfecto": True, "fecha": "2026-09-20"}
        self.assertEqual(ids(practica.candidatos(p, CURSOS, HOY)), [("hola-mundo", 1)])

    def test_registro_de_leccion_o_de_paso_que_no_es_un_objeto(self):
        for malo in ("x", ["x"], 7, None):
            with self.subTest(registro=malo):
                p = perfil()
                p["lecciones"]["hola-mundo"] = malo
                self.assertEqual(ids(practica.candidatos(p, CURSOS, HOY)), sorted(SANAS))
                q = perfil(("hola-mundo", [1, 2]))
                q["lecciones"]["hola-mundo"]["pasos"]["2"] = malo
                self.assertEqual(ids(practica.candidatos(q, CURSOS, HOY)), sorted(SANAS + [("hola-mundo", 1)]))
                r = perfil(("hola-mundo", [1]))
                r["lecciones"]["hola-mundo"]["pasos"] = malo
                self.assertEqual(ids(practica.candidatos(r, CURSOS, HOY)), sorted(SANAS))


class TestFechaDelPasoInvalida(unittest.TestCase):
    FECHAS_MALAS = ("no-es-fecha", "2026-13-45", "2026-02-30", "20260920", "2026-9-20", 20260920, 1.5, ["2026-09-20"], True)

    def test_una_fecha_de_paso_mal_formada_aisla_ese_paso(self):
        for mala in self.FECHAS_MALAS:
            with self.subTest(fecha=mala):
                p = perfil(("hola-mundo", [1]))
                p["lecciones"]["hola-mundo"]["pasos"]["1"]["fecha"] = mala
                self.assertEqual(ids(practica.candidatos(p, CURSOS, HOY)), sorted(SANAS))

    def test_la_fecha_maxima_no_desborda(self):
        p = perfil(("hola-mundo", [1]))
        p["lecciones"]["hola-mundo"]["pasos"]["1"]["fecha"] = "9999-12-31"       # +1 día no existe
        self.assertEqual(ids(practica.candidatos(p, CURSOS, HOY)), sorted(SANAS))

    def test_sin_fecha_sigue_tocando_como_en_el_progreso_viejo(self):
        # Semántica heredada: la clave ausente (o vacía) es «progreso viejo», no un dato dañado.
        for sin in (None, ""):
            with self.subTest(fecha=sin):
                p = perfil(("hola-mundo", [1]))
                if sin is None:
                    del p["lecciones"]["hola-mundo"]["pasos"]["1"]["fecha"]
                else:
                    p["lecciones"]["hola-mundo"]["pasos"]["1"]["fecha"] = sin
                self.assertIn(("hola-mundo", 1), ids(practica.candidatos(p, CURSOS, HOY)))

    def test_si_la_tarjeta_esta_programada_la_fecha_mala_del_paso_no_importa(self):
        p = perfil(("hola-mundo", [1]))
        p["lecciones"]["hola-mundo"]["pasos"]["1"]["fecha"] = "no-es-fecha"
        p["repaso"]["hola-mundo:1"] = {"caja": 2, "proximo": "2026-09-24", "aciertos": 1, "fallos": 0}
        self.assertIn(("hola-mundo", 1), ids(practica.candidatos(p, CURSOS, HOY)))


class TestTarjetaDeRepasoDanada(unittest.TestCase):
    def _con_tarjeta(self, tarjeta):
        p = perfil(("hola-mundo", [1]))
        p["repaso"]["hola-mundo:1"] = tarjeta
        return p

    def test_proximo_invalido_aisla_la_tarjeta_sin_inventar_un_vencimiento(self):
        for malo in ("nunca", "2026-13-01", "2026-9-1", "20260901", 5, 0, 1.5, ["2026-09-01"], True, False, {}, []):
            with self.subTest(proximo=malo):
                p = self._con_tarjeta({"caja": 2, "proximo": malo, "aciertos": 1, "fallos": 0})
                self.assertEqual(ids(practica.candidatos(p, CURSOS, HOY)), sorted(SANAS))

    def test_proximo_ausente_o_vacio_es_tarjeta_sin_programar_y_usa_la_fecha_del_paso(self):
        for sin in (None, ""):
            with self.subTest(proximo=sin):
                p = self._con_tarjeta({"caja": 1, "proximo": sin})
                self.assertIn(("hola-mundo", 1), ids(practica.candidatos(p, CURSOS, HOY)))

    def test_una_tarjeta_que_no_es_un_objeto_se_ignora(self):
        for mala in ("x", ["x"], 7, 0, None, "", []):
            with self.subTest(tarjeta=mala):
                p = self._con_tarjeta(mala)
                self.assertEqual(ids(practica.candidatos(p, CURSOS, HOY)), sorted(SANAS))

    def test_caja_defectuosa_aisla_la_tarjeta(self):
        for mala in ("2", 2.0, 1.5, True, False, -1, practica.MAX_CAJA + 1, 99, None, [2]):
            with self.subTest(caja=mala):
                p = self._con_tarjeta({"caja": mala, "proximo": "2026-09-01"})
                self.assertEqual(ids(practica.candidatos(p, CURSOS, HOY)), sorted(SANAS))

    def test_las_cajas_validas_de_0_a_max_siguen_funcionando(self):
        for caja in range(0, practica.MAX_CAJA + 1):
            with self.subTest(caja=caja):
                p = self._con_tarjeta({"caja": caja, "proximo": "2026-09-01"})
                tarjetas = {(c["leccion"], c["paso"]): c for c in practica.candidatos(p, CURSOS, HOY)}
                self.assertEqual(tarjetas[("hola-mundo", 1)]["caja"], caja)

    def test_tarjeta_sin_caja_sigue_siendo_caja_cero(self):
        p = self._con_tarjeta({"proximo": "2026-09-01"})
        tarjetas = {(c["leccion"], c["paso"]): c for c in practica.candidatos(p, CURSOS, HOY)}
        self.assertEqual(tarjetas[("hola-mundo", 1)]["caja"], 0)


class TestCorrupcionParcial(unittest.TestCase):
    def _perfil_mezclado(self):
        """Seis tarjetas sanas vencidas y cinco defectuosas, en lecciones distintas."""
        p = con_pasos(("hola-mundo", [1, 2, 3, 4]), ("texto-o-cuenta", [1, 2, 3, 4]),
                      ("tu-primera-variable", [1, 2, 3, 4]))
        p["repaso"]["hola-mundo:1"] = {"caja": 2, "proximo": "nunca"}                  # proximo roto
        p["repaso"]["hola-mundo:2"] = "x"                                              # no es objeto
        p["repaso"]["texto-o-cuenta:1"] = {"caja": "2", "proximo": "2026-09-01"}       # caja rota
        p["repaso"]["texto-o-cuenta:2"] = {"caja": 99, "proximo": "2026-09-01"}
        p["lecciones"]["tu-primera-variable"]["pasos"]["abc"] = {"fecha": "2026-09-20"}  # clave rota
        p["lecciones"]["tu-primera-variable"]["pasos"]["1"]["fecha"] = "2026-09-99"      # fecha rota
        return p

    SANAS_MEZCLA = [("hola-mundo", 3), ("hola-mundo", 4), ("texto-o-cuenta", 3), ("texto-o-cuenta", 4),
                    ("tu-primera-variable", 2), ("tu-primera-variable", 3), ("tu-primera-variable", 4)]

    def test_lo_sano_se_procesa_y_lo_roto_no_aparece(self):
        p = self._perfil_mezclado()
        self.assertEqual(ids(practica.candidatos(p, CURSOS, HOY)), sorted(self.SANAS_MEZCLA))
        self.assertEqual(practica.pendientes(p, CURSOS, HOY), len(self.SANAS_MEZCLA))

    def test_la_sesion_se_arma_solo_con_tarjetas_sanas(self):
        p = self._perfil_mezclado()
        elegidas = practica.elegir(p, CURSOS, HOY)
        self.assertEqual(len(elegidas), 6)
        self.assertTrue(set(elegidas) <= set(self.SANAS_MEZCLA))

    def test_leer_no_modifica_ni_repara_el_perfil(self):
        p = self._perfil_mezclado()
        antes = copy.deepcopy(p)
        practica.candidatos(p, CURSOS, HOY)
        practica.pendientes(p, CURSOS, HOY)
        practica.elegir(p, CURSOS, HOY)
        practica.diagnosticar(p, CURSOS, HOY)
        self.assertEqual(p, antes)                                        # nada se borra ni se «corrige» al leer

    def test_el_orden_y_los_datos_de_las_tarjetas_sanas_no_cambian(self):
        sano = con_pasos(("hola-mundo", [3, 4]), ("texto-o-cuenta", [3, 4]), ("tu-primera-variable", [2, 3, 4]))
        roto = self._perfil_mezclado()
        self.assertEqual(sorted(practica.candidatos(sano, CURSOS, HOY), key=lambda c: (c["leccion"], c["paso"])),
                         sorted(practica.candidatos(roto, CURSOS, HOY), key=lambda c: (c["leccion"], c["paso"])))

    def test_un_perfil_sano_no_tiene_diagnostico(self):
        self.assertEqual(practica.diagnosticar(con_pasos(("hola-mundo", [1, 2, 3, 4])), CURSOS, HOY), [])

    def test_el_diagnostico_nombra_cada_registro_danado(self):
        d = practica.diagnosticar(self._perfil_mezclado(), CURSOS, HOY)
        self.assertEqual(sorted((x["leccion"], str(x["paso"])) for x in d),
                         sorted([("hola-mundo", "1"), ("hola-mundo", "2"), ("texto-o-cuenta", "1"),
                                 ("texto-o-cuenta", "2"), ("tu-primera-variable", "abc"),
                                 ("tu-primera-variable", "1")]))
        self.assertTrue(all(x["motivo"] for x in d))

    def test_se_deja_constancia_en_el_log(self):
        with self.assertLogs("tortuscript.practica", level="WARNING") as cap:
            practica.candidatos(self._perfil_mezclado(), CURSOS, HOY)
        self.assertIn("6", cap.output[0])                                 # cuántos registros se ignoraron

    def test_un_perfil_sano_no_escribe_en_el_log(self):
        with self.assertNoLogs("tortuscript.practica", level="WARNING"):
            practica.candidatos(con_pasos(("hola-mundo", [1, 2])), CURSOS, HOY)

    def test_contenedores_que_no_son_diccionarios_equivalen_a_vacios(self):
        for roto in (None, [], "x", 7):
            with self.subTest(contenedor=roto):
                self.assertEqual(practica.candidatos({"lecciones": roto, "repaso": {}}, CURSOS, HOY), [])
                p = con_pasos(("hola-mundo", [1]))
                p["repaso"] = roto
                self.assertEqual(ids(practica.candidatos(p, CURSOS, HOY)), [("hola-mundo", 1)])


class TestRegistrarSobreTarjetaDanada(unittest.TestCase):
    """`registrar` se llama tras una respuesta real. Con una tarjeta no interpretable parte de cero (sin
    información que preservar) y deja la tarjeta sana; no toca las demás."""

    def test_tarjeta_que_no_es_objeto_se_reemplaza_por_una_nueva(self):
        for mala in ("x", ["x"], 7, None):
            with self.subTest(tarjeta=mala):
                p = {"repaso": {"l:1": mala, "otra:2": {"caja": 3, "proximo": "2026-10-01", "aciertos": 3, "fallos": 0}}}
                t = practica.registrar(p, "l", 1, True, HOY)
                self.assertEqual((t["caja"], t["aciertos"], t["fallos"]), (1, 1, 0))
                self.assertEqual(t["proximo"], str(HOY + timedelta(days=practica.INTERVALOS[0])))
                self.assertEqual(p["repaso"]["otra:2"]["caja"], 3)

    def test_campos_danados_de_una_tarjeta_se_reinician_y_los_sanos_se_conservan(self):
        p = {"repaso": {"l:1": {"caja": "x", "aciertos": "muchos", "fallos": 2, "proximo": 5}}}
        t = practica.registrar(p, "l", 1, False, HOY)
        self.assertEqual((t["caja"], t["aciertos"], t["fallos"]), (1, 0, 3))          # fallos=2 era válido
        self.assertEqual(t["proximo"], str(HOY + timedelta(days=1)))

    def test_caja_fuera_de_rango_no_salta_los_intervalos(self):
        for mala in (-1, practica.MAX_CAJA + 1, True):
            with self.subTest(caja=mala):
                p = {"repaso": {"l:1": {"caja": mala, "aciertos": 0, "fallos": 0}}}
                t = practica.registrar(p, "l", 1, True, HOY)
                self.assertEqual(t["caja"], 1)

    def test_repaso_que_no_es_diccionario_se_reemplaza_por_uno_vacio(self):
        p = {"repaso": ["x"]}
        practica.registrar(p, "l", 1, True, HOY)
        self.assertEqual(list(p["repaso"]), ["l:1"])

    def test_los_intervalos_no_cambiaron(self):
        self.assertEqual(practica.INTERVALOS, (1, 2, 4, 8, 16))
        p = {"repaso": {}}
        dias = [(practica.registrar(p, "l", 1, True, HOY)["proximo"]) for _ in range(6)]
        self.assertEqual(dias, [str(HOY + timedelta(days=d)) for d in (1, 2, 4, 8, 16, 16)])

    def test_registrar_practica_con_tarjeta_danada_da_el_xp_de_siempre(self):
        p = progreso._migrar({"version": 11})
        p["repaso"]["l:1"] = "x"
        self.assertEqual(progreso.registrar_practica(p, "l", 1, True, HOY), practica.XP_ACIERTO)
        self.assertEqual(p["xp_total"], practica.XP_ACIERTO)


class TestEvidenciaDelCatalogo(unittest.TestCase):
    """`catalogo_producto` también lee `repaso[...]['proximo']` (Progress.v1 → «repasar»)."""
    UNIDAD = "nivel0-programa"
    CLAVE = "alfabetizacion-digital:nivel0-programa"

    def _repasar(self, tarjeta):
        p = {"lecciones": {"nivel0-programa": {"pasos": {}, "completada": True}}, "repaso": {self.CLAVE: tarjeta}}
        return catalogo_producto._evidencia_lecciones(p, self.UNIDAD)["repasar"]

    def test_una_fecha_vencida_valida_pide_repasar(self):
        self.assertTrue(self._repasar({"proximo": "2020-01-01"}))
        self.assertFalse(self._repasar({"proximo": (date.today() + timedelta(days=3)).isoformat()}))

    def test_un_dato_danado_no_inventa_un_repaso(self):
        for malo in ("0000", "000", "abc", "2026-13-01", 5, ["2020-01-01"], True):
            with self.subTest(proximo=malo):
                self.assertFalse(self._repasar({"proximo": malo}))

    def test_una_tarjeta_que_no_es_objeto_no_rompe_la_evidencia(self):
        for malo in ("x", ["x"], 7, None):
            with self.subTest(tarjeta=malo):
                self.assertFalse(self._repasar(malo))


@unittest.skipUnless(HAY_FLASK, "Flask no instalado")
class TestEstadoGeneralConRegistrosDanados(unittest.TestCase):
    """Un defecto interno en el repaso no debe terminar en HTTP 500 (estado general, práctica y portada)."""
    _progreso_cuenta = test_camino.TestWebCamino._progreso_cuenta
    _guardar_progreso_cuenta = test_camino.TestWebCamino._guardar_progreso_cuenta

    def setUp(self):
        self._dir = Path(tempfile.mkdtemp())
        self._orig = (persistencia_local.DIRECTORIO, persistencia_local.PERFIL_ACTUAL)
        persistencia_local.DIRECTORIO = self._dir
        persistencia_local.PERFIL_ACTUAL = "default"
        from web.app import create_app
        self.app = create_app(token="t")
        self.app.config.update(TESTING=True, ACCOUNT_DB=self._dir / "cuentas.sqlite3", ACCOUNT_COOKIE_SECURE=False,
                               PROGRESS_DIR=self._dir / "progreso_perfiles")
        self.c = self.app.test_client()
        self.h = {"X-Tortu-Token": "t"}
        from fixtures_cuenta import preparar_sesion_educativa
        preparar_sesion_educativa(self.app, self.c, email="robustez@example.com", nombre="Lua", token="t",
                                  complete_onboarding=True)

    def tearDown(self):
        persistencia_local.DIRECTORIO, persistencia_local.PERFIL_ACTUAL = self._orig
        shutil.rmtree(self._dir)

    def _perfil_con(self, dañar):
        """Cinco tarjetas sanas vencidas (texto-o-cuenta 1,2; dos-lineas 1; hola-mundo 1,2) y el defecto de `dañar`."""
        p = self._progreso_cuenta()["data"]
        ayer = (date.today() - timedelta(days=5)).isoformat()
        for leccion_id, indices in (("texto-o-cuenta", [1, 2]), ("dos-lineas", [1]), ("hola-mundo", [1, 2])):
            p["lecciones"][leccion_id] = {"completada": True, "pasos": {
                str(i): {"xp": 5, "perfecto": True, "fecha": ayer} for i in indices}}
        dañar(p)
        self._guardar_progreso_cuenta(p)

    DEFECTOS = {
        "clave no numérica": lambda p: p["lecciones"]["hola-mundo"]["pasos"].update({"abc": {"fecha": "2026-01-01"}}),
        "fecha de paso inválida": lambda p: p["lecciones"]["hola-mundo"]["pasos"]["1"].update({"fecha": "no-es-fecha"}),
        "proximo inválido": lambda p: p["repaso"].update({"hola-mundo:1": {"caja": 2, "proximo": "nunca"}}),
        "tarjeta que no es objeto": lambda p: p["repaso"].update({"hola-mundo:1": "x"}),
        "caja no entera": lambda p: p["repaso"].update({"hola-mundo:1": {"caja": "2", "proximo": "2026-01-01"}}),
        "caja fuera de rango": lambda p: p["repaso"].update({"hola-mundo:1": {"caja": 99, "proximo": "2026-01-01"}}),
    }

    def test_estado_practica_y_portada_responden_sin_500(self):
        for nombre, dañar in self.DEFECTOS.items():
            with self.subTest(defecto=nombre):
                self._perfil_con(dañar)
                estado = self.c.get("/api/estado", headers=self.h)
                self.assertEqual(estado.status_code, 200, nombre)
                # 5 sanas (texto-o-cuenta 1 y 2, dos-lineas 1, hola-mundo 1 y 2); hola-mundo:1 deja de contar si es el dañado
                esperado = 5 if nombre == "clave no numérica" else 4
                self.assertEqual(estado.get_json()["practica_pendientes"], esperado, nombre)
                self.assertEqual(self.c.get("/practica").status_code, 200, nombre)
                self.assertEqual(self.c.get("/").status_code, 200, nombre)
                datos = self._progreso_cuenta()["data"]
                self.assertEqual(datos["lecciones"]["hola-mundo"]["pasos"].get("2", {}).get("xp"), 5)   # lo sano sigue ahí

    def test_el_perfil_danado_no_se_reescribe_al_consultarlo(self):
        self._perfil_con(self.DEFECTOS["tarjeta que no es objeto"])
        antes = self._progreso_cuenta()["data"]["repaso"]
        self.c.get("/api/estado", headers=self.h)
        self.c.get("/practica")
        self.assertEqual(self._progreso_cuenta()["data"]["repaso"], antes)


if __name__ == "__main__":
    unittest.main()
