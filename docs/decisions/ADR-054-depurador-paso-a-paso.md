# ADR-054 — Depurador paso a paso para programas de texto

- **Estado:** Aceptada (Marcos, 19/10/2026: «entra» en V1)
- **Fecha:** 19/10/2026
- **Responsable de decisión:** Marcos
- **Relacionado:** ADR-006 (runtime educativo y de juegos); `docs/ROADMAP_INVENTAR_CON_PYTHON.md` (L5); `tortuscript/proceso.py`, `tortuscript/worker.py`, `tortuscript/executor.py`

## Contexto

La tortuga ya marca, al reproducir un dibujo, la línea que se ejecuta. Los programas de texto (mostrar, preguntar, cuentas,
condicionales, bucles, funciones) no tienen nada parecido: el chico ve solo la salida final. Seguir el programa línea por
línea, mirando cómo cambian las variables, es la forma clásica de aprender a encontrar errores de semántica.

## Decisión

El depurador es un **registro**, no una sesión en vivo, igual que la tortuga y TortuGame:

1. El programa se ejecuta **completo y una sola vez** en el mismo worker, con los mismos límites de `proceso.py`
   (tiempo, CPU, memoria, archivos, entorno) y el mismo análisis de código permitido. No hay proceso que quede esperando
   órdenes, ni comandos «pausar/seguir» que viajen al servidor.
2. Dentro del worker, `sys.settrace` registra solo los eventos `line` del código del alumno (no de la biblioteca ni del
   ejecutor). Cada paso guarda: número de línea **del código del alumno**, variables del alumno visibles en ese momento
   y salida acumulada.
3. Límites del registro: a lo sumo `MAX_PASOS = 500` pasos; a lo sumo 20 variables por paso; solo tipos simples
   (`int`, `float`, `bool`, `str`, `None`, y listas o diccionarios de esos tipos), y cada valor como `repr` recortado a
   60 caracteres. Al llegar al tope, el registro se corta y se avisa («el programa siguió, pero el depurador muestra
   solo los primeros 500 pasos»). Nada de eso cambia la ejecución ni su salida.
4. Las líneas de TortuScript se mapean a las de Python con la misma correspondencia que usa la tortuga; si una línea no
   se puede mapear, ese paso se muestra sin marca de línea.
5. La página reproduce el registro: «siguiente», «anterior», «hasta el final» y velocidad. Todo en el navegador, sin pedidos
   nuevos al servidor.
6. Es una herramienta, no una evaluación: no da ni quita XP, no cambia el progreso y no se guarda.
7. Ruta nueva `POST /api/depurar` con el mismo control de acceso, límite de tamaño y límite de pedidos que `/api/ejecutar`.

## Condiciones antes de integrar

- Revisión de seguridad del cambio en el worker (lo que se serializa del registro no puede filtrar nada fuera de las
  variables del alumno: ni `__builtins__`, ni módulos, ni objetos del ejecutor).
- Tests: tope de pasos, recorte de valores, filtrado de variables, programas con `preguntar`, bucles infinitos (corta el
  límite de tiempo como hoy) y correspondencia de líneas en TortuScript y Python.

## Consecuencias

- Costo: `settrace` hace más lento el programa; con el tope de 500 pasos y los límites actuales alcanza para los
  programas de las lecciones. Si no alcanza, se ajusta el tope, no los límites del worker.
- Prepara L6 (simulaciones) y L2 (feedback de errores de semántica).
