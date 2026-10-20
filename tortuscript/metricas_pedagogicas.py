
"""Métricas pedagógicas locales (P6, docs/ESPECIFICACION_P1_P6.md).

Puro: solo lee lo que el progreso ya guarda; no recopila datos nuevos ni manda nada afuera.
"""
from . import dominio, planificador

ESTADOS = dominio.ESTADOS


def _entero(valor, minimo=None):
    return isinstance(valor, int) and not isinstance(valor, bool) and (minimo is None or valor >= minimo)


def metricas(progreso, cursos, mapa=None):
    """Resumen de pasos, escritura, repaso y conceptos de un perfil. Los registros dañados se cuentan y se ignoran."""
    if not isinstance(progreso, dict):
        progreso = {}
    
    unidades = dominio.cargar_mapa() if mapa is None else mapa
    
    # Init counters
    res = {
        "pasos_rapidos": {"total": 0, "primer_intento": 0, "con_reintentos": 0, "ayudados": 0},
        "escribir": {"total": 0, "autonomos": 0, "con_ayuda": 0},
        "repaso": {"tarjetas": 0, "aciertos": 0, "fallos": 0, "tasa_acierto": None, "retenidas": 0},
        "conceptos": {estado: 0 for estado in ESTADOS},
        "recomendaciones": {},
        "datos_danados": 0
    }
    
    # 1. Pasos (rápidos y escribir)
    lecciones_progreso = progreso.get("lecciones", {})
    if not isinstance(lecciones_progreso, dict):
        lecciones_progreso = {}

    for curso in cursos if isinstance(cursos, list) else []:
        if not isinstance(curso, dict): continue
        for seccion in curso.get("secciones", []) if isinstance(curso.get("secciones"), list) else []:
            if not isinstance(seccion, dict): continue
            for leccion in seccion.get("lecciones", []) if isinstance(seccion.get("lecciones"), list) else []:
                if not isinstance(leccion, dict): continue
                
                l_id = leccion.get("id")
                if not isinstance(l_id, str): continue
                
                pasos = leccion.get("pasos", [])
                if not isinstance(pasos, list): continue
                
                l_prog = lecciones_progreso.get(l_id)
                if not isinstance(l_prog, dict): continue
                
                pasos_prog = l_prog.get("pasos", {})
                if not isinstance(pasos_prog, dict): continue
                
                for idx, paso in enumerate(pasos):
                    if not isinstance(paso, dict): continue
                    
                    tipo = paso.get("tipo")
                    registro = pasos_prog.get(str(idx))
                    
                    if tipo == "explicacion":
                        continue
                        
                    if registro is None:
                        continue
                        
                    if not isinstance(registro, dict):
                        res["datos_danados"] += 1
                        continue
                    
                    if tipo in ("elegir", "predecir", "completar", "ordenar"):
                        xp = registro.get("xp")
                        if not isinstance(xp, int) or isinstance(xp, bool):
                            res["datos_danados"] += 1
                            continue
                        
                        res["pasos_rapidos"]["total"] += 1
                        if xp >= 5:
                            res["pasos_rapidos"]["primer_intento"] += 1
                        elif xp >= 1:
                            res["pasos_rapidos"]["con_reintentos"] += 1
                        else:
                            res["pasos_rapidos"]["ayudados"] += 1
                            
                    elif tipo == "escribir":
                        res["escribir"]["total"] += 1
                        estrellas = registro.get("estrellas")
                        perfecto = registro.get("perfecto")
                        
                        is_autonomo = False
                        if isinstance(estrellas, int) and not isinstance(estrellas, bool) and estrellas >= 3:
                            is_autonomo = True
                        elif perfecto is True:
                            is_autonomo = True
                            
                        if is_autonomo:
                            res["escribir"]["autonomos"] += 1
                        else:
                            res["escribir"]["con_ayuda"] += 1

    # 2. Repaso
    repaso_prog = progreso.get("repaso", {})
    if not isinstance(repaso_prog, dict):
        repaso_prog = {}
        
    for clave, tarjeta in repaso_prog.items():
        if not isinstance(tarjeta, dict):
            res["datos_danados"] += 1
            continue
            
        caja = tarjeta.get("caja", 0)
        aciertos = tarjeta.get("aciertos", 0)
        fallos = tarjeta.get("fallos", 0)
        
        if not (_entero(caja, 0) and _entero(aciertos, 0) and _entero(fallos, 0)):
            res["datos_danados"] += 1
            continue
            
        res["repaso"]["tarjetas"] += 1
        res["repaso"]["aciertos"] += aciertos
        res["repaso"]["fallos"] += fallos
        if caja >= 3 and aciertos >= 2:
            res["repaso"]["retenidas"] += 1
            
    if res["repaso"]["aciertos"] + res["repaso"]["fallos"] > 0:
        res["repaso"]["tasa_acierto"] = round(res["repaso"]["aciertos"] / (res["repaso"]["aciertos"] + res["repaso"]["fallos"]), 3)
        
    # 3. Conceptos y Recomendaciones
    # dominio ya ignora los datos dañados sin lanzar
    for uid, estado in dominio.dominio(progreso, cursos, unidades).items():
        res["conceptos"][estado["estado"]] += 1
        reco = planificador.recomendar(estado)
        if reco:
            res["recomendaciones"][uid] = reco

    return res
