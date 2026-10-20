"""Modelo de dominio pedagógico V1 (docs/MODELO_DOMINIO_V1.md). Todo con datos en memoria, sin disco."""
import copy
import unittest

from tortuscript import contenido, dominio


def paso(tipo):
    return {"tipo": tipo}


CURSOS = [
    {"id": "c1", "secciones": [{"id": "s1", "lecciones": [
        {"id": "solo-elegir", "pasos": [paso("explicacion"), paso("elegir"), paso("elegir")]},
        {"id": "mixta", "pasos": [paso("explicacion"), paso("elegir"), paso("predecir"), paso("completar"),
                                  paso("ordenar"), paso("escribir")]},
        {"id": "dos", "pasos": [paso("elegir"), paso("predecir")]},
        {"id": "solo-explicacion", "pasos": [paso("explicacion")]},
        {"id": "sin-pasos", "pasos": []},
    ]}]},
    {"id": "c2", "secciones": [{"id": "s2", "lecciones": [{"id": "solo-elegir", "pasos": [paso("escribir")]}]}]},
]

MAPA = {
    "u-uno": {"tipo": "lecciones", "curso": "c1", "lecciones": ["solo-elegir"]},
    "u-dos": {"tipo": "lecciones", "curso": "c1", "lecciones": ["dos"]},
    "u-mixta": {"tipo": "lecciones", "curso": "c1", "lecciones": ["mixta"]},
    "u-proyecto": {"tipo": "proyecto", "proyecto": "algo"},
    "u-explicacion": {"tipo": "lecciones", "curso": "c1", "lecciones": ["solo-explicacion", "sin-pasos"]},
    "u-sin-curso": {"tipo": "lecciones", "curso": "no-existe", "lecciones": ["solo-elegir"]},
    "u-sin-leccion": {"tipo": "lecciones", "curso": "c1", "lecciones": ["no-existe"]},
    "u-otro-curso": {"tipo": "lecciones", "curso": "c2", "lecciones": ["solo-elegir"]},
}


def fuerte(tipo="elegir"):
    return {"xp": 5, "perfecto": True} if tipo != "escribir" else {"xp": 0, "perfecto": True, "estrellas": 3}


def progreso(leccion, registros, repaso=None):
    """registros = {indice_de_paso: registro}."""
    p = {"lecciones": {leccion: {"pasos": {str(i): r for i, r in registros.items()}}}}
    if repaso is not None:
        p["repaso"] = repaso
    return p


def estado(p, unidad="u-mixta"):
    return dominio.estado_concepto(p, CURSOS, unidad, MAPA)


# pasos de "mixta": 1 elegir, 2 predecir, 3 completar, 4 ordenar, 5 escribir
TODO_FUERTE = {1: fuerte(), 2: fuerte(), 3: fuerte(), 4: fuerte(), 5: fuerte("escribir")}
TARJETA_BUENA = {"mixta:1": {"caja": 3, "aciertos": 2}}


class TestNiveles(unittest.TestCase):
    def test_0_sin_evidencia_con_progreso_vacio(self):
        e = estado({})
        self.assertEqual((e["nivel"], e["estado"]), (0, "sin_evidencia"))

    def test_1_visto_con_solo_evidencia_debil_o_ayudada(self):
        for registro in ({"xp": 2}, {"xp": 0}, {"xp": 4}, {"xp": 1}):
            with self.subTest(registro=registro):
                e = estado(progreso("mixta", {1: registro}))
                self.assertEqual((e["nivel"], e["estado"], e["fuertes"]), (1, "visto", []))

    def test_2_reconocido_con_un_acierto_en_un_formato(self):
        e = estado(progreso("mixta", {1: fuerte()}))
        self.assertEqual((e["nivel"], e["estado"], e["fuertes"]), (2, "reconocido", ["reconocimiento"]))

    def test_dos_aciertos_en_el_mismo_formato_no_pasan_de_reconocido(self):
        e = estado(progreso("mixta", {3: fuerte(), 4: fuerte()}))
        self.assertEqual((e["nivel"], e["fuertes"]), (2, ["construccion"]))

    def test_3_aplicado_con_dos_formatos_distintos(self):
        e = estado(progreso("mixta", {1: fuerte(), 2: fuerte()}))
        self.assertEqual((e["nivel"], e["estado"]), (3, "aplicado"))
        self.assertEqual(e["fuertes"], ["prediccion", "reconocimiento"])

    def test_4_autonomo_con_todos_los_formatos_fuertes(self):
        e = estado(progreso("mixta", TODO_FUERTE))
        self.assertEqual((e["nivel"], e["estado"], e["retencion"]), (4, "autonomo", False))

    def test_justo_debajo_de_autonomo_falta_un_formato(self):
        for faltantes in ({1}, {2}, {5}, {3, 4}):
            with self.subTest(sin=faltantes):
                registros = {i: r for i, r in TODO_FUERTE.items() if i not in faltantes}
                self.assertEqual(estado(progreso("mixta", registros))["nivel"], 3)

    def test_construccion_se_cubre_con_completar_o_con_ordenar(self):
        for faltante in (3, 4):
            with self.subTest(sin=faltante):
                registros = {i: r for i, r in TODO_FUERTE.items() if i != faltante}
                self.assertEqual(estado(progreso("mixta", registros))["nivel"], 4)

    def test_5_consolidado_con_retencion(self):
        e = estado(progreso("mixta", TODO_FUERTE, TARJETA_BUENA))
        self.assertEqual((e["nivel"], e["estado"], e["retencion"]), (5, "consolidado", True))

    def test_la_retencion_sin_autonomia_no_sube_el_nivel(self):
        e = estado(progreso("mixta", {1: fuerte(), 2: fuerte()}, TARJETA_BUENA))
        self.assertEqual((e["nivel"], e["retencion"]), (3, True))

    def test_concepto_de_un_solo_formato_llega_a_autonomo_y_consolidado(self):
        p = progreso("solo-elegir", {1: fuerte()})
        self.assertEqual(estado(p, "u-uno")["nivel"], 4)
        p["repaso"] = {"solo-elegir:1": {"caja": 5, "aciertos": 9}}
        self.assertEqual(estado(p, "u-uno")["nivel"], 5)

    def test_concepto_de_dos_formatos_con_uno_fuerte_es_reconocido_y_con_ambos_autonomo(self):
        self.assertEqual(estado(progreso("dos", {0: fuerte()}), "u-dos")["nivel"], 2)
        self.assertEqual(estado(progreso("dos", {0: fuerte(), 1: fuerte()}), "u-dos")["nivel"], 4)

    def test_estados_son_los_de_la_especificacion(self):
        self.assertEqual(dominio.ESTADOS, ("sin_evidencia", "visto", "reconocido", "aplicado", "autonomo", "consolidado"))
        self.assertEqual(dominio.CATEGORIAS, ("reconocimiento", "prediccion", "construccion", "produccion"))


class TestFuerza(unittest.TestCase):
    def fuerzas(self, tipo_paso, registros):
        indice = {"elegir": 1, "predecir": 2, "completar": 3, "ordenar": 4, "escribir": 5}[tipo_paso]
        cat = {"elegir": "reconocimiento", "predecir": "prediccion", "completar": "construccion",
               "ordenar": "construccion", "escribir": "produccion"}[tipo_paso]
        return estado(progreso("mixta", {indice: registros}))["evidencias"][cat]

    def test_xp_en_los_bordes(self):
        for xp, esperado in ((5, "fuerte"), (6, "fuerte"), (30, "fuerte"), (4, "debil"), (2, "debil"), (1, "debil"),
                             (0, "ayudado"), (-1, "ayudado"), (-50, "ayudado")):
            with self.subTest(xp=xp):
                cuentas = self.fuerzas("elegir", {"xp": xp})
                self.assertEqual(cuentas[esperado], 1)
                self.assertEqual(sum(cuentas.values()), 1)

    def test_todos_los_formatos_de_xp_usan_la_misma_escala(self):
        for tipo in ("elegir", "predecir", "completar", "ordenar"):
            with self.subTest(tipo=tipo):
                self.assertEqual(self.fuerzas(tipo, {"xp": 5})["fuerte"], 1)
                self.assertEqual(self.fuerzas(tipo, {"xp": 4})["debil"], 1)
                self.assertEqual(self.fuerzas(tipo, {"xp": 0})["ayudado"], 1)

    def test_escribir_con_estrellas(self):
        for estrellas, esperado in ((3, "fuerte"), (4, "fuerte"), (2, "debil"), (1, "debil"), (0, "ayudado"), (-1, "ayudado")):
            with self.subTest(estrellas=estrellas):
                cuentas = self.fuerzas("escribir", {"estrellas": estrellas, "perfecto": True})
                self.assertEqual(cuentas[esperado], 1)

    def test_escribir_sin_estrellas_usa_perfecto(self):
        self.assertEqual(self.fuerzas("escribir", {"perfecto": True, "xp": 0})["fuerte"], 1)
        self.assertEqual(self.fuerzas("escribir", {"perfecto": False, "xp": 0})["debil"], 1)
        self.assertEqual(self.fuerzas("escribir", {"xp": 0})["debil"], 1)

    def test_escribir_ignora_el_xp_y_los_otros_tipos_ignoran_estrellas_y_perfecto(self):
        self.assertEqual(self.fuerzas("escribir", {"xp": 99, "perfecto": False})["debil"], 1)
        self.assertEqual(self.fuerzas("elegir", {"xp": 0, "estrellas": 3, "perfecto": True})["ayudado"], 1)

    def test_explicacion_no_es_evidencia_aunque_tenga_registro(self):
        e = estado(progreso("mixta", {0: fuerte()}))
        self.assertEqual((e["nivel"], e["fuertes"]), (0, []))

    def test_pasos_sin_registro_no_cuentan_pero_el_formato_esta_disponible(self):
        e = estado(progreso("mixta", {1: fuerte()}))
        self.assertEqual(e["disponibles"], ["construccion", "prediccion", "produccion", "reconocimiento"])
        self.assertEqual(e["evidencias"]["prediccion"], {"fuerte": 0, "debil": 0, "ayudado": 0})
        self.assertEqual(e["evidencias"]["construccion"], {"fuerte": 0, "debil": 0, "ayudado": 0})

    def test_las_cuentas_se_acumulan_por_categoria(self):
        e = estado(progreso("mixta", {3: {"xp": 5}, 4: {"xp": 2}}))
        self.assertEqual(e["evidencias"]["construccion"], {"fuerte": 1, "debil": 1, "ayudado": 0})
        e = estado(progreso("solo-elegir", {1: {"xp": 5}, 2: {"xp": 0}}), "u-uno")
        self.assertEqual(e["evidencias"]["reconocimiento"], {"fuerte": 1, "debil": 0, "ayudado": 1})


class TestPropiedades(unittest.TestCase):
    def test_un_solo_acierto_no_pasa_de_reconocido_si_hay_dos_o_mas_formatos(self):
        for indice in (1, 2, 3, 4, 5):
            with self.subTest(paso=indice):
                tipo = "escribir" if indice == 5 else "elegir"
                self.assertEqual(estado(progreso("mixta", {indice: fuerte(tipo)}))["nivel"], 2)

    def test_agregar_evidencia_nunca_baja_el_nivel(self):
        registros, anterior = {}, 0
        secuencia = [(1, {"xp": 0}), (1, {"xp": 2}), (1, {"xp": 5}), (2, {"xp": 0}), (2, {"xp": 5}), (3, {"xp": 1}),
                     (3, {"xp": 5}), (4, {"xp": 5}), (5, {"estrellas": 0}), (5, {"estrellas": 3})]
        for indice, registro in secuencia:
            registros[indice] = registro
            nivel = estado(progreso("mixta", registros, TARJETA_BUENA))["nivel"]
            self.assertGreaterEqual(nivel, anterior, (indice, registro))
            anterior = nivel
        self.assertEqual(anterior, 5)

    def test_la_ayuda_y_los_errores_no_castigan(self):
        base = progreso("mixta", {1: fuerte(), 2: fuerte()})
        con_ayuda = progreso("mixta", {1: fuerte(), 2: fuerte(), 3: {"xp": 0}, 4: {"xp": 1}, 5: {"estrellas": 0}})
        self.assertGreaterEqual(estado(con_ayuda)["nivel"], estado(base)["nivel"])

    def test_concepto_sin_pasos_evidenciables_queda_en_sin_evidencia(self):
        p = {"lecciones": {"solo-explicacion": {"pasos": {"0": fuerte()}}}, "repaso": {"solo-explicacion:0": {"caja": 5, "aciertos": 9}}}
        e = estado(p, "u-explicacion")
        self.assertEqual((e["nivel"], e["disponibles"], e["fuertes"], e["evidencias"]), (0, [], [], {}))

    def test_no_muta_el_progreso_ni_los_datos_de_entrada(self):
        p = progreso("mixta", TODO_FUERTE, TARJETA_BUENA)
        antes = (copy.deepcopy(p), copy.deepcopy(CURSOS), copy.deepcopy(MAPA))
        estado(p)
        dominio.dominio(p, CURSOS, MAPA)
        self.assertEqual((p, CURSOS, MAPA), antes)

    def test_es_determinista(self):
        p = progreso("mixta", TODO_FUERTE, TARJETA_BUENA)
        self.assertEqual(estado(p), estado(copy.deepcopy(p)))

    def test_no_agrega_claves_al_progreso(self):
        p = {}
        estado(p)
        self.assertEqual(p, {})


class TestRetencion(unittest.TestCase):
    def retiene(self, repaso):
        return estado(progreso("mixta", {}, repaso))["retencion"]

    def test_bordes_de_caja_y_aciertos(self):
        for caja, aciertos, esperado in ((3, 2, True), (4, 2, True), (3, 3, True), (2, 2, False), (3, 1, False),
                                         (2, 1, False), (5, 0, False), (0, 9, False)):
            with self.subTest(caja=caja, aciertos=aciertos):
                self.assertEqual(self.retiene({"mixta:1": {"caja": caja, "aciertos": aciertos}}), esperado)

    def test_la_clave_debe_ser_de_una_leccion_del_concepto(self):
        self.assertFalse(self.retiene({"otra:1": {"caja": 5, "aciertos": 5}}))
        self.assertFalse(self.retiene({"mixta2:1": {"caja": 5, "aciertos": 5}}))
        self.assertFalse(self.retiene({"mixt:1": {"caja": 5, "aciertos": 5}}))
        self.assertFalse(self.retiene({"mixta": {"caja": 5, "aciertos": 5}}))
        self.assertFalse(self.retiene({"mixta:x": {"caja": 5, "aciertos": 5}}))
        self.assertTrue(self.retiene({"mixta:5": {"caja": 5, "aciertos": 5}}))

    def test_basta_una_tarjeta_buena_entre_varias(self):
        self.assertTrue(self.retiene({"mixta:1": {"caja": 1, "aciertos": 0}, "mixta:2": {"caja": 3, "aciertos": 2}}))

    def test_la_retencion_de_una_leccion_no_cuenta_para_otro_concepto(self):
        p = progreso("solo-elegir", {1: fuerte()}, {"mixta:1": {"caja": 5, "aciertos": 5}})
        self.assertEqual(estado(p, "u-uno")["nivel"], 4)

    def test_tarjetas_danadas_se_ignoran(self):
        malas = ["x", None, 3, [], {"caja": True, "aciertos": 2}, {"caja": 3, "aciertos": True}, {"caja": "3", "aciertos": 2},
                 {"caja": 3.0, "aciertos": 2}, {"caja": 3}, {"aciertos": 2}, {}]
        for mala in malas:
            with self.subTest(tarjeta=mala):
                self.assertFalse(self.retiene({"mixta:1": mala}))

    def test_repaso_que_no_es_dict_se_trata_como_vacio(self):
        for repaso in ("x", ["mixta:1"], 5, None, True):
            with self.subTest(repaso=repaso):
                self.assertFalse(self.retiene(repaso))

    def test_claves_que_no_son_texto_no_rompen(self):
        self.assertFalse(self.retiene({1: {"caja": 5, "aciertos": 5}, None: {"caja": 5, "aciertos": 5}}))

    def test_el_borde_de_longitud_del_indice(self):
        self.assertTrue(self.retiene({"mixta:" + "1" * 10: {"caja": 5, "aciertos": 5}}))
        self.assertFalse(self.retiene({"mixta:" + "1" * 11: {"caja": 5, "aciertos": 5}}))

    def test_indice_enorme_no_cuenta(self):
        self.assertFalse(self.retiene({"mixta:" + "9" * 5000: {"caja": 5, "aciertos": 5}}))


class TestRobustez(unittest.TestCase):
    def test_progreso_que_no_es_dict_no_rompe(self):
        for p in (None, "x", [], 7, True):
            with self.subTest(progreso=p):
                self.assertEqual(estado(p)["nivel"], 0)
                self.assertTrue(dominio.dominio(p, CURSOS, MAPA))

    def test_ramas_que_no_son_dict_se_tratan_como_vacias(self):
        for lecciones in ("x", [], None, 3):
            with self.subTest(lecciones=lecciones):
                self.assertEqual(estado({"lecciones": lecciones})["nivel"], 0)
        for registro in ("x", [], None, 3, {"pasos": "x"}, {"pasos": []}, {"pasos": None}):
            with self.subTest(registro_leccion=registro):
                self.assertEqual(estado({"lecciones": {"mixta": registro}})["nivel"], 0)

    def test_registros_de_paso_danados_se_ignoran(self):
        malos = ["x", None, 3, [], True, {"xp": True}, {"xp": "5"}, {"xp": None}, {"xp": 5.0}, {"xp": [5]}, {"perfecto": True}, {}]
        for malo in malos:
            with self.subTest(registro=malo):
                e = estado(progreso("mixta", {1: malo}))
                self.assertEqual((e["nivel"], e["fuertes"]), (0, []))
                self.assertEqual(e["evidencias"]["reconocimiento"], {"fuerte": 0, "debil": 0, "ayudado": 0})

    def test_estrellas_danadas_se_ignoran(self):
        for malo in (True, "3", None, 3.0, [3]):
            with self.subTest(estrellas=malo):
                self.assertEqual(estado(progreso("mixta", {5: {"estrellas": malo, "perfecto": True}}))["nivel"], 0)

    def test_un_danado_no_afecta_a_los_hermanos_sanos(self):
        e = estado(progreso("mixta", {1: "x", 2: fuerte(), 3: None}))
        self.assertEqual((e["nivel"], e["fuertes"]), (2, ["prediccion"]))

    def test_claves_de_paso_que_no_son_indices_se_ignoran(self):
        pasos = {"abc": fuerte(), "-1": fuerte(), "": fuerte(), "01": fuerte(), "1.0": fuerte(), " 1": fuerte(),
                 "99": fuerte(), "9" * 5000: fuerte(), "6": fuerte()}
        p = {"lecciones": {"mixta": {"pasos": pasos}}}
        self.assertEqual(estado(p)["nivel"], 0)

    def test_la_clave_canonica_si_cuenta(self):
        p = {"lecciones": {"mixta": {"pasos": {"1": fuerte(), "abc": "x"}}}}
        self.assertEqual(estado(p)["nivel"], 2)

    def test_lecciones_y_cursos_inexistentes_aportan_cero_evidencia(self):
        p = {"lecciones": {"solo-elegir": {"pasos": {"1": fuerte(), "2": fuerte()}}, "no-existe": {"pasos": {"0": fuerte()}}}}
        self.assertEqual(estado(p, "u-sin-curso")["nivel"], 0)
        self.assertEqual(estado(p, "u-sin-leccion")["nivel"], 0)
        self.assertEqual(estado(p, "u-sin-curso")["disponibles"], [])

    def test_la_leccion_se_busca_en_el_curso_de_la_unidad(self):
        p = {"lecciones": {"solo-elegir": {"pasos": {"0": fuerte("escribir")}}}}
        e = estado(p, "u-otro-curso")
        self.assertEqual((e["disponibles"], e["fuertes"], e["nivel"]), (["produccion"], ["produccion"], 4))
        self.assertEqual(estado(p, "u-uno")["nivel"], 0)

    def test_cursos_danados_no_rompen(self):
        for cursos in (None, "x", [None, "x", 3, {}, {"id": "c1", "secciones": None}, {"id": "c1", "secciones": ["x", {"lecciones": "x"}]},
                                  {"id": "c1", "secciones": [{"lecciones": [None, {"id": "solo-elegir", "pasos": "x"}]}]}]):
            with self.subTest(cursos=cursos):
                self.assertEqual(dominio.estado_concepto({}, cursos, "u-uno", MAPA)["nivel"], 0)

    def test_pasos_danados_dentro_del_curso_se_saltan(self):
        cursos = [{"id": "c1", "secciones": [{"lecciones": [{"id": "x", "pasos": [None, "x", {"tipo": 3}, {}, paso("elegir")]}]}]}]
        mapa = {"u": {"tipo": "lecciones", "curso": "c1", "lecciones": ["x"]}}
        e = dominio.estado_concepto(progreso("x", {4: fuerte()}), cursos, "u", mapa)
        self.assertEqual((e["disponibles"], e["nivel"]), (["reconocimiento"], 4))

    def test_lista_de_lecciones_con_elementos_raros(self):
        mapa = {"u": {"tipo": "lecciones", "curso": "c1", "lecciones": [None, 3, "solo-elegir"]}}
        self.assertEqual(dominio.estado_concepto(progreso("solo-elegir", {1: fuerte()}), CURSOS, "u", mapa)["nivel"], 4)
        for lecciones in (None, "solo-elegir", 3):
            with self.subTest(lecciones=lecciones):
                mapa = {"u": {"tipo": "lecciones", "curso": "c1", "lecciones": lecciones}}
                self.assertEqual(dominio.estado_concepto({}, CURSOS, "u", mapa)["nivel"], 0)

    def test_unidad_inexistente_o_de_otro_tipo_lanza_keyerror(self):
        for unidad in ("no-existe", "u-proyecto", ""):
            with self.subTest(unidad=unidad):
                with self.assertRaises(KeyError):
                    estado({}, unidad)

    def test_unidad_con_tipo_distinto_de_lecciones_lanza_keyerror(self):
        for tipo in ("leccion", "Lecciones", None, 3):
            mapa = {"u": {"tipo": tipo, "curso": "c1", "lecciones": ["solo-elegir"]}}
            with self.subTest(tipo=tipo):
                with self.assertRaises(KeyError):
                    dominio.estado_concepto({}, CURSOS, "u", mapa)

    def test_unidad_que_no_es_dict_lanza_keyerror(self):
        with self.assertRaises(KeyError):
            dominio.estado_concepto({}, CURSOS, "u", {"u": "x"})


class TestForma(unittest.TestCase):
    def test_forma_exacta_del_estado(self):
        e = estado(progreso("mixta", {1: fuerte(), 3: {"xp": 2}}, TARJETA_BUENA))
        self.assertEqual(e, {
            "unidad": "u-mixta", "nivel": 2, "estado": "reconocido",
            "disponibles": ["construccion", "prediccion", "produccion", "reconocimiento"],
            "fuertes": ["reconocimiento"],
            "evidencias": {
                "construccion": {"fuerte": 0, "debil": 1, "ayudado": 0},
                "prediccion": {"fuerte": 0, "debil": 0, "ayudado": 0},
                "produccion": {"fuerte": 0, "debil": 0, "ayudado": 0},
                "reconocimiento": {"fuerte": 1, "debil": 0, "ayudado": 0}},
            "retencion": True})

    def test_evidencias_solo_para_categorias_disponibles(self):
        self.assertEqual(list(estado({}, "u-uno")["evidencias"]), ["reconocimiento"])
        self.assertEqual(estado({}, "u-explicacion")["evidencias"], {})

    def test_las_listas_salen_ordenadas(self):
        e = estado(progreso("mixta", TODO_FUERTE))
        self.assertEqual(e["disponibles"], sorted(e["disponibles"]))
        self.assertEqual(e["fuertes"], sorted(e["fuertes"]))
        self.assertEqual(list(e["evidencias"]), sorted(e["evidencias"]))

    def test_dominio_devuelve_solo_lecciones_en_el_orden_del_mapa(self):
        d = dominio.dominio({}, CURSOS, MAPA)
        self.assertEqual(list(d), [u for u, v in MAPA.items() if v["tipo"] == "lecciones"])
        self.assertNotIn("u-proyecto", d)
        self.assertEqual(d["u-mixta"], estado({}))

    def test_dominio_refleja_el_progreso_de_cada_concepto(self):
        d = dominio.dominio(progreso("dos", {0: fuerte(), 1: fuerte()}), CURSOS, MAPA)
        self.assertEqual((d["u-dos"]["nivel"], d["u-uno"]["nivel"], d["u-mixta"]["nivel"]), (4, 0, 0))

    def test_dominio_de_un_mapa_vacio(self):
        self.assertEqual(dominio.dominio({}, CURSOS, {}), {})


class TestDatosReales(unittest.TestCase):
    def test_cargar_mapa_devuelve_las_unidades(self):
        mapa = dominio.cargar_mapa()
        self.assertEqual(len(mapa), 37)
        self.assertNotIn("unidades", mapa)
        self.assertEqual(mapa["nivel0-programa"]["curso"], "alfabetizacion-digital")

    def test_toda_leccion_del_mapa_existe_en_su_curso(self):
        cursos = contenido.todos_los_cursos()
        por_curso = {c["id"]: {l["id"] for s in c["secciones"] for l in s["lecciones"]} for c in cursos}
        for uid, unidad in dominio.cargar_mapa().items():
            if unidad["tipo"] != "lecciones":
                continue
            with self.subTest(unidad=uid):
                self.assertIn(unidad["curso"], por_curso)
                for leccion in unidad["lecciones"]:
                    self.assertIn(leccion, por_curso[unidad["curso"]])

    def test_con_progreso_vacio_todo_es_sin_evidencia(self):
        d = dominio.dominio({}, contenido.todos_los_cursos())
        self.assertTrue(d)
        self.assertEqual({e["estado"] for e in d.values()}, {"sin_evidencia"})

    def test_toda_unidad_real_tiene_formatos_evidenciables(self):
        for uid, e in dominio.dominio({}, contenido.todos_los_cursos()).items():
            with self.subTest(unidad=uid):
                self.assertTrue(e["disponibles"])

    def test_un_curso_real_completo_llega_a_autonomo(self):
        cursos = contenido.todos_los_cursos()
        unidad = dominio.cargar_mapa()["nivel0-programa"]
        leccion = next(l for c in cursos if c["id"] == unidad["curso"] for s in c["secciones"] for l in s["lecciones"]
                       if l["id"] == unidad["lecciones"][0])
        registros = {i: fuerte(p["tipo"]) for i, p in enumerate(leccion["pasos"]) if p["tipo"] != "explicacion"}
        e = dominio.estado_concepto(progreso(leccion["id"], registros), cursos, "nivel0-programa")
        self.assertEqual(e["estado"], "autonomo")


if __name__ == "__main__":
    unittest.main()
