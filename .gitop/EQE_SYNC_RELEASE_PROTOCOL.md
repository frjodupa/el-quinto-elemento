# EQE — Protocolo de sincronización y publicación segura

## Fuente oficial
- Repositorio: frjodupa/el-quinto-elemento
- Código de producción: main (solo promocionar versiones verificadas).
- Referencia histórica de datos: D1 eqe_recovery_archive, tag OFICIAL_ESTABLE_V717_2026-10-17.
- Referencia de código tomada el 19/10: backup/eqe-main-snapshot-2026-10-19. NO confundir con código original exacto V717 hasta comprobarlo.
- Antes de publicar, hacer una exportación externa verificada de D1 y registrar hash, hora, esquema y restauración de prueba.

## Dos canales distintos
A. Contenido (sin despliegue): localStorage 'quintoElemento.*' <-> Worker /api/sync <-> D1 app_state. Actualización bajo demanda y cada 30 s en primer plano. El receptor ofrece «Actualizar ahora / Más tarde». No aplicar datos remotos sobre ediciones locales pendientes.
B. Programa: version.json + APP_VERSION en index.html + versión del registro de sw.js + nombre de caché del SW. Deben avanzar conjuntamente EN CADA RELEASE. El receptor avisa al abrir o recuperar foco; tras confirmación actualiza PWA. NUNCA publicar solo version.json antes que el resto de recursos.

## Release obligatoria (no omitir)
1. Revisar branch/diff y comprobar que la versión oficial y el respaldo D1 siguen íntegros.
2. Probar con datos ficticios en base D1 separada, sin conectar staging a producción.
3. Pruebas A: alta de canción, letra, acordes, pase, restauración offline; iPhone→Mac→iPad y viceversa, con confirmación en nube. Simular 409 y latencia.
4. Pruebas B: despliegue candidato, detección de nueva versión por clientes de versión antigua, botón actualizar, caché offline, reapertura y conservación de datos.
5. Auditoría de regresión: LA PASMA (NUEVA), pases y acordes; cabecera PDF La Pasma; nada se borra ni se transforma.
6. Antes del despliegue aumentar la MISMA versión en public/version.json, APP_VERSION, sw.js (CACHE, manifest y registro), y documentar los cambios.
7. Desplegar solo con autorización y verificar URL, tres plataformas y copias de datos; si falla, volver al código previo y restaurar datos solo tras análisis y aprobación específica.

## Pendientes/bloqueos
- No hay verificación externa de la copia D1 completa ni restauración ensayada.
- Falta comprobar la app desde dispositivos físicos; pruebas estáticas de diffs no son pruebas funcionales.
- Conflictos 409 requieren solución que preserve ambas copias, nunca sobrescribir por fuerza.
- La sincronización no debe depender de acceder a cuentas ni servicios de terceros adicionales.
