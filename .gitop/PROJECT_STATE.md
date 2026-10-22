# Estado de proyecto — el-quinto-elemento

- Identidad: El Quinto Elemento — cancionero y acordes
- Fuente de verdad: este repositorio, sus commits, issues y recursos oficiales.
- Última instalación de reglas: 2026-10-16 (GITOP 2.0).
- Versión estable actual: POR VERIFICAR. No asumir que main equivale a producción.
- Funciones protegidas: POR INVENTARIAR con evidencia. No sobrescribir recursos aprobados.
- Incidencias: ver `.gitop/incidents.json`. No marcar como resueltas sin prueba.
- Próximo paso: auditoría de solo lectura; identificar problemas y pruebas existentes antes de modificar código.
- Despliegue autorizado: NO.


## Intervención 22/10/2026 · sincronización y versión

- HECHO: candidata v98 sobre main 2864c77, sin incorporar los cambios funcionales de PR49. Motor de combinación por canción/pase y base por dispositivo; protección CAS existente conservada.
- PROBADO: 23 pruebas Node de sincronización; coherencia PWA y 25 scripts inline; guardas globales y navegación. Ver docs/SYNC-V98-20261022.md.
- BLOQUEADO local: falta navegador ejecutable; CI incorpora Chromium/WebKit.
- PENDIENTE: exportaciones Mac/iPhone, referencia original, auditoría completa y prueba física de los tres equipos. Confirmar assets publicados: main no se considera equivalente a producción.
- PUBLICADO: NO. Sin cambios en D1 ni importación de datos.
