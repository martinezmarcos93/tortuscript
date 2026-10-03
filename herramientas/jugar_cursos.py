#!/usr/bin/env python3
"""Juega TODAS las lecciones de los cursos por la interfaz real (Chromium), resolviendo cada paso desde
los propios datos del curso. Sirve para verificar que ninguna lección quedó rota después de un cambio.

Requiere Playwright (opcional, no está en requirements.txt) y un servidor de prueba andando:
    python herramientas/servidor_de_prueba.py            (en otra terminal)
    python herramientas/jugar_cursos.py [curso ...] [--url http://127.0.0.1:5077]

Sale con código 1 si alguna lección falla o si el navegador registra errores de consola.
"""
import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from tortuscript import contenido  # noqa: E402


def _modal_si_hay(pg, entradas):
    if pg.is_visible("#modal-pregunta"):
        pg.fill("#mp-campo", entradas.pop(0) if entradas else "x")
        pg.keyboard.press("Enter")
        return True
    return False


def _esperar_pie(pg, entradas, clase="bien", intentos=400):
    for _ in range(intentos):
        if _modal_si_hay(pg, entradas):
            continue
        if pg.locator(f".pie-leccion.{clase}").count() and pg.is_visible(".pie-leccion"):
            return
        pg.wait_for_timeout(100)
    raise AssertionError(f"no apareció la barra de feedback «{clase}»")


def _click_exacto(pg, selector, texto):
    idx = pg.evaluate("([s, t]) => [...document.querySelectorAll(s)].findIndex(e => e.textContent === t && !e.disabled)",
                      [selector, texto])
    assert idx >= 0, f"no encontré {selector} con el texto {texto!r}"
    pg.locator(selector).nth(idx).click()


def _jugar_paso(pg, paso):
    tipo, entradas = paso["tipo"], list(paso.get("entradas_prueba") or [])
    if tipo == "explicacion":
        # El pie empieza oculto y lo muestra leccion.js; esperar a que el
        # navegador lo inicialice y a que termine la comprobación asíncrona.
        contador_antes = pg.locator("#lec-contador").inner_text()
        try:
            pg.wait_for_selector("#lec-principal:visible", timeout=10000)
        except Exception as exc:
            raise AssertionError(
                f"El control de explicación no aparece en {pg.url}; "
                f"cuerpo={pg.locator('body').inner_text()[:400]!r}"
            ) from exc
        pg.click("#lec-principal")
        pg.wait_for_function(
            "(antes) => { const c = document.querySelector('#lec-contador'); "
            "const f = document.querySelector('#lec-paso h2'); "
            "return !c || c.textContent !== antes || (f && /Lección perfecta|Lección completada|Práctica terminada/.test(f.textContent)); }",
            arg=contador_antes,
            timeout=10000,
        )
        return
    if tipo in ("elegir", "predecir"):
        pg.wait_for_selector(".opcion-paso")
        _click_exacto(pg, ".opcion-paso", str(paso["opciones"][paso["correcta"]]))
    elif tipo == "completar":
        pg.wait_for_selector(".ficha-paso")
        for respuesta in paso["respuesta"]:
            _click_exacto(pg, ".ficha-paso", respuesta)
    elif tipo == "ordenar":
        pg.wait_for_selector(".zona-ordenar.pool .linea-paso")
        for linea in paso["lineas"]:
            _click_exacto(pg, ".zona-ordenar.pool .linea-paso", linea)
    elif tipo == "escribir":
        pg.wait_for_selector(".paso-caja .CodeMirror")
        pg.evaluate("s => document.querySelector('.paso-caja .CodeMirror').CodeMirror.setValue(s)", paso["solucion"])
        boton = (
            "text=▶ Probar" if paso.get("web")
            else "text=▶ Ejecutar consulta" if paso.get("lenguaje") == "sql"
            else "text=▶ Jugar" if paso.get("juego")
            else "text=▶ Dibujar" if paso.get("tortuga")
            else "text=▶ Ejecutar"
        )
        pg.click(boton)
        _esperar_pie(pg, entradas)
        pg.click("#lec-principal")
        return
    pg.click("#lec-principal")               # Comprobar
    _esperar_pie(pg, entradas)
    pg.click("#lec-principal")               # Continuar


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cursos", nargs="*", help="ids de curso (todos si no se pasa ninguno)")
    ap.add_argument("--url", default="http://127.0.0.1:5077")
    args = ap.parse_args()
    from playwright.sync_api import sync_playwright

    ids = [c for c in contenido.ids_cursos() if not args.cursos or c in args.cursos]
    errores, pasos_jugados = [], 0
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pg = navegador.new_page(viewport={"width": 1280, "height": 900})
        pg.on("console", lambda m: errores.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errores.append(str(e)))
        pg.goto(args.url + "/cuenta/__test__/bootstrap")
        pg.goto(args.url + "/bienvenida")
        pg.evaluate("t => fetch('/api/onboarding', {method: 'POST', headers: {'Content-Type': 'application/json', "
                    "'X-Tortu-Token': t}, body: JSON.stringify({meta_min: 10})})", "prueba")
        pg.wait_for_timeout(500)
        for curso_id in ids:
            curso = contenido.cargar_curso(curso_id)
            for seccion in curso["secciones"]:
                for lec in seccion["lecciones"]:
                    pg.goto(f"{args.url}/leccion/{lec['id']}")
                    if "/leccion/" not in pg.url:
                        print(f"BLOQUEADA {curso_id}/{lec['id']} → {pg.url} (¿faltan cursos previos? corré todos, en orden)")
                        return 1
                    for paso in lec["pasos"]:
                        _jugar_paso(pg, paso)
                        pasos_jugados += 1
                    pg.wait_for_selector("text=¡Lección perfecta!", timeout=8000)
                    print("OK", curso_id, lec["id"], len(lec["pasos"]), "pasos", flush=True)
        estado = pg.evaluate("t => fetch('/api/estado', {headers: {'X-Tortu-Token': t}}).then(r => r.json())", "prueba")
        navegador.close()
    print(f"pasos jugados: {pasos_jugados} · lecciones {estado['lecciones_hechas']}/{estado['lecciones_total']} · XP {estado['xp']}")
    print("errores de consola:", errores[:5] or "ninguno")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
