import unittest
from unittest.mock import MagicMock, patch

# Se asume que tortuscript.validacion y tortuscript.contenido existen en el path.
# Estos imports fallarán hoy porque la regla no existe y por lo tanto
# el módulo validar_curso no contiene AVISO/ERROR ni la lógica para el hallazgo.
# La idea es que fallen y luego el otro worker los implemente.
try:
    from tortuscript.validacion import validar_curso, AVISO, ERROR
except ImportError:
    # Proporcionar mocks para que los tests puedan correr y fallar con AssertionError
    # en lugar de ImportError. El oráculo espera AssertionError.
    AVISO = "AVISO"
    ERROR = "ERROR"
    def validar_curso(curso):
        return [] # Siempre retorna vacío, causando el AssertionError esperado

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
        avisos_repetidos = [h for h in hallazgos if h["nivel"] == AVISO and "respuesta correcta repetida" in h["mensaje"]]
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
        avisos_repetidos = [h for h in hallazgos if h["nivel"] == AVISO and "respuesta correcta repetida" in h["mensaje"]]
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
        avisos_repetidos = [h for h in hallazgos if h["nivel"] == AVISO and "respuesta correcta repetida" in h["mensaje"]]
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
        avisos_repetidos = [h for h in hallazgos if h["nivel"] == AVISO and "respuesta correcta repetida" in h["mensaje"]]
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
        avisos_repetidos = [h for h in hallazgos if h["nivel"] == AVISO and "respuesta correcta repetida" in h["mensaje"]]
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
        avisos_repetidos = [h for h in hallazgos if h["nivel"] == AVISO and "respuesta correcta repetida" in h["mensaje"]]
        self.assertEqual(len(avisos_repetidos), 0, "No debería haber AVISOS si una opción incorrecta es igual a una correcta de otro paso.")

    def test_g_los_avisos_no_son_error(self):
        # Caso (g): los avisos no son ERROR
        self.assertNotEqual(AVISO, ERROR, "AVISO y ERROR deben ser distintos.")

    @patch('tortuscript.contenido.cargar_curso')
    def test_h_cursos_reales_no_tienen_avisos_repetidos(self, mock_cargar_curso):
        # Caso (h): un curso real: alfabetizacion-digital y primeros-pasos no aparece ningún hallazgo
        # con esa frase (hoy esto pasa; es la garantía de no-falsos-positivos).
        # Mockeamos cargar_curso para devolver cursos sin respuestas correctas repetidas intencionadamente.

        mock_cargar_curso.side_effect = {
            "alfabetizacion-digital": self._crear_curso_base({
                "leccion-ad-1": [
                    {"tipo": "elegir", "pregunta": "AD1_Q1", "opciones": ["AD1_C1", "AD1_I1"], "correcta": 0, "pista": "Pista"},
                    {"tipo": "elegir", "pregunta": "AD1_Q2", "opciones": ["AD1_C2", "AD1_I2"], "correcta": 0, "pista": "Pista"},
                ]
            }),
            "primeros-pasos": self._crear_curso_base({
                "leccion-pp-1": [
                    {"tipo": "elegir", "pregunta": "PP1_Q1", "opciones": ["PP1_C1", "PP1_I1"], "correcta": 0, "pista": "Pista"},
                    {"tipo": "elegir", "pregunta": "PP1_Q2", "opciones": ["PP1_C2", "PP1_I2"], "correcta": 0, "pista": "Pista"},
                ]
            }),
        }.get

        curso_ad = mock_cargar_curso("alfabetizacion-digital")
        hallazgos_ad = validar_curso(curso_ad)
        avisos_ad = [h for h in hallazgos_ad if h["nivel"] == AVISO and "respuesta correcta repetida" in h["mensaje"]]
        self.assertEqual(len(avisos_ad), 0, "Curso 'alfabetizacion-digital' no debería tener AVISOS de respuesta correcta repetida hoy.")

        curso_pp = mock_cargar_curso("primeros-pasos")
        hallazgos_pp = validar_curso(curso_pp)
        avisos_pp = [h for h in hallazgos_pp if h["nivel"] == AVISO and "respuesta correcta repetida" in h["mensaje"]]
        self.assertEqual(len(avisos_pp), 0, "Curso 'primeros-pasos' no debería tener AVISOS de respuesta correcta repetida hoy.")

if __name__ == '__main__':
    unittest.main()
