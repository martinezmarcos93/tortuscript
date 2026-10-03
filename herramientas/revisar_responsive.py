#!/usr/bin/env python3
"""Revisa que ninguna página se desborde hacia los costados (scroll horizontal) en pantallas chicas.

Requiere Playwright (opcional) y un servidor de prueba andando:
    python herramientas/servidor_de_prueba.py            (en otra terminal)
    python herramientas/revisar_responsive.py [--url http://127.0.0.1:5077] [--capturas carpeta]

Prueba los viewports obligatorios 320×800, 375×812, 390×844 y 768×1024 sobre las páginas principales y sobre un paso de cada tipo
de lección. Sale con código 1 si algo se desborda; con --capturas guarda una imagen de cada caso.
"""
import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "herramientas"))

VIEWPORTS = ((320, 800), (375, 812), (390, 844), (768, 1024))
RUTAS = ["/", "/bienvenida", "/aprender", "/leccion/hola-mundo", "/ejercicios/1", "/referencia", "/mapa", "/resumen", "/logros", "/liga", "/experimentar", "/tortuga",
         "/proyectos", "/proyectos-integradores", "/repaso", "/practica", "/ayuda", "/leccion/laberinto-1", "/leccion/rpg-heroe",
         "/juego", "/leccion/juego-ganar", "/no-existe"]   # la última: página de error 404

# Qué elementos se salen del ancho de la ventana (ignora los que se desplazan por dentro a propósito)
JS_DESBORDE = r"""
() => {
  const ancho = document.documentElement.clientWidth, malos = [];
  for (const el of document.querySelectorAll("body *")) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0 || getComputedStyle(el).position === "fixed") continue;
    if (el.closest(".CodeMirror, pre, [hidden], details:not([open]) .mas-lista") || el.matches(".mas-lista")) continue;
    if (r.right > ancho + 1 || r.left < -1) malos.push(String(el.className || el.tagName).slice(0, 40) + " (" + Math.round(r.left) + ".." + Math.round(r.right) + ")");
  }
  return {scroll: document.documentElement.scrollWidth - ancho, malos: malos.slice(0, 5)};
}
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://127.0.0.1:5077")
    ap.add_argument("--capturas", default=None)
    args = ap.parse_args()
    from playwright.sync_api import sync_playwright

    problemas = 0
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pg = navegador.new_page(viewport={"width": 1280, "height": 900})
        pg.goto(args.url + "/cuenta/__test__/bootstrap")
        pg.goto(args.url + "/bienvenida")
        pg.evaluate("t => fetch('/api/onboarding', {method: 'POST', headers: {'Content-Type': 'application/json', "
                    "'X-Tortu-Token': t}, body: JSON.stringify({meta_min: 10})})", "prueba")
        pg.wait_for_timeout(400)
        for ancho, alto in VIEWPORTS:
            pg.set_viewport_size({"width": ancho, "height": alto})
            for ruta in RUTAS:
                pg.goto(args.url + ruta)
                pg.wait_for_timeout(200)
                r = pg.evaluate(JS_DESBORDE)
                if r["scroll"] > 1 or r["malos"]:
                    problemas += 1
                    print(f"[{ancho}px] {ruta}: se desborda {r['scroll']}px → {r['malos']}")
                    if args.capturas:
                        Path(args.capturas).mkdir(parents=True, exist_ok=True)
                        pg.screenshot(path=str(Path(args.capturas) / f"desborde_{ancho}_{ruta.strip('/').replace('/', '_') or 'inicio'}.png"))
        # Un paso de cada tipo de la primera lección (elegir, completar, ordenar, predecir y escribir)
        import jugar_cursos
        from tortuscript import contenido
        leccion = contenido.cargar_curso()["secciones"][0]["lecciones"][0]
        for ancho, alto in VIEWPORTS:
            pg.set_viewport_size({"width": ancho, "height": alto})
            pg.goto(f"{args.url}/leccion/{leccion['id']}")
            for i, paso in enumerate(leccion["pasos"]):
                pg.wait_for_timeout(250)
                r = pg.evaluate(JS_DESBORDE)
                if r["scroll"] > 1 or r["malos"]:
                    problemas += 1
                    print(f"[{ancho}px] lección hola-mundo, paso {i + 1} ({paso['tipo']}): se desborda {r['scroll']}px → {r['malos']}")
                    if args.capturas:
                        Path(args.capturas).mkdir(parents=True, exist_ok=True)
                        pg.screenshot(path=str(Path(args.capturas) / f"desborde_{ancho}_paso{i + 1}.png"))
                jugar_cursos._jugar_paso(pg, paso)
        navegador.close()
    print("Responsive: sin desbordes" if not problemas else f"Responsive: {problemas} páginas con desborde")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
