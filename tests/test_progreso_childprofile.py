"""Pruebas del adaptador persistente por ChildProfile."""
import shutil
import tempfile
import unittest
from pathlib import Path

from tortuscript.progreso_childprofile import ProgresoChildProfile, ProgresoPerfilError


class ProgresoChildProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.store = ProgresoChildProfile(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_guarda_y_carga_por_id_interno(self):
        snapshot = self.store.crear_si_no_existe("child_0123456789abcdef01234567", {"xp_total": 25})
        self.assertEqual(snapshot.profile_id, "child_0123456789abcdef01234567")
        loaded = self.store.cargar("child_0123456789abcdef01234567")
        self.assertEqual(loaded.data["xp_total"], 25)

    def test_dos_perfiles_quedan_aislados(self):
        a = "child_0123456789abcdef01234567"
        b = "child_abcdef012345678901234567"
        self.store.crear_si_no_existe(a, {"xp_total": 10})
        self.store.crear_si_no_existe(b, {"xp_total": 90})
        self.assertEqual(self.store.cargar(a).data["xp_total"], 10)
        self.assertEqual(self.store.cargar(b).data["xp_total"], 90)

    def test_rechaza_nombre_visible_como_identidad(self):
        with self.assertRaises(ProgresoPerfilError):
            self.store.crear_si_no_existe("Ana", {"xp_total": 10})

    def test_crear_no_sobrescribe_progreso_existente(self):
        profile = "child_0123456789abcdef01234567"
        self.store.crear_si_no_existe(profile, {"xp_total": 10})
        snapshot = self.store.crear_si_no_existe(profile, {"xp_total": 999})
        self.assertEqual(snapshot.data["xp_total"], 10)

    def test_rechaza_snapshot_cuyo_profile_id_no_coincide_con_el_archivo(self):
        import json

        profile_a = "child_0123456789abcdef01234567"
        profile_b = "child_abcdef012345678901234567"
        self.store.crear_si_no_existe(profile_a, {"xp_total": 10})
        archivo = self.tmp / f"progreso_{profile_a}.json"
        documento = json.loads(archivo.read_text(encoding="utf-8"))
        documento["profile_id"] = profile_b
        archivo.write_text(json.dumps(documento), encoding="utf-8")

        with self.assertRaises(ProgresoPerfilError):
            self.store.cargar(profile_a)


if __name__ == "__main__":
    unittest.main()
