# AUDITORÍA EQE — estado del cancionero y soluciones de GitHub

**Fecha:** 10 de octubre de 2026  
**Proyecto:** El Quinto Elemento Cancionero Interactivo, independiente de los demás proyectos.  
**Versión del código revisado:** interfaz v79 / técnica 83, rama `main`.  
**Evidencias:** GitHub Actions `38064601110` (inventario y acordes), `38065604091` (23 canciones de LA PASMA), `38065759592` (fuentes originales) y `38065341263` (otras fuentes armónicas).  
**Alcance de esta revisión:** análisis de código, ejecución y logs de auditorías verificadas, y evaluación de repositorios externos. **Solo lectura; no se ha modificado D1 ni el repertorio.**

## 1. Datos verificados

- Último inventario D1 confirmado por las acciones consultadas: **88 canciones distintas**, **17 personalizadas**, **0 sin acordes**, **0 anclajes huérfanos**, **2 pases**. Estos valores corresponden a los snapshots de las acciones y deben reconfirmarse inmediatamente antes de escribir, porque D1 y el iPhone pueden cambiar.
- **27 de 88 canciones** tienen menos del **70% de líneas de letra con acordes**; **4** bajan del 25%. Este porcentaje es una señal para revisión, no equivale a error musical automáticamente (hay silencios y líneas sin armonía).
- **La Pasma Nueva** tiene **23 canciones distintas**, **8 bajo el 70%**, y **222 líneas de letra sin acordes asignados** según la auditoría. No se debe reinterpretar este número como 222 errores armónicos.
- En la auditoría más reciente de fuentes externas de La Pasma, se analizaron 23 canciones, 21 partituras UG encontradas y **0 candidatos fuertes**. Todos los resultados señalados quedaron en revisión manual; por ello no procede actualizar el pase masivamente con una sola fuente por título.
- Anteriormente existían 14 pares de duplicados. El inventario reciente registra 88 títulos distintos; **no ejecutar scripts de deduplicación antiguos diseñados para 99 registros**. Las referencias de los pases usan índices numéricos: una eliminación sin migración puede romperlos.

## 2. Prioridades por cobertura (snapshot de 88 canciones)

| ID | Canción | Acordes | Líneas | Líneas con acordes | Cobertura |
|---:|---|---:|---:|---:|---:|
| 51 | QUÉ NAVIDAD TAN ESPECIAL | 21 | 30 | 3 | 10,3% |
| 26 | ESPALDAS MOJADAS | 27 | 50 | 7 | 14,0% |
| 73 | ESCUELA DE CALOR | 10 | 32 | 5 | 15,6% |
| 62 | TE SIGO SOÑANDO | 8 | 41 | 8 | 19,5% |
| 7 | BOLILLÓN | 35 | 35 | 12 | 34,3% |
| 23 | EL VALS DEL OBRERO | 29 | 54 | 20 | 37,0% |
| 43 | MI AGÜITA AMARILLA | 30 | 63 | 24 | 38,1% |

En La Pasma, priorizar **Escuela de calor (15,6%)**, **Salta (46,4%)**, **Adiós papá (46,8%)**, **Eso que tú me das (48,8%)**, **El ritmo del garaje (51,7%)**, **No puedo vivir sin ti (53,8%)**, **Enamorado de la moda juvenil (58,0%)** y **Clavado en un bar (68,8%)**.

## 3. Fallos técnicos detectados en `main`

1. **Alineación inconsistente.** `src/worker.js` → `parseInlineUg()` elimina varios espacios con `replace(/\s+/g," ").trim()`, pero toma posiciones de acordes antes de ese cambio. Esto puede desplazar los anclajes cuando el proveedor usa espacios para colocar los acordes.
2. **Extracción HTML frágil.** `extractCifraContent()` usa regex de cierre `</div>` para `div.cifra_cnt` / `div.cifra`. Los bloques anidados pueden producir una extracción truncada. CifraClub ha respondido 403 en el buscador desde Cloudflare.
3. **Validación insuficiente de importación.** En `public/index.html`, `completeExisting()` acepta la coincidencia global ≥85%, y puede reemplazar letra por longitud. Debe exigirse concordancia por línea/estrofa, identidad del artista, acordes realmente utilizables y concordancia de tonalidad.
4. **Falta de un modelo común y pruebas de ida/vuelta.** No existe aún un test que certifique que importar → convertir → editar → exportar → reimportar conserva `lines`, `words`, `intro`, `introText`, `instrumentals`, `instrumentalsText`, `references` y los índices de palabra.
5. **Fuentes limitadas.** Usar el primer resultado de una búsqueda UG no basta: las variantes en vivo, traducciones, covers y homónimos hacen que el título solo sea insuficiente. Deben compararse al menos 2–3 fuentes si las hay y conservar evidencia de origen.

## 4. Repositorios reales comprobados

| Repositorio | Actividad y licencia | Qué reutilizar | Evaluación |
|---|---|---|---|
| [Pilfer/ultimate-guitar-scraper](https://github.com/Pilfer/ultimate-guitar-scraper) | 132 estrellas; último push noviembre 2023; licencia no identificada por API | `fetch -id` y metadatos UG para auditoría/fuentes | API no oficial, antigüedad >18 meses: usar con tests, sin asumir estabilidad ni autorización de reutilización |
| [olimontes/setlive](https://github.com/olimontes/setlive) | 1 estrella; actualizado marzo 2026; licencia no identificada por API | `cifra_scraper.py` como referencia de estrategia CifraClub | Referencia de extracción; acceso 403 y licencia por verificar; no copiar sin comprobar permisos |
| [mfuentesg/capo](https://github.com/mfuentesg/capo) | 3 estrellas; actualizado septiembre 2026; licencia no identificada por API | Diseño de biblioteca, ChordPro, auto-scroll y preferencias por canción | Buen ejemplo de producto, no dependencia directa ni sustituto del esquema EQE |
| [martijnversluis/ChordSheetJS](https://github.com/martijnversluis/ChordSheetJS) | 444 estrellas; actividad octubre 2026; **GPL-2.0** según API | Parsing de acordes encima de letra, Ultimate Guitar y ChordPro | Biblioteca potente; estudiar obligaciones GPL antes de incorporarla/distribuirla |
| [dennisworks/chordpro](https://github.com/dennisworks/chordpro) | 0 estrellas; actividad agosto 2026; MIT | Parser ChordPro sin dependencias con AST | Candidato técnico pequeño; requiere pruebas de compatibilidad antes de incluirlo |

La ausencia de una licencia detectada no se interpreta como licencia libre.

## 5. Propuesta de reparación no destructiva

**Fase A — Congelar y respaldar.** Obtener `/export` fresco, comprobar el recuento real de canciones, guardar hash SHA-256 y backup D1. No asumir que sigue habiendo 88 canciones: cambiar de dispositivo puede sincronizar contenido.

**Fase B — Enriquecer metadatos.** Identificar artista/título/versiones de cada canción. Registrar fuente URL, ID, tono y fecha; distinguir fuente musical de originalidad lírica.

**Fase C — Comparar y alinear.** Para cada canción, leer la cifra/ChordPro desde 2 fuentes cuando sea posible, respetar columnas/espacios, normalizar la tonalidad y alinear estrofas por contenido sin desplazar anclajes de palabras. Si hay discrepancia, marcar `revision_manual`.

**Fase D — Validación automática.** Exigir artista fiable, similitud de letra ≥85%, coincidencia línea/estrofa ≥85%, mapeo estable, ningún acorde existente sobrescrito, secciones Intro/Instrumental/referencias inalteradas, y más posiciones válidas que antes. Si no cumple, no modificar.

**Fase E — Aplicación.** Crear backup D1, aplicar solo los diffs válidos, verificar desde `/export` que el estado coincide, asegurar que la PWA sigue offline y no cambia de versión técnica por una actualización de repertorio.

**Fase F — QA en directo.** Verificar 23 temas de La Pasma, navegación por pases, renderizado iPhone, transposición y acordes en palabras y líneas. Confirmar que no desaparezcan letras ni estribillos.

## 6. Criterio de finalización

El repertorio no se considera terminado por el hecho de tener “algunos acordes”. Se considera **auditado** cuando cada canción tiene su identidad y fuente revisadas, sus estrofas analizadas, sus acordes alineados y todo cambio trazable/reversible; los casos no fiables deben quedar expresamente pendientes, no marcarse como corregidos.

**Estado:** diagnóstico y referencias finalizados; **corrección automática masiva no autorizada por estos resultados**. Cualquier propuesta de “100% corregido” sin pasar los controles anteriores sería engañosa.
