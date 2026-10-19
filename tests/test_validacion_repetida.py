import unittest

from tortuscript.validacion import validar_curso, AVISO, ERROR

class TestRespuestaCorrectaRepetida(unittest.TestCase):

    def _crear_curso_base(self, lecciones_data):
        """Crea una estructura de curso sintético."""
        curso = {
            "id": "curso-sintetico",
            "titulo": "Curso Sintético para Tests",
            "secciones": []
        }
        seccion = {
            "id": "seccion-1",
            "titulo": "Sección de Prueba",
            "lecciones": []
        }
        for leccion_id, pasos_data in lecciones_data.items():
            leccion = {
                "id": leccion_id,
                "titulo": f"Lección {leccion_id}",
                "pasos": []
            }
            for i, paso_data in enumerate(pasos_data):
                paso = {
                    "id": f"paso-{leccion_id}-{i+1}",
                    "tipo": paso_data["tipo"],
                    "pregunta": paso_data["pregunta"],
                    "opciones": paso_data["opciones"],
                    "correcta": paso_data["correcta"],
                    "pista": paso_data["pista"]
                }
                leccion["pasos"].append(paso)
            seccion["lecciones"].append(leccion)
        curso["secciones"].append(seccion)
        return curso

    def test_a_dos_elegir_misma_leccion_igual_correcta_un_aviso(self):
        # Caso (a): dos elegir de la misma lección con igual correcta -> exactamente 1 AVISO
        lecciones_data = {
            "leccion-1": [
                {
                    "tipo": "elegir",
                    "pregunta": "¿Qué es A?",
                    "opciones": ["Opción A", "Opción B"],
                    "correcta": 0,
                    "pista": "Pista A"
                },
                {
                    "tipo": "elegir",
                    "pregunta": "¿Qué es A otra vez?",
                    "opciones": ["Opción C", "Opción A"], # Misma respuesta correcta "Opción A" (índice 1)
                    "correcta": 1,
                    "pista": "Pista B"
                }
            ]
        }
        curso = self._crear_curso_base(lecciones_data)
        hallazgos = validar_curso(curso)
        avisos_repetidos = [h for h in hallazgos if h.nivel == AVISO and "respuesta correcta repetida" in h.mensaje]
        self.assertEqual(len(avisos_repetidos), 1, "Debería haber exactamente 1 AVISO de respuesta correcta repetida.")

    def test_b_tres_elegir_misma_leccion_igual_correcta_dos_avisos(self):
        # Caso (b): tres repetidas -> 2 avisos
        lecciones_data = {
            "leccion-1": [
                {
                    "tipo": "elegir",
                    "pregunta": "¿Qué es A?",
                    "opciones": ["Opción A", "Opción B"],
                    "correcta": 0,
                    "pista": "Pista A"
                },
                {
                    "tipo": "elegir",
                    "pregunta": "¿Qué es A otra vez?",
                    "opciones": ["Opción C", "Opción A"], # Misma respuesta correcta "Opción A"
                    "correcta": 1,
                    "pista": "Pista B"
                },
                {
                    "tipo": "elegir",
                    "pregunta": "¿Y una tercera vez A?",
                    "opciones": ["Opción D", "Opción E", "Opción A"], # Misma respuesta correcta "Opción A"
                    "correcta": 2,
                    "pista": "Pista C"
                }
            ]
        }
        curso = self._crear_curso_base(lecciones_data)
        hallazgos = validar_curso(curso)
        avisos_repetidos = [h for h in hallazgos if h.nivel == AVISO and "respuesta correcta repetida" in h.mensaje]
        self.assertEqual(len(avisos_repetidos), 2, "Debería haber exactamente 2 AVISOS de respuesta correcta repetida.")

    def test_c_misma_correcta_lecciones_distintas_ningun_aviso(self):
        # Caso (c): mismas correctas pero en lecciones distintas -> ninguno
        lecciones_data = {
            "leccion-1": [
                {
                    "tipo": "elegir",
                    "pregunta": "¿Qué es A?",
                    "opciones": ["Opción A", "Opción B"],
                    "correcta": 0,
                    "pista": "Pista A"
                }
            ],
            "leccion-2": [
                {
                    "tipo": "elegir",
                    "pregunta": "¿Qué es A en otra lección?",
                    "opciones": ["Opción C", "Opción A"], # Misma respuesta correcta "Opción A"
                    "correcta": 1,
                    "pista": "Pista B"
                }
            ]
        }
        curso = self._crear_curso_base(lecciones_data)
        hallazgos = validar_curso(curso)
        avisos_repetidos = [h for h in hallazgos if h.nivel == AVISO and "respuesta correcta repetida" in h.mensaje]
        self.assertEqual(len(avisos_repetidos), 0, "No debería haber AVISOS de respuesta correcta repetida en lecciones distintas.")

    def test_d_correctas_distintas_ningun_aviso(self):
        # Caso (d): correctas distintas -> ninguno
        lecciones_data = {
            "leccion-1": [
                {
                    "tipo": "elegir",
                    "pregunta": "¿Qué es A?",
                    "opciones": ["Opción A", "Opción B"],
                    "correcta": 0,
                    "pista": "Pista A"
                },
                {
                    "tipo": "elegir",
                    "pregunta": "¿Qué es B?",
                    "opciones": ["Opción C", "Opción B"], # Respuesta correcta "Opción B"
                    "correcta": 1,
                    "pista": "Pista B"
                }
            ]
        }
        curso = self._crear_curso_base(lecciones_data)
        hallazgos = validar_curso(curso)
        avisos_repetidos = [h for h in hallazgos if h.nivel == AVISO and "respuesta correcta repetida" in h.mensaje]
        self.assertEqual(len(avisos_repetidos), 0, "No debería haber AVISOS si las respuestas correctas son distintas.")

    def test_e_diferencia_solo_espacios_cuenta_como_repetida_un_aviso(self):
        # Caso (e): diferencia solo de espacios al borde -> cuenta como repetida
        lecciones_data = {
            "leccion-1": [
                {
                    "tipo": "elegir",
                    "pregunta": "¿Qué es X?",
                    "opciones": [" Opción X ", "Opción Y"],
                    "correcta": 0,
                    "pista": "Pista X"
                },
                {
                    "tipo": "elegir",
                    "pregunta": "¿Qué es X otra vez?",
                    "opciones": ["Opción Z", "Opción X"], # Respuesta correcta "Opción X"
                    "correcta": 1,
                    "pista": "Pista Y"
                }
            ]
        }
        curso = self._crear_curso_base(lecciones_data)
        hallazgos = validar_curso(curso)
        avisos_repetidos = [h for h in hallazgos if h.nivel == AVISO and "respuesta correcta repetida" in h.mensaje]
        self.assertEqual(len(avisos_repetidos), 1, "Debería haber 1 AVISO si la diferencia es solo de espacios.")

    def test_f_opcion_incorrecta_igual_a_correcta_otro_paso_no_cuenta_ningun_aviso(self):
        # Caso (f): una opción incorrecta igual a la correcta de otro paso no cuenta
        lecciones_data = {
            "leccion-1": [
                {
                    "tipo": "elegir",
                    "pregunta": "¿Qué es P?",
                    "opciones": ["Opción P", "Opción Q"],
                    "correcta": 0,
                    "pista": "Pista P"
                },
                {
                    "tipo": "elegir",
                    "pregunta": "¿Qué es R?",
                    "opciones": ["Opción P", "Opción R"], # Opción incorrecta "Opción P" es igual a correcta del paso anterior
                    "correcta": 1,
                    "pista": "Pista R"
                }
            ]
        }
        curso = self._crear_curso_base(lecciones_data)
        hallazgos = validar_curso(curso)
        avisos_repetidos = [h for h in hallazgos if h.nivel == AVISO and "respuesta correcta repetida" in h.mensaje]
        self.assertEqual(len(avisos_repetidos), 0, "No debería haber AVISOS si una opción incorrecta es igual a una correcta de otro paso.")

    def test_g_los_avisos_no_son_error(self):
        # Caso (g): los avisos no son ERROR
        self.assertNotEqual(AVISO, ERROR, "AVISO y ERROR deben ser distintos.")

    def test_h_cursos_reales_no_tienen_avisos_repetidos(self):
        # Garantía de no-falsos-positivos: ningún curso real dispara la regla.
        from tortuscript.contenido import CARPETA, cargar_curso
        ids = sorted(p.stem for p in CARPETA.glob("*.json"))
        self.assertGreaterEqual(len(ids), 9)
        for curso_id in ids:
            with self.subTest(curso=curso_id):
                self.assertEqual(_repetidos(cargar_curso(curso_id)), [])


def _elegir(opciones, correcta):
    return {"tipo": "elegir", "pregunta": "¿?", "opciones": opciones, "correcta": correcta, "pista": "p"}


def _curso(pasos):
    return {"id": "c", "titulo": "C", "secciones": [{"id": "s", "titulo": "S", "lecciones": [
        {"id": "l", "titulo": "L", "pasos": pasos}]}]}


def _repetidos(curso):
    return [h for h in validar_curso(curso) if "respuesta correcta repetida" in h.mensaje]


class TestRespuestaRepetidaDetalle(unittest.TestCase):
    def test_el_aviso_nombra_el_paso_repetido_y_el_primero(self):
        (h,) = _repetidos(_curso([_elegir(["A", "B"], 0), _elegir(["X", "A"], 1)]))
        self.assertIn("paso 2 (elegir)", h.donde)
        self.assertIn("paso 1", h.mensaje)

    def test_el_tercero_apunta_al_primero_y_cuenta_desde_uno(self):
        pasos = [_elegir(["A", "B"], 0), {"tipo": "explicacion", "texto": "t"}, _elegir(["A", "C"], 0), _elegir(["C", "A"], 1)]
        h1, h2 = _repetidos(_curso(pasos))
        self.assertIn("paso 3 (elegir)", h1.donde)
        self.assertIn("paso 4 (elegir)", h2.donde)
        self.assertTrue(h1.mensaje.endswith("paso 1") and h2.mensaje.endswith("paso 1"))

    def test_correcta_en_el_limite_o_negativa_se_ignora_sin_romper(self):
        for malo in (2, -1):
            with self.subTest(correcta=malo):
                self.assertEqual(_repetidos(_curso([_elegir(["A", "B"], 0), _elegir(["X", "A"], malo)])), [])

    def test_correcta_booleana_o_no_entera_se_ignora(self):
        for malo in (True, "1", 1.0, None):
            with self.subTest(correcta=malo):
                self.assertEqual(_repetidos(_curso([_elegir(["B", "A"], 1), _elegir(["X", "A"], malo)])), [])

    def test_opciones_que_no_son_lista_se_ignoran(self):
        self.assertEqual(_repetidos(_curso([_elegir(["A"], 0), _elegir("A", 0)])), [])

    def test_correcta_cero_cuenta(self):
        self.assertEqual(len(_repetidos(_curso([_elegir(["A", "B"], 0), _elegir(["A", "C"], 0)]))), 1)

    def test_correcta_en_la_ultima_opcion_cuenta(self):
        self.assertEqual(len(_repetidos(_curso([_elegir(["B", "A"], 1), _elegir(["C", "A"], 1)]))), 1)
