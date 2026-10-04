"""
Ejecución del código del alumno.

Protecciones (sin dependencias externas):
- Validación del árbol de sintaxis (AST) ANTES de ejecutar: no se permite `import`
  ni nombres/atributos que empiecen con `_` (así se cierra la puerta clásica
  `().__class__.__base__.__subclasses__()` para llegar a `os`). `_` solo sí se permite.
- Builtins recortados.
- Límite TOTAL de pasos (líneas ejecutadas) para cortar bucles infinitos.
- Límite de caracteres de salida.

Límites conocidos: no hay tope de memoria (haría falta un subproceso) y no es un
sandbox apto para código hostil; está pensado para proteger a un chico de errores
y de copiar/pegar cosas peligrosas, no de un atacante.
"""
import ast
import io
import random
import sys
from .error_handler import armar_mensaje_error

MAX_PASOS = 50_000
MAX_CARAS = 1000             # dado(caras): de 2 a 1000 caras
MAX_SALIDA = 20_000          # caracteres
ARCHIVO_ALUMNO = "<tu código>"
# str.format recorre atributos e índices escritos DENTRO del texto ("{0.__globals__[sys]}"), donde la
# validación del árbol no los ve: con eso se llegaba a los módulos del intérprete y a su entorno.
ATRIBUTOS_PROHIBIDOS = frozenset({"format", "format_map"})


# Las señales internas heredan de BaseException para que un `try/except Exception`
# escrito por el alumno no pueda tragárselas (p. ej. dentro de un bucle infinito).
class BucleInfinito(BaseException):
    """El código superó MAX_PASOS."""


class SalidaDemasiadoLarga(BaseException):
    """El código mostró más de MAX_SALIDA caracteres."""


class NecesitaEntrada(BaseException):
    """El programa llegó a preguntar() y no hay respuesta ni forma de pedirla.
    La interfaz web la muestra y vuelve a ejecutar con la respuesta agregada."""

    def __init__(self, pregunta):
        super().__init__(pregunta)
        self.pregunta = pregunta


class ErrorDado(Exception):
    """El chico le pidió algo raro al dado (se explica en lenguaje simple)."""


def _hacer_dado(azar):
    """dado(caras): un número al azar de 1 a `caras` (ADR-009). El azar sale de `azar` (random.Random con una
    semilla): con la misma semilla, el mismo programa tira siempre los mismos números, así se puede evaluar."""
    def dado(caras=6):
        if isinstance(caras, bool) or not isinstance(caras, int) or not 2 <= caras <= MAX_CARAS:
            raise ErrorDado(f"dado necesita un número entero de caras, de 2 a {MAX_CARAS}. Por ejemplo:  dado(6)")
        return azar.randint(1, caras)
    return dado


class CodigoNoPermitido(Exception):
    """El código usa algo que TortuScript no permite (import, nombres con _)."""

    def __init__(self, mensaje, linea=None):
        super().__init__(mensaje)
        self.linea = linea


# -------------------------
# VALIDACIÓN PREVIA (AST)
# -------------------------
def validar_codigo(codigo_python):
    """Levanta SyntaxError o CodigoNoPermitido. Devuelve el objeto de código compilado."""
    arbol = ast.parse(codigo_python, filename=ARCHIVO_ALUMNO)
    for nodo in ast.walk(arbol):
        linea = getattr(nodo, "lineno", None)
        if isinstance(nodo, (ast.Import, ast.ImportFrom)):
            raise CodigoNoPermitido("En TortuScript no se pueden importar módulos.", linea)
        if isinstance(nodo, ast.Attribute) and nodo.attr.startswith("_"):
            raise CodigoNoPermitido(
                f"No se puede usar «.{nodo.attr}»: los nombres que empiezan con _ son internos de Python.",
                linea)
        if isinstance(nodo, ast.Attribute) and nodo.attr in ATRIBUTOS_PROHIBIDOS:
            raise CodigoNoPermitido(
                f"No se puede usar «.{nodo.attr}». Para armar un texto, uní las partes con + o usá mostrar con comas.",
                linea)
        if isinstance(nodo, ast.Name) and nodo.id.startswith("__"):
            raise CodigoNoPermitido(
                f"No se puede usar «{nodo.id}»: es un nombre interno de Python.", linea)
    return compile(arbol, ARCHIVO_ALUMNO, "exec")


# -------------------------
# SALIDA CON TOPE
# -------------------------
class _Salida(io.StringIO):
    """Guarda lo que muestra el programa. `pantalla` además incluye el eco de las
    respuestas a preguntar() (como en una terminal); `programa` solo lo de print."""

    def __init__(self):
        super().__init__()
        self.programa = io.StringIO()

    def write(self, texto):
        if self.tell() + len(texto) > MAX_SALIDA:
            raise SalidaDemasiadoLarga()
        self.programa.write(texto)
        return super().write(texto)

    def eco(self, texto):
        """Solo pantalla (prompts y respuestas de preguntar)."""
        return super().write(texto)


# -------------------------
# INPUT
# -------------------------
class InputInteractivo:
    """input() del alumno, sin depender de ninguna interfaz:
    1. primero usa las `entradas_fijas` (respuestas ya conocidas), en orden;
    2. si se acabaron, detiene el programa con NecesitaEntrada: la web muestra la pregunta y
       vuelve a ejecutar con las respuestas acumuladas.
    Con `completar_con_vacio=True` responde "" en vez de detenerse (evaluación)."""

    def __init__(self, salida, entradas_fijas=None, registro=None, completar_con_vacio=False):
        self._salida = salida
        self._fijas = list(entradas_fijas or [])
        self._registro = registro
        self._vacio = completar_con_vacio

    def __call__(self, prompt=""):
        if self._fijas:
            respuesta = self._fijas.pop(0)
        elif self._vacio:
            respuesta = ""
        else:
            self._salida.eco(str(prompt))
            raise NecesitaEntrada(str(prompt))
        if self._registro is not None:
            self._registro.append(respuesta)
        self._salida.eco(f"{prompt}{respuesta}\n")
        return respuesta


# -------------------------
# ENTORNO
# -------------------------
def _hacer_globals(salida, entradas, registro, completar_con_vacio, semilla=None):
    return {
        "__builtins__": {
            "dado": _hacer_dado(random.Random(semilla)),
            "print": print,
            "input": InputInteractivo(salida, entradas, registro, completar_con_vacio),
            "range": range, "len": len, "int": int, "float": float, "str": str,
            "list": list, "dict": dict, "tuple": tuple, "set": set, "bool": bool,
            "True": True, "False": False, "None": None,
            "abs": abs, "min": min, "max": max, "sum": sum, "round": round,
            "type": type, "enumerate": enumerate, "zip": zip,
            "sorted": sorted, "reversed": reversed, "isinstance": isinstance,
            # para que `raise`/`try` y los mensajes funcionen normalmente
            "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError,
            "ZeroDivisionError": ZeroDivisionError, "IndexError": IndexError,
            "KeyError": KeyError, "NameError": NameError,
        }
    }


def _hacer_tracer(callback_linea):
    pasos = [0]

    def local(frame, event, arg):
        if event == "line":
            pasos[0] += 1
            if pasos[0] > MAX_PASOS:
                raise BucleInfinito()
            if callback_linea is not None:
                callback_linea(frame.f_lineno)
        return local

    def global_(frame, event, arg):
        # Solo se traza el código del alumno (no el del propio ejecutor).
        if frame.f_code.co_filename == ARCHIVO_ALUMNO:
            return local
        return None

    return global_


# -------------------------
# EJECUCIÓN PRINCIPAL
# -------------------------
def ejecutar_codigo(codigo_python, extra_globals=None, callback_linea=None,
                    entradas_fijas=None, detalles=None,
                    completar_con_vacio=None, semilla=None):
    """Ejecuta el código y devuelve (salida_pantalla, hubo_error, mensaje_error).

    - semilla: la del azar de dado() (misma semilla → mismas tiradas). None = azar nuevo.

    - callback_linea(n): se llama antes de ejecutar cada línea n del alumno (depurador).
    - entradas_fijas: respuestas para preguntar(), en orden. Si se pasa (aunque sea []),
      las preguntas de más se responden con "" (así se evalúa la solución oficial).
    - completar_con_vacio: True responde "" a las preguntas de más; False se detiene
      con la pregunta pendiente (web: respuestas ya dadas + la que falta). Por defecto,
      True solo si se pasaron entradas_fijas.
      Sin esto ni entradas, el programa se detiene en la primera pregunta y
      detalles['pregunta_pendiente'] la trae (app web: pregunta y re-ejecuta).
    - detalles (dict opcional): 'salida_programa' (solo prints), 'entradas' (respuestas
      usadas) y 'pregunta_pendiente' (None si el programa terminó).
    """
    salida = _Salida()
    registro_entradas = []
    pregunta_pendiente = None
    stdout_original = sys.stdout
    try:
        codigo = validar_codigo(codigo_python)
        if completar_con_vacio is None:
            completar_con_vacio = entradas_fijas is not None
        entorno = _hacer_globals(salida, entradas_fijas, registro_entradas, completar_con_vacio, semilla)
        if extra_globals:
            entorno.update(extra_globals)
        sys.stdout = salida
        sys.settrace(_hacer_tracer(callback_linea))
        try:
            exec(codigo, entorno)
        finally:
            sys.settrace(None)
            sys.stdout = stdout_original
        resultado = (salida.getvalue(), False, "")
    except NecesitaEntrada as e:
        pregunta_pendiente = e.pregunta
        resultado = (salida.getvalue(), False, "")
    except (BucleInfinito, SalidaDemasiadoLarga, Exception) as e:
        resultado = (salida.getvalue(), True, armar_mensaje_error(e, ARCHIVO_ALUMNO))
    finally:
        sys.settrace(None)
        sys.stdout = stdout_original
        if detalles is not None:
            detalles["salida_programa"] = salida.programa.getvalue()
            detalles["entradas"] = registro_entradas
            detalles["pregunta_pendiente"] = pregunta_pendiente
    return resultado
