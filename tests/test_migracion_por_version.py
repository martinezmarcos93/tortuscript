
import unittest
import copy
from tortuscript.progreso import _migrar, PROGRESO_INICIAL, VERSION_ESQUEMA

class TestMigracionProgresoPorVersion(unittest.TestCase):

    def _get_historical_profile(self, version_target):
        profile = copy.deepcopy(PROGRESO_INICIAL)

        # Simular esquema de versiones históricas (borrando campos posteriores)
        if version_target < 11:
            profile.pop("recorrido_inicial", None)
        if version_target < 10:
            profile.pop("intereses", None)
        if version_target < 9:
            profile.pop("salteadas", None)
            profile.pop("proyectos_integradores", None)
        if version_target < 7:
            profile.pop("proyectos", None)
        if version_target < 6:
            profile.pop("repaso", None)
            profile.pop("xp_practica", None)
        if version_target < 5:
            profile.pop("congeladores", None)
            profile.pop("dias_congelados", None)
            profile.pop("dias_meta", None)
            profile.pop("logros", None)
            profile.pop("liga", None)
            profile.pop("stats", None)
            profile.pop("avisos", None)
        if version_target < 4:
            profile.pop("config", None)
        if version_target < 3:
            profile.pop("lecciones", None)

        profile["version"] = version_target
        return profile

    def _populate_profile_with_data(self, profile, version):
        """Llena un perfil con datos de usuario significativos para esa versión."""
        if "xp_total" in profile:
            profile["xp_total"] = 500
        if "ejercicios" in profile:
            profile["ejercicios"] = {"1": {"estrellas": 3, "xp": 20}}
        if "racha" in profile:
            profile["racha"] = 10
            profile["racha_max"] = 10
        if "lecciones" in profile:
            profile["lecciones"] = {"intro": {"pasos": {"0": {"xp": 5}}, "completada": True}}
        if "logros" in profile:
            profile["logros"] = {"primer_paso": "2026-01-01"}
        if "repaso" in profile:
            profile["repaso"] = {"leccion:0": {"caja": 1, "proximo": "2026-10-20"}}
        if "config" in profile:
            profile["config"]["nombre"] = "TestUser"
            profile["config"]["meta_min"] = 15
            if "ajustes" in profile["config"]:
                # Valores válidos presentes
                profile["config"]["ajustes"]["tam"] = "grande"
                profile["config"]["ajustes"]["movimiento"] = "reducido"
                # Valores actuales (no importa si son "válidos" o no, _migrar solo completa lo ausente)
                profile["config"]["ajustes"]["voz"] = "si"
        return profile

    def test_version_final(self):
        for version in range(1, VERSION_ESQUEMA + 1):
            with self.subTest(version=version):
                initial = self._get_historical_profile(version)
                migrated = _migrar(copy.deepcopy(initial))
                self.assertEqual(migrated["version"], VERSION_ESQUEMA)

    def test_claves_completas_y_tipos(self):
        for version in range(1, VERSION_ESQUEMA + 1):
            with self.subTest(version=version):
                initial = self._get_historical_profile(version)
                migrated = _migrar(copy.deepcopy(initial))
                
                for key, expected_value in PROGRESO_INICIAL.items():
                    self.assertIn(key, migrated)
                    if isinstance(expected_value, (dict, list)):
                        self.assertIsInstance(migrated[key], type(expected_value))

    def test_conserva_datos_del_alumno(self):
        for version in range(1, VERSION_ESQUEMA + 1):
            with self.subTest(version=version):
                initial = self._populate_profile_with_data(self._get_historical_profile(version), version)
                migrated = _migrar(copy.deepcopy(initial))
                
                # Datos simples
                if "xp_total" in initial:
                    self.assertEqual(migrated["xp_total"], initial["xp_total"])
                if "racha" in initial:
                    self.assertEqual(migrated["racha"], initial["racha"])
                
                # Config
                if "config" in initial:
                    self.assertEqual(migrated["config"]["nombre"], initial["config"]["nombre"])
                    self.assertEqual(migrated["config"]["meta_min"], initial["config"]["meta_min"])
                    if "ajustes" in initial["config"]:
                        self.assertEqual(migrated["config"]["ajustes"]["tam"], initial["config"]["ajustes"]["tam"])
                        self.assertEqual(migrated["config"]["ajustes"]["movimiento"], initial["config"]["ajustes"]["movimiento"])

    def test_idempotencia(self):
        for version in range(1, VERSION_ESQUEMA + 1):
            with self.subTest(version=version):
                initial = self._populate_profile_with_data(self._get_historical_profile(version), version)
                m1 = _migrar(copy.deepcopy(initial))
                m2 = _migrar(copy.deepcopy(m1))
                self.assertEqual(m1, m2)

    def test_no_comparte_estado_con_el_inicial(self):
        for version in range(1, VERSION_ESQUEMA + 1):
            with self.subTest(version=version):
                initial = self._populate_profile_with_data(self._get_historical_profile(version), version)
                initial_copy = copy.deepcopy(initial)
                migrated = _migrar(copy.deepcopy(initial))
                
                # Mutar algo anidado en el resultado
                if "lecciones" in migrated:
                    migrated["lecciones"]["test"] = "valor"
                if "config" in migrated and "ajustes" in migrated["config"]:
                    migrated["config"]["ajustes"]["voz"] = "mutado"
                    
                # Verificar que el PROGRESO_INICIAL original no cambió (bueno, el inicial no, sino la copia)
                self.assertEqual(initial, initial_copy)

    def test_tipo_equivocado_se_restituye_sin_perder_hermanos(self):
        for version in range(1, VERSION_ESQUEMA + 1):
            with self.subTest(version=version):
                initial = self._get_historical_profile(version)
                
                # Corromper tipos si existen
                if "config" in initial:
                    initial["config"] = "string_en_lugar_de_dict"
                    # Hermanos válidos (si los hubiera)
                    initial["config"] = {"nombre": "SiblingUser"}
                    initial["config"] = "corrupto" # Se vuelve a corromper
                
                migrated = _migrar(copy.deepcopy(initial))
                
                # Debería haber restaurado los tipos por defecto de PROGRESO_INICIAL
                self.assertIsInstance(migrated["config"], dict)
                self.assertIsInstance(migrated["config"]["ajustes"], dict)

    def test_ajustes_validos_no_se_pisan_ausentes_toman_default(self):
        for version in range(1, VERSION_ESQUEMA + 1):
            with self.subTest(version=version):
                if version < 4: continue # ajustes requiere config (v4)
                
                initial = self._get_historical_profile(version)
                initial["config"]["ajustes"] = {"tam": "enorme"} # presente
                
                migrated = _migrar(copy.deepcopy(initial))
                
                # Presente se conserva
                self.assertEqual(migrated["config"]["ajustes"]["tam"], "enorme")
                # Ausente toma default
                self.assertEqual(migrated["config"]["ajustes"]["voz"], PROGRESO_INICIAL["config"]["ajustes"]["voz"])

if __name__ == '__main__':
    unittest.main()
