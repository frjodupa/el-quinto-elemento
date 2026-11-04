# GITOP 2.1 — Incidencia P0 de sincronización iPad (2026-11-04)

## Alcance y respaldo
- Repositorio: frjodupa/el-quinto-elemento.
- Prioridad: proteger arreglos del iPad de directo; el usuario exportó el 2026-11-04 a las 09:28:35 UTC un JSON `quinto-elemento-v62-export` (version 79, buildVersion 83), con 95 canciones principales y 365 claves localStorage. **El JSON del usuario no se guarda en el repositorio.**
- No ejecutar importaciones ni restauraciones en el iPad antes de preservar/contrastar los cambios.

## Hallazgos confirmados en main (solo lectura)
1. `public/index.html`, alrededor de las líneas 4605–4613: `collectState()` genera un único objeto con todas las claves `quintoElemento.*`.
2. Líneas 4620–4635: `applyState()` borra todas esas claves y coloca la copia remota. No es una fusión.
3. Líneas 4660–4668: `pushLocal()` sube la instantánea completa y marca dirty=0 únicamente al recibir éxito.
4. Líneas 4722–4755: `syncNow()` con dirty=1 intenta directamente `pushLocal()`; si devuelve 409 muestra «Copias distintas», pero no fusiona ni reintenta de modo seguro.
5. Líneas 4795–4800: el sondeo cada 30 s solo descarga cuando dirty != 1, por lo que el iPad puede quedar bloqueado indefinidamente.
6. `src/worker.js` líneas 869–913: la escritura requiere `expectedUpdatedAt` igual al `updated_at` remoto; en caso contrario devuelve `STALE_SNAPSHOT` (409). Protección de concurrencia útil, pero sin resolución cliente.
7. `public/index.html` líneas 4810–4816: otro listener cierra el modal al tocar «Sincronizar ahora», incluso si la operación fracasa. El usuario interpreta el botón como inoperante.
8. `public/version.json`: version 82 mientras el export del iPad declara buildVersion 83, y la interfaz principal del repositorio muestra v80. Son esquemas de versión distintos o desalineados; verificar el mecanismo antes de tocar el actualizador.
9. El aviso de compartir en el propio HTML (aprox. línea 3418) reconoce sincronización **sin autenticación**. Exige auditoría de acceso antes de distribuir cambios.

## ADR — sincronización segura
- No usar «última instantánea gana» ni copiar toda la nube sobre cambios locales.
- Mantener el control CAS del backend (409), pero añadir una base de tres vías: última instantánea confirmada, estado local y estado remoto.
- Fusionar primero campos independientes por canción; para el **mismo** campo modificado en ambos lados, conservar ambas variantes y solicitar elección, sin escritura destructiva automática.
- `customSongs.v1` y `passes.v1` son arrays serializados: una comparación por clave no basta. Crear identidad estable por canción/pase y migración compatible. Los pases referencian índices de canción: no reordenar ni asignar nuevos índices sin migración y comprobación.
- Borrados requieren tombstones y control de conflictos; nunca inferir borrado por ausencia de clave en un dispositivo antiguo.
- Guardar de forma persistente la base de sincronización y los cambios pendientes; detectar cuota de almacenamiento y fallos de escritura. No asumir que navigator.onLine confirma acceso a Cloudflare.
- Tras 409, leer remoto y calcular merge antes de PUT con nueva revisión; si hay conflictos, no sobrescribir y ofrecer resolución segura.
- No marcar estado sincronizado hasta confirmación del servidor. Evitar `applyState()` destructiva antes del backup local y la validación de datos.
- Verificar acceso/autenticación y aislamiento de usuarios antes de publicar; el Worker actual parece compartir un registro `app_state/main`.

## Pruebas de aceptación pendientes de ejecución
1. Editar acordes en iPad + crear otra canción en Mac: convergencia en los tres dispositivos.
2. Editar letras en iPhone + editar acordes de la misma canción en iPad: conservar ambos cambios.
3. Editar la misma línea de letra en dos dispositivos offline: conservar ambas versiones, mostrar conflicto, resolverlo sin duplicar.
4. Crear dos canciones distintas offline con identidades estables: no perder ni duplicar y respetar pases.
5. Borrar una canción en un dispositivo mientras otro la modifica: sin pérdida silenciosa.
6. Cortar red antes/después de PUT, reintentar, reiniciar PWA y comprobar persistencia e idempotencia.
7. Simular 409 de concurrencia y errores 401/403/500/cuota: informar y conservar datos.
8. Regresión: acordes por palabra, transposiciones, posición, scroll, pases, modo directo, visualización.
9. Verificar version.json, SW cache, buildVersion y aplicación instalada en iPadOS.
10. Pruebas de aislamiento/autenticación en entorno de pruebas, nunca con arreglos reales.

## Estado
Diagnóstico comprobado por lectura del código de `main`. Diseño propuesto; no implementado todavía. No hay prueba de integración ni despliegue. Mantener la copia exportada del iPad y las instantáneas Cloudflare intactas.
