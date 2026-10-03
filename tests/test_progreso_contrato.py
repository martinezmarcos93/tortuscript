"""Pruebas del contrato de progreso por ChildProfile."""
import unittest

from tortuscript.progreso_contrato import (
    MemoriaProgresoStore,
    ProgresoContratoError,
    exportar_snapshot,
    importar_snapshot,
    nuevo_snapshot,
)


class ProgresoContratoTests(unittest.TestCase):
    def test_snapshot_usa_profile_id_y_no_nombre_visible(self):
        data = {"xp": 40, "lecciones": {"1": {"completada": True}}}
        snapshot = nuevo_snapshot("child_abc123", data)
        self.assertEqual(snapshot.profile_id, "child_abc123")
        self.assertEqual(snapshot.data["xp"], 40)
        self.assertNotIn("email", snapshot.data)

    def test_store_aisla_por_profile_id(self):
        store = MemoriaProgresoStore()
        store.guardar(nuevo_snapshot("child_a", {"xp": 10}))
        store.guardar(nuevo_snapshot("child_b", {"xp": 90}))
        self.assertEqual(store.cargar("child_a").data["xp"], 10)
        self.assertEqual(store.cargar("child_b").data["xp"], 90)

    def test_store_no_expone_referencia_mutable(self):
        store = MemoriaProgresoStore()
        original = {"xp": 10}
        store.guardar(nuevo_snapshot("child_a", original))
        original["xp"] = 999
        recuperado = store.cargar("child_a")
        self.assertEqual(recuperado.data["xp"], 10)

    def test_exportar_importar_conserva_contrato(self):
        documento = exportar_snapshot("child_a", {"xp": 10})
        recuperado = importar_snapshot(documento)
        self.assertEqual(recuperado.profile_id, "child_a")
        self.assertEqual(recuperado.data, {"xp": 10})

    def test_rechaza_profile_id_ausente(self):
        with self.assertRaises(ProgresoContratoError):
            nuevo_snapshot("", {"xp": 10})

    def test_rechaza_version_desconocida(self):
        with self.assertRaises(ProgresoContratoError):
            importar_snapshot({
                "contract_version": 999,
                "profile_id": "child_a",
                "updated_at": "2026-09-30T12:00:00+00:00",
                "data": {},
            })

    def test_rechaza_fecha_invalida_o_sin_zona_horaria(self):
        for fecha in ("no-es-fecha", "2026-09-30T12:00:00"):
            documento = exportar_snapshot("child_a", {"xp": 10})
            documento["updated_at"] = fecha
            with self.subTest(fecha=fecha):
                with self.assertRaises(ProgresoContratoError):
                    importar_snapshot(documento)

    def test_rechaza_version_boolean_aunque_true_equivalga_a_uno(self):
        documento = exportar_snapshot("child_a", {"xp": 10})
        documento["contract_version"] = True
        with self.assertRaises(ProgresoContratoError):
            importar_snapshot(documento)

    def test_rechaza_datos_no_serializables_como_json(self):
        with self.assertRaises(ProgresoContratoError):
            nuevo_snapshot("child_a", {"objeto": object()})


if __name__ == "__main__":
    unittest.main()
