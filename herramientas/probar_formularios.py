#!/usr/bin/env python3
"""Prueba en un navegador real los formularios de cuenta: ingresar, elegir perfil, renombrar y cerrar sesión.

Las pruebas con el cliente de Flask no mandan las cabeceras que manda un navegador (Origin, Sec-Fetch-Site):
un control de origen puede pasar todos los tests y aun así rechazar a todas las personas reales. Pasó: con
`Referrer-Policy: no-referrer` Chromium manda `Origin: null` y el ingreso por formulario respondía 403.

Requiere Playwright y el servidor de prueba (herramientas/servidor_de_prueba.py).
"""
import argparse
import sys

CORREO, CLAVE = "prueba@example.invalid", "clave-temporal-solo-pruebas-123"     # las del servidor de prueba


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:5077")
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright

    fallos = []
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pagina = navegador.new_page()
        rechazos = []
        pagina.on("response", lambda r: rechazos.append(f"{r.request.method} {r.url} → {r.status}")
                  if r.request.method == "POST" and r.status in (403, 500) else None)

        def paso(nombre, condicion):
            print(("OK   " if condicion else "FALLA") + " " + nombre)
            if not condicion:
                fallos.append(nombre)

        def enviar(selector):
            with pagina.expect_navigation():
                pagina.click(selector)

        # 1. Clave incorrecta: la misma página con un mensaje, no un 403 ni un JSON crudo.
        pagina.goto(args.url + "/cuenta/ingresar?next=/logros")
        pagina.fill("#email", CORREO)
        pagina.fill("#password", "no-es-la-clave-123")
        enviar("form[action$='/cuenta/login'] button[type=submit]")
        paso("clave incorrecta muestra el formulario con un aviso",
             pagina.locator("[role=alert]").count() == 1 and pagina.locator("#email").count() == 1)

        # 2. Ingreso correcto → selector de perfiles.
        pagina.fill("#email", CORREO)
        pagina.fill("#password", CLAVE)
        enviar("form[action$='/cuenta/login'] button[type=submit]")
        paso("ingresar lleva al selector de perfiles", "/cuenta/seleccionar-perfil" in pagina.url)

        # 3. Elegir perfil → llega al destino pedido antes de ingresar.
        enviar("form[action$='/cuenta/perfil'] button[type=submit]")
        # (Un perfil que todavía no pasó por la bienvenida va primero ahí: también es correcto.)
        paso("elegir perfil lleva al destino pedido (/logros) o a la bienvenida",
             pagina.url.rstrip("?").endswith(("/logros", "/bienvenida")))

        # 4. Renombrar el perfil desde la configuración y dejarlo como estaba.
        pagina.goto(args.url + "/cuenta/configuracion")
        original = pagina.input_value("#nombre-1")
        pagina.fill("#nombre-1", original + " 2")
        enviar("form[action$='/renombrar'] button[type=submit]")
        paso("renombrar perfil confirma el cambio", pagina.locator("[role=status]").count() >= 1
             and pagina.input_value("#nombre-1") == original + " 2")
        pagina.fill("#nombre-1", original)
        enviar("form[action$='/renombrar'] button[type=submit]")
        paso("el nombre vuelve al original", pagina.input_value("#nombre-1") == original)

        # 5. Una acción de la app (API con token) sigue funcionando desde el navegador.
        pagina.goto(args.url + "/resumen")
        estado = pagina.evaluate(
            "t => fetch('/api/config', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Tortu-Token': t},"
            " body: JSON.stringify({meta_min: 10})}).then(r => r.status)", "prueba")
        paso("la API acepta un POST de la propia página", estado == 200)

        # 6. Cerrar sesión por formulario.
        pagina.goto(args.url + "/cuenta/configuracion")
        enviar("form[action$='/cuenta/logout'] button[type=submit]")
        paso("cerrar sesión vuelve al ingreso", "/cuenta/ingresar" in pagina.url)
        pagina.goto(args.url + "/mapa")
        paso("sin sesión el mapa pide ingresar", "/cuenta/ingresar" in pagina.url)

        paso("ningún formulario propio fue rechazado (403) ni rompió (500)", not rechazos)
        for linea in rechazos:
            print("     " + linea)
        navegador.close()
    print(f"Formularios en navegador: {len(fallos)} falla(s).")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
