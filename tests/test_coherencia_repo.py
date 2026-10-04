"""Barrido 1 — nada huérfano y un solo registro de lengua.

Plantillas que nadie renderiza, archivos estáticos que nadie pide, módulos que nadie importa, contenido que
nadie carga y herramientas que ningún documento menciona son deuda que se acumula sin que falle nada. Y el
producto le habla al chico de «vos»: una consigna en «tú» o con palabras de otra variante desentona.
"""
import json
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CARPETAS_DE_CODIGO = ("web", "tortuscript", "herramientas", "lanzadores", "despliegue", ".github")
EXTENSIONES = {".py", ".html", ".js", ".css", ".json", ".yml", ".sh", ".bat", ".ps1", ".command", ".iss", ".md", ".txt"}
IGNORADAS = {"__pycache__", "node_modules", ".venv", "dist", "build"}


def _archivos(*carpetas):
    for carpeta in carpetas:
        base = RAIZ / carpeta
        if not base.exists():
            continue
        for ruta in sorted(base.rglob("*")):
            if ruta.is_file() and not (IGNORADAS & set(ruta.relative_to(RAIZ).parts)):
                yield ruta


def _textos(*carpetas, sueltos=()):
    textos = {}
    for ruta in list(_archivos(*carpetas)) + [RAIZ / s for s in sueltos]:
        if ruta.suffix in EXTENSIONES and ruta.is_file():
            textos[ruta] = ruta.read_text(encoding="utf-8", errors="ignore")
    return textos


class TestNadaHuerfano(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codigo = _textos(*CARPETAS_DE_CODIGO, sueltos=("iniciar_web.py", "wsgi.py"))
        cls.todo = dict(cls.codigo)
        cls.todo.update(_textos("docs", "tests", sueltos=("README.md", "CLAUDE.md", "CHANGELOG.md")))

    def _mencionado(self, texto, propio, donde=None):
        return any(texto in contenido for ruta, contenido in (donde or self.codigo).items() if ruta != propio)

    def test_cada_plantilla_se_usa(self):
        base = RAIZ / "web" / "templates"
        sin_uso = [str(p.relative_to(base)) for p in _archivos("web/templates")
                   if not self._mencionado(p.relative_to(base).as_posix(), p)]
        self.assertEqual(sin_uso, [])

    def test_cada_archivo_estatico_se_usa(self):
        sin_uso = [str(p.relative_to(RAIZ)) for p in _archivos("web/static")
                   if p.suffix != ".txt" and not self._mencionado(p.name, p)]      # los .txt son las licencias de las fuentes
        self.assertEqual(sin_uso, [])

    def test_cada_modulo_se_importa_fuera_de_los_tests(self):
        sin_uso = []
        for modulo in _archivos("tortuscript"):
            if modulo.suffix != ".py" or modulo.name == "__init__.py":
                continue
            patron = re.compile(rf"\b{re.escape(modulo.stem)}\b")
            if not any(patron.search(t) for ruta, t in self.codigo.items() if ruta != modulo and ruta.suffix == ".py"):
                sin_uso.append(modulo.name)
        self.assertEqual(sin_uso, [])

    def test_cada_archivo_de_contenido_se_carga(self):
        python = {r: t for r, t in self.codigo.items() if r.suffix == ".py"}
        sin_uso = []
        for archivo in _archivos("contenido"):
            carpeta = archivo.parent.name
            if not any(archivo.name in t or archivo.stem in t or f'"{carpeta}"' in t for t in python.values()):
                sin_uso.append(str(archivo.relative_to(RAIZ)))
        self.assertEqual(sin_uso, [])

    def test_cada_herramienta_esta_documentada_o_conectada(self):
        sin_mencion = [p.name for p in _archivos("herramientas")
                       if p.suffix == ".py" and not self._mencionado(p.name, p, self.todo)]
        self.assertEqual(sin_mencion, [])

    def test_cada_adr_figura_en_el_indice(self):
        indice = (RAIZ / "docs" / "decisions" / "README.md").read_text(encoding="utf-8")
        faltan = [p.name for p in sorted((RAIZ / "docs" / "decisions").glob("ADR-*.md")) if p.name not in indice]
        self.assertEqual(faltan, [])

    def test_el_indice_y_cada_adr_dicen_el_mismo_estado(self):
        indice = (RAIZ / "docs" / "decisions" / "README.md").read_text(encoding="utf-8")
        distintos = []
        for adr in sorted((RAIZ / "docs" / "decisions").glob("ADR-*.md")):
            estado = re.search(r"^- Estado:\s*\**\s*(\w+)", adr.read_text(encoding="utf-8"), re.MULTILINE)
            fila = re.search(rf"\]\({re.escape(adr.name)}\)[^\n]*\|\s*\**\s*(\w+)[^|\n]*\|\s*$", indice, re.MULTILINE)
            if estado and fila and estado.group(1).lower() != fila.group(1).lower():
                distintos.append(f"{adr.name}: «{estado.group(1)}» en la ADR, «{fila.group(1)}» en el índice")
        self.assertEqual(distintos, [])


class TestRegistroDeLengua(unittest.TestCase):
    """Lo que lee el chico o el adulto: contenido, plantillas y mensajes del navegador."""
    # Segunda persona en «tú» y formas de otras variantes del español. Las terceras personas que coinciden en la
    # escritura («mostrar escribe el texto», «SELECT elige qué datos leer») no son tuteo: el patrón pide el pronombre
    # o una forma que solo existe en segunda persona.
    TUTEO = re.compile(
        r"\b(tú|ti|contigo|tienes|puedes|quieres|debes|necesitas|eres|estás listo|sabes que|"
        r"haz clic|pulsa (el|la|en)|pincha|"
        r"vosotros|os (doy|damos|dejo)|pulsad|escribid|"
        r"ordenador|fichero|vídeo|móvil)\b", re.IGNORECASE)

    def _visible(self):
        for ruta in _archivos("contenido", "web/templates", "web/static/js"):
            if ruta.suffix == ".json":
                yield ruta, "\n".join(self._cadenas(json.loads(ruta.read_text(encoding="utf-8"))))
            elif ruta.suffix == ".html":
                yield ruta, ruta.read_text(encoding="utf-8")
            elif ruta.suffix == ".js":
                # Solo los textos entre comillas: los comentarios son para quien mantiene el código.
                yield ruta, "\n".join(m.group(2) for m in
                                      re.finditer(r"""(["'`])((?:\\.|(?!\1).)*)\1""", ruta.read_text(encoding="utf-8")))

    def _cadenas(self, nodo, clave=None):
        if isinstance(nodo, str):
            # Identificadores, código y soluciones no son prosa.
            if clave not in ("id", "codigo", "solucion", "inicial", "esperado", "curso", "leccion", "seccion"):
                yield nodo
        elif isinstance(nodo, dict):
            for k, v in nodo.items():
                yield from self._cadenas(v, k)
        elif isinstance(nodo, list):
            for v in nodo:
                yield from self._cadenas(v, clave)

    def test_el_producto_habla_de_vos(self):
        hallazgos = []
        for ruta, texto in self._visible():
            for linea in texto.splitlines():
                m = self.TUTEO.search(linea)
                if m:
                    hallazgos.append(f"{ruta.relative_to(RAIZ)}: «{m.group(0)}» en «{linea.strip()[:80]}»")
        self.assertEqual(hallazgos, [])


if __name__ == "__main__":
    unittest.main()
