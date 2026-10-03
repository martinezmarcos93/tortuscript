#!/usr/bin/env python3
"""Prueba SIMULADA con chicos: 8 perfiles juegan por la interfaz real (Chromium) y se equivocan como chicos.

⚠️  Es una simulación, no chicos de verdad. Sirve para encontrar fricción que se puede medir: errores de la interfaz,
callejones sin salida, pantallas que se desbordan, ayudas que no alcanzan para destrabar, y para probar los flujos
reales (bienvenida, diagnóstico, pistas, "ver respuesta", teclado, accesibilidad, celular). NO mide si a un chico le
gusta, si vuelve al otro día ni si aprende: eso solo lo contesta una prueba con chicos reales (Puerta 1 del roadmap).

Requiere Playwright (requirements-dev.txt) y el servidor de prueba SIN --todo-desbloqueado (cada perfil pasa por la
bienvenida):
    python herramientas/servidor_de_prueba.py                     (en otra terminal)
    python herramientas/simular_chicos.py [--url ...] [--informe docs/validacion/simulacion-AAAA-MM-DD.md]

Es reproducible: cada perfil usa su propia semilla para decidir cuándo se equivoca.
"""
import argparse
import random
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tortuscript import contenido  # noqa: E402
import jugar_cursos as jc  # noqa: E402

# nombre, edad, experiencia, entrada (None = desde el principio), prob. de error, pantalla, ajustes, comportamiento
PERFILES = [
    {"nombre": "Sofi", "edad": 10, "experiencia": "nunca", "entrada": None, "error": 0.35, "pantalla": (360, 740),
     "ajustes": {}, "estilo": "usa pistas", "lecciones": 8},
    {"nombre": "Tomi", "edad": 12, "experiencia": "poquito", "entrada": "tu-primera-variable", "error": 0.15,
     "pantalla": (1280, 800), "ajustes": {}, "estilo": "normal", "lecciones": 8},
    {"nombre": "Juli", "edad": 11, "experiencia": "nunca", "entrada": None, "error": 0.25, "pantalla": (1280, 800),
     "ajustes": {"tam": "enorme", "contraste": "alto"}, "estilo": "normal", "lecciones": 6},
    {"nombre": "Mati", "edad": 13, "experiencia": "bastante", "entrada": "si-es-grande", "error": 0.10,
     "pantalla": (1280, 800), "ajustes": {}, "estilo": "solo teclado", "lecciones": 8},
    {"nombre": "Cami", "edad": 10, "experiencia": "nunca", "entrada": None, "error": 0.45, "pantalla": (414, 860),
     "ajustes": {"movimiento": "reducido", "letra": "legible"}, "estilo": "se rinde rápido", "lecciones": 6},
    {"nombre": "Leo", "edad": 14, "experiencia": "bastante", "entrada": None, "error": 0.05, "pantalla": (1280, 800),
     "ajustes": {}, "estilo": "rápido", "lecciones": 10},
    {"nombre": "Vale", "edad": 11, "experiencia": "nunca", "entrada": None, "error": 0.30, "pantalla": (768, 1024),
     "ajustes": {"tam": "grande"}, "estilo": "usa pistas", "lecciones": 7},
    {"nombre": "Nico", "edad": 12, "experiencia": "nunca", "entrada": None, "error": 0.20, "pantalla": (1280, 800),
     "ajustes": {}, "estilo": "normal", "lecciones": 6, "despues": ["tortuga-avanzar", "tortuga-girar", "cuadrado-a-mano"]},
]


def con_error(solucion):
    """Un error típico de chico sobre la solución: comillas sin cerrar, un número cambiado o una palabra mal escrita."""
    if '"' in solucion:
        return solucion.replace('"', "", 1)
    numero = re.search(r"\d+", solucion)
    if numero:
        return solucion[:numero.start()] + str(int(numero.group()) + 1) + solucion[numero.end():]
    return solucion.replace("mostrar", "mostar", 1)


class Chico:
    def __init__(self, pg, perfil, url):
        self.pg, self.p, self.url = pg, perfil, url
        self.azar = random.Random(perfil["nombre"])
        self.m = Counter()                    # métricas
        self.errores_por_paso = defaultdict(int)
        self.problemas = []

    # ── acciones ──
    def principal(self):
        if self.p["estilo"] == "solo teclado":
            self.pg.evaluate("() => document.activeElement && document.activeElement.blur()")
            self.pg.keyboard.press("Enter")
        else:
            self.pg.click("#lec-principal")

    def elegir_opcion(self, texto):
        if self.p["estilo"] == "solo teclado":
            idx = self.pg.evaluate("t => [...document.querySelectorAll('.opcion-paso')].findIndex(b => b.textContent === t)", texto)
            self.pg.evaluate("() => document.activeElement && document.activeElement.blur()")
            self.pg.keyboard.press(str(idx + 1))
        else:
            jc._click_exacto(self.pg, ".opcion-paso", texto)

    def esperar(self, clase, entradas=None):
        jc._esperar_pie(self.pg, list(entradas or []), clase)

    def se_equivoca(self):
        return self.azar.random() < self.p["error"]

    # ── pasos ──
    def paso(self, lec_id, i, paso):
        tipo = paso["tipo"]
        self.m[f"pasos_{tipo}"] += 1
        clave = f"{lec_id}#{i + 1} ({tipo})"
        if tipo in ("elegir", "predecir"):
            self.pg.wait_for_selector(".opcion-paso")
            correcta = str(paso["opciones"][paso["correcta"]])
            malas = [str(o) for o in paso["opciones"] if str(o) != correcta]
            errores = 0
            while self.se_equivoca() and errores < 3:
                self.elegir_opcion(self.azar.choice(malas))
                self.principal(); self.esperar("mal")
                errores += 1; self.errores_por_paso[clave] += 1
                if errores >= 2 and self.p["estilo"] == "se rinde rápido" and self.pg.is_visible("#lec-ver"):
                    self.pg.click("#lec-ver"); self.esperar("info"); self.m["respuestas_vistas"] += 1
                    self.principal(); return
                self.principal()                                  # Reintentar
            self.m["primer_intento_ok" if errores == 0 else "con_errores"] += 1
            self.elegir_opcion(correcta)
            self.principal(); self.esperar("bien"); self.principal()
        elif tipo == "escribir":
            entradas = paso.get("entradas_prueba") or []
            self.pg.wait_for_selector(".paso-caja .CodeMirror")
            errores = 0
            while self.se_equivoca() and errores < 2:
                self.pg.evaluate("s => document.querySelector('.paso-caja .CodeMirror').CodeMirror.setValue(s)",
                                 con_error(paso["solucion"]))
                self.pg.click("text=▶ Jugar" if paso.get("juego") else "text=▶ Dibujar" if paso.get("tortuga") else "text=▶ Ejecutar")
                self.esperar("mal", entradas)
                errores += 1; self.errores_por_paso[clave] += 1
                self.pg.click("#lec-principal")                   # Reintentar
                if self.p["estilo"] == "usa pistas":
                    self.pg.click("text=💡 Pista"); self.pg.wait_for_selector(".pista-caja .veredicto")
                    self.m["pistas_vistas"] += 1
            self.m["primer_intento_ok" if errores == 0 else "con_errores"] += 1
            self.pg.evaluate("s => document.querySelector('.paso-caja .CodeMirror').CodeMirror.setValue(s)", paso["solucion"])
            self.pg.click("text=▶ Jugar" if paso.get("juego") else "text=▶ Dibujar" if paso.get("tortuga") else "text=▶ Ejecutar")
            self.esperar("bien", entradas); self.principal()
        else:
            jc._jugar_paso(self.pg, paso)                          # explicación, completar y ordenar: bien jugados
            if tipo != "explicacion":
                self.m["primer_intento_ok"] += 1

    # ── recorrido ──
    def bienvenida(self):
        pg = self.pg
        pg.goto(self.url + "/cuenta/__test__/bootstrap?perfil=" + self.p["nombre"])
        pg.goto(self.url + "/bienvenida")                     # cada perfil nuevo empieza por la bienvenida
        pg.fill("#bv-nombre", self.p["nombre"]); pg.click("#bv-sig-1")
        pg.click(f'[data-campo="experiencia"] [data-valor="{self.p["experiencia"]}"]')
        if self.p["entrada"]:
            pg.click(f'[data-campo="entrada"] [data-valor="{self.p["entrada"]}"]')
        pg.click("#bv-sig-2"); pg.click("#bv-empezar"); pg.wait_for_url(self.url + "/")
        for ajuste, valor in self.p["ajustes"].items():
            pg.evaluate("([a, v]) => Tortu.api('/api/ajustes', {[a]: v})", [ajuste, valor])
        if self.p["ajustes"]:
            pg.reload()

    def revisar_pantalla(self, donde):
        ancho = self.pg.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
        if ancho > 1:
            self.problemas.append(f"se desborda {ancho}px en {donde}")

    def jugar(self):
        self.bienvenida()
        self.revisar_pantalla("el inicio")
        hechas = 0
        for _ in range(self.p["lecciones"]):
            actual = self.pg.get_attribute(".hero .boton.verde", "href") or ""
            if "/leccion/" not in actual:
                self.problemas.append("el inicio no ofrece una lección para seguir"); break
            self.jugar_leccion(actual.rsplit("/", 1)[1])
            hechas += 1
            self.pg.goto(self.url + "/")
        for lec_id in self.p.get("despues", []):
            self.jugar_leccion(lec_id)
            hechas += 1
        self.m["lecciones_jugadas"] = hechas
        estado = self.pg.evaluate("() => Tortu.api('/api/estado')")
        self.m["lecciones_hechas"], self.m["xp"] = estado["lecciones_hechas"], estado["xp"]

    def jugar_leccion(self, lec_id):
        lec = next(l for c in contenido.todos_los_cursos() for _, l in contenido.lecciones(c) if l["id"] == lec_id)
        self.pg.goto(f"{self.url}/leccion/{lec_id}")
        if "/leccion/" not in self.pg.url:
            self.problemas.append(f"no pudo abrir {lec_id}"); return
        self.revisar_pantalla(f"la lección {lec_id}")
        for i, paso in enumerate(lec["pasos"]):
            self.paso(lec_id, i, paso)
        self.pg.wait_for_selector("text=¡Lección", timeout=10000)
        self.revisar_pantalla(f"el cierre de {lec_id}")


def auditar_contenido():
    """Señales objetivas de posible fricción en el contenido (no dependen de la simulación)."""
    sin_pista, largos = [], []
    for curso in contenido.todos_los_cursos():
        for _, lec in contenido.lecciones(curso):
            for i, paso in enumerate(lec["pasos"]):
                if paso["tipo"] in ("elegir", "predecir", "completar", "ordenar") and not paso.get("pista") \
                        and paso.get("cuenta") != "trazos":
                    sin_pista.append(f"{lec['id']}#{i + 1}")
                texto = paso.get("consigna") or paso.get("pregunta") or paso.get("texto") or ""
                if len(texto) > 160:
                    largos.append(f"{lec['id']}#{i + 1} ({len(texto)})")
    return sin_pista, largos


def informe(chicos, errores_consola, segundos, sin_pista, largos):
    hoy = date.today().isoformat()
    total = Counter()
    for c in chicos:
        total.update(c.m)
    friccion = Counter()
    for c in chicos:
        friccion.update(c.errores_por_paso)
    problemas = [f"{c.p['nombre']}: {x}" for c in chicos for x in c.problemas]
    filas = []
    for c in chicos:
        intentos = c.m["primer_intento_ok"] + c.m["con_errores"]
        filas.append(f"| {c.p['nombre']} ({c.p['edad']}) | {c.p['experiencia']}"
                     f"{' → ' + c.p['entrada'] if c.p['entrada'] else ''} | {c.p['pantalla'][0]}px"
                     f"{', ' + ', '.join(f'{k}={v}' for k, v in c.p['ajustes'].items()) if c.p['ajustes'] else ''} | "
                     f"{c.p['estilo']} · error {int(c.p['error'] * 100)}% | {c.m['lecciones_jugadas']} | "
                     f"{c.m['lecciones_hechas']} | {c.m['xp']} | "
                     f"{(100 * c.m['primer_intento_ok'] // intentos) if intentos else 0}% | "
                     f"{c.m['pistas_vistas']} / {c.m['respuestas_vistas']} |")
    robusto = not errores_consola and not problemas and all(c.m["lecciones_jugadas"] for c in chicos)
    return f"""# Prueba SIMULADA con chicos — {hoy}

> ⚠️ **Simulación, no chicos reales.** {len(chicos)} perfiles sintéticos jugaron por la interfaz real (Chromium) con
> `herramientas/simular_chicos.py`, equivocándose con probabilidades fijas y reproducibles. Mide la **robustez** del
> producto (que nadie quede trabado, que la interfaz no falle, que las ayudas destraben, que se vea bien en cada
> pantalla y con cada ajuste). **No mide** si a un chico le gusta, si vuelve al día siguiente ni si aprende: la
> Puerta 1 del roadmap sigue necesitando chicos reales.

## Perfiles y resultados

| Chico | Experiencia | Pantalla / ajustes | Comportamiento | Lecciones jugadas | Hechas (total) | XP | Al primer intento | Pistas / respuestas vistas |
|---|---|---|---|---|---|---|---|---|
{chr(10).join(filas)}

Total: {total['lecciones_jugadas']} lecciones y {sum(v for k, v in total.items() if k.startswith('pasos_'))} pasos jugados en {segundos:.0f} s.

## Robustez (lo que sí mide)

- Errores de consola (incluye violaciones de CSP): **{len(errores_consola)}**{(' → ' + '; '.join(errores_consola[:5])) if errores_consola else ''}
- Callejones sin salida y pantallas desbordadas: **{len(problemas)}**{(chr(10) + chr(10).join('  - ' + x for x in problemas)) if problemas else ''}
- Todos los pasos con error se destrabaron con reintento, pista o "ver respuesta": **{'sí' if robusto else 'revisar'}**.

## Dónde se equivocaron (simulado)

Los errores de la simulación son al azar: esta lista muestra **dónde se probó** la recuperación, no qué es difícil.

{chr(10).join(f'- {k}: {v} error(es)' for k, v in friccion.most_common(10)) or '- (ninguno)'}

## Señales objetivas en el contenido (no dependen de la simulación)

- Pasos de elegir/predecir/completar/ordenar **sin pista propia** (usan la genérica): **{len(sin_pista)}**.
  Primeros: {', '.join(sin_pista[:12])}{' …' if len(sin_pista) > 12 else ''}
- Consignas de más de 160 caracteres: **{len(largos)}**{(' → ' + ', '.join(largos[:8])) if largos else ''}

## Veredicto de la Puerta 1 (simulada)

- **Robustez: {'PASA' if robusto else 'NO PASA'}.** {'Ningún perfil quedó trabado, sin errores de interfaz ni desbordes.' if robusto else 'Hay problemas para corregir antes de seguir (arriba).'}
- **Retención y gusto: SIN RESPUESTA.** Una simulación no puede contestarlo. Se toma la decisión de Marcos (26/09/2026)
  de seguir con la Fase 2 usando esta prueba como sustituto provisorio, y queda pendiente probar con chicos reales.
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://127.0.0.1:5077")
    ap.add_argument("--informe", help="dónde escribir el informe en Markdown")
    args = ap.parse_args()
    from playwright.sync_api import sync_playwright

    errores, chicos, inicio = [], [], time.time()
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        for perfil in PERFILES:
            pagina = navegador.new_page(viewport={"width": perfil["pantalla"][0], "height": perfil["pantalla"][1]})
            pagina.on("console", lambda m, n=perfil["nombre"]: errores.append(f"{n}: {m.text}") if m.type == "error" else None)
            pagina.on("pageerror", lambda e, n=perfil["nombre"]: errores.append(f"{n}: {e}"))
            chico = Chico(pagina, perfil, args.url)
            try:
                chico.jugar()
            except Exception as e:                                # un perfil trabado es un hallazgo, no un corte
                chico.problemas.append(f"se trabó: {type(e).__name__}: {str(e).splitlines()[0][:160]}")
            print(f"{perfil['nombre']}: {dict(chico.m)} {chico.problemas or ''}", flush=True)
            chicos.append(chico)
            pagina.close()
        navegador.close()
    texto = informe(chicos, errores, time.time() - inicio, *auditar_contenido())
    if args.informe:
        Path(args.informe).parent.mkdir(parents=True, exist_ok=True)
        Path(args.informe).write_text(texto, encoding="utf-8")
        print("informe:", args.informe)
    else:
        print(texto)
    return 0 if not errores and not any(c.problemas for c in chicos) else 1


if __name__ == "__main__":
    sys.exit(main())
