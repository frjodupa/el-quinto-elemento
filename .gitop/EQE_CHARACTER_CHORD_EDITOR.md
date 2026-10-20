# EQE — Editor de acordes por carácter

Objetivo: anclar cada acorde sobre cualquier carácter o espacio de la letra, no solo sobre palabras.

Compatibilidad: conservar d.words y d.lines sin alteraciones. Nuevo modelo opcional d.positions[line] con entradas {offset,chord}. Nunca migrar acordes automáticamente.
Interfaz: modo Por carácter para colocar, arrastrar, copiar, pegar, editar y eliminar, válido en táctil iPhone/iPad y cursor Mac.
Guardar cambios mediante el almacenamiento existente y sincronizar a Cloudflare D1; no modificar pases.
Pruebas: acentos, espacios, versos largos, transposición, PDF, recuperación, compatibilidad con versiones antiguas y sincronización entre dispositivos.

ESTADO: especificación pendiente de implementación y pruebas. No desplegar.