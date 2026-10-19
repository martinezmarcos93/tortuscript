import unittest
from datetime import date
from tortuscript import logros

class TestLogros(unittest.TestCase):
    def setUp(self):
        self.p_vacio = {
            "lecciones": {},
            "ejercicios": {},
            "xp_total": 0,
            "proyectos": {},
            "logros": {},
            "avisos": []
        }
        # Progreso que se usa para avisos en revisar()
        self.p_revisar = {
            "lecciones": {},
            "ejercicios": {},
            "xp_total": 0,
            "proyectos": {},
            "logros": {},
            "avisos": []
        }
        self.resumen_vacio = {
            "pasos_hechos": 0,
            "hechas_ids": set(),
            "perfectas": 0,
            "cursos": {},
            "estrellas3": 0,
            "nivel": 0,
            "proyectos": 0
        }

    def test_logros_condiciones_bordes(self):
        # Ayudante para crear resumen básico
        def base_r():
            return {
                "pasos_hechos": 0,
                "hechas_ids": set(),
                "perfectas": 0,
                "cursos": {"primeros-pasos": (0, 10)},
                "estrellas3": 0,
                "nivel": 0,
                "proyectos": 0
            }

        # Subtests para cada logro (valor justo debajo / valor en borde)
        
        # 1. primer-paso (pasos >= 1)
        with self.subTest(logro="primer-paso"):
            r = base_r(); r["pasos_hechos"] = 0
            self.assertFalse(logros.LOGROS[0][4](self.p_vacio, r))
            r["pasos_hechos"] = 1
            self.assertTrue(logros.LOGROS[0][4](self.p_vacio, r))

        # 2. primera-leccion (hechas >= 1)
        with self.subTest(logro="primera-leccion"):
            r = base_r(); r["hechas_ids"] = set()
            self.assertFalse(logros.LOGROS[1][4](self.p_vacio, r))
            r["hechas_ids"] = {"lec1"}
            self.assertTrue(logros.LOGROS[1][4](self.p_vacio, r))

        # 3. cinco-lecciones (hechas >= 5)
        with self.subTest(logro="cinco-lecciones"):
            r = base_r(); r["hechas_ids"] = set([f"l{i}" for i in range(4)])
            self.assertFalse(logros.LOGROS[2][4](self.p_vacio, r))
            r["hechas_ids"] = set([f"l{i}" for i in range(5)])
            self.assertTrue(logros.LOGROS[2][4](self.p_vacio, r))

        # 4. diez-lecciones (hechas >= 10)
        with self.subTest(logro="diez-lecciones"):
            r = base_r(); r["hechas_ids"] = set([f"l{i}" for i in range(9)])
            self.assertFalse(logros.LOGROS[3][4](self.p_vacio, r))
            r["hechas_ids"] = set([f"l{i}" for i in range(10)])
            self.assertTrue(logros.LOGROS[3][4](self.p_vacio, r))

        # 5. veinticinco-lecciones (hechas >= 25)
        with self.subTest(logro="veinticinco-lecciones"):
            r = base_r(); r["hechas_ids"] = set([f"l{i}" for i in range(24)])
            self.assertFalse(logros.LOGROS[4][4](self.p_vacio, r))
            r["hechas_ids"] = set([f"l{i}" for i in range(25)])
            self.assertTrue(logros.LOGROS[4][4](self.p_vacio, r))

        # 6. perfecta (perfectas >= 1)
        with self.subTest(logro="perfecta"):
            r = base_r(); r["perfectas"] = 0
            self.assertFalse(logros.LOGROS[5][4](self.p_vacio, r))
            r["perfectas"] = 1
            self.assertTrue(logros.LOGROS[5][4](self.p_vacio, r))

        # 7. cinco-perfectas (perfectas >= 5)
        with self.subTest(logro="cinco-perfectas"):
            r = base_r(); r["perfectas"] = 4
            self.assertFalse(logros.LOGROS[6][4](self.p_vacio, r))
            r["perfectas"] = 5
            self.assertTrue(logros.LOGROS[6][4](self.p_vacio, r))

        # 8. sin-pistas (estrellas3 >= 10)
        with self.subTest(logro="sin-pistas"):
            r = base_r(); r["estrellas3"] = 9
            self.assertFalse(logros.LOGROS[7][4](self.p_vacio, r))
            r["estrellas3"] = 10
            self.assertTrue(logros.LOGROS[7][4](self.p_vacio, r))

        # 9. racha-3 (racha_max >= 3)
        with self.subTest(logro="racha-3"):
            p = {"racha_max": 2}
            self.assertFalse(logros.LOGROS[8][4](p, base_r()))
            p["racha_max"] = 3
            self.assertTrue(logros.LOGROS[8][4](p, base_r()))

        # 10. racha-7 (racha_max >= 7)
        with self.subTest(logro="racha-7"):
            p = {"racha_max": 6}
            self.assertFalse(logros.LOGROS[9][4](p, base_r()))
            p["racha_max"] = 7
            self.assertTrue(logros.LOGROS[9][4](p, base_r()))

        # 11. racha-30 (racha_max >= 30)
        with self.subTest(logro="racha-30"):
            p = {"racha_max": 29}
            self.assertFalse(logros.LOGROS[10][4](p, base_r()))
            p["racha_max"] = 30
            self.assertTrue(logros.LOGROS[10][4](p, base_r()))

        # 12. primer-proyecto (proyectos >= 1)
        with self.subTest(logro="primer-proyecto"):
            r = base_r(); r["proyectos"] = 0
            self.assertFalse(logros.LOGROS[11][4](self.p_vacio, r))
            r["proyectos"] = 1
            self.assertTrue(logros.LOGROS[11][4](self.p_vacio, r))

        # 13. cinco-proyectos (proyectos >= 5)
        with self.subTest(logro="cinco-proyectos"):
            r = base_r(); r["proyectos"] = 4
            self.assertFalse(logros.LOGROS[12][4](self.p_vacio, r))
            r["proyectos"] = 5
            self.assertTrue(logros.LOGROS[12][4](self.p_vacio, r))

        # 14. congelador (congeladores_ganados >= 1)
        with self.subTest(logro="congelador"):
            p = {"stats": {"congeladores_ganados": 0}}
            self.assertFalse(logros.LOGROS[13][4](p, base_r()))
            p = {"stats": {"congeladores_ganados": 1}}
            self.assertTrue(logros.LOGROS[13][4](p, base_r()))

        # 15. meta-diaria (len(dias_meta) >= 1)
        with self.subTest(logro="meta-diaria"):
            p = {"dias_meta": []}
            self.assertFalse(logros.LOGROS[14][4](p, base_r()))
            p = {"dias_meta": ["2026-09-01"]}
            self.assertTrue(logros.LOGROS[14][4](p, base_r()))

        # 16. cinco-metas (len(dias_meta) >= 5)
        with self.subTest(logro="cinco-metas"):
            p = {"dias_meta": ["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04"]}
            self.assertFalse(logros.LOGROS[15][4](p, base_r()))
            p = {"dias_meta": ["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04", "2026-09-05"]}
            self.assertTrue(logros.LOGROS[15][4](p, base_r()))

        # 17. curso-1 (curso_id: (hechas, total) >= total > 0)
        with self.subTest(logro="curso-1"):
            r = base_r()
            # Borde: 9/10 (NO)
            r["cursos"] = {"primeros-pasos": (9, 10)}
            self.assertFalse(logros.LOGROS[16][4](self.p_vacio, r))
            # Borde: 10/10 (SI)
            r["cursos"] = {"primeros-pasos": (10, 10)}
            self.assertTrue(logros.LOGROS[16][4](self.p_vacio, r))
            # Caso 0/0 (NO, según regla)
            r["cursos"] = {"primeros-pasos": (0, 0)}
            self.assertFalse(logros.LOGROS[16][4](self.p_vacio, r))

        # 18. primer-dibujo (tortuga-avanzar in hechas_ids)
        with self.subTest(logro="primer-dibujo"):
            r = base_r(); r["hechas_ids"] = set()
            self.assertFalse(logros.LOGROS[17][4](self.p_vacio, r))
            r["hechas_ids"] = {"tortuga-avanzar"}
            self.assertTrue(logros.LOGROS[17][4](self.p_vacio, r))

        # 19. artista (curso tortuga)
        with self.subTest(logro="artista"):
            r = base_r()
            r["cursos"] = {"tortuga": (0, 5)} # total > 0
            self.assertFalse(logros.LOGROS[18][4](self.p_vacio, r))
            r["cursos"] = {"tortuga": (5, 5)}
            self.assertTrue(logros.LOGROS[18][4](self.p_vacio, r))

        # 20. primer-python (py-print in hechas_ids)
        with self.subTest(logro="primer-python"):
            r = base_r(); r["hechas_ids"] = set()
            self.assertFalse(logros.LOGROS[19][4](self.p_vacio, r))
            r["hechas_ids"] = {"py-print"}
            self.assertTrue(logros.LOGROS[19][4](self.p_vacio, r))

        # 21. programador (curso python)
        with self.subTest(logro="programador"):
            r = base_r()
            r["cursos"] = {"python-real": (0, 5)}
            self.assertFalse(logros.LOGROS[20][4](self.p_vacio, r))
            r["cursos"] = {"python-real": (5, 5)}
            self.assertTrue(logros.LOGROS[20][4](self.p_vacio, r))

        # 22. nivel-5 (nivel >= 5)
        with self.subTest(logro="nivel-5"):
            r = base_r(); r["nivel"] = 4
            self.assertFalse(logros.LOGROS[21][4](self.p_vacio, r))
            r["nivel"] = 5
            self.assertTrue(logros.LOGROS[21][4](self.p_vacio, r))

        # 23. nivel-10 (nivel >= 10)
        with self.subTest(logro="nivel-10"):
            r = base_r(); r["nivel"] = 9
            self.assertFalse(logros.LOGROS[22][4](self.p_vacio, r))
            r["nivel"] = 10
            self.assertTrue(logros.LOGROS[22][4](self.p_vacio, r))

        # 24. liga-plata (nivel >= 1)
        with self.subTest(logro="liga-plata"):
            p = {"liga": {"nivel": 0}}
            self.assertFalse(logros.LOGROS[23][4](p, base_r()))
            p = {"liga": {"nivel": 1}}
            self.assertTrue(logros.LOGROS[23][4](p, base_r()))

        # 25. liga-oro (nivel >= 2)
        with self.subTest(logro="liga-oro"):
            p = {"liga": {"nivel": 1}}
            self.assertFalse(logros.LOGROS[24][4](p, base_r()))
            p = {"liga": {"nivel": 2}}
            self.assertTrue(logros.LOGROS[24][4](p, base_r()))

    def test_logros_mutantes_cobertura(self):
        # 1. _curso_completo (L24)
        with self.subTest(mutante="_curso_completo"):
            # Curso ausente
            self.assertFalse(logros._curso_completo("curso-a")({}, {"cursos": {}}))
            # Curso (0, 0)
            self.assertFalse(logros._curso_completo("curso-a")({}, {"cursos": {"curso-a": (0, 0)}}))
            # Curso (3, 3) -> completo
            self.assertTrue(logros._curso_completo("curso-a")({}, {"cursos": {"curso-a": (3, 3)}}))
            # Curso (2, 3) -> no completo
            self.assertFalse(logros._curso_completo("curso-a")({}, {"cursos": {"curso-a": (2, 3)}}))
            # Curso (4, 3) -> completo
            self.assertTrue(logros._curso_completo("curso-a")({}, {"cursos": {"curso-a": (4, 3)}}))

        # 2. racha_max por defecto (L32)
        with self.subTest(mutante="racha_max_default"):
            # progreso sin racha_max
            self.assertFalse(logros._racha(3)({}, self.resumen_vacio))
            # progreso con racha_max=2
            self.assertFalse(logros._racha(3)({"racha_max": 2}, self.resumen_vacio))
            # progreso con racha_max=3
            self.assertTrue(logros._racha(3)({"racha_max": 3}, self.resumen_vacio))

        # 3. liga-oro (L63)
        with self.subTest(mutante="liga-oro_no_key"):
            # sin liga
            self.assertFalse(logros.LOGROS[24][4]({}, self.resumen_vacio))
            # con liga nivel 1
            self.assertFalse(logros.LOGROS[24][4]({"liga": {"nivel": 1}}, self.resumen_vacio))
            # con liga nivel 2
            self.assertTrue(logros.LOGROS[24][4]({"liga": {"nivel": 2}}, self.resumen_vacio))

        # 4. resumen_de (L72-L86)
        with self.subTest(mutante="resumen_de_detalles"):
            camino = [{
                "id": "curso1",
                "secciones": [{
                    "lecciones": [
                        {"id": "lec1", "estado": "perfecta"},
                        {"id": "lec2", "estado": "perfecta"},
                        {"id": "lec3", "estado": "hecha"}
                    ]
                }]
            }]
            # perfectas = 2 (dos lecciones perfecta)
            # hechas_ids = 3
            p = {
                "lecciones": {
                    "lec1": {"pasos": {}},
                    "lec2": {"pasos": {}},
                    "lec3": {"pasos": {}}
                },
                "ejercicios": {
                    "ex1": {"completado": True},
                    "ex2": {"completado": True},
                    "ex3": {"completado": False}
                }
            }
            r = logros.resumen_de(p, camino)
            self.assertEqual(r["perfectas"], 2)
            self.assertEqual(len(r["hechas_ids"]), 3)
            # Pasos: ejercicios (2) + pasos de lecciones. Aqui lecciones no tienen pasos.
            # pasos_hechos = sum(len(l.pasos)) + sum(1 for e if completado)
            # sum(len(l.pasos)) = 0 + 0 + 0 = 0
            # sum(1 for e if completado) = 1 (ex1) + 1 (ex2) + 0 (ex3) = 2
            self.assertEqual(r["pasos_hechos"], 2)
            
            # Cursos: (h, t)
            # curso1: 3 hechas, 3 totales
            self.assertEqual(r["cursos"]["curso1"], (3, 3))
            
            # estrellas3:
            # ejercicios: ex1 (estrellas 2), ex2 (estrellas 3), ex3 (no estrellas)
            p["ejercicios"]["ex1"]["estrellas"] = 2
            p["ejercicios"]["ex2"]["estrellas"] = 3
            # pasos de leccion:
            p["lecciones"]["lec1"]["pasos"] = {
                "p1": {"estrellas": 3, "xp": 10},
                "p2": {"estrellas": 3, "xp": 0}
            }
            # estrellas3 = ejercicios(1) + lecciones(1 paso con xp>0 y estrellas=3) = 2
            r = logros.resumen_de(p, camino)
            self.assertEqual(r["estrellas3"], 2)

        # 5. IDS (L65)
        with self.subTest(mutante="IDS"):
            self.assertEqual(logros.IDS[0], "primer-paso")
            self.assertEqual(len(logros.IDS), len(logros.LOGROS))
