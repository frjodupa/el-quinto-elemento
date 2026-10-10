# Changelog

## v63 — 2026-10-10

- Añadido export 1-click para iPhone.
- Botón flotante “⤓ Exportar v62” con Web Share API en iPhone y descarga directa en escritorio.
- Exportación conservadora de las canciones actuales, claves relevantes de localStorage y todas las bases/objectStores de IndexedDB disponibles.
- Nuevo endpoint `GET /export` para descargar el estado persistido en Cloudflare D1.
- El endpoint de exportación queda fuera de la caché offline.
- La versión técnica de caché/PWA pasa de 65 a 66 para no degradar el sistema de actualización existente.

## v64 — 2026-10-10

- Auditoría automática del cancionero con CifraClub / Ultimate Guitar y normalización ChordPro.
- Enriquecimiento conservador de acordes solo en coincidencias validadas.
- Versión técnica PWA actualizada de 66 a 67 para el siguiente despliegue.

## v65 — 2026-10-10

- Portada rediseñada para uso en directo.
- La portada queda reducida a Buscar canción, Pases y Ajustes; “Nuevo pase” se crea desde Pases.
- Al iniciar un pase se activa automáticamente el Modo directo.
- Se dejan visibles únicamente Buscar canción, Pases, Crear pase y Ajustes.
- Nueva lista compacta de canciones para mostrar más repertorio en iPhone.
- Nueva canción, copias, exportación, compartir acceso y mantenimiento se trasladan a Ajustes sin eliminar funcionalidad.
- Barra de canción simplificada para directo.
- Versión técnica PWA actualizada a 68.

## v65 · hotfix

- Exportación JSON alineada con interfaz v65.
- Metadatos de exportación actualizados a versión 65 / build técnico 69.
- Caché offline y version.json actualizados a 69.

## v66 — 2026-10-10

- Pantalla de canción optimizada para directo.
- Barra superior reducida a Índice, anterior/siguiente, Scroll, velocidad, tonalidad ±1, tamaño de letra y Ajustes.
- Tonalidad accesible directamente sin abrir Ajustes.
- Cualquier canción se abre automáticamente en Modo directo.
- Herramientas de edición y mantenimiento siguen disponibles desde Ajustes.
- Interfaz v66 / build técnico PWA 70.

## v67 — 2026-10-10

- Ajustes contextuales para directo.
- Desde una canción se muestran solo Tonalidad, Visualización, Scroll y Directo/Ficha.
- Desde el índice se muestran Estado, Sincronización, Copias y Mantenimiento.
- “Más herramientas” permite recuperar todas las opciones avanzadas sin eliminar funcionalidad.
- Interfaz v67 / build técnico PWA 71.

## v68 — 2026-10-10

- Detalle de Pases optimizado para actuación.
- En uso normal se muestran Empezar pase y la lista de canciones.
- Renombrar, duplicar, compartir, imprimir, eliminar, añadir, quitar y reordenar quedan detrás de “Editar pase”.
- No se elimina ninguna función.
- Interfaz v68 / build técnico PWA 72.

## v69 — 2026-10-10

- Búsqueda real en Internet integrada en la caja de canciones.
- Se mantiene la búsqueda local inmediata y se añade “Buscar en Internet”.
- CifraClub se consulta con la estrategia verificada de setlive: imprimir.html / pre y fallback de cifra.
- Ultimate Guitar se consulta replicando el API y cabeceras del scraper de Pilfer.
- Las fuentes se convierten al formato interno lines/words/Intro/Instrumental/references.
- Canciones existentes: <70% bloqueado, 70–85% revisión manual, >85% permite completar con backup previo.
- Canciones nuevas: se pueden añadir como canción personalizada con letra y acordes importados.
- Interfaz v69 / build técnico PWA 73.

## v70 — 2026-10-10

- Corregido el parser de Ultimate Guitar para conservar líneas de acordes separadas sobre la letra.
- El parser ya no descarta líneas formadas solo por etiquetas [ch]...[/ch].
- Si el buscador de CifraClub devuelve 403, se prueban slugs directos derivados de artista/título de Ultimate Guitar y solo se muestran los que responden con cifra válida.
- Interfaz v70 / build técnico PWA 74.

## v71 — 2026-10-10

- Tipografía de letras más pequeña y rango ampliado hasta 0,52 en iPhone; se guarda por canción.
- Menos márgenes y espacios en letra para mostrar líneas más completas sin cambiar el texto original.
- Ajustes de directo simplificados: edición, tonalidad y apariencia; scroll y transposición ya en la barra superior.
- Se oculta la ficha musical de directo y se eliminan botones duplicados de la vista. Los datos y handlers se conservan.
- Cache PWA y metadatos subidos a versión técnica 75.

## v72 — Premium Stage · 2026-10-10

- Diseño visual de escenario premium, negro grafito y azul noche con detalles dorados; contraste accesible en modo oscuro y claro.
- Iconos vectoriales locales, modernos y coherentes; sin fuentes remotas y compatibles con PWA offline.
- Home, búsqueda, lista, pases, barra de canción y Ajustes refinados para iPhone y iPad.
- Barra de canción móvil reorganizada para evitar controles cortados en pantallas estrechas.
- Ajustes simplificados visualmente, preservando herramientas avanzadas sin borrar ninguna funcionalidad.
- Icono PWA sustituido por el diseño aportado (180, 192 y 512), con variante maskable y nombres nuevos para evitar caché obsoleta.
- CSS y JS incluidos en precaché offline; versión técnica 76, exportación 72/76.
- Ningún cambio en letras, acordes, Intro, Instrumental, referencias o datos D1.

## v73 — 2026-10-10

- Espaciado legible entre palabras en letras con acordes, sin cambiar letra ni anclajes de acordes.
- Favicon premium actualizado y cache busting consistente.
- Versión técnica offline 77 y exportación 73/77.

## v74 — 2026-10-10

- Botón «Buscar en Internet» permanentemente visible bajo el buscador principal en iPhone, iPad y escritorio.
- Los resultados externos aparecen antes de la lista local, sin obligar a desplazarse por el repertorio.
- El botón muestra ayuda cuando no hay título y avisa si no existe conexión.
- Se mantienen búsqueda local offline, importación conservadora y el servicio actual CifraClub / Ultimate Guitar.
- Interfaz v74 / versión técnica y caché PWA 78.

## v75 — 2026-10-10

- Protección de sincronización Cloudflare mediante comparación de revisión: un dispositivo antiguo ya no puede sobrescribir el repertorio completo recuperado.
- Actualización en caliente del catálogo de canciones personalizadas al recibir cambios desde D1.
- Herramienta temporal, de una sola operación, para fusionar las 14 canciones únicas perdidas de «LA PASMA (NUEVA)» desde una copia verificada de Cloudflare, conservando «PERO A TU LADO» y sin recuperar los 14 duplicados.
- Copia histórica y copia previa guardadas de forma permanente en D1 antes de cualquier migración.
- Preparada auditoría y mejora posterior de acordes por línea sobre los 23 temas del pase.
- Interfaz v75, build técnico PWA 79.

## v76 — 2026-10-10

- En Ajustes → Tonalidad se puede transponer en semitonos en el intervalo −12 a +12.
- Deslizador de un semitono por paso, botones −1/+1, saltos de octava −12/+12 y vuelta a «Original».
- Los controles directos ♭/♯ también respetan los límites −12 y +12.
- El indicador muestra el desplazamiento guardado para cada canción y desactiva los controles al llegar al límite.
- Las octavas exactas no reescriben nombres de acordes; Intro, Instrumentales y acordes entre palabras usan el transpositor existente.
- No se modifica ninguna letra ni se toca la sincronización de Cloudflare.
- Interfaz v76; build técnico PWA 80.

## v77 — 2026-10-10

- Botón «Editar» visible en la barra de cada canción durante el directo.
- Acceso inmediato a Editar letra/título y Editar acordes por palabra, sin entrar en Ajustes.
- Herramientas rápidas de acordes con Intro, Instrumental, Deshacer y Guardar y salir.
- Conserva los editores, sincronización y modelo de datos existentes; no modifica ninguna letra ni acorde en la publicación.
- Mejora de accesibilidad y diseño adaptable iPhone/iPad/escritorio.
- Interfaz v77 / build técnico y caché offline 81.
