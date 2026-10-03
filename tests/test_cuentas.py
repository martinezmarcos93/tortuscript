"""Pruebas del límite de identidad/comercial, sin autenticar ni cobrar."""
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tortuscript.cuentas import CuentaError, CuentaRepository, MAX_CHILD_PROFILES


class CuentaRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = CuentaRepository(self.tmp / "cuentas.sqlite3")
        self.repo.ensure_schema()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_crea_cuenta_y_perfiles(self):
        cuenta = self.repo.crear_account(" Adulto@Ejemplo.com ")
        perfiles = [
            self.repo.crear_child_profile(cuenta.id, f"Hijo {i}")
            for i in range(1, 3)
        ]
        self.assertEqual(cuenta.email, "adulto@ejemplo.com")
        self.assertEqual([p.display_name for p in perfiles], ["Hijo 1", "Hijo 2"])
        self.assertEqual(len(self.repo.listar_child_profiles(cuenta.id)), 2)

    def test_un_entitlement_del_account_habilita_a_todos_sus_perfiles(self):
        cuenta = self.repo.crear_account("adulto@example.com")
        ana = self.repo.crear_child_profile(cuenta.id, "Ana")
        beto = self.repo.crear_child_profile(cuenta.id, "Beto")
        self.assertFalse(self.repo.tiene_entitlement_por_perfil(ana.id, "tortuscript-premium"))
        self.repo.establecer_entitlement(cuenta.id, "tortuscript-premium", True, "payment")
        self.assertTrue(self.repo.tiene_entitlement_por_perfil(ana.id, "tortuscript-premium"))
        self.assertTrue(self.repo.tiene_entitlement_por_perfil(beto.id, "tortuscript-premium"))

    def test_no_se_puede_superar_el_limite_de_perfiles(self):
        cuenta = self.repo.crear_account("adulto@example.com")
        for i in range(MAX_CHILD_PROFILES):
            self.repo.crear_child_profile(cuenta.id, f"Perfil {i}")
        with self.assertRaises(CuentaError):
            self.repo.crear_child_profile(cuenta.id, "Perfil extra")

    def test_no_acepta_email_invalido(self):
        with self.assertRaises(CuentaError):
            self.repo.crear_account("no-es-un-email")

    def test_no_duplica_cuenta_ni_nombre_de_perfil(self):
        cuenta = self.repo.crear_account("adulto@example.com")
        with self.assertRaises(CuentaError):
            self.repo.crear_account("ADULTO@example.com")
        self.repo.crear_child_profile(cuenta.id, "Ana")
        with self.assertRaises(CuentaError):
            self.repo.crear_child_profile(cuenta.id, " Ana ")

    def test_nombre_de_perfil_no_duplica_por_mayusculas(self):
        cuenta = self.repo.crear_account("adulto@example.com")
        self.repo.crear_child_profile(cuenta.id, "Ana")
        with self.assertRaises(CuentaError):
            self.repo.crear_child_profile(cuenta.id, "ANA")

    def test_id_de_perfil_es_opaco_y_unico(self):
        cuenta = self.repo.crear_account("adulto@example.com")
        ana = self.repo.crear_child_profile(cuenta.id, "Ana")
        beto = self.repo.crear_child_profile(cuenta.id, "Beto")
        self.assertRegex(ana.id, r"^child_[a-f0-9]{24}$")
        self.assertRegex(beto.id, r"^child_[a-f0-9]{24}$")
        self.assertNotEqual(ana.id, beto.id)

    def test_nombre_equivalente_por_unicode_nfkc_no_se_duplica(self):
        cuenta = self.repo.crear_account("adulto@example.com")
        self.repo.crear_child_profile(cuenta.id, "Ana")
        with self.assertRaises(CuentaError):
            self.repo.crear_child_profile(cuenta.id, "Ａna")

    def test_esquema_v2_migra_a_v3_y_conserva_perfiles(self):
        legacy_path = self.tmp / "legacy.sqlite3"
        with sqlite3.connect(legacy_path) as con:
            con.executescript("""
                CREATE TABLE schema_version (version INTEGER NOT NULL);
                INSERT INTO schema_version(version) VALUES (2);
                CREATE TABLE accounts (
                    id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'adult'
                );
                CREATE TABLE child_profiles (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                    display_name TEXT NOT NULL, created_at TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(account_id, display_name)
                );
                INSERT INTO accounts(id,email,created_at,role)
                    VALUES ('acc_legacy','legacy@example.com','2026-01-01','adult');
                INSERT INTO child_profiles(id,account_id,display_name,created_at,active)
                    VALUES ('child_legacy','acc_legacy','Ana','2026-01-02',1);
            """)
        migrated = CuentaRepository(legacy_path)
        migrated.ensure_schema()
        with sqlite3.connect(legacy_path) as con:
            version = con.execute("SELECT version FROM schema_version").fetchone()[0]
            columns = {row[1] for row in con.execute("PRAGMA table_info(child_profiles)")}
            profile = con.execute(
                "SELECT id,display_name,display_name_key FROM child_profiles"
            ).fetchone()
            indexes = {row[1] for row in con.execute("PRAGMA index_list(child_profiles)")}
        self.assertEqual(version, 3)
        self.assertIn("display_name_key", columns)
        self.assertEqual(profile, ("child_legacy", "Ana", "ana"))
        self.assertIn("idx_child_profiles_account_name_key", indexes)

    def test_migracion_rechaza_alias_historicos_equivalentes_sin_perder_filas(self):
        legacy_path = self.tmp / "legacy-duplicados.sqlite3"
        with sqlite3.connect(legacy_path) as con:
            con.executescript("""
                CREATE TABLE schema_version (version INTEGER NOT NULL);
                INSERT INTO schema_version(version) VALUES (2);
                CREATE TABLE accounts (
                    id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE child_profiles (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                    display_name TEXT NOT NULL, created_at TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(account_id, display_name)
                );
                INSERT INTO accounts(id,email,created_at)
                    VALUES ('acc_legacy','legacy@example.com','2026-01-01');
                INSERT INTO child_profiles(id,account_id,display_name,created_at,active)
                    VALUES ('child_1','acc_legacy','Ana','2026-01-02',1);
                INSERT INTO child_profiles(id,account_id,display_name,created_at,active)
                    VALUES ('child_2','acc_legacy','ANA','2026-01-03',1);
            """)
        migrated = CuentaRepository(legacy_path)
        with self.assertRaisesRegex(CuentaError, "nombres equivalentes"):
            migrated.ensure_schema()
        with sqlite3.connect(legacy_path) as con:
            profiles = con.execute(
                "SELECT id,display_name FROM child_profiles ORDER BY id"
            ).fetchall()
            columns = {row[1] for row in con.execute("PRAGMA table_info(child_profiles)")}
            account_columns = {row[1] for row in con.execute("PRAGMA table_info(accounts)")}
        self.assertEqual(profiles, [("child_1", "Ana"), ("child_2", "ANA")])
        self.assertNotIn("display_name_key", columns)
        self.assertNotIn("role", account_columns)

    def test_esquema_futuro_se_rechaza_sin_alterar_tablas_existentes(self):
        future_path = self.tmp / "future.sqlite3"
        with sqlite3.connect(future_path) as con:
            con.executescript("""
                CREATE TABLE schema_version (version INTEGER NOT NULL);
                INSERT INTO schema_version(version) VALUES (3);
                INSERT INTO schema_version(version) VALUES (4);
                CREATE TABLE accounts (
                    id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE child_profiles (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                    display_name TEXT NOT NULL, created_at TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(account_id, display_name)
                );
            """)
        with self.assertRaisesRegex(CuentaError, "no compatible"):
            CuentaRepository(future_path).ensure_schema()
        with sqlite3.connect(future_path) as con:
            account_columns = {row[1] for row in con.execute("PRAGMA table_info(accounts)")}
            profile_columns = {row[1] for row in con.execute("PRAGMA table_info(child_profiles)")}
            tables = {row[0] for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
        self.assertNotIn("role", account_columns)
        self.assertNotIn("display_name_key", profile_columns)
        self.assertNotIn("subscriptions", tables)
        self.assertNotIn("entitlements", tables)

    def test_esquema_es_reproducible(self):
        self.repo.ensure_schema()
        self.repo.ensure_schema()
        cuenta = self.repo.crear_account("adulto@example.com")
        self.assertIsNotNone(self.repo.obtener_account(cuenta.id))


if __name__ == "__main__":
    unittest.main()
