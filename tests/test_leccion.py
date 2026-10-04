"""Motor de lecciones: pasos públicos, comprobación, XP y progreso por lección."""
import shutil
import tempfile
import unittest
from pathlib import Path

from tortuscript import persistencia_local, contenido, leccion, progreso
from tortuscript.worker import atender

ELEGIR = {"tipo": "elegir", "pregunta": "¿Cuál?", "opciones": ["a", "b", "c"], "correcta": 1}
PREDECIR = {"tipo": "predecir", "codigo": 'mostrar "x"', "opciones": ["x", '"x"'], "correcta": 0, "pista": "Mirá las comillas."}
COMPLETAR = {"tipo": "completar", "consigna": "c", "codigo": '___ "Hola"', "fichas": ["mostrar", "Hola", "sumar"],
             "respuesta": ["mostrar"], "salida": "Hola"}
COMPLETAR2 = {"tipo": "completar", "consigna": "c", "codigo": "a es ___\nb es ___\nmostrar a", "fichas": ["1", "2", "3"],
              "respuesta": ["1", "2"], "salida": "1"}
ORDENAR = {"tipo": "ordenar", "consigna": "o", "lineas": ['mostrar "Hola"', 'mostrar "Chau"', 'mostrar "Fin"']}
ORDEN_LIBRE = {"tipo": "ordenar", "consigna": "o", "lineas": ["a es 1", "b es 2", "mostrar a + b"]}
EXPLICACION = {"tipo": "explicacion", "texto": "t", "codigo": 'mostrar "Hola"'}
ESCRIBIR = {"tipo": "escribir", "consigna": "e", "solucion": 'mostrar "Hola"'}


def ejecutar_real(fuente, entradas, op="ejecutar"):
    r = atender({"op": op, "fuente": fuente, "entradas": entradas})
    if r["error"] or r["pregunta"] is not None:
        return None
    return {"salida": r["salida_programa"], "ordenes": r.get("ordenes", [])}


def ejecutar_dibujo(fuente, entradas):
    return ejecutar_real(fuente, entradas, "tortuga")


class TestPasoPublico(unittest.TestCase):
    def test_nunca_filtra_la_respuesta(self):
        for paso in (ELEGIR, PREDECIR, COMPLETAR, ORDENAR, EXPLICACION, ESCRIBIR):
            publico = leccion.paso_publico(paso, "leccion", 0, 1)
            with self.subTest(tipo=paso["tipo"]):
                for prohibido in ("correcta", "respuesta", "solucion", "salida", "pista"):
                    self.assertNotIn(prohibido, publico)

    def test_mezcla_reproducible_y_completa(self):
        a = leccion.paso_publico(ELEGIR, "x", 3)["opciones"]
        self.assertEqual(a, leccion.paso_publico(ELEGIR, "x", 3)["opciones"])
        self.assertEqual(sorted(a), ["a", "b", "c"])

    def test_ordenar_no_llega_ya_ordenado(self):
        for i in range(30):
            lineas = leccion.paso_publico(ORDENAR, f"l{i}", i)["lineas"]
            self.assertNotEqual(lineas, ORDENAR["lineas"])
            self.assertEqual(sorted(lineas), sorted(ORDENAR["lineas"]))

    def test_completar_cuenta_huecos(self):
        self.assertEqual(leccion.paso_publico(COMPLETAR2, "x", 0)["huecos"], 2)

    def test_escribir_lleva_el_numero_de_ejercicio(self):
        self.assertEqual(leccion.paso_publico(ESCRIBIR, "x", 0, 7)["ejercicio"], 7)


class TestComprobar(unittest.TestCase):
    def test_elegir_y_predecir(self):
        self.assertTrue(leccion.comprobar(ELEGIR, "b")["ok"])
        r = leccion.comprobar(ELEGIR, "a")
        self.assertFalse(r["ok"])
        self.assertIn("pista", r)
        self.assertTrue(r["pista"])                                   # pista genérica
        self.assertEqual(leccion.comprobar(PREDECIR, '"x"')["pista"], "Mirá las comillas.")   # la del autor
        self.assertFalse(leccion.comprobar(ELEGIR, None)["ok"])
        self.assertFalse(leccion.comprobar(ELEGIR, 1)["ok"])          # tiene que ser el texto

    def test_completar_marca_los_huecos_mal(self):
        self.assertTrue(leccion.comprobar(COMPLETAR2, ["1", "2"])["ok"])
        r = leccion.comprobar(COMPLETAR2, ["1", "3"])
        self.assertEqual((r["ok"], r["malos"]), (False, [1]))
        self.assertFalse(leccion.comprobar(COMPLETAR2, ["1"])["ok"])          # faltan huecos
        self.assertFalse(leccion.comprobar(COMPLETAR2, "1,2")["ok"])

    def test_completar_acepta_otra_solucion_con_la_misma_salida(self):
        # a=1,b=1 → muestra 1, igual que la respuesta oficial (a=1,b=2)
        self.assertFalse(leccion.comprobar(COMPLETAR2, ["1", "1"])["ok"])          # sin ejecutar: exacto
        self.assertTrue(leccion.comprobar(COMPLETAR2, ["1", "1"], ejecutar_real)["ok"])
        self.assertFalse(leccion.comprobar(COMPLETAR2, ["2", "1"], ejecutar_real)["ok"])   # muestra 2

    def test_ordenar(self):
        ok = leccion.comprobar(ORDENAR, ORDENAR["lineas"])
        self.assertTrue(ok["ok"])
        r = leccion.comprobar(ORDENAR, [ORDENAR["lineas"][1], ORDENAR["lineas"][0], ORDENAR["lineas"][2]])
        self.assertEqual((r["ok"], r["malos"]), (False, [0, 1]))
        self.assertFalse(leccion.comprobar(ORDENAR, ORDENAR["lineas"][:2])["ok"])

    def test_ordenar_acepta_otro_orden_que_muestra_lo_mismo(self):
        alterno = ["b es 2", "a es 1", "mostrar a + b"]
        self.assertFalse(leccion.comprobar(ORDEN_LIBRE, alterno)["ok"])
        self.assertTrue(leccion.comprobar(ORDEN_LIBRE, alterno, ejecutar_real)["ok"])
        # mostrar antes de definir → error → no vale
        self.assertFalse(leccion.comprobar(ORDEN_LIBRE, ["mostrar a + b", "a es 1", "b es 2"], ejecutar_real)["ok"])

    def test_dos_ordenamientos_equivalentes_del_curso_se_aceptan(self):
        # Las dos asignaciones independientes pueden permutarse sin cambiar la salida.
        curso = contenido.cargar_curso()
        alternativas = {
            "dos-variables": ["b es 2", "a es 1", "mostrar a", "mostrar b"],
            "tabla-del-2": [
                "contador es 1", "n es 2", "repetir 3 veces:",
                "    mostrar n * contador", "    contador es contador + 1",
            ],
        }
        for leccion_id, lineas in alternativas.items():
            _, leccion_data, _ = leccion.buscar_leccion(curso, leccion_id)
            paso = next(p for p in leccion_data["pasos"] if p["tipo"] == "ordenar")
            with self.subTest(leccion=leccion_id):
                resultado = leccion.comprobar(paso, lineas, ejecutar_real)
                self.assertTrue(resultado["ok"], resultado)

    def test_solo_los_pares_rechaza_incrementar_antes_de_comprobar(self):
        curso = contenido.cargar_curso()
        _, leccion_data, _ = leccion.buscar_leccion(curso, "solo-los-pares")
        paso = next(p for p in leccion_data["pasos"] if p["tipo"] == "ordenar")
        alternativa = [
            "n es 1", "repetir 5 veces:", "    n es n + 1",
            "    si n % 2 == 0:", "        mostrar n",
        ]
        resultado = leccion.comprobar(paso, alternativa, ejecutar_real)
        self.assertFalse(resultado["ok"], resultado)

    def test_explicacion_siempre_ok_y_escribir_no_se_comprueba_aca(self):
        self.assertTrue(leccion.comprobar(EXPLICACION, None)["ok"])
        with self.assertRaises(ValueError):
            leccion.comprobar(ESCRIBIR, "x")

    def test_respuesta_correcta(self):
        self.assertEqual(leccion.respuesta_correcta(ELEGIR), "b")
        self.assertEqual(leccion.respuesta_correcta(COMPLETAR2), ["1", "2"])
        self.assertEqual(leccion.respuesta_correcta(ORDENAR), ORDENAR["lineas"])
        self.assertEqual(leccion.respuesta_correcta(ESCRIBIR), 'mostrar "Hola"')
        self.assertIsNone(leccion.respuesta_correcta(EXPLICACION))


class TestXP(unittest.TestCase):
    def test_xp_por_intentos(self):
        self.assertEqual(leccion.xp_por_intentos(1, False), 5)
        self.assertEqual(leccion.xp_por_intentos(3, False), 2)
        self.assertEqual(leccion.xp_por_intentos(1, True), 0)

    def test_ver_respuesta_solo_tras_dos_errores(self):
        self.assertFalse(leccion.puede_ver_respuesta(1))
        self.assertTrue(leccion.puede_ver_respuesta(2))


class TestNavegacion(unittest.TestCase):
    def setUp(self):
        self.curso = contenido.cargar_curso()

    def test_buscar_y_siguiente(self):
        seccion, lec, pos = leccion.buscar_leccion(self.curso, "hola-mundo")
        self.assertEqual((seccion["nivel"], pos), (1, 0))
        self.assertEqual(leccion.leccion_siguiente(self.curso, "hola-mundo")["id"], "texto-o-cuenta")
        ultima = leccion.lista_lecciones(self.curso)[-1]["id"]
        self.assertIsNone(leccion.leccion_siguiente(self.curso, ultima))
        self.assertIsNone(leccion.buscar_leccion(self.curso, "no-existe"))

    def test_lista_lecciones_coincide_con_el_contenido(self):
        self.assertEqual(len(leccion.lista_lecciones(self.curso)), len(contenido.lecciones(self.curso)))

    def test_indices_de_ejercicio_por_leccion(self):
        idx = contenido.indices_ejercicio("hola-mundo")
        self.assertEqual(idx, {5: 0})               # el paso 6 (índice 5) es el escribir → ejercicio 0
        self.assertEqual(contenido.indices_ejercicio("texto-o-cuenta"), {5: 1})

    def test_esta_completada_compatibilidad_con_progreso_viejo(self):
        viejo = {"ejercicios": {"0": {"completado": True, "estrellas": 2}}}
        self.assertTrue(leccion.esta_completada(viejo, "hola-mundo", [0]))
        self.assertFalse(leccion.esta_completada(viejo, "texto-o-cuenta", [1]))
        self.assertFalse(leccion.esta_completada({}, "x", []))                    # sin escribir ni registro
        nuevo = {"lecciones": {"x": {"completada": True}}}
        self.assertTrue(leccion.esta_completada(nuevo, "x", []))


class TestProgresoLecciones(unittest.TestCase):
    def setUp(self):
        self._dir = Path(tempfile.mkdtemp())
        self._orig = persistencia_local.DIRECTORIO
        persistencia_local.DIRECTORIO = self._dir

    def tearDown(self):
        persistencia_local.DIRECTORIO = self._orig
        shutil.rmtree(self._dir)

    def test_completa_al_terminar_todos_los_pasos(self):
        p = persistencia_local.cargar_progreso()
        r = progreso.registrar_paso_leccion(p, "l", 0, 5, True, 2)
        self.assertEqual((r["completa"], r["xp_ganado"], p["xp_total"]), (False, 5, 5))
        r = progreso.registrar_paso_leccion(p, "l", 1, 2, False, 2)
        self.assertTrue(r["completa"] and r["recien_completa"])
        self.assertFalse(r["perfecta"])
        self.assertEqual(p["xp_total"], 7)

    def test_repetir_no_da_xp_doble_pero_si_mejora(self):
        p = persistencia_local.cargar_progreso()
        progreso.registrar_paso_leccion(p, "l", 0, 2, False, 1)
        r = progreso.registrar_paso_leccion(p, "l", 0, 2, False, 1)
        self.assertEqual((r["xp_ganado"], r["recien_completa"], p["xp_total"]), (0, False, 2))
        r = progreso.registrar_paso_leccion(p, "l", 0, 5, True, 1)
        self.assertEqual((r["xp_ganado"], r["perfecta"], p["xp_total"]), (3, True, 5))

    def test_se_guarda_y_sobrevive_al_recargar(self):
        p = persistencia_local.cargar_progreso()
        progreso.registrar_paso_leccion(p, "l", 0, 5, True, 1)
        self.assertTrue(persistencia_local.guardar_progreso(p))
        again = persistencia_local.cargar_progreso()
        self.assertTrue(again["lecciones"]["l"]["completada"])
        self.assertEqual(again["version"], progreso.VERSION_ESQUEMA)

    def test_progreso_viejo_sin_lecciones_se_migra(self):
        (self._dir / "progreso_default.json").write_text(
            '{"version": 2, "xp_total": 30, "ejercicios": {"0": {"completado": true, "estrellas": 3, "xp": 30}}}',
            encoding="utf-8")
        p = persistencia_local.cargar_progreso()
        self.assertEqual(p["lecciones"], {})
        self.assertEqual(p["xp_total"], 30)
        self.assertTrue(p["ejercicios"]["0"]["completado"])


def _leccion(id_, titulo, pasos=1):
    return {"id": id_, "titulo": titulo, "pasos": [{"tipo": "escribir"}] * pasos}


def _curso(id_, ids, requiere=None):
    curso = {"id": id_, "titulo": id_.title(), "secciones": [{"nivel": 1, "titulo": "S", "lecciones": [
        _leccion(i, f"{n + 1}. Lección {i}") for n, i in enumerate(ids)]}]}
    if requiere:
        curso["requiere"] = {"leccion": requiere}
    return curso


class TestVariosCursos(unittest.TestCase):
    def setUp(self):
        self.cursos = [_curso("a", ["a1", "a2"]), _curso("b", ["b1", "b2"], requiere="a2")]
        self.hechas = {"lecciones": {"a1": {"completada": True}}}

    def estados(self, progreso_):
        return {l["id"]: l["estado"] for l in leccion.lecciones_planas(leccion.estado_cursos(self.cursos, progreso_, {}))}

    def test_curso_cerrado_hasta_completar_lo_que_pide(self):
        est = leccion.estado_cursos(self.cursos, self.hechas, {})
        self.assertEqual([c["abierto"] for c in est], [True, False])
        self.assertEqual(est[1]["requiere"], "Lección a2")
        self.assertEqual(self.estados(self.hechas), {"a1": "hecha", "a2": "actual", "b1": "bloqueada", "b2": "bloqueada"})

    def test_al_completar_lo_requerido_se_abre_el_curso(self):
        p = {"lecciones": {"a1": {"completada": True}, "a2": {"completada": True}}}
        est = leccion.estado_cursos(self.cursos, p, {})
        self.assertTrue(est[1]["abierto"])
        self.assertIsNone(est[1]["requiere"])
        self.assertEqual(self.estados(p)["b1"], "actual")
        self.assertEqual(leccion.leccion_actual(est)["id"], "b1")

    def test_leccion_actual_y_planas(self):
        est = leccion.estado_cursos(self.cursos, {}, {})
        self.assertEqual(leccion.leccion_actual(est)["id"], "a1")
        self.assertEqual([l["curso"] for l in leccion.lecciones_planas(est)], ["a", "a", "b", "b"])
        todo = {"lecciones": {i: {"completada": True} for i in ("a1", "a2", "b1", "b2")}}
        self.assertIsNone(leccion.leccion_actual(leccion.estado_cursos(self.cursos, todo, {})))

    def test_buscar_y_siguiente_entre_cursos(self):
        curso, seccion, lec = leccion.buscar_en_cursos(self.cursos, "b1")
        self.assertEqual((curso["id"], lec["id"]), ("b", "b1"))
        self.assertIsNone(leccion.buscar_en_cursos(self.cursos, "zzz"))
        self.assertEqual(leccion.siguiente_global(self.cursos, "a1")["id"], "a2")
        self.assertEqual(leccion.siguiente_global(self.cursos, "a2")["id"], "b1")       # pasa al curso siguiente
        self.assertIsNone(leccion.siguiente_global(self.cursos, "b2"))

    def test_curso_que_pide_una_leccion_inexistente_queda_cerrado(self):
        cursos = [_curso("a", ["a1"]), _curso("b", ["b1"], requiere="fantasma")]
        est = leccion.estado_cursos(cursos, {}, {})
        self.assertFalse(est[1]["abierto"])
        self.assertEqual(est[1]["requiere"], "fantasma")

    def test_curso_puede_pedir_otro_curso_completo(self):
        web = _curso("web", ["w1", "w2"])
        python = _curso("python", ["p1"], requiere=None)
        python["requiere"] = {"curso": "web"}
        p = {"lecciones": {"w1": {"completada": True}, "w2": {"completada": True}}}
        est = leccion.estado_cursos([web, python], p, {})
        self.assertTrue(est[1]["abierto"])
        self.assertEqual(est[1]["hechas"], 0)

    def test_curso_puede_pedir_uno_de_varios_cursos(self):
        web = _curso("web", ["w1"])
        python = _curso("python", ["p1"])
        sql = _curso("sql", ["s1"])
        sql["requiere"] = {"uno_de_cursos": ["web", "python"]}
        p = {"lecciones": {"p1": {"completada": True}}}
        est = leccion.estado_cursos([web, python, sql], p, {})
        self.assertFalse(est[0]["completo"])
        self.assertTrue(est[2]["abierto"])
        self.assertIsNone(est[2]["requiere"])


class TestLeccionQuePideOtra(unittest.TestCase):
    def setUp(self):
        base = _curso("a", ["a1", "a2"])
        proyecto = _curso("p", ["p1", "p2", "p3"])
        proyecto["secciones"][0]["lecciones"][1]["requiere"] = "a2"          # p2 pide a2
        self.cursos = [base, proyecto]

    def estados(self, hechas):
        p = {"lecciones": {i: {"completada": True} for i in hechas}}
        est = leccion.estado_cursos(self.cursos, p, {})
        return {l["id"]: (l["estado"], l.get("pide")) for l in leccion.lecciones_planas(est)}

    def test_la_leccion_queda_bloqueada_con_el_aviso_y_las_siguientes_tambien(self):
        e = self.estados(["a1", "p1"])
        self.assertEqual(e["p2"], ("bloqueada", "Lección a2"))
        self.assertEqual(e["p3"], ("bloqueada", None))                      # no se saltea: espera a p2
        self.assertEqual(e["a2"][0], "actual")

    def test_al_cumplir_lo_que_pide_se_abre(self):
        e = self.estados(["a1", "a2", "p1"])
        self.assertEqual(e["p2"], ("actual", None))
        self.assertEqual(e["p3"][0], "bloqueada")

    def test_una_leccion_ya_hecha_no_pierde_el_estado_aunque_pida_algo(self):
        e = self.estados(["p1", "p2"])                                      # (progreso viejo o forzado)
        self.assertEqual((e["p2"][0], e["p3"][0]), ("hecha", "actual"))


DIBUJO_ORDENAR = {"tipo": "ordenar", "consigna": "o", "tortuga": True,
                  "lineas": ["avanzar 50", "girar_der 90", "avanzar 50"]}
DIBUJO_COMPLETAR = {"tipo": "completar", "consigna": "c", "tortuga": True, "codigo": "avanzar ___\ngirar_der 90\navanzar ___",
                    "fichas": ["50", "20", "100"], "respuesta": ["50", "50"]}


class TestComprobarConDibujos(unittest.TestCase):
    def test_ordenar_por_dibujo(self):
        self.assertTrue(leccion.comprobar(DIBUJO_ORDENAR, DIBUJO_ORDENAR["lineas"], ejecutar_dibujo)["ok"])
        self.assertFalse(leccion.comprobar(DIBUJO_ORDENAR, ["avanzar 50", "avanzar 50", "girar_der 90"], ejecutar_dibujo)["ok"])

    def test_ordenar_acepta_otro_orden_que_dibuja_lo_mismo(self):
        paso = {"tipo": "ordenar", "consigna": "o", "tortuga": True,
                "lineas": ["avanzar 30", "girar_der 90", "avanzar 30", "girar_izq 90"]}
        alterno = ["avanzar 30", "girar_der 90", "avanzar 30", "girar_izq 90"]
        self.assertTrue(leccion.comprobar(paso, alterno, ejecutar_dibujo)["ok"])

    def test_completar_por_dibujo(self):
        self.assertTrue(leccion.comprobar(DIBUJO_COMPLETAR, ["50", "50"], ejecutar_dibujo)["ok"])
        r = leccion.comprobar(DIBUJO_COMPLETAR, ["20", "50"], ejecutar_dibujo)
        self.assertEqual((r["ok"], r["malos"]), (False, [0]))

    def test_completar_por_dibujo_acepta_una_alternativa_equivalente(self):
        paso = {"tipo": "completar", "consigna": "c", "tortuga": True, "codigo": "avanzar ___\navanzar ___",
                "fichas": ["30", "70", "100"], "respuesta": ["30", "70"]}
        self.assertTrue(leccion.comprobar(paso, ["70", "30"], ejecutar_dibujo)["ok"])          # misma recta de 100
        self.assertFalse(leccion.comprobar(paso, ["30", "30"], ejecutar_dibujo)["ok"])


class TestQueEnsenaCadaLeccion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tortuscript import contenido
        cls.r = leccion.resumen_de_palabras(contenido.todos_los_cursos())

    def test_cada_leccion_muestra_algo(self):
        vacias = [k for k, v in self.r.items()
                  if not k.startswith("nivel0-") and not v["aprendiste"] and not v["practicaste"]]
        self.assertEqual(vacias, [])

    def test_una_palabra_se_aprende_una_sola_vez_en_todos_los_cursos(self):
        aprendidas = [p for v in self.r.values() for p in v["aprendiste"]]
        self.assertEqual(len(aprendidas), len(set(aprendidas)))
        self.assertEqual(self.r["hola-mundo"]["aprendiste"], ["mostrar"])
        self.assertEqual(self.r["tortuga-avanzar"]["aprendiste"], ["avanzar"])
        self.assertEqual(self.r["proyecto-adivinador"]["aprendiste"], [])           # todo ya se había visto

    def test_practicaste_no_repite_lo_aprendido_y_python_usa_sus_palabras(self):
        self.assertEqual(self.r["texto-o-cuenta"], {"aprendiste": [], "practicaste": ["mostrar"]})
        self.assertIn("repetir", self.r["laberinto-3"]["practicaste"])
        self.assertIn("print", self.r["py-print"]["practicaste"])
        for v in self.r.values():
            self.assertFalse(set(v["aprendiste"]) & set(v["practicaste"]))
            self.assertFalse({"verdadero", "falso", "="} & set(v["aprendiste"] + v["practicaste"]))


class TestSalteadasPorDiagnostico(unittest.TestCase):
    def setUp(self):
        self.cursos = contenido.todos_los_cursos()
        self.p = {"lecciones": {}, "ejercicios": {}, "salteadas": {}}

    def estados(self):
        return {l["id"]: l["estado"] for l in leccion.lecciones_planas(leccion.estado_cursos(self.cursos, self.p, {}))}

    def test_saltear_hasta_condicionales_abre_el_camino_y_los_cursos_sin_completarlos(self):
        ids = [lec["id"] for _, lec in contenido.lecciones(contenido.cargar_curso())]
        for i in ids[:ids.index("si-es-grande")]:
            self.p["salteadas"][i] = "2026-09-26"
        e = self.estados()
        self.assertEqual(e["si-es-grande"], "actual")
        self.assertEqual(e["dos-variables"], "salteada")
        self.assertEqual(e["tortuga-avanzar"], "actual")          # el curso de la tortuga pide «Dos variables»: salteada alcanza
        estado = leccion.estado_cursos(self.cursos, self.p, {})
        self.assertEqual(estado[0]["hechas"], 0)
        self.assertFalse(estado[0]["completo"])                    # sin certificado por saltear


class TestSaltearHasta(unittest.TestCase):
    def setUp(self):
        self._dir = Path(tempfile.mkdtemp())
        self._orig = persistencia_local.DIRECTORIO
        persistencia_local.DIRECTORIO = self._dir

    def tearDown(self):
        persistencia_local.DIRECTORIO = self._orig
        shutil.rmtree(self._dir)

    def test_solo_marca_las_anteriores_no_hechas(self):
        p = persistencia_local.cargar_progreso()
        p["lecciones"]["b"] = {"pasos": {}, "completada": True, "perfecta": False}
        progreso.saltear_hasta(p, ["a", "b", "c", "d"], "c")
        self.assertTrue(persistencia_local.guardar_progreso(p))
        self.assertEqual(sorted(persistencia_local.cargar_progreso()["salteadas"]), ["a"])
        with self.assertRaises(ValueError):
            progreso.saltear_hasta(p, ["a", "b"], "z")

    def test_un_progreso_v8_gana_el_campo_nuevo(self):
        viejo = {"version": 8, "xp_total": 10, "ejercicios": {}}
        self.assertEqual(progreso._migrar(viejo)["salteadas"], {})


if __name__ == "__main__":
    unittest.main()
