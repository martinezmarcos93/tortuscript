"""Regresiones de backup/restauración SQLite sin datos reales."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tortuscript.respaldo_sqlite import ErrorRespaldo, crear_respaldo, restaurar_respaldo


class RespaldoSQLiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "origen.sqlite3"
        with sqlite3.connect(self.db) as con:
            con.execute("CREATE TABLE progreso (perfil TEXT PRIMARY KEY, xp INTEGER NOT NULL)")
            con.execute("INSERT INTO progreso VALUES ('perfil-prueba', 125)")

    def tearDown(self):
        self.tmp.cleanup()

    def _xp(self, path):
        with sqlite3.connect(path) as con:
            return con.execute("SELECT xp FROM progreso WHERE perfil='perfil-prueba'").fetchone()[0]

    def test_crea_respaldo_consistente_y_contenido(self):
        destino = self.root / "backup.sqlite3"
        resultado = crear_respaldo(self.db, destino)
        self.assertEqual(resultado, destino)
        self.assertEqual(self._xp(destino), 125)

    def test_no_sobrescribe_respaldo_existente(self):
        destino = self.root / "backup.sqlite3"
        destino.write_bytes(b"no sobrescribir")
        with self.assertRaisesRegex(ErrorRespaldo, "ya existe"):
            crear_respaldo(self.db, destino)
        self.assertEqual(destino.read_bytes(), b"no sobrescribir")

    def test_rechaza_origen_ausente(self):
        with self.assertRaisesRegex(ErrorRespaldo, "no existe"):
            crear_respaldo(self.root / "ausente.sqlite3", self.root / "backup.sqlite3")

    def test_rechaza_respaldo_corrupto_sin_tocar_destino(self):
        corrupto = self.root / "corrupto.sqlite3"
        corrupto.write_bytes(b"esto no es sqlite")
        destino = self.root / "destino.sqlite3"
        with self.assertRaises(ErrorRespaldo):
            restaurar_respaldo(corrupto, destino)
        self.assertFalse(destino.exists())

    def test_restaurar_requiere_confirmacion_para_sobrescribir(self):
        backup = crear_respaldo(self.db, self.root / "backup.sqlite3")
        destino = self.root / "destino.sqlite3"
        with sqlite3.connect(destino) as con:
            con.execute("CREATE TABLE anterior (valor TEXT)")
            con.execute("INSERT INTO anterior VALUES ('conservar')")
        with self.assertRaisesRegex(ErrorRespaldo, "confirmá explícitamente"):
            restaurar_respaldo(backup, destino)
        with sqlite3.connect(destino) as con:
            self.assertEqual(con.execute("SELECT valor FROM anterior").fetchone()[0], "conservar")

    def test_restauracion_confirmada_reemplaza_base_de_forma_consistente(self):
        backup = crear_respaldo(self.db, self.root / "backup.sqlite3")
        destino = self.root / "destino.sqlite3"
        with sqlite3.connect(destino) as con:
            con.execute("CREATE TABLE anterior (valor TEXT)")
        restaurar_respaldo(backup, destino, permitir_sobrescritura=True)
        self.assertEqual(self._xp(destino), 125)
        with sqlite3.connect(destino) as con:
            tablas = {fila[0] for fila in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
        self.assertIn("progreso", tablas)
        self.assertNotIn("anterior", tablas)

    def test_no_acepta_mismo_archivo_como_origen_y_destino(self):
        with self.assertRaisesRegex(ErrorRespaldo, "diferente"):
            crear_respaldo(self.db, self.db)
        with self.assertRaisesRegex(ErrorRespaldo, "diferentes"):
            restaurar_respaldo(self.db, self.db)


if __name__ == "__main__":
    unittest.main()
