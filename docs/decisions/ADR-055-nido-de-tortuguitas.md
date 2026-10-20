# ADR-055 — Nido de tortuguitas: constancia diaria, premios y ayudas especiales

- **Estado:** Aceptada (Marcos, 20/10/2026, eligió cada opción)
- **Fecha:** 20/10/2026
- **Responsable de decisión:** Marcos
- **Relacionado:** gamificación amable (esquema v5: racha, congeladores, logros), ADR-050 (gratuidad), ADR-052 (dominio), P4 (pistas)

## Contexto

Ya existen la racha de días seguidos, los congeladores (uno cada 7 días seguidos, hasta 2), los logros de racha y la meta
diaria (5, 10 o 15 minutos). Falta un incentivo para volver cada día que no castigue a quien no puede usar la compu todos
los días (los chicos de 9 a 15 años dependen de un adulto) y que dé algo útil o lindo a cambio.

## Decisión

1. **Tortuguita del día.** La primera vez en el día que el chico **cumple su meta diaria**, nace una tortuguita en su
   nido. Una por día, con la fecha del servidor.
2. **Nido de 7.** Al juntar 7 tortuguitas el nido se completa y queda **un premio por elegir**. **No hacen falta días
   seguidos** y **nunca se pierden tortuguitas** por faltar. La racha de días seguidos sigue igual, aparte.
3. **El chico elige el premio** de cada nido completo:
   - **un cosmético permanente** para su tortuga (se ve en su perfil y en la tortuga que dibuja), o
   - **un pack de 3 ayudas especiales**, que elige entre:
     - 🔍 **Lupa** (elegir/predecir con 3 o más opciones): tacha una opción incorrecta;
     - 🕵️ **Tortuga detective** (escribir, después de un intento fallido): señala dónde empieza el problema —la línea del
       error si el programa falló al correr, o la primera línea de la salida que no coincide— sin mostrar la solución;
     - 🧊 **Congelador extra**: suma un congelador (respeta el máximo de 2);
     - 🐢 **Consulta extra a Tortu**: una consulta más al tutor ese día (solo si el tutor está disponible).
4. **Honestidad pedagógica.** Una ayuda especial cuenta como ayuda: con la lupa, un paso rápido vale como reintento
   (`XP_REINTENTO`, evidencia «débil» para el dominio); el detective cuenta como una pista vista en `escribir`
   (mismas estrellas que hoy). No se castiga más que una pista común.
5. **Límites:** como máximo 6 ayudas guardadas en total; los premios pendientes se acumulan sin límite.
6. Sin compras, sin datos personales nuevos, igual para cuentas gratis y premium.

## Datos (esquema v12, aditivo)

```
"nido": {"tortuguitas": 0, "dias": [], "completos": 0, "premios_pendientes": 0},
"ayudas_especiales": {"lupa": 0, "detective": 0, "tortu": 0},
"cosmeticos": [],
"cosmetico_puesto": null
```
`dias` guarda las fechas en que nació una tortuguita (últimas 30). La migración solo agrega valores por defecto.

## Consecuencias

- Un perfil viejo arranca con el nido vacío; nada de lo ganado antes cambia.
- El congelador extra puede no estar disponible si ya hay 2.
- El catálogo inicial de cosméticos es contenido (`contenido/cosmeticos.json`) y puede crecer sin cambiar código.
