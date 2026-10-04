"""Pagos (ADR-032): eventos del proveedor → suscripción → acceso. Sin proveedor real ni cobros."""
import json
import shutil
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tortuscript import pagos
from tortuscript.acceso import AccesoProducto
from tortuscript.cuentas import CuentaRepository
from tortuscript.pagos import APLICADO, DUPLICADO, OBSOLETO, REVISION, EventoPago, PagoError, ServicioPagos

T0 = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
PREMIUM = "tortuscript-premium"


def dias(n):
    return T0 + timedelta(days=n)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        db = self.tmp / "cuentas.sqlite3"
        self.cuentas = CuentaRepository(db)
        self.cuentas.ensure_schema()
        self.pagos = ServicioPagos(db)
        self.pagos.ensure_schema()
        self.cuenta = self.cuentas.crear_account("familia@example.com")
        self.ana = self.cuentas.crear_child_profile(self.cuenta.id, "Ana")
        self.bruno = self.cuentas.crear_child_profile(self.cuenta.id, "Bruno")
        self.acceso = AccesoProducto(self.cuentas)
        self.n = 0

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def evento(self, tipo, ocurrido=T0, periodo_hasta=None, **cambios):
        self.n += 1
        datos = dict(proveedor="prueba", id=f"evt_{self.n}", tipo=tipo, cuenta_id=self.cuenta.id, producto=PREMIUM,
                     suscripcion="sub_1", ocurrido=ocurrido, periodo_hasta=periodo_hasta)
        datos.update(cambios)
        return EventoPago(**datos)

    def tiene(self, cuando, perfil=None):
        """¿Tiene acceso premium en ese momento? (el vencimiento se evalúa contra el reloj)"""
        from unittest import mock
        from tortuscript import cuentas
        with mock.patch.object(cuentas, "_ahora", return_value=cuando.isoformat(timespec="seconds")):
            return self.acceso.puede_acceder((perfil or self.ana).id, PREMIUM)

    def estado(self):
        return self.pagos.listar_suscripciones(self.cuenta.id)[0]["estado"]


class TestCicloDeVida(Base):
    def test_terminar_el_checkout_no_da_acceso_y_el_pago_si_a_todos_los_perfiles(self):
        self.assertEqual(self.pagos.aplicar(self.evento("checkout_completed"), ahora=T0).estado, APLICADO)
        self.assertEqual(self.estado(), "incomplete")
        self.assertFalse(self.tiene(T0))

        r = self.pagos.aplicar(self.evento("payment_succeeded", dias(0), dias(30)), ahora=T0)
        self.assertEqual((r.estado, self.estado()), (APLICADO, "active"))
        self.assertTrue(self.tiene(dias(1)))
        self.assertTrue(self.tiene(dias(1), self.bruno))                              # una suscripción, toda la familia
        # El acceso es del producto pagado, no de otro.
        self.assertFalse(self.acceso.puede_acceder(self.ana.id, "croco-script"))

    def test_sin_renovacion_el_acceso_vence_solo_tras_el_periodo_y_la_gracia(self):
        self.pagos.aplicar(self.evento("payment_succeeded", dias(0), dias(30)), ahora=T0)
        self.assertTrue(self.tiene(dias(30) + timedelta(days=pagos.DIAS_DE_GRACIA - 1)))
        self.assertFalse(self.tiene(dias(30) + timedelta(days=pagos.DIAS_DE_GRACIA, seconds=1)))

    def test_renovacion_extiende_el_acceso(self):
        self.pagos.aplicar(self.evento("payment_succeeded", dias(0), dias(30)), ahora=T0)
        self.pagos.aplicar(self.evento("payment_succeeded", dias(30), dias(60)), ahora=dias(30))
        self.assertTrue(self.tiene(dias(59)))
        self.assertEqual(len(self.pagos.listar_suscripciones(self.cuenta.id)), 1)

    def test_pago_rechazado_mantiene_el_acceso_solo_durante_la_gracia(self):
        self.pagos.aplicar(self.evento("payment_succeeded", dias(0), dias(30)), ahora=T0)
        self.pagos.aplicar(self.evento("payment_failed", dias(30)), ahora=dias(30))
        self.assertEqual(self.estado(), "past_due")
        self.assertTrue(self.tiene(dias(33)))
        self.assertFalse(self.tiene(dias(38)))
        # Si el reintento del proveedor cobra, vuelve a estar al día.
        self.pagos.aplicar(self.evento("payment_succeeded", dias(34), dias(60)), ahora=dias(34))
        self.assertEqual(self.estado(), "active")
        self.assertTrue(self.tiene(dias(50)))

    def test_cancelar_respeta_lo_pagado_sin_gracia_y_no_borra_nada(self):
        self.pagos.aplicar(self.evento("payment_succeeded", dias(0), dias(30)), ahora=T0)
        self.pagos.aplicar(self.evento("subscription_canceled", dias(10)), ahora=dias(10))
        self.assertEqual(self.estado(), "canceled")
        self.assertTrue(self.tiene(dias(29)))
        self.assertFalse(self.tiene(dias(30) + timedelta(seconds=1)))
        self.assertEqual(len(self.cuentas.listar_child_profiles(self.cuenta.id)), 2)      # los perfiles siguen

    def test_cancelar_con_el_periodo_ya_vencido_corta_el_acceso(self):
        self.pagos.aplicar(self.evento("payment_succeeded", dias(0), dias(30)), ahora=T0)
        self.pagos.aplicar(self.evento("subscription_canceled", dias(33)), ahora=dias(33))
        self.assertFalse(self.tiene(dias(33)))

    def test_reembolso_corta_el_acceso_de_inmediato(self):
        self.pagos.aplicar(self.evento("payment_succeeded", dias(0), dias(30)), ahora=T0)
        self.pagos.aplicar(self.evento("refund", dias(2)), ahora=dias(2))
        self.assertEqual(self.estado(), "refunded")
        self.assertFalse(self.tiene(dias(2)))

    def test_volver_a_pagar_tras_cancelar_reactiva(self):
        self.pagos.aplicar(self.evento("payment_succeeded", dias(0), dias(30)), ahora=T0)
        self.pagos.aplicar(self.evento("subscription_canceled", dias(10)), ahora=dias(10))
        self.pagos.aplicar(self.evento("payment_succeeded", dias(40), dias(70)), ahora=dias(40))
        self.assertEqual(self.estado(), "active")
        self.assertTrue(self.tiene(dias(60)))

    def test_actualizacion_cambia_el_fin_de_periodo_de_una_suscripcion_activa(self):
        self.pagos.aplicar(self.evento("payment_succeeded", dias(0), dias(30)), ahora=T0)
        self.pagos.aplicar(self.evento("subscription_updated", dias(5), dias(365)), ahora=dias(5))
        self.assertTrue(self.tiene(dias(300)))
        # …pero no revive una cancelada.
        self.pagos.aplicar(self.evento("subscription_canceled", dias(6)), ahora=dias(6))
        self.pagos.aplicar(self.evento("subscription_updated", dias(7), dias(900)), ahora=dias(7))
        self.assertEqual(self.estado(), "canceled")
        self.assertFalse(self.tiene(dias(901)))


class TestIdempotenciaYOrden(Base):
    def test_el_mismo_evento_dos_veces_se_aplica_una(self):
        pago = self.evento("payment_succeeded", dias(0), dias(30))
        self.assertEqual(self.pagos.aplicar(pago, ahora=T0).estado, APLICADO)
        self.pagos.aplicar(self.evento("refund", dias(1)), ahora=dias(1))
        # El proveedor reenvía el pago viejo: no puede devolver el acceso reembolsado.
        self.assertEqual(self.pagos.aplicar(pago, ahora=dias(2)).estado, DUPLICADO)
        self.assertFalse(self.tiene(dias(2)))

    def test_evento_viejo_que_llega_tarde_no_pisa_el_estado_nuevo(self):
        self.pagos.aplicar(self.evento("payment_succeeded", dias(0), dias(30)), ahora=T0)
        self.pagos.aplicar(self.evento("refund", dias(5)), ahora=dias(5))
        atrasado = self.evento("payment_succeeded", dias(3), dias(60))               # ocurrió antes del reembolso
        self.assertEqual(self.pagos.aplicar(atrasado, ahora=dias(6)).estado, OBSOLETO)
        self.assertEqual(self.estado(), "refunded")
        self.assertFalse(self.tiene(dias(6)))
        self.assertEqual(self.pagos.aplicar(atrasado, ahora=dias(7)).estado, DUPLICADO)   # y quedó registrado

    def test_entregas_simultaneas_del_mismo_evento_aplican_una_sola(self):
        pago = self.evento("payment_succeeded", dias(0), dias(30))
        resultados = []

        def entregar():
            resultados.append(ServicioPagos(self.tmp / "cuentas.sqlite3").aplicar(pago, ahora=T0).estado)

        hilos = [threading.Thread(target=entregar) for _ in range(8)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        self.assertEqual(sorted(resultados), [APLICADO] + [DUPLICADO] * 7)

    def test_un_fallo_a_mitad_de_camino_no_deja_el_evento_registrado_ni_acceso_a_medias(self):
        from unittest import mock
        pago = self.evento("payment_succeeded", dias(0), dias(30))
        real = ServicioPagos._aplicar_en_transaccion

        def falla_despues_de_aplicar(servicio, con, e, ahora):
            real(servicio, con, e, ahora)
            raise RuntimeError("se cortó la luz")

        with mock.patch.object(ServicioPagos, "_aplicar_en_transaccion", falla_despues_de_aplicar), \
                self.assertRaises(RuntimeError):
            self.pagos.aplicar(pago, ahora=T0)
        self.assertFalse(self.tiene(dias(1)))
        self.assertEqual(self.pagos.listar_suscripciones(self.cuenta.id), [])
        # El reintento del proveedor ahora sí se aplica.
        self.assertEqual(self.pagos.aplicar(pago, ahora=T0).estado, APLICADO)
        self.assertTrue(self.tiene(dias(1)))


class TestRevision(Base):
    def test_eventos_inconsistentes_quedan_en_revision_y_no_dan_acceso(self):
        otra = self.cuentas.crear_account("otra@example.com")
        self.pagos.aplicar(self.evento("payment_succeeded", dias(0), dias(30)), ahora=T0)
        casos = (
            self.evento("payment_succeeded", dias(1), dias(30), cuenta_id="acc_inexistente", suscripcion="sub_x"),
            self.evento("payment_succeeded", dias(1), dias(30), producto="todo-gratis", suscripcion="sub_y"),
            self.evento("payment_succeeded", dias(1), None, suscripcion="sub_z"),                 # sin período
            self.evento("refund", dias(1), suscripcion="sub_desconocida"),
            self.evento("payment_succeeded", dias(1), dias(60), cuenta_id=otra.id),              # sub de otra cuenta
            self.evento("payment_succeeded", dias(1), dias(60), producto="croco-script"),        # sub de otro producto
        )
        for e in casos:
            with self.subTest(e=e.id):
                self.assertEqual(self.pagos.aplicar(e, ahora=dias(1)).estado, REVISION)
        self.assertEqual(len(self.pagos.listar_en_revision()), len(casos))
        self.assertFalse(self.cuentas.tiene_entitlement(otra.id, PREMIUM))
        self.assertFalse(self.cuentas.tiene_entitlement(self.cuenta.id, "croco-script"))
        self.assertEqual(self.estado(), "active")                                     # la suscripción buena no se tocó
        # Lo que quedó en revisión no guarda datos de pago ni el cuerpo del evento.
        columnas = {r[1] for r in sqlite3.connect(self.tmp / "cuentas.sqlite3").execute("PRAGMA table_info(payment_events)")}
        self.assertFalse(columnas & {"payload", "body", "card", "amount"})

    def test_un_acceso_concedido_a_mano_no_lo_recorta_un_evento_de_pago(self):
        self.cuentas.establecer_entitlement(self.cuenta.id, PREMIUM, True, "soporte")
        self.pagos.aplicar(self.evento("payment_succeeded", dias(0), dias(30)), ahora=T0)
        self.pagos.aplicar(self.evento("refund", dias(1)), ahora=dias(1))
        self.assertTrue(self.tiene(dias(400)))


class TestEsquema(Base):
    def test_ensure_schema_es_repetible_y_convive_con_el_de_cuentas(self):
        for _ in range(2):
            self.pagos.ensure_schema()
            self.cuentas.ensure_schema()
        self.pagos.aplicar(self.evento("payment_succeeded", dias(0), dias(30)), ahora=T0)
        self.cuentas.ensure_schema()
        self.assertTrue(self.tiene(dias(1)))

    def test_sin_esquema_de_cuentas_falla_con_mensaje_claro(self):
        with self.assertRaises(PagoError):
            ServicioPagos(self.tmp / "vacia.sqlite3").ensure_schema()

    def test_una_base_anterior_gana_el_vencimiento_sin_perder_entitlements(self):
        db = self.tmp / "vieja.sqlite3"
        viejo = CuentaRepository(db)
        viejo.ensure_schema()
        cuenta = viejo.crear_account("vieja@example.com")
        viejo.establecer_entitlement(cuenta.id, PREMIUM, True, "soporte")
        con = sqlite3.connect(db)
        con.execute("ALTER TABLE entitlements DROP COLUMN expires_at")                # como la creó la versión anterior
        con.commit()
        con.close()
        viejo.ensure_schema()
        self.assertTrue(viejo.tiene_entitlement(cuenta.id, PREMIUM))


class TestHerramientaDeRevision(Base):
    def _correr(self, *args):
        import contextlib
        import io
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "herramientas"))
        import revisar_pagos
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(salida):
            codigo = revisar_pagos.main(["--db", str(self.tmp / "cuentas.sqlite3"), *args])
        return codigo, salida.getvalue()

    def test_sin_nada_pendiente_sale_con_cero_y_con_revision_con_dos(self):
        self.pagos.aplicar(self.evento("payment_succeeded", dias(0), dias(30)), ahora=T0)
        codigo, texto = self._correr("--suscripciones")
        self.assertEqual(codigo, 0)
        self.assertIn("Eventos en revisión: 0", texto)
        self.assertIn("active", texto)
        self.pagos.aplicar(self.evento("refund", dias(1), suscripcion="sub_fantasma"), ahora=dias(1))
        codigo, texto = self._correr()
        self.assertEqual(codigo, 2)
        self.assertIn("suscripción que no se conoce", texto)
        self.assertNotIn("familia@example.com", texto)              # identificadores opacos, sin correos

    def test_base_inexistente_es_un_error_claro(self):
        import contextlib
        import io
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "herramientas"))
        import revisar_pagos
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(revisar_pagos.main(["--db", str(self.tmp / "no-existe.sqlite3")]), 1)


class TestFirma(unittest.TestCase):
    CUERPO = b'{"id": "evt_1"}'

    def test_firma_valida_reciente_pasa(self):
        ahora = T0
        pagos.verificar_firma("secreto", self.CUERPO, pagos.firmar("secreto", self.CUERPO, int(ahora.timestamp())), ahora)

    def test_se_rechaza_todo_lo_demas(self):
        t = int(T0.timestamp())
        buena = pagos.firmar("secreto", self.CUERPO, t)
        casos = {
            "otro secreto": ("otro", self.CUERPO, buena, T0),
            "cuerpo alterado": ("secreto", self.CUERPO + b" ", buena, T0),
            "reenvío viejo": ("secreto", self.CUERPO, buena, T0 + timedelta(seconds=pagos.TOLERANCIA_FIRMA_SEGUNDOS + 1)),
            "momento cambiado": ("secreto", self.CUERPO, buena.replace(f"t={t}", f"t={t + 1}"), T0),
            "sin firma": ("secreto", self.CUERPO, "", T0),
            "cabecera ausente": ("secreto", self.CUERPO, None, T0),
            "basura": ("secreto", self.CUERPO, "t=abc,v1=zzz", T0),
            "sin secreto configurado": ("", self.CUERPO, pagos.firmar("", self.CUERPO, t), T0),
        }
        for nombre, args in casos.items():
            with self.subTest(nombre), self.assertRaises(PagoError):
                pagos.verificar_firma(*args)


class TestFormato(unittest.TestCase):
    def _cuerpo(self, **cambios):
        datos = {"id": "evt_1", "tipo": "payment_succeeded", "cuenta": "acc_1", "producto": PREMIUM,
                 "suscripcion": "sub_1", "ocurrido": "2026-11-01T12:00:00Z", "periodo_hasta": "2026-12-01T12:00:00+00:00"}
        datos.update(cambios)
        return json.dumps({k: v for k, v in datos.items() if v is not ...}).encode()

    def test_evento_bien_formado(self):
        e = pagos.ADAPTADORES["prueba"](self._cuerpo())
        self.assertEqual((e.proveedor, e.tipo, e.ocurrido, e.periodo_hasta),
                         ("prueba", "payment_succeeded", T0, datetime(2026, 12, 1, 12, 0, tzinfo=timezone.utc)))
        self.assertIsNone(pagos.ADAPTADORES["prueba"](self._cuerpo(periodo_hasta=None)).periodo_hasta)

    def test_eventos_mal_formados_se_rechazan(self):
        malos = (b"{no json", b"[]", b"\xff\xfe", self._cuerpo(tipo="regalo"), self._cuerpo(id=""), self._cuerpo(id=7),
                 self._cuerpo(cuenta=["x"]), self._cuerpo(ocurrido="ayer"), self._cuerpo(ocurrido="2026-11-01T12:00:00"),
                 self._cuerpo(periodo_hasta=5), self._cuerpo(suscripcion="x" * 201), self._cuerpo(producto=...))
        for cuerpo in malos:
            with self.subTest(cuerpo=cuerpo[:40]), self.assertRaises(PagoError):
                pagos.ADAPTADORES["prueba"](cuerpo)


if __name__ == "__main__":
    unittest.main()
