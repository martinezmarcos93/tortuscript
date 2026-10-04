"""Respaldo completo (cuentas + progreso): crear, verificar y restaurar sin perder nada."""
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from tortuscript import respaldo_datos, respaldo_sqlite
from tortuscript.auth import AuthRepository
from tortuscript.cuentas import CuentaRepository
from tortuscript.progreso_childprofile import ProgresoChildProfile
from tortuscript.progreso_contrato import nuevo_snapshot
from tortuscript.respaldo_datos import ErrorRespaldo

T1 = datetime(2026, 10, 3, 12, 0, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 10, 3, 12, 0, 1, tzinfo=timezone.utc)


class TestRespaldoDatos(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.instance = self.tmp / "instance"
        self.respaldos = self.tmp / "respaldos"
        cuentas = CuentaRepository(self.instance / "cuentas.sqlite3")
        cuentas.ensure_schema()
        AuthRepository(self.instance / "cuentas.sqlite3").ensure_schema()
        cuenta = cuentas.crear_account("familia@example.com")
        self.cuentas = cuentas
        self.ana = cuentas.crear_child_profile(cuenta.id, "Ana").id
        self.bruno = cuentas.crear_child_profile(cuenta.id, "Bruno").id
        self.store = ProgresoChildProfile(self.instance / "progreso_perfiles")
        self.store.guardar(nuevo_snapshot(self.ana, {"xp_total": 10}))
        self.store.guardar(nuevo_snapshot(self.ana, {"xp_total": 120}))        # deja además un .bak
        (self.instance / "progreso_perfiles" / "progreso_x.json.corrupto-1").write_text("basura", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _xp(self, instance, perfil):
        return ProgresoChildProfile(instance / "progreso_perfiles").cargar(perfil).data["xp_total"]

    def test_crear_incluye_base_y_progreso_vigente_y_nada_mas(self):
        antes = sorted(p.name for p in self.instance.rglob("*"))
        carpeta = respaldo_datos.crear(self.instance, self.respaldos, ahora=T1)
        self.assertEqual(carpeta.name, "respaldo-20261003-120000")
        self.assertEqual(sorted(p.relative_to(carpeta).as_posix() for p in carpeta.rglob("*") if p.is_file()),
                         ["MANIFIESTO.json", "cuentas.sqlite3", f"progreso_perfiles/progreso_{self.ana}.json"])
        resumen = respaldo_datos.verificar(carpeta)
        self.assertEqual((resumen["perfiles"], resumen["perfiles_con_progreso"], resumen["esquema_de_cuentas"]), (2, 1, 3))
        # El origen no cambia y no quedan carpetas a medias.
        self.assertEqual(sorted(p.name for p in self.instance.rglob("*")), antes)
        self.assertEqual([p.name for p in self.respaldos.iterdir()], [carpeta.name])
        self.assertEqual(respaldo_datos.listar(self.respaldos), [carpeta])

    def test_no_pisa_un_respaldo_existente(self):
        respaldo_datos.crear(self.instance, self.respaldos, ahora=T1)
        with self.assertRaises(ErrorRespaldo):
            respaldo_datos.crear(self.instance, self.respaldos, ahora=T1)

    def test_sin_base_o_dentro_del_progreso_se_rechaza(self):
        with self.assertRaises(ErrorRespaldo):
            respaldo_datos.crear(self.tmp / "vacia", self.respaldos)
        with self.assertRaises(ErrorRespaldo):
            respaldo_datos.crear(self.instance, self.instance / "progreso_perfiles" / "respaldos")

    def test_verificar_detecta_cualquier_alteracion(self):
        carpeta = respaldo_datos.crear(self.instance, self.respaldos, ahora=T1)
        progreso = carpeta / "progreso_perfiles" / f"progreso_{self.ana}.json"
        original = progreso.read_bytes()

        def alterado(accion):
            copia = self.tmp / "copia"
            shutil.rmtree(copia, ignore_errors=True)
            shutil.copytree(carpeta, copia)
            accion(copia)
            with self.assertRaises(ErrorRespaldo):
                respaldo_datos.verificar(copia)

        alterado(lambda c: (c / "progreso_perfiles" / progreso.name).write_bytes(original.replace(b"120", b"999")))
        alterado(lambda c: (c / "progreso_perfiles" / progreso.name).unlink())
        alterado(lambda c: (c / "extra.txt").write_text("x", encoding="utf-8"))
        alterado(lambda c: (c / "cuentas.sqlite3").write_bytes(b"no soy sqlite"))
        alterado(lambda c: (c / "MANIFIESTO.json").unlink())
        alterado(lambda c: (c / "MANIFIESTO.json").write_text("{", encoding="utf-8"))

    def test_verificar_rechaza_manifiesto_coherente_pero_con_datos_invalidos(self):
        """Hashes correctos no alcanzan: el contenido también tiene que ser un respaldo válido."""
        carpeta = respaldo_datos.crear(self.instance, self.respaldos, ahora=T1)

        def reescribir(nombre, contenido):
            copia = self.tmp / "copia"
            shutil.rmtree(copia, ignore_errors=True)
            shutil.copytree(carpeta, copia)
            archivo = copia / "progreso_perfiles" / nombre
            archivo.write_text(contenido, encoding="utf-8")
            m = json.loads((copia / "MANIFIESTO.json").read_text(encoding="utf-8"))
            m["archivos"] = {k: v for k, v in m["archivos"].items() if k == "cuentas.sqlite3"}
            for p in (copia / "progreso_perfiles").iterdir():
                m["archivos"][f"progreso_perfiles/{p.name}"] = {"sha256": respaldo_datos._sha256(p), "bytes": p.stat().st_size}
            (copia / "MANIFIESTO.json").write_text(json.dumps(m), encoding="utf-8")
            return copia

        valido = json.loads((carpeta / "progreso_perfiles" / f"progreso_{self.ana}.json").read_text(encoding="utf-8"))
        huerfano = dict(valido, profile_id="child_ffffffffffffffffffffffff")
        casos = (
            (f"progreso_{self.ana}.json", "{roto"),                                             # snapshot ilegible
            (f"progreso_{self.bruno}.json", json.dumps(valido)),                                # archivo de otro perfil
            ("progreso_child_ffffffffffffffffffffffff.json", json.dumps(huerfano)),             # perfil que no existe
        )
        for nombre, contenido in casos:
            with self.subTest(nombre=nombre), self.assertRaises(ErrorRespaldo):
                respaldo_datos.verificar(reescribir(nombre, contenido))

    def test_manifiesto_no_puede_nombrar_rutas_fuera_del_respaldo(self):
        carpeta = respaldo_datos.crear(self.instance, self.respaldos, ahora=T1)
        (carpeta / "progreso_perfiles" / "sub").mkdir()
        intruso = carpeta / "progreso_perfiles" / "sub" / "x.json"
        intruso.write_text("{}", encoding="utf-8")
        m = json.loads((carpeta / "MANIFIESTO.json").read_text(encoding="utf-8"))
        m["archivos"]["progreso_perfiles/sub/x.json"] = {"sha256": respaldo_datos._sha256(intruso), "bytes": 2}
        (carpeta / "MANIFIESTO.json").write_text(json.dumps(m), encoding="utf-8")
        with self.assertRaises(ErrorRespaldo):
            respaldo_datos.verificar(carpeta)

    def test_respaldo_de_version_futura_se_rechaza(self):
        carpeta = respaldo_datos.crear(self.instance, self.respaldos, ahora=T1)
        m = json.loads((carpeta / "MANIFIESTO.json").read_text(encoding="utf-8"))
        m["version"] = 2
        (carpeta / "MANIFIESTO.json").write_text(json.dumps(m), encoding="utf-8")
        with self.assertRaises(ErrorRespaldo):
            respaldo_datos.restaurar(carpeta, self.tmp / "otra")

    def test_restaurar_en_carpeta_vacia_reproduce_los_datos(self):
        carpeta = respaldo_datos.crear(self.instance, self.respaldos, ahora=T1)
        nueva = self.tmp / "otra-compu" / "instance"
        self.assertIsNone(respaldo_datos.restaurar(carpeta, nueva, ahora=T2))
        self.assertEqual(self._xp(nueva, self.ana), 120)
        perfiles = CuentaRepository(nueva / "cuentas.sqlite3").listar_child_profiles(
            self.cuentas.obtener_account_por_email("familia@example.com").id)
        self.assertEqual(sorted(p.display_name for p in perfiles), ["Ana", "Bruno"])
        self.assertFalse((nueva / "MANIFIESTO.json").exists())
        self.assertEqual([p.name for p in nueva.parent.iterdir()], ["instance"])       # sin carpetas temporales

    def test_restaurar_sobre_datos_exige_confirmacion_y_conserva_lo_anterior(self):
        carpeta = respaldo_datos.crear(self.instance, self.respaldos, ahora=T1)
        # Después del respaldo la familia siguió usando la app.
        self.store.guardar(nuevo_snapshot(self.ana, {"xp_total": 500}))
        self.store.guardar(nuevo_snapshot(self.bruno, {"xp_total": 7}))
        with self.assertRaises(ErrorRespaldo):
            respaldo_datos.restaurar(carpeta, self.instance)
        self.assertEqual(self._xp(self.instance, self.ana), 500)                       # intacto sin confirmación

        anterior = respaldo_datos.restaurar(carpeta, self.instance, confirmar=True, ahora=T2)
        self.assertEqual(self._xp(self.instance, self.ana), 120)
        self.assertIsNone(ProgresoChildProfile(self.instance / "progreso_perfiles").cargar(self.bruno))
        self.assertEqual(anterior.name, "instance.antes-de-restaurar-20261003-120001")
        self.assertEqual(self._xp(anterior, self.ana), 500)                             # nada se borró
        self.assertEqual(self._xp(anterior, self.bruno), 7)

    def test_respaldo_danado_no_toca_el_destino(self):
        carpeta = respaldo_datos.crear(self.instance, self.respaldos, ahora=T1)
        (carpeta / "cuentas.sqlite3").write_bytes(b"roto")
        with self.assertRaises(ErrorRespaldo):
            respaldo_datos.restaurar(carpeta, self.instance, confirmar=True, ahora=T2)
        self.assertEqual(self._xp(self.instance, self.ana), 120)
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), ["instance", "respaldos"])

    def test_si_falla_la_publicacion_los_datos_vuelven_a_su_lugar(self):
        carpeta = respaldo_datos.crear(self.instance, self.respaldos, ahora=T1)
        real = respaldo_datos.os.rename
        llamadas = []

        def rename(origen, destino):
            llamadas.append(Path(origen).name)
            if len(llamadas) == 2:                                   # falla al publicar lo restaurado
                raise OSError("disco lleno")
            return real(origen, destino)

        with mock.patch.object(respaldo_datos.os, "rename", rename), self.assertRaises(ErrorRespaldo):
            respaldo_datos.restaurar(carpeta, self.instance, confirmar=True, ahora=T2)
        self.assertEqual(self._xp(self.instance, self.ana), 120)
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), ["instance", "respaldos"])

    def test_la_base_se_respalda_consistente_con_una_conexion_abierta(self):
        import sqlite3
        con = sqlite3.connect(self.instance / "cuentas.sqlite3")
        con.execute("BEGIN")
        con.execute("UPDATE accounts SET role='admin'")              # transacción sin confirmar: no debe verse
        try:
            carpeta = respaldo_datos.crear(self.instance, self.respaldos, ahora=T1)
        finally:
            con.rollback()
            con.close()
        cuenta = CuentaRepository(carpeta / "cuentas.sqlite3").obtener_account_por_email("familia@example.com")
        self.assertEqual(cuenta.role, "adult")


class TestSinEnlacesDuros(unittest.TestCase):
    """Pendrives FAT/exFAT y algunos recursos de red no admiten link()."""

    def setUp(self):
        import sqlite3
        self.tmp = Path(tempfile.mkdtemp())
        self.db = self.tmp / "origen.sqlite3"
        with sqlite3.connect(self.db) as con:
            con.execute("CREATE TABLE t (x INTEGER)")
            con.execute("INSERT INTO t VALUES (7)")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_respaldo_y_restauracion_funcionan_y_siguen_sin_sobrescribir(self):
        import sqlite3
        with mock.patch.object(respaldo_sqlite.os, "link", side_effect=PermissionError("sin enlaces duros")):
            destino = respaldo_sqlite.crear_respaldo(self.db, self.tmp / "copia.sqlite3")
            with sqlite3.connect(destino) as con:
                self.assertEqual(con.execute("SELECT x FROM t").fetchone()[0], 7)
            with self.assertRaises(respaldo_sqlite.ErrorRespaldo):
                respaldo_sqlite.crear_respaldo(self.db, destino)
            restaurado = respaldo_sqlite.restaurar_respaldo(destino, self.tmp / "restaurada.sqlite3")
            with self.assertRaises(respaldo_sqlite.ErrorRespaldo):
                respaldo_sqlite.restaurar_respaldo(destino, restaurado)
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()),
                         ["copia.sqlite3", "origen.sqlite3", "restaurada.sqlite3"])     # sin temporales

    def test_carrera_sin_enlaces_duros_no_pisa_al_que_llego_antes(self):
        destino = self.tmp / "copia.sqlite3"

        def link(_origen, _destino):
            destino.write_text("de otro proceso", encoding="utf-8")   # aparece justo antes de publicar
            raise PermissionError("sin enlaces duros")

        with mock.patch.object(respaldo_sqlite.os, "link", link), self.assertRaises(respaldo_sqlite.ErrorRespaldo):
            respaldo_sqlite.crear_respaldo(self.db, destino)
        self.assertEqual(destino.read_text(encoding="utf-8"), "de otro proceso")


class TestHerramienta(unittest.TestCase):
    def test_crear_verificar_listar_y_restaurar_por_linea_de_comandos(self):
        import contextlib
        import io
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "herramientas"))
        import respaldar_datos
        with tempfile.TemporaryDirectory() as d:
            datos = Path(d)
            cuentas = CuentaRepository(datos / "instance" / "cuentas.sqlite3")
            cuentas.ensure_schema()
            base = ["--datos", str(datos)]
            salida = io.StringIO()
            with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(salida):
                self.assertEqual(respaldar_datos.main(base + ["crear"]), 0)
                carpeta = respaldo_datos.listar(datos / "respaldos")[0]
                self.assertEqual(respaldar_datos.main(base + ["listar"]), 0)
                self.assertEqual(respaldar_datos.main(base + ["verificar", str(carpeta)]), 0)
                self.assertEqual(respaldar_datos.main(base + ["restaurar", str(carpeta)]), 1)       # falta confirmar
                self.assertEqual(respaldar_datos.main(base + ["restaurar", str(carpeta), "--confirmar"]), 0)
                self.assertEqual(respaldar_datos.main(base + ["verificar", str(datos)]), 1)
            texto = salida.getvalue()
            self.assertIn("Respaldo creado y verificado", texto)
            self.assertIn("confirmá explícitamente", texto)
            self.assertIn("antes-de-restaurar", texto)


if __name__ == "__main__":
    unittest.main()
