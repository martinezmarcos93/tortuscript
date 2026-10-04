"""Contratos transversales de presentación de errores en el frontend."""
from pathlib import Path
import unittest


class FrontendErrorContractTests(unittest.TestCase):
    def test_scripts_de_aplicacion_no_exponen_excepciones_crudas(self):
        raiz = Path(__file__).resolve().parents[1] / "web" / "static" / "js"
        infracciones = []
        for archivo in raiz.rglob("*.js"):
            texto = archivo.read_text(encoding="utf-8")
            if "String(e)" in texto:
                infracciones.append(str(archivo.relative_to(raiz)))
        self.assertEqual(
            infracciones,
            [],
            "No mostrar String(e) al alumno; usar un mensaje seguro y comprensible.",
        )


if __name__ == "__main__":
    unittest.main()
