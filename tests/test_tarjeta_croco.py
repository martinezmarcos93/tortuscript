"""La tarjeta «Siguiente paso: Croco-Script» del inicio y el botón del menú de cuenta (ADR-037)."""
import unittest

from tests.test_federacion_respuestas import _Base
from tortuscript.progreso_childprofile import ProgresoChildProfile
from tortuscript.progreso_contrato import nuevo_snapshot


class TestTarjetaCroco(_Base):
    def setUp(self):
        super().setUp()
        self.c.post("/cuenta/perfil", json={"perfil_id": self.perfil}, headers={"X-Tortu-CSRF": self.csrf})
        # Un perfil nuevo pasa primero por la bienvenida: se la damos por hecha para llegar al inicio.
        ProgresoChildProfile(self.tmp / "progreso_perfiles").guardar(nuevo_snapshot(self.perfil, {"config": {"onboarding": True}}))

    def inicio(self):
        return self.c.get("/", follow_redirects=True).get_data(as_text=True)

    def test_sin_acceso_invita_a_conocerlo_y_lleva_al_plan(self):
        pagina = self.inicio()
        self.assertIn('id="siguiente-paso-croco"', pagina)
        self.assertIn("Más adelante: Croco-Script", pagina)
        self.assertIn("16 años o más", pagina)
        self.assertIn('href="/cuenta/suscripcion#plan-croco-script"', pagina)
        self.assertNotIn('href="/cuenta/ir/croco-script"', pagina)          # ni en la tarjeta ni en el menú
        self.assertIn("Conocer Croco-Script", pagina)

    def test_con_acceso_entra_directo(self):
        self.dar_acceso()
        pagina = self.inicio()
        self.assertIn("Entrar a Croco-Script", pagina)
        self.assertIn('href="/cuenta/ir/croco-script"', pagina)
        self.assertNotIn("Un adulto de la familia puede activarlo", pagina)

    def test_el_acceso_se_decide_en_servidor_y_vence(self):
        self.dar_acceso()
        self.dar_acceso(False)
        self.assertNotIn('href="/cuenta/ir/croco-script"', self.inicio())

    def test_un_admin_entra_sin_pagar(self):
        self.cuentas.establecer_role(self.cuenta_id, "admin")
        self.assertIn('href="/cuenta/ir/croco-script"', self.inicio())

    def test_sin_el_puente_configurado_no_hay_tarjeta_ni_boton(self):
        self.app.config["FEDERACION"] = {}
        pagina = self.inicio()
        self.assertNotIn("siguiente-paso-croco", pagina)
        self.assertNotIn("Croco-Script", pagina)


if __name__ == "__main__":
    unittest.main()
