import copy
import importlib.util
import unittest
from pathlib import Path

_ruta = Path(__file__).resolve().parent.parent / "herramientas" / "verificar_solo_agregados.py"
_spec = importlib.util.spec_from_file_location("verificar_solo_agregados", _ruta)
verificar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verificar)

VIEJO = {"secciones": [{"id": "s", "lecciones": [
    {"id": "l1", "pasos": [{"tipo": "explicacion", "texto": "a"}, {"tipo": "elegir", "pista": "p"}]}]}]}


class SoloAgregadosTests(unittest.TestCase):
    def test_agregar_al_final_esta_permitido(self):
        nuevo = copy.deepcopy(VIEJO)
        nuevo["secciones"][0]["lecciones"][0]["pasos"].append({"tipo": "ordenar"})
        nuevo["secciones"][0]["lecciones"].append({"id": "l2", "pasos": []})
        nuevo["secciones"].append({"id": "s2", "lecciones": []})
        self.assertEqual(verificar.comparar(VIEJO, nuevo), [])

    def test_insertar_borrar_o_cambiar_un_paso_no(self):
        for cambio in ("insertar", "borrar", "cambiar"):
            nuevo = copy.deepcopy(VIEJO)
            pasos = nuevo["secciones"][0]["lecciones"][0]["pasos"]
            {"insertar": lambda: pasos.insert(0, {"tipo": "elegir"}),
             "borrar": lambda: pasos.pop(),
             "cambiar": lambda: pasos[1].update(pista="otra")}[cambio]()
            with self.subTest(cambio=cambio):
                self.assertTrue(verificar.comparar(VIEJO, nuevo))

    def test_cambiar_ids_de_leccion_o_seccion_no(self):
        nuevo = copy.deepcopy(VIEJO)
        nuevo["secciones"][0]["lecciones"][0]["id"] = "otro"
        self.assertTrue(verificar.comparar(VIEJO, nuevo))
        nuevo = copy.deepcopy(VIEJO)
        nuevo["secciones"][0]["id"] = "otra"
        self.assertTrue(verificar.comparar(VIEJO, nuevo))

    def test_campo_nuevo_solo_si_se_permite(self):
        nuevo = copy.deepcopy(VIEJO)
        nuevo["secciones"][0]["lecciones"][0]["pasos"][1]["pistas"] = ["x"]
        self.assertTrue(verificar.comparar(VIEJO, nuevo))
        self.assertEqual(verificar.comparar(VIEJO, nuevo, {"pistas"}), [])


if __name__ == "__main__":
    unittest.main()
