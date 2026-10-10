# AUDITORÍA PRIORITARIA — Cancionero El Quinto Elemento

Actualizado: **10 de octubre de 2026**. Este documento se mantiene en la rama de auditoría, separada de la aplicación publicada.

## Instrucción principal

**Completar y verificar letra y acordes de TODAS las canciones del cancionero.** Este objetivo tiene prioridad sobre el diseño, iconografía o nuevas funciones. No sustituir versiones distintas, no borrar canciones válidas ni romper pases. Preservar la estructura original `lines`, `words`, `intro`, `instrumentals`, `references`, la tonalidad y los acordes existentes.

## Estado de Cloudflare verificado DESPUÉS de la corrección

- Inventario D1: **86 canciones, 86 títulos diferentes**.
- **0** canciones sin letra; **0** canciones sin acordes; **0** duplicados de título.
- **8** canciones todavía con menos del 25% de líneas con acordes; **31** con menos del 70%.
- **0** posiciones de acorde fuera de rango.
- **2 pases**, sin referencias a ID inexistentes.
- `LA PASMA (NUEVA)`: **23 canciones**, todas presentes y con referencias válidas; **5** siguen con menos del 50% de líneas con acordes.
- Foto técnica: **D1 updatedAt 1791629436013**; PWA sin modificaciones durante la corrección.
- Backup manual pre-corrección: **380**; backup automático posterior: **381**.
- Revisión posterior a los cambios: [GitHub Actions, verificada](https://github.com/frjodupa/el-quinto-elemento/actions/runs/38046547916).

## Correcciones comprobadas y aplicadas a D1

Sólo acordes nuevos de tablaturas que coinciden con las letras existentes a nivel de fragmento con umbral **≥98,5%**. Letras e información anterior NO modificadas. Las posiciones ambiguas se descartan.

| ID | Tema | Acordes nuevos | Líneas cubiertas | Fuente identificada |
|---:|---|---:|---:|---|
| 77 | Sabor de amor — Danza Invisible | 96 | 34/45 (75,6%) | UG #1036283 |
| 80 | El ritmo del garaje — Loquillo y Trogloditas | 51 | 15/29 (51,7%) | UG #2639544 |
| 81 | Enamorado de la moda juvenil — Radio Futura | 21 | 18/50 (36,0%) | UG #1612960 |

Total **168 nuevas posiciones de acorde**, con copia y verificación D1: [ejecución confirmada](https://github.com/frjodupa/el-quinto-elemento/actions/runs/38046282174).

**Estas canciones siguen pendientes de completar al 100% y comprobar su interpretación musical.** La validación técnica de coincidencia no sustituye una revisión musical humana.

## Próximas canciones prioritarias: cobertura inferior al 25%

| ID | Canción | Cobertura inicial |
|---:|---|---:|
| 5 | Aquí no hay playa | 2,6% |
| 51 | Qué Navidad tan especial | 3,4% |
| 62 | Te sigo soñando | 9,8% |
| 73 | Escuela de calor | 11,4% |
| 26 | Espaldas mojadas | 14,0% |
| 43 | Mi agüita amarilla | 17,5% |
| 54 | Salta | 17,9% |
| 70 | Yo soy quien espía los juegos de los niños | 19,4% |

Las cifras de cobertura son orientativas: una sección instrumental, acorde sostenido o repetición puede explicar una línea sin acorde. Se requiere revisión por estructura musical.

## Pase `LA PASMA (NUEVA)` — temas pendientes más importantes

| ID | Canción | Cobertura tras la recuperación |
|---:|---|---:|
| 73 | Escuela de calor | 11,4% |
| 54 | Salta | 18,2% |
| 81 | Enamorado de la moda juvenil | 36,0% |
| 82 | Adiós papá | 46,8% |
| 25 | Eso que tú me das | 47,6% |

Estos cinco forman parte del pase confirmado y deben revisarse antes de considerarlo completo.

## Siete fuentes candidatas descartadas para sustitución automática

La pasada de fuentes externas (sobre el estado previo a los 168 acordes) encontró estas posibilidades. **No se han aplicado**: las coincidencias de tonalidad y los conflictos de posición no permiten garantizar un resultado correcto.

| ID | Tema | Acordes candidatos | Confianza tonal | Conflictos |
|---:|---|---:|---:|---:|
| 6 | Aunque tú no lo sepas | +16 | 69,4% | 15 |
| 11 | Carbón y ramas secas | +38 | 67,6% | 24 |
| 44 | Mi gran noche | +29 | 63,4% | 15 |
| 48 | Pájaros de barro | +44 | 36,7% | 20 |
| 56 | Si me das a elegir | +2 | 91,3% | 6 |
| 73 | Escuela de calor | +7 | 66,7% | 1 |
| 74 | Hace calor | +61 | 60,0% | 8 |

Fuentes verificadas con métodos de los repositorios `olimontes/setlive`, `Pilfer/ultimate-guitar-scraper` y `mfuentesg/capo`. CifraClub ha bloqueado parcialmente solicitudes automáticas con 403. Una letra coincidente por sí sola **no** garantiza la tonalidad de la actuación.

Auditoría de fuentes de 86 canciones: [ejecución y metadatos originales](https://github.com/frjodupa/el-quinto-elemento/actions/runs/38045689357).

## Procedimiento obligado de cada corrección

1. Cargar el inventario **actual** de `/export` y confirmar sus ID, pases y versión.
2. Identificar título, artista y versión correctos; comprobar la letra que ya existe.
3. Comparar línea por línea, incluidas estrofas divididas en varias líneas y repeticiones.
4. Detectar tonalidad y transposición desde los acordes existentes. Sin coincidencia suficiente, **revisión manual**.
5. Añadir sólo posiciones nuevas verificadas en el formato propio; preservar todas las demás estructuras.
6. Crear backup D1 antes de escribir y usar `expectedUpdatedAt` al guardar para evitar sobrescrituras concurrentes.
7. Verificar inmediatamente los acordes, letras, los 86 IDs y los 23 registros del pase. No cambiar versión PWA para corregir D1.
8. Repetir la medición de cobertura y registrar avances; no declarar completado el repertorio mientras queden dudas.

**Pendiente:** auditoría musical y mejora verificable de los restantes acordes incompletos; la interfaz premium permanece subordinada a esta tarea.
