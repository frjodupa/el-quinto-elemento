EL QUINTO ELEMENTO · v39 · ESTABILIDAD Y CARGA RÁPIDA

CORRECCIÓN CRÍTICA
- Eliminado el bucle de recargas provocado por la sincronización D1.
- Los cambios recibidos desde Cloudflare se aplican en caliente, sin recargar toda la app.
- La sincronización periódica ya no provoca recargas automáticas.
- El arranque muestra primero los datos locales y sincroniza en segundo plano.
- Navegación, index.html, version.json y sw.js se sirven con no-cache desde el Worker.
- El Service Worker usa red primero con espera máxima corta y conserva fallback offline.
- La comprobación de versión comienza antes, sin bloquear la interfaz.
- Se conserva la función v38 de duplicar bloques de acordes.

OBJETIVO
Carga inmediata, actualización fiable y funcionamiento offline sin bucles.

DESPLIEGUE
GitHub → Cloudflare automático.
