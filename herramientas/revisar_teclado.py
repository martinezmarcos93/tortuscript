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


RUTAS_DE_CUENTA = [
    "/cuenta/ingresar", "/cuenta/registrar", "/cuenta/recuperar", "/cuenta/restablecer-password?token=x",
    "/cuenta/verificar-email?token=x",
]
RUTAS_DE_CUENTA_CON_SESION = ["/cuenta/seleccionar-perfil", "/cuenta/configuracion", "/cuenta/suscripcion"]

FOCO = r"""
() => {
  const e = document.activeElement;
  if (!e || e === document.body || e === document.documentElement) return null;
  const r = e.getBoundingClientRect(), s = getComputedStyle(e);
  const editor = e.closest('.CodeMirror');
  const marco = editor ? getComputedStyle(editor) : s;
  const indicador = (parseFloat(marco.outlineWidth) > 0 && marco.outlineStyle !== 'none') || marco.boxShadow !== 'none';
  if (!e.dataset.tecladoId) e.dataset.tecladoId = String(++window.__tecladoN || (window.__tecladoN = 1));
  return {clave: e.dataset.tecladoId, tag: e.tagName, id: e.id, texto: (e.innerText || e.value || '').trim().slice(0, 40),
          editor: !!editor, indicador, visible: s.visibility !== 'hidden' && r.width > 0 && r.height > 0,
          enPantalla: r.bottom > 0 && r.top < innerHeight};
}
"""

TACTILES = r"""
() => {
  const visible = e => { const s = getComputedStyle(e), r = e.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0; };
  // WCAG 2.5.8 (AA): 24×24 px CSS como mínimo. Los enlaces dentro de un párrafo están exceptuados.
  return [...document.querySelectorAll('a[href],button,input:not([type=hidden]),select,[role="button"]')]
    .filter(visible)
    .filter(e => !(e.tagName === 'A' && e.closest('p,li,td,.tenue')) && !e.closest('.CodeMirror') && !e.classList.contains('saltar'))
    .map(e => ({e, r: e.getBoundingClientRect()}))
    .filter(({r}) => r.width < 24 || r.height < 24)
    .map(({e, r}) => ({tag: e.tagName, id: e.id, clase: String(e.className || '').slice(0, 40),
                       texto: (e.innerText || e.getAttribute('aria-label') || '').trim().slice(0, 30),
                       ancho: Math.round(r.width), alto: Math.round(r.height)}));
}
"""


def recorrer_con_tab(page, ruta, tabulables):
    """Recorre la página con Tab: detecta trampas de foco y controles sin indicador de foco visible.
    Del editor de código se sale con Escape (Tab ahí escribe sangría, a propósito)."""
    hallazgos, vistos, anterior, repetidos = [], {}, None, 0
    for _ in range(min(tabulables + 6, 90)):
        page.keyboard.press("Tab")
        foco = page.evaluate(FOCO)
        if foco is None:
            anterior = None                      # el foco salió del documento (barra del navegador): fin del ciclo
            continue
        if foco["editor"]:
            page.keyboard.press("Escape")
            salio = page.evaluate(FOCO)
            if salio is None or salio["clave"] == foco["clave"]:
                hallazgos.append(f"TECLADO {ruta}: no se puede salir del editor de código con Escape")
                break
        if anterior == foco["clave"]:
            repetidos += 1
            if repetidos >= 2:
                hallazgos.append(f"TECLADO {ruta}: el foco queda atrapado en {foco['tag']}#{foco['id']} «{foco['texto']}»")
                break
        else:
            repetidos = 0
        anterior = foco["clave"]
        if foco["clave"] in vistos:
            continue
        vistos[foco["clave"]] = foco
        if not foco["visible"]:
            hallazgos.append(f"TECLADO {ruta}: el foco cae en un control invisible: {foco['tag']}#{foco['id']}")
        elif not foco["indicador"]:
            hallazgos.append(f"FOCO {ruta}: sin indicador de foco visible: {foco['tag']}#{foco['id']} «{foco['texto']}»")
    return hallazgos


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:5077")
    parser.add_argument("--estricto", action="store_true", help="devolver 1 si hay hallazgos (puerta de CI)")
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
            page.goto(args.url + route)
            page.wait_for_timeout(100)
            for linea in recorrer_con_tab(page, route, data["tabulables"]):
                hallazgos += 1
                print(linea)

        # Páginas de cuenta con sesión, y después sin sesión (otro contexto, sin cookies).
        sin_sesion = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
        for pagina, rutas in ((page, RUTAS_DE_CUENTA_CON_SESION), (sin_sesion, RUTAS_DE_CUENTA)):
            for route in rutas:
                pagina.goto(args.url + route)
                pagina.wait_for_timeout(100)
                data = pagina.evaluate(AUDITAR)
                for item in data["sinNombre"]:
                    hallazgos += 1
                    print(f"ACCESIBILIDAD {route}: control sin nombre accesible: {item}")
                for linea in recorrer_con_tab(pagina, route, data["tabulables"]):
                    hallazgos += 1
                    print(linea)

        # Tamaño de los objetivos táctiles en un teléfono angosto.
        movil = browser.new_context(viewport={"width": 360, "height": 740}, has_touch=True).new_page()
        movil.goto(args.url + "/cuenta/__test__/bootstrap")
        for route in RUTAS + RUTAS_DE_CUENTA_CON_SESION:
            movil.goto(args.url + route)
            movil.wait_for_timeout(100)
            for item in movil.evaluate(TACTILES):
                hallazgos += 1
                print(f"TACTIL {route}: objetivo menor a 24×24 px: {item}")
        browser.close()
    print(f"Auditoría diagnóstica de teclado: {hallazgos} hallazgos en las rutas inspeccionadas.")
    # Sin --estricto es un diagnóstico informativo; con --estricto es una puerta de aceptación.
    return 1 if (hallazgos and args.estricto) else 0


if __name__ == "__main__":
    sys.exit(main())
