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

    # ── recuperación ante archivo dañado ──
    PERFIL = "child_0123456789abcdef01234567"

    def _con_respaldo(self):
        """Deja progreso (xp 20) con un .bak válido (xp 10)."""
        from tortuscript.progreso_contrato import nuevo_snapshot
        self.store.guardar(nuevo_snapshot(self.PERFIL, {"xp_total": 10}))
        self.store.guardar(nuevo_snapshot(self.PERFIL, {"xp_total": 20}))
        return self.tmp / f"progreso_{self.PERFIL}.json"

    def test_archivo_sano_se_carga_sin_apartar_nada(self):
        self._con_respaldo()
        self.assertEqual(self.store.cargar_o_recuperar(self.PERFIL).data["xp_total"], 20)
        self.assertFalse(list(self.tmp.glob("*.corrupto-*")))
        self.assertIsNone(self.store.cargar_o_recuperar("child_abcdef012345678901234567"))

    def test_archivo_danado_se_aparta_y_se_recupera_del_respaldo(self):
        archivo = self._con_respaldo()
        for basura in ("{roto", "[]", '{"contract_version": 1, "profile_id": "x"}', ""):
            with self.subTest(basura=basura):
                for viejo in self.tmp.glob("*.corrupto-*"):
                    viejo.unlink()
                archivo.write_text(basura, encoding="utf-8")
                with self.assertLogs("tortuscript.progreso_childprofile", "WARNING"):
                    recuperado = self.store.cargar_o_recuperar(self.PERFIL)
                self.assertEqual(recuperado.data["xp_total"], 10)
                apartados = list(self.tmp.glob("*.corrupto-*"))
                self.assertEqual(len(apartados), 1)
                self.assertEqual(apartados[0].read_text(encoding="utf-8"), basura)   # el dañado no se pierde
                self.assertEqual(self.store.cargar(self.PERFIL).data["xp_total"], 10)  # y el perfil vuelve a andar

    def test_sin_respaldo_valido_empieza_de_cero_sin_borrar_lo_danado(self):
        archivo = self._con_respaldo()
        archivo.write_text("{roto", encoding="utf-8")
        archivo.with_name(archivo.name + ".bak").write_text("tampoco", encoding="utf-8")
        with self.assertLogs("tortuscript.progreso_childprofile", "ERROR"):
            self.assertIsNone(self.store.cargar_o_recuperar(self.PERFIL))
        self.assertFalse(archivo.exists())
        self.assertEqual(len(list(self.tmp.glob("*.corrupto-*"))), 1)

    def test_respaldo_de_otro_perfil_no_se_restaura(self):
        import json
        archivo = self._con_respaldo()
        archivo.write_text("{roto", encoding="utf-8")
        respaldo = archivo.with_name(archivo.name + ".bak")
        documento = json.loads(respaldo.read_text(encoding="utf-8"))
        documento["profile_id"] = "child_abcdef012345678901234567"
        respaldo.write_text(json.dumps(documento), encoding="utf-8")
        with self.assertLogs("tortuscript.progreso_childprofile", "ERROR"):
            self.assertIsNone(self.store.cargar_o_recuperar(self.PERFIL))

    def test_archivo_de_una_version_futura_se_rechaza_sin_tocarlo(self):
        import json
        archivo = self._con_respaldo()
        documento = json.loads(archivo.read_text(encoding="utf-8"))
        documento["contract_version"] = 2
        futuro = json.dumps(documento)
        archivo.write_text(futuro, encoding="utf-8")
        with self.assertRaises(ProgresoPerfilError):
            self.store.cargar_o_recuperar(self.PERFIL)
        self.assertEqual(archivo.read_text(encoding="utf-8"), futuro)
        self.assertFalse(list(self.tmp.glob("*.corrupto-*")))

    def test_los_logs_de_recuperacion_no_incluyen_datos_del_alumno(self):
        archivo = self._con_respaldo()
        archivo.write_text('{"contract_version": 1, "secreto": "nombre-real-del-alumno"', encoding="utf-8")
        with self.assertLogs("tortuscript.progreso_childprofile", "WARNING") as logs:
            self.store.cargar_o_recuperar(self.PERFIL)
        self.assertNotIn("nombre-real-del-alumno", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
