"""Tests de borde para practica.py."""
import unittest
from datetime import date, timedelta

from tortuscript import contenido, practica

CURSOS = contenido.todos_los_cursos()
HOY = date(2026, 9, 25)

def con_pasos(*pares, fecha="2026-09-20"):
    """Progreso con pasos terminados: pares = (leccion, [índices])."""
    p = {"lecciones": {}, "repaso": {}}
    for leccion_id, indices in pares:
        p["lecciones"][leccion_id] = {"pasos": {str(i): {"xp": 5, "perfecto": True, "fecha": fecha} for i in indices},
                                      "completada": True}
    return p

class TestPracticaBordes(unittest.TestCase):
    def test_vencimiento_exacto_toca_hoy(self):
        # Vence hace 5 días. HOY es 2026-09-25. 2026-09-20 + 5 = 2026-09-25.
        p = con_pasos(("hola-mundo", [1]), fecha="2026-09-20")
        # Por defecto, toca el día después (2026-09-21)
        # Vamos a programarlo para que venza exactamente HOY
        p["repaso"]["hola-mundo:1"] = {"caja": 1, "proximo": str(HOY)}
        
        candidatos = practica.candidatos(p, CURSOS, HOY)
        self.assertEqual(len(candidatos), 1)
        self.assertEqual(candidatos[0]["vencido"], 0)

    def test_vencimiento_ayer_no_toca_hoy(self):
        # Toca mañana
        p = con_pasos(("hola-mundo", [1]), fecha="2026-09-20")
        p["repaso"]["hola-mundo:1"] = {"caja": 1, "proximo": str(HOY + timedelta(days=1))}
        
        self.assertEqual(len(practica.candidatos(p, CURSOS, HOY)), 0)

    def test_tope_caja_5_intervalo_16(self):
        p = {}
        # Sube a caja 5
        for _ in range(4):
            practica.registrar(p, "l", 1, True, HOY)
        t = practica.registrar(p, "l", 1, True, HOY)
        
        self.assertEqual(t["caja"], 5)
        self.assertEqual(t["proximo"], str(HOY + timedelta(days=16)))
        
        # Otro acierto más: debe seguir en 5
        t = practica.registrar(p, "l", 1, True, HOY)
        self.assertEqual(t["caja"], 5)
        self.assertEqual(t["proximo"], str(HOY + timedelta(days=16)))

    def test_error_desde_caja_5_vuelve_a_1(self):
        p = {}
        # Caja 5
        for _ in range(5):
            practica.registrar(p, "l", 1, True, HOY)
        
        t = practica.registrar(p, "l", 1, False, HOY)
        self.assertEqual(t["caja"], 1)
        self.assertEqual(t["proximo"], str(HOY + timedelta(days=1)))

    def test_desempate_caja_y_paso(self):
        p = con_pasos(("hola-mundo", [1, 2]))
        # Mismo día de vencimiento (vencido = 9999 o igual)
        # Desempate: (-vencido, caja, paso)
        # Queremos: caja 1 vs caja 2 -> caja 1 debe ser elegida primero
        p["repaso"]["hola-mundo:1"] = {"caja": 1, "proximo": str(HOY)}
        p["repaso"]["hola-mundo:2"] = {"caja": 2, "proximo": str(HOY)}
        
        # candidatos los ordena, pero el `elegir` hace sort.
        # `elegir` hace: lista.sort(key=lambda c: (-c["vencido"], c["caja"], c["paso"]))
        # Como vencido es igual, sort por caja. Caja 1 < Caja 2.
        
        elegidas = practica.elegir(p, CURSOS, HOY, cantidad=2)
        self.assertEqual(elegidas, [("hola-mundo", 1), ("hola-mundo", 2)])

    def test_cantidad_menor_disponible(self):
        p = con_pasos(("hola-mundo", [1, 2, 3]))
        elegidas = practica.elegir(p, CURSOS, HOY, cantidad=2)
        self.assertEqual(len(elegidas), 2)

    def test_proximo_manda_sobre_fecha_paso(self):
        # Si tiene fecha de paso y fecha de proximo, proximo debe prevalecer
        p = con_pasos(("hola-mundo", [1]), fecha="2026-09-01")
        p["repaso"]["hola-mundo:1"] = {"caja": 1, "proximo": str(HOY + timedelta(days=5))}
        
        # HOY no debería tocar
        self.assertEqual(len(practica.candidatos(p, CURSOS, HOY)), 0)
        # Toca en 5 días
        self.assertEqual(len(practica.candidatos(p, CURSOS, HOY + timedelta(days=5))), 1)

    # --- NUENOS TESTS PARA MUTANTES ---

    def test_POR_SESION_y_MAX_POR_LECCION(self):
        p = con_pasos(
            ("hola-mundo", [1, 2]),
            ("texto-o-cuenta", [1, 2]),
            ("dos-lineas", [1, 2]),
            ("puntuacion", [1, 2])
        )
        for lec in ("hola-mundo", "texto-o-cuenta", "dos-lineas", "puntuacion"):
            for i in (1, 2):
                p["repaso"][f"{lec}:{i}"] = {"caja": 1, "proximo": str(HOY)}
            
        elegidas = practica.elegir(p, CURSOS, HOY, cantidad=6)
        self.assertEqual(len(elegidas), 6)
        
        counts = {}
        for lec, _ in elegidas:
            counts[lec] = counts.get(lec, 0) + 1
        for lec in counts:
            self.assertLessEqual(counts[lec], 2)

    def test_candidatos_fuera_de_rango(self):
        p = con_pasos(("hola-mundo", [1])) 
        p["lecciones"]["hola-mundo"]["pasos"]["10"] = {"xp": 5, "perfecto": True, "fecha": str(HOY)}
        
        candidatos = practica.candidatos(p, CURSOS, HOY)
        for c in candidatos:
            self.assertNotEqual(c["paso"], 10)
        self.assertEqual(len(candidatos), 1)
        self.assertEqual(candidatos[0]["paso"], 1)

    def test_caja_default_cero(self):
        p = con_pasos(("hola-mundo", [1]))
        candidatos = practica.candidatos(p, CURSOS, HOY)
        self.assertEqual(candidatos[0]["caja"], 0)
        
        p["repaso"]["hola-mundo:1"] = {"caja": 3, "proximo": str(HOY)}
        candidatos = practica.candidatos(p, CURSOS, HOY)
        self.assertEqual(candidatos[0]["caja"], 3)

    def test_vencido_exacto_y_min(self):
        p = con_pasos(("hola-mundo", [1]))
        p["repaso"]["hola-mundo:1"] = {"caja": 1, "proximo": str(HOY)}
        c = practica.candidatos(p, CURSOS, HOY)[0]
        self.assertEqual(c["vencido"], 0)
        
        p = con_pasos(("hola-mundo", [1]), fecha=None)
        p["lecciones"]["hola-mundo"]["pasos"]["1"].pop("fecha")
        
        c = practica.candidatos(p, CURSOS, HOY)[0]
        self.assertEqual(c["vencido"], 9999)

    def test_desempate_alfabetico(self):
        p = con_pasos(("hola-mundo", [1]), ("texto-o-cuenta", [1]))
        p["repaso"]["hola-mundo:1"] = {"caja": 1, "proximo": str(HOY)}
        p["repaso"]["texto-o-cuenta:1"] = {"caja": 1, "proximo": str(HOY)}
        
        elegidas = practica.elegir(p, CURSOS, HOY, cantidad=2)
        self.assertEqual(elegidas[0][0], "hola-mundo")
        self.assertEqual(elegidas[1][0], "texto-o-cuenta")

    def test_cantidad_elegir_bordes(self):
        p = con_pasos(("hola-mundo", [1, 2]))
        p["repaso"]["hola-mundo:1"] = {"caja": 1, "proximo": str(HOY)}
        p["repaso"]["hola-mundo:2"] = {"caja": 1, "proximo": str(HOY)}
        
        self.assertEqual(len(practica.elegir(p, CURSOS, HOY, cantidad=2)), 2)
        self.assertEqual(len(practica.elegir(p, CURSOS, HOY, cantidad=0)), 0)
        self.assertEqual(len(practica.elegir(p, CURSOS, HOY, cantidad=5)), 2)
        
        p = con_pasos(("hola-mundo", [1, 2, 3, 4]))
        for i in (1, 2, 3, 4):
            p["repaso"][f"hola-mundo:{i}"] = {"caja": 1, "proximo": str(HOY)}
        
        self.assertEqual(len(practica.elegir(p, CURSOS, HOY, cantidad=5)), 4)

if __name__ == "__main__":
    unittest.main()
