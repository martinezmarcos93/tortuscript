#!/usr/bin/env python3
"""Revisa el contraste de color (WCAG AA: 4.5:1, o 3:1 para texto grande) del texto visible de las
páginas principales, en modo normal y de alto contraste.

Requiere Playwright (opcional) y un servidor de prueba andando:
    python herramientas/servidor_de_prueba.py            (en otra terminal)
    python herramientas/revisar_contraste.py [--url http://127.0.0.1:5077]

Sale con código 1 si algún texto no llega al mínimo. Los elementos atenuados a propósito (opacidad < 1,
como las lecciones bloqueadas) no se cuentan.
"""
import argparse
import sys

RUTAS = ["/", "/bienvenida", "/aprender", "/leccion/hola-mundo", "/ejercicios/1", "/referencia", "/mapa", "/resumen", "/logros", "/liga", "/experimentar",
         "/tortuga", "/proyectos", "/proyectos-integradores", "/repaso", "/practica", "/ayuda", "/leccion/laberinto-1",
         "/leccion/rpg-heroe", "/juego", "/leccion/juego-ganar", "/cuenta/configuracion", "/cuenta/suscripcion", "/cuenta/seleccionar-perfil", "/no-existe"]   # la última: página de error 404

JS = r"""
() => {
  const parse = (c) => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(",").map(Number); return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1}; };
  const lum = ({r, g, b}) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const mezcla = (a, b) => ({r: a.r * a.a + b.r * (1 - a.a), g: a.g * a.a + b.g * (1 - a.a), b: a.b * a.a + b.b * (1 - a.a), a: 1});
  const fondoDe = (el) => {
    const capas = [];
    for (let e = el; e; e = e.parentElement) {
      const cs = getComputedStyle(e), c = parse(cs.backgroundColor);
      if (c && c.a > 0) capas.push(c);
      if (c && c.a === 1) break;
    }
    let base = {r: 0, g: 0, b: 0, a: 1};
    for (const c of capas.reverse()) base = mezcla(c, base);
    return base;
  };
  const malos = [], vistos = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const nodo = walker.currentNode, el = nodo.parentElement;
    if (!nodo.textContent.trim() || !el || vistos.has(el) || el.closest("[hidden], .solo-lector, script, style, .CodeMirror, canvas")) continue;
    const cs = getComputedStyle(el), r = el.getBoundingClientRect();
    if (cs.visibility === "hidden" || cs.display === "none" || r.width === 0 || r.height === 0) continue;
    vistos.add(el);
    let op = 1; for (let e = el; e; e = e.parentElement) op *= parseFloat(getComputedStyle(e).opacity);
    if (op < 0.99) continue;
    const fondo = fondoDe(el); let color = parse(cs.color); if (!color) continue;
    if (color.a < 1) color = mezcla(color, fondo);
    const l1 = lum(color), l2 = lum(fondo), ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    const px = parseFloat(cs.fontSize), grande = px >= 24 || (px >= 18.66 && parseInt(cs.fontWeight) >= 700);
    if (ratio < (grande ? 3 : 4.5)) malos.push({texto: nodo.textContent.trim().slice(0, 40), ratio: Math.round(ratio * 100) / 100, elemento: String(el.className || el.tagName).slice(0, 40)});
  }
  return malos;
}
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://127.0.0.1:5077")
    args = ap.parse_args()
    from playwright.sync_api import sync_playwright

    total = 0
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pg = navegador.new_page(viewport={"width": 1280, "height": 900})
        pg.goto(args.url + "/cuenta/__test__/bootstrap")
        pg.goto(args.url + "/bienvenida")
        api = ("args => fetch(args[2], {method: 'POST', headers: {'Content-Type': 'application/json', "
               "'X-Tortu-Token': args[0]}, body: JSON.stringify(args[1])})")
        pg.evaluate(api, ["prueba", {"meta_min": 10}, "/api/onboarding"])
        for modo in ("normal", "alto"):
            pg.evaluate(api, ["prueba", {"contraste": modo}, "/api/ajustes"])
            pg.wait_for_timeout(400)
            for ruta in RUTAS:
                pg.goto(args.url + ruta)
                pg.wait_for_timeout(250)
                malos = pg.evaluate(JS)
                total += len(malos)
                if malos:
                    print(f"[{modo}] {ruta}: {len(malos)} con poco contraste")
                    for m in malos[:6]:
                        print("    ", m)
        navegador.close()
    print("Contraste: sin problemas" if not total else f"Contraste: {total} textos por debajo del mínimo")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
