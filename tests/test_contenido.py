"""El contenido de los cursos se valida solo: nunca un ejercicio roto llega a pantalla."""
import unittest

from tortuscript import contenido
from tortuscript.validacion import AVISO, ERROR, validar_curso


def curso_con(*pasos):
    return {"id": "c", "titulo": "C", "secciones": [{"id": "s", "nivel": 1, "titulo": "S", "lecciones": [
        {"id": "l", "titulo": "1. L", "pasos": list(pasos)}]}]}


def errores(*pasos):
    return [h.mensaje for h in validar_curso(curso_con(*pasos)) if h.nivel == ERROR]


EXPL = {"tipo": "explicacion", "texto": "Mirá.", "codigo": 'mostrar "x"'}
EXPL_T = {"tipo": "explicacion", "texto": "Mirá.", "codigo": "avanzar 10\ngirar_der 90\ngirar_izq 90\nsubir_lapiz\nbajar_lapiz", "lienzo": True}


class TestCursosReales(unittest.TestCase):
    def test_todos_los_cursos_validan_sin_errores(self):
        cursos = sorted(p.stem for p in contenido.CARPETA.glob("*.json"))
        self.assertTrue(cursos)
        for curso_id in cursos:
            with self.subTest(curso=curso_id):
                malos = [str(h) for h in validar_curso(contenido.cargar_curso(curso_id)) if h.nivel == ERROR]
                self.assertEqual(malos, [])

    def test_ids_de_leccion_unicos_entre_cursos(self):
        vistos = {}
        for p in contenido.CARPETA.glob("*.json"):
            for _, lec in contenido.lecciones(contenido.cargar_curso(p.stem)):
                self.assertNotIn(lec["id"], vistos, f"{lec['id']} está en {p.stem} y en {vistos.get(lec['id'])}")
                vistos[lec["id"]] = p.stem

    def test_nivel_0_cubre_el_diccionario_digital_basico(self):
        curso = contenido.cargar_curso("alfabetizacion-digital")
        self.assertEqual(curso["secciones"][0]["id"], "mundo-digital")
        self.assertEqual(curso["secciones"][1]["id"], "datos-y-servicios")
        ids = [l["id"] for _, l in contenido.lecciones(curso)]
        esperadas = {
            "nivel0-programa", "nivel0-lenguaje", "nivel0-codigo", "nivel0-navegador",
            "nivel0-internet", "nivel0-servidor", "nivel0-frontend", "nivel0-backend",
            "nivel0-datos", "nivel0-base-datos", "nivel0-api", "nivel0-seguridad",
            "nivel0-integracion", "nivel0-json", "nivel0-git", "nivel0-github",
        }
        self.assertEqual(set(ids), esperadas)
        self.assertEqual(len(ids), 16)
        for _, lec in contenido.lecciones(curso):
            self.assertGreaterEqual(len(lec["pasos"]), 3)
            self.assertEqual(lec["pasos"][0]["tipo"], "explicacion")
            self.assertTrue(all(p.get("pista") for p in lec["pasos"] if p["tipo"] in ("elegir", "predecir", "ordenar", "completar")))

    def test_nivel_0_no_repite_preguntas_dentro_de_una_leccion(self):
        curso = contenido.cargar_curso("alfabetizacion-digital")
        for _, lec in contenido.lecciones(curso):
            preguntas = [p["pregunta"] for p in lec["pasos"] if p["tipo"] == "elegir"]
            self.assertEqual(len(preguntas), len(set(preguntas)), f"pregunta repetida en {lec['id']}")


    def test_el_curso_principal_conserva_sus_30_ejercicios_en_orden(self):
        # El índice de cada 'escribir' es la clave del progreso guardado: no puede cambiar de lugar.
        ej = contenido.ejercicios()
        self.assertEqual(len(ej), 30)
        self.assertEqual([e["nivel"] for e in ej], [1] * 3 + [2] * 3 + [3] * 3 + [4] * 3 + [5] * 3 + [6] * 3 + [7] * 3 + [8] * 9)
        self.assertEqual(ej[0]["solucion"], 'mostrar "Hola mundo"')
        self.assertEqual(ej[3]["solucion"], "edad es 12\nmostrar edad")
        self.assertEqual(ej[29]["leccion_id"], "desafio-final")

    def test_cada_leccion_del_principal_tiene_practica_y_termina_escribiendo(self):
        for _, lec in contenido.lecciones(contenido.cargar_curso()):
            with self.subTest(leccion=lec["id"]):
                tipos = [p["tipo"] for p in lec["pasos"]]
                self.assertGreaterEqual(len(tipos), 4)
                self.assertEqual(tipos[-1], "escribir")
                self.assertEqual(tipos[0], "explicacion")
                self.assertLessEqual(tipos.count("explicacion"), 2)

    def test_el_curso_usa_los_6_tipos_de_paso(self):
        usados = {p["tipo"] for _, _, _, p in contenido.pasos(contenido.cargar_curso())}
        self.assertEqual(usados, set(contenido.TIPOS))


class TestVariosCursos(unittest.TestCase):
    def test_lo_que_pide_cada_curso_existe_y_esta_en_otro_curso(self):
        cursos = contenido.todos_los_cursos()
        for curso in cursos:
            requiere = (curso.get("requiere") or {}).get("leccion")
            if not requiere:
                continue
            with self.subTest(curso=curso["id"]):
                donde = [c["id"] for c in cursos if any(l["id"] == requiere for _, l in contenido.lecciones(c))]
                self.assertTrue(donde, f"{requiere} no existe")
                self.assertNotIn(curso["id"], donde, "un curso no puede pedir una lección propia")
                self.assertLess(contenido.ids_cursos().index(donde[0]), contenido.ids_cursos().index(curso["id"]))

    def test_todo_curso_tiene_titulo_icono_y_descripcion(self):
        for curso in contenido.todos_los_cursos():
            with self.subTest(curso=curso["id"]):
                self.assertTrue(curso["titulo"] and curso.get("icono") and curso.get("descripcion"))

    def test_el_orden_de_cursos_incluye_todos_los_archivos(self):
        archivos = {p.stem for p in contenido.CARPETA.glob("*.json")}
        self.assertEqual(set(contenido.ids_cursos()), archivos)
        self.assertEqual(contenido.ids_cursos()[0], "alfabetizacion-digital")

    def test_curso_de_tortuga_todos_los_pasos_de_dibujo_estan_marcados(self):
        curso = contenido.cargar_curso("tortuga")
        for _, lec, i, paso in contenido.pasos(curso):
            with self.subTest(leccion=lec["id"], paso=i):
                if paso["tipo"] in ("escribir", "completar", "ordenar"):
                    self.assertTrue(paso.get("tortuga"), "sin 'tortuga': se compararía por texto")
                if paso["tipo"] == "predecir":
                    self.assertEqual(paso.get("cuenta"), "trazos")
                if paso["tipo"] == "explicacion":
                    self.assertTrue(paso.get("lienzo") or paso["codigo"] is None)
        self.assertGreaterEqual(len(contenido.lecciones(curso)), 10)


class TestElValidadorAtrapaErrores(unittest.TestCase):
    def test_tipo_desconocido(self):
        self.assertTrue(any("tipo de paso desconocido" in m for m in errores({"tipo": "bailar"})))

    def test_campo_faltante(self):
        self.assertTrue(any("falta el campo" in m for m in errores({"tipo": "elegir", "pregunta": "?"})))

    def test_elegir_correcta_fuera_de_rango_y_opciones_repetidas(self):
        self.assertTrue(any("fuera de rango" in m for m in errores(
            EXPL, {"tipo": "elegir", "pregunta": "?", "opciones": ["a", "b"], "correcta": 5})))
        self.assertTrue(any("repetidas" in m for m in errores(
            EXPL, {"tipo": "elegir", "pregunta": "?", "opciones": ["a", "a"], "correcta": 0})))

    def test_predecir_con_respuesta_equivocada(self):
        m = errores(EXPL, {"tipo": "predecir", "codigo": 'mostrar "x"', "opciones": ["y", "x"], "correcta": 0})
        self.assertTrue(any("la opción correcta dice" in x for x in m))

    def test_predecir_con_dos_respuestas_validas(self):
        m = errores(EXPL, {"tipo": "predecir", "codigo": 'mostrar "x"', "opciones": ["x", "x "], "correcta": 0})
        self.assertTrue(any("repetidas" in x or "también es correcta" in x for x in m))

    def test_completar_cantidad_de_huecos_y_fichas(self):
        self.assertTrue(any("huecos" in m for m in errores(EXPL, {
            "tipo": "completar", "consigna": "c", "codigo": "___ ___", "fichas": ["a"], "respuesta": ["a"]})))
        self.assertTrue(any("no están entre las fichas" in m for m in errores(EXPL, {
            "tipo": "completar", "consigna": "c", "codigo": '___ "x"', "fichas": ["sumar"], "respuesta": ["mostrar"]})))

    def test_completar_requiere_fichas_duplicadas_para_respuestas_repetidas(self):
        hallazgos = errores(EXPL, {
            "tipo": "completar", "consigna": "c", "codigo": "___ ___",
            "fichas": ["h1"], "respuesta": ["h1", "h1"], "lenguaje": "html",
        })
        self.assertTrue(any("faltan fichas duplicadas" in m for m in hallazgos))


    def test_completar_que_no_muestra_lo_esperado(self):
        m = errores(EXPL, {"tipo": "completar", "consigna": "c", "codigo": '___ "x"', "fichas": ["mostrar"],
                           "respuesta": ["mostrar"], "salida": "otra cosa"})
        self.assertTrue(any("se esperaba" in x for x in m))

    def test_ordenar_que_no_corre(self):
        self.assertTrue(any("no corre" in m for m in errores(EXPL, {
            "tipo": "ordenar", "consigna": "o", "lineas": ["mostrar a", "a es 1"]})))

    def test_escribir_con_solucion_rota_o_muda(self):
        self.assertTrue(any("no corre" in m for m in errores({"tipo": "escribir", "consigna": "c", "solucion": "mostrar x",
                                                              "forma": "mostrar 1"})))
        self.assertTrue(any("no muestra nada" in m for m in errores({"tipo": "escribir", "consigna": "c",
                                                                     "solucion": "x es 1", "forma": "x es 1"})))

    def test_preguntar_sin_entradas_de_prueba(self):
        m = errores({"tipo": "escribir", "consigna": "c", "solucion": 'a es preguntar("?")\nmostrar a',
                     "forma": 'a es preguntar("?")'})
        self.assertTrue(any("entradas_prueba" in x for x in m))

    def test_usar_una_palabra_antes_de_ensenarla(self):
        m = errores({"tipo": "escribir", "consigna": "c", "solucion": 'mostrar "x"'})
        self.assertTrue(any("antes de enseñarlo" in x for x in m))

    def test_ejemplo_que_no_corre(self):
        self.assertTrue(any("el ejemplo no corre" in m for m in errores(
            {"tipo": "explicacion", "texto": "t", "codigo": "mostrar nada_definido"})))

    def test_ids_repetidos_y_seccion_vacia(self):
        curso = curso_con(EXPL)
        curso["secciones"].append({"id": "s", "nivel": 2, "titulo": "S2", "lecciones": []})
        m = [h.mensaje for h in validar_curso(curso) if h.nivel == ERROR]
        self.assertTrue(any("id de sección repetido" in x for x in m))
        self.assertTrue(any("sección sin lecciones" in x for x in m))
        self.assertTrue(any("no tiene secciones" in h.mensaje for h in validar_curso({"id": "x", "secciones": []})))

    def test_dibujos_predecir_con_cuenta_equivocada(self):
        m = errores(EXPL_T, {"tipo": "predecir", "codigo": "avanzar 10\ngirar_der 90\navanzar 10", "cuenta": "trazos",
                             "opciones": ["3", "2"], "correcta": 0})
        self.assertTrue(any("dibuja 2 línea" in x for x in m))
        m = errores(EXPL_T, {"tipo": "predecir", "codigo": "avanzar 10", "cuenta": "trazos",
                             "opciones": ["1", "1"], "correcta": 0})
        self.assertTrue(any("repetidas" in x or "también es correcta" in x for x in m))

    def test_dibujos_ejemplo_con_lienzo_que_no_dibuja(self):
        m = errores({"tipo": "explicacion", "texto": "t", "codigo": "subir_lapiz\navanzar 10", "lienzo": True})
        self.assertTrue(any("no dibuja nada" in x for x in m))

    def test_dibujos_completar_ordenar_y_escribir_deben_dibujar(self):
        for paso in (
            {"tipo": "completar", "consigna": "c", "codigo": "subir_lapiz\navanzar ___", "fichas": ["10"],
             "respuesta": ["10"], "tortuga": True},
            {"tipo": "ordenar", "consigna": "o", "lineas": ["subir_lapiz", "avanzar 10"], "tortuga": True},
            {"tipo": "escribir", "consigna": "e", "solucion": "subir_lapiz\navanzar 10", "tortuga": True},
        ):
            with self.subTest(tipo=paso["tipo"]):
                m = errores(EXPL_T, {"tipo": "explicacion", "texto": "t", "codigo": "subir_lapiz", "lienzo": False}, paso)
                self.assertTrue(any("no dibuja nada" in x for x in m), m)

    def test_dibujos_ordenar_con_otro_orden_equivalente_avisa(self):
        curso = curso_con(EXPL_T, {"tipo": "explicacion", "texto": "t", "codigo": "girar_der 90"},
                          {"tipo": "ordenar", "consigna": "o", "tortuga": True,
                           "lineas": ["avanzar 10", "girar_der 90", "girar_izq 90", "avanzar 10"]})
        avisos = [h.mensaje for h in validar_curso(curso) if h.nivel == AVISO]
        self.assertFalse([h for h in validar_curso(curso) if h.nivel == ERROR])
        self.assertTrue(any("otro orden" in a for a in avisos))

    def test_avisos_de_estilo(self):
        largo = {"tipo": "explicacion", "texto": "palabra " * 40, "codigo": 'mostrar "x"'}
        jerga = {"tipo": "explicacion", "texto": "Esto es un string con sintaxis.", "codigo": 'mostrar "x"'}
        tilde = {"tipo": "explicacion", "texto": "Mirá la linea de abajo.", "codigo": 'mostrar "x"'}
        for paso, esperado in ((largo, "texto largo"), (jerga, "jerga"), (tilde, "tilde")):
            avisos = [h.mensaje for h in validar_curso(curso_con(paso)) if h.nivel == AVISO]
            self.assertTrue(any(esperado in a for a in avisos), (esperado, avisos))


LAB = {"paredes": [[-30, 30, -30, -130], [30, 30, 30, -130], [-30, 30, 30, 30]], "salida": [0, -100]}


def escribir_lab(solucion="avanzar 100", **extra):
    return {"tipo": "escribir", "consigna": "Llegá.", "solucion": solucion, "tortuga": True, "laberinto": LAB, **extra}


class TestValidadorDeLaberintos(unittest.TestCase):
    def test_laberinto_bien_hecho(self):
        self.assertEqual(errores(EXPL_T, escribir_lab()), [])

    def test_la_solucion_choca_o_no_llega(self):
        self.assertTrue(any("choca con una pared (línea 2)" in m for m in errores(EXPL_T, escribir_lab("girar_der 90\navanzar 100"))))
        self.assertTrue(any("no termina en la salida" in m for m in errores(EXPL_T, escribir_lab("avanzar 40"))))

    def test_dato_mal_escrito_o_sin_tortuga(self):
        mal = {**escribir_lab(), "laberinto": {"paredes": [[1, 2]], "salida": [0, 0]}}
        self.assertTrue(any("pared mal escrita" in m for m in errores(EXPL_T, mal)))
        sin = {k: v for k, v in escribir_lab().items() if k != "tortuga"}
        self.assertTrue(any("necesita «tortuga»" in m for m in errores(EXPL_T, sin)))

    def test_usar_se_comprueba_contra_la_solucion(self):
        m = errores(EXPL_T, escribir_lab(usar=["repetir"]))
        self.assertTrue(any("exige repetir" in x for x in m))

    def test_laberinto_y_usar_solo_en_escribir(self):
        m = errores(EXPL_T, {"tipo": "elegir", "pregunta": "?", "opciones": ["a", "b"], "correcta": 0, "laberinto": LAB})
        self.assertTrue(any("«laberinto» solo sirve" in x for x in m))
        m = errores(EXPL_T, {"tipo": "escribir", "consigna": "Dibujá.", "solucion": "avanzar 10", "tortuga": True,
                             "usar": ["repetir"]})
        self.assertTrue(any("«usar» por ahora" in x for x in m))


class TestValidadorConDado(unittest.TestCase):
    def test_dado_hay_que_ensenarlo_antes_de_usarlo(self):
        paso = {"tipo": "escribir", "consigna": "Tirá.", "solucion": "mostrar dado(6)"}
        self.assertTrue(any("dado" in m and "antes de enseñarlo" in m for m in errores(EXPL, paso)))
        explicado = {"tipo": "explicacion", "texto": "El dado.", "codigo": "mostrar dado(6)"}
        self.assertEqual(errores(EXPL, explicado, paso), [])

    def test_predecir_con_dado_es_reproducible(self):
        from tortuscript.evaluacion import SEMILLA_EVALUACION
        from tortuscript.executor import ejecutar_codigo
        real = ejecutar_codigo("print(dado(6))", semilla=SEMILLA_EVALUACION)[0].strip()
        explicado = {"tipo": "explicacion", "texto": "El dado.", "codigo": "mostrar dado(6)"}
        otras = [str(n) for n in range(1, 7) if str(n) != real][:2]
        paso = {"tipo": "predecir", "codigo": "mostrar dado(6)", "opciones": [real] + otras, "correcta": 0}
        self.assertEqual(errores(EXPL, explicado, paso), [])


class TestPistasPropias(unittest.TestCase):
    def test_todos_los_pasos_con_opciones_tienen_pista_propia(self):
        faltan = [f"{lec['id']}#{i}" for curso in contenido.todos_los_cursos() for _, lec in contenido.lecciones(curso)
                  for i, p in enumerate(lec["pasos"])
                  if p["tipo"] in ("elegir", "predecir", "completar", "ordenar") and not p.get("pista")]
        self.assertEqual(faltan, [])

    def test_el_validador_avisa_si_falta_la_pista_o_si_esta_mal_escrita(self):
        def avisos(*pasos):
            return [h.mensaje for h in validar_curso(curso_con(*pasos)) if h.nivel == AVISO]
        sin = {"tipo": "elegir", "pregunta": "¿Cuál?", "opciones": ["a", "b"], "correcta": 0}
        self.assertTrue(any("sin «pista» propia" in m for m in avisos(EXPL, sin)))
        con_jerga = {**sin, "pista": "Es un string."}
        self.assertTrue(any("jerga" in m for m in avisos(EXPL, con_jerga)))
        self.assertEqual(avisos(EXPL, {**sin, "pista": "Fijate en la primera."}), [])


if __name__ == "__main__":
    unittest.main()
