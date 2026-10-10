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
