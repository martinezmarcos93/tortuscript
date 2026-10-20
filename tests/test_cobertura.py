import unittest

from tortuscript import cobertura, contenido, dominio


def curso(curso_id, lecciones):
    return {"id": curso_id, "secciones": [{"id": "s", "lecciones": [
        {"id": lid, "pasos": [{"tipo": t} for t in tipos]} for lid, tipos in lecciones.items()]}]}


CURSOS = [
    curso("c1", {"l1": ["explicacion", "elegir", "predecir"], "l2": ["completar", "ordenar", "escribir"]}),
    curso("c2", {"l3": ["explicacion", "elegir", "elegir"]}),
]
MAPA = {
    "completa": {"tipo": "lecciones", "curso": "c1", "lecciones": ["l1", "l2"]},
    "un-proyecto": {"tipo": "proyecto", "proyecto": "algo"},
    "solo-elegir": {"tipo": "lecciones", "curso": "c2", "lecciones": ["l3", "no-existe"]},
    "curso-fantasma": {"tipo": "lecciones", "curso": "nada", "lecciones": ["l1"]},
}


class CoberturaTests(unittest.TestCase):
    def setUp(self):
        self.cob = cobertura.cobertura(CURSOS, MAPA)

    def test_solo_unidades_de_lecciones_en_el_orden_del_mapa(self):
        self.assertEqual(list(self.cob), ["completa", "solo-elegir", "curso-fantasma"])

    def test_conteo_por_tipo_con_ceros(self):
        self.assertEqual(self.cob["solo-elegir"]["tipos"],
                         {"explicacion": 1, "elegir": 2, "completar": 0, "ordenar": 0, "predecir": 0, "escribir": 0})
        self.assertEqual(self.cob["solo-elegir"]["pasos"], 3)
        self.assertEqual(self.cob["completa"]["pasos"], 6)

    def test_categorias_y_faltan_en_orden(self):
        self.assertEqual(self.cob["completa"]["categorias"], list(dominio.CATEGORIAS))
        self.assertEqual(self.cob["completa"]["faltan"], [])
        self.assertEqual(self.cob["solo-elegir"]["categorias"], ["reconocimiento"])
        self.assertEqual(self.cob["solo-elegir"]["faltan"], ["prediccion", "construccion", "produccion"])

    def test_explicacion_no_es_categoria(self):
        cob = cobertura.cobertura([curso("c", {"l": ["explicacion"]})],
                                  {"u": {"tipo": "lecciones", "curso": "c", "lecciones": ["l"]}})
        self.assertEqual(cob["u"]["categorias"], [])
        self.assertEqual(cob["u"]["pasos"], 1)

    def test_curso_o_leccion_inexistente_aporta_cero(self):
        self.assertEqual(self.cob["curso-fantasma"]["pasos"], 0)
        self.assertEqual(self.cob["curso-fantasma"]["faltan"], list(dominio.CATEGORIAS))
        self.assertEqual(self.cob["solo-elegir"]["lecciones"], ["l3", "no-existe"])

    def test_resumen(self):
        self.assertEqual(cobertura.resumen(self.cob), {
            "unidades": 3,
            "con_una_categoria": ["solo-elegir"],
            "sin_produccion": ["solo-elegir", "curso-fantasma"],
            "completas": ["completa"],
        })

    def test_tabla(self):
        lineas = cobertura.tabla_markdown(self.cob).splitlines()
        self.assertEqual(lineas[0], "| Unidad | Curso | Pasos | Reconocimiento | Predicción | Construcción | Producción | Faltan |")
        self.assertEqual(lineas[3], "| `solo-elegir` | c2 | 3 | ✅ | — | — | — | Predicción, Construcción, Producción |")
        self.assertEqual(len(lineas), 2 + 3)

    def test_datos_reales(self):
        mapa = dominio.cargar_mapa()
        cob = cobertura.cobertura(contenido.todos_los_cursos(), mapa)
        self.assertEqual(len(cob), sum(1 for u in mapa.values() if u.get("tipo") == "lecciones"))
        self.assertTrue(all(d["pasos"] > 0 for d in cob.values()), "toda unidad del mapa tiene pasos")


if __name__ == "__main__":
    unittest.main()


class MatrizTransferenciaTests(unittest.TestCase):
    def test_desafio_cuenta_para_la_unidad_de_sus_lecciones(self):
        desafios = {"id": "d", "secciones": [{"id": "s", "lecciones": [
            {"id": "r1", "transferencia": {"conceptos": ["l1", "l2", "l3"]}, "pasos": []},
            {"id": "r2", "transferencia": {"conceptos": ["l3", "fuera-del-mapa"]}, "pasos": []},
            {"id": "r3", "pasos": []}]}]}
        matriz = cobertura.matriz_transferencia(CURSOS + [desafios], MAPA)
        self.assertEqual(matriz, {"completa": ["r1"], "solo-elegir": ["r1", "r2"], "curso-fantasma": []})

    def test_datos_reales_cubre_todas_las_unidades(self):
        mapa = dominio.cargar_mapa()
        matriz = cobertura.matriz_transferencia(contenido.todos_los_cursos(), mapa)
        self.assertEqual(set(matriz), {u for u, d in mapa.items() if d.get("tipo") == "lecciones"})
        self.assertTrue(any(matriz.values()), "los desafíos de Python usan unidades del mapa")
