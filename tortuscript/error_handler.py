"""
Explica los errores de Python en lenguaje simple para chicos de 10 a 14 años.

- `armar_mensaje_error(excepcion, archivo)` arma el mensaje completo: qué pasó, en
  qué línea mirar y cómo arreglarlo; el detalle técnico (en inglés) va aparte, al
  final, para quien tenga curiosidad.
- `explicar_error(texto)` se mantiene por compatibilidad: recibe "Tipo: detalle".
"""
import re


def _explicacion(tipo, detalle):
    d = detalle.lower()

    if tipo == "BucleInfinito":
        return ("🔁 Tu programa no termina nunca\n\n"
                "Repitió tantas veces que parece un bucle infinito.\n\n"
                "💡 Revisá tu `mientras`: ¿la condición en algún momento se vuelve falsa?\n"
                "   Por ejemplo, ¿te olvidaste de sumar 1 al contador?")
    if tipo == "RecursionError":
        return ("🌀 Una función se llama a sí misma sin parar\n\n"
                "💡 Toda función que se llama a sí misma necesita un caso en el que se detenga.")
    if tipo in ("MemoryError", "SinMemoria"):
        return ("🧠 Tu programa usó demasiada memoria\n\n"
                "💡 ¿Estás armando un texto o una lista gigante? Probá con números más chicos.")
    if tipo == "TardoDemasiado":
        return ("⏱️ Tu programa tardó demasiado y lo frenamos\n\n"
                "💡 ¿Hay un bucle que no termina o una cuenta enorme?")
    if tipo == "Ocupado":
        return ("🐢 Hay muchos programas corriendo a la vez\n\n"
                "💡 Tu código no tiene nada malo: esperá unos segundos y probá de nuevo.")
    if tipo == "SalidaDemasiadoLarga":
        return ("📜 Tu programa mostró demasiado texto\n\n"
                "💡 ¿Pusiste un `mostrar` dentro de un bucle que repite muchísimas veces?")
    if tipo == "ErrorTortuga":
        return f"🐢 La tortuga no entendió la orden\n\n{detalle}"
    if tipo == "ErrorDado":
        return f"🎲 El dado no entendió\n\n{detalle}"
    if tipo == "ErrorJuego":
        return f"🎮 El juego no entendió\n\n{detalle}"
    if tipo == "CodigoNoPermitido":
        return f"🚫 Eso no se puede usar acá\n\n{detalle}"

    if tipo == "IndentationError" or "indent" in d:
        return ("❌ Error de indentación (los espacios al principio)\n\n"
                "Las líneas que van ADENTRO de un si, repetir, mientras o funcion\n"
                "tienen que estar corridas hacia la derecha, todas igual.\n\n"
                "💡 Ejemplo:\n"
                "si edad > 10:\n"
                "    mostrar \"Grande\"   ← con 4 espacios adelante")
    if tipo == "SyntaxError":
        if "unterminated string" in d or "eol while scanning" in d or "eof while scanning" in d:
            pista = "- Te faltó cerrar las comillas de un texto: \"así\""
        elif "expected ':'" in d:
            pista = "- Te faltaron los dos puntos : al final de la línea (si, repetir, mientras, funcion)"
        elif "was never closed" in d or "unexpected eof" in d:
            pista = "- Abriste un paréntesis ( o corchete [ y no lo cerraste"
        elif "invalid syntax" in d:
            pista = ("- Hay una palabra mal escrita o en un orden raro\n"
                     "- ¿Te faltó una coma o un operador (+, -, ==)?")
        else:
            pista = "- Revisá que la línea esté completa y bien escrita"
        return ("❌ Error de escritura (sintaxis)\n\n"
                "Python no entendió cómo está escrita esa línea.\n\n"
                f"💡 Posible causa:\n{pista}")
    if tipo == "NameError":
        m = re.search(r"name '([^']+)' is not defined", detalle)
        nombre = m.group(1) if m else "ese nombre"
        return ("❌ Nombre desconocido\n\n"
                f"Usaste «{nombre}», pero no existe todavía.\n\n"
                "💡 Revisá:\n"
                f"- ¿Creaste «{nombre}» antes con  {nombre} es ...?\n"
                "- ¿Está escrito exactamente igual (mayúsculas incluidas)?\n"
                "- Si es texto, ¿le faltan las comillas?")
    if tipo == "TypeError":
        if "can only concatenate str" in d or "unsupported operand" in d or "must be str" in d:
            return ("❌ Estás mezclando texto con números\n\n"
                    "💡 \"Tengo \" + 12  ❌   →   \"Tengo \" + str(12)  ✅\n"
                    "   Y si el número vino de preguntar, convertilo con int(...)")
        return ("❌ Error de tipo\n\n"
                "Estás usando un dato de una forma que no corresponde.\n\n"
                "💡 Revisá qué tipo de dato tiene cada variable (texto, número, lista).")
    if tipo == "ZeroDivisionError":
        return "❌ División por cero\n\nNo se puede dividir por 0.\n\n💡 Revisá el número de abajo de la división."
    if tipo == "ValueError":
        return ("❌ Valor incorrecto\n\n"
                "Intentaste convertir algo que no se puede, como int(\"hola\").\n\n"
                "💡 Si pediste un número con preguntar, escribí solo dígitos.")
    if tipo == "IndexError":
        return ("❌ Posición fuera de la lista\n\n"
                "Pediste un elemento que no existe. Ojo: las listas empiezan en 0.")
    if tipo == "KeyError":
        return "❌ Clave que no existe\n\nBuscaste en un diccionario algo que no está guardado."
    if tipo == "AttributeError":
        return "❌ Eso no tiene esa propiedad\n\nEl dato no tiene lo que buscaste después del punto."
    return ("❌ Ocurrió un error poco común\n\n"
            "💡 Revisá tu código paso a paso, línea por línea.")


def _linea_del_error(excepcion, archivo):
    if isinstance(excepcion, SyntaxError):
        return excepcion.lineno
    if getattr(excepcion, "linea", None):
        return excepcion.linea
    linea = None
    tb = excepcion.__traceback__
    while tb is not None:
        if tb.tb_frame.f_code.co_filename == archivo:
            linea = tb.tb_lineno
        tb = tb.tb_next
    return linea


_BLOQUES = ("if", "elif", "else", "for", "while", "def", "class", "try", "except", "finally", "with")


def _falta_dos_puntos(excepcion):
    """True si la línea con error abre un bloque (if, for, def...) y no termina en ':'."""
    if "invalid syntax" not in (excepcion.msg or ""):
        return False
    texto = (excepcion.text or "").split("#")[0].strip()
    primera = texto.split(" ", 1)[0].rstrip(":(")
    return bool(texto) and primera in _BLOQUES and not texto.endswith(":")


def armar_mensaje_error(excepcion, archivo="<tu código>"):
    tipo = type(excepcion).__name__
    detalle = excepcion.msg if isinstance(excepcion, SyntaxError) else str(excepcion)
    aclarado = detalle
    if isinstance(excepcion, SyntaxError) and _falta_dos_puntos(excepcion):
        aclarado = "expected ':'"          # Python < 3.10 solo dice "invalid syntax"
    partes = [_explicacion(tipo, aclarado or "")]
    linea = _linea_del_error(excepcion, archivo)
    if linea:
        partes.append(f"📍 Mirá la línea {linea}")
    if tipo not in ("BucleInfinito", "SalidaDemasiadoLarga", "CodigoNoPermitido", "ErrorTortuga", "ErrorDado", "ErrorJuego",
                    "MemoryError", "SinMemoria", "TardoDemasiado", "Ocupado"):
        partes.append(f"🔧 Para curiosos (en inglés): {tipo}: {detalle}")
    return "\n\n".join(partes)


def explicar_error(error_msg):
    """Compatibilidad: recibe 'Tipo: detalle' y devuelve la explicación."""
    tipo, _, detalle = error_msg.partition(":")
    return _explicacion(tipo.strip(), detalle.strip())
