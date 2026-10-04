#!/usr/bin/env python3
"""Auditoría diagnóstica de foco de teclado y nombres accesibles en páginas principales.

Genera hallazgos para revisión; no falla el CI automáticamente hasta que los falsos
positivos y excepciones de los controles personalizados estén clasificados.
Requiere Playwright y un servidor aislado de pruebas.
"""
import argparse
import sys

RUTAS = [
    "/", "/bienvenida", "/aprender", "/leccion/hola-mundo", "/ejercicios/1",
    "/referencia", "/mapa", "/resumen", "/logros", "/liga", "/experimentar",
    "/tortuga", "/proyectos", "/proyectos-integradores", "/repaso", "/practica",
    "/ayuda", "/leccion/laberinto-1", "/leccion/rpg-heroe", "/juego",
    "/leccion/juego-ganar", "/no-existe",
]

AUDITAR = r"""
() => {
  const visible = e => {
    const s = getComputedStyle(e), r = e.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' &&
      Number(s.opacity) > 0 && r.width > 0 && r.height > 0;
  };
  const controles = [...document.querySelectorAll(
    'a[href],button,input,select,textarea,[role="button"],[role="link"],[tabindex]:not([tabindex="-1"]),[contenteditable="true"]'
  )].filter(visible);
  const nombre = e => {
    const aria = e.getAttribute('aria-label');
    if (aria && aria.trim()) return aria.trim();
    const ids = (e.getAttribute('aria-labelledby') || '').split(/\s+/).filter(Boolean);
    const etiquetado = ids.map(id => document.getElementById(id)?.innerText || '').join(' ').trim();
    if (etiquetado) return etiquetado;
    if (e.labels && e.labels.length) {
      const labels = [...e.labels].map(x => x.innerText.trim()).filter(Boolean).join(' ');
      if (labels) return labels;
    }
    const title = e.getAttribute('title');
    if (title && title.trim()) return title.trim();
    const texto = (e.innerText || e.textContent || '').trim();
    if (texto) return texto.slice(0, 100);
    return '';
  };
  const sinNombre = controles.filter(e => !nombre(e)).map(e => ({
    tag: e.tagName, id: e.id, role: e.getAttribute('role'),
    type: e.getAttribute('type'), clase: String(e.className || '').slice(0, 60)
  }));
  const tabulables = controles.filter(e => !e.disabled && e.tabIndex >= 0);
  return {sinNombre, controles: controles.length, tabulables: tabulables.length};
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:5077")
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright

    hallazgos = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(args.url + "/cuenta/__test__/bootstrap")
        page.goto(args.url + "/bienvenida")
        page.evaluate(
            "t => fetch('/api/onboarding', {method:'POST', headers:{'Content-Type':'application/json',"
            "'X-Tortu-Token':t}, body:JSON.stringify({meta_min:10})})",
            "prueba",
        )
        page.wait_for_timeout(300)
        for route in RUTAS:
            page.goto(args.url + route)
            page.wait_for_timeout(100)
            data = page.evaluate(AUDITAR)
            for item in data["sinNombre"]:
                hallazgos += 1
                print(f"ACCESIBILIDAD {route}: control sin nombre accesible: {item}")
            if data["controles"] and not data["tabulables"]:
                hallazgos += 1
                print(f"TECLADO {route}: hay {data['controles']} controles visibles pero ninguno tabulable")
            page.keyboard.press("Tab")
            foco = page.evaluate("""() => {
              const e = document.activeElement;
              if (!e || e === document.body || e === document.documentElement) return null;
              const r = e.getBoundingClientRect(), s = getComputedStyle(e);
              return {tag:e.tagName,id:e.id,tabIndex:e.tabIndex,visible:s.display!=='none' &&
                s.visibility!=='hidden' && r.width>0 && r.height>0};
            }""")
            if data["tabulables"] and (not foco or not foco["visible"] or foco["tabIndex"] < 0):
                hallazgos += 1
                print(f"TECLADO {route}: el primer Tab no aterriza en un control visible: {foco}")
        browser.close()
    print(f"Auditoría diagnóstica de teclado: {hallazgos} hallazgos en las rutas inspeccionadas.")
    # Diagnóstico informativo hasta revisar controles personalizados y falsos positivos.
    return 0


if __name__ == "__main__":
    sys.exit(main())
