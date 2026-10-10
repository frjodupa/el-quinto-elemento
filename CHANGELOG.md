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
- Se dejan visibles únicamente Buscar canción, Pases, Crear pase y Ajustes.
- Nueva lista compacta de canciones para mostrar más repertorio en iPhone.
- Nueva canción, copias, exportación, compartir acceso y mantenimiento se trasladan a Ajustes sin eliminar funcionalidad.
- Barra de canción simplificada para directo.
- Versión técnica PWA actualizada a 68.
