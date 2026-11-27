-- Respaldo generado por el Sistema de Reportes BOMBEROS
-- Fecha: 2026-11-27T12:33:58

-- Tabla: secuencias_control
-- (sin registros) secuencias_control

-- Tabla: usuarios
INSERT INTO "usuarios" ("id", "username", "password_hash", "nombre", "apellido", "cedula", "rango", "rol", "activo", "fecha_registro") VALUES (1, 'admin', 'scrypt:32768:8:1$Oq4p8vckAmefeTA7$9fae21ce189bb39173b448b17a5cde9d39769a533a95f6cb2122a84504315d04f5770b654f117a53d2a4d6830f5807b96c89e728018b1db199cb7824b1c7cd53', 'Jefe', 'Administrador', 'V-12345678', 'Coronel', 'administrador', TRUE, '2026-06-23T14:04:02.955990');
INSERT INTO "usuarios" ("id", "username", "password_hash", "nombre", "apellido", "cedula", "rango", "rol", "activo", "fecha_registro") VALUES (2, 'bombero', 'scrypt:32768:8:1$dgb9rt6mj7fnSk6H$8ed3d01b087250acae588f4bdbf8c2e1d44940da22eee6251d1456adba6b7e28f0e05e547d66e51427adfdd263ced6eaaa0508b5b9a900a1756fc4e17f924550', 'Juan', 'Pérez', 'V-87654321', 'Cabo Primero', 'bombero', TRUE, '2026-06-23T14:04:02.955990');
INSERT INTO "usuarios" ("id", "username", "password_hash", "nombre", "apellido", "cedula", "rango", "rol", "activo", "fecha_registro") VALUES (3, 'soporte', 'scrypt:32768:8:1$3nRLYpmfN0wN3mNR$fb00306bcc78f2566ef41d8413f54be491a5b1021d16bf35a6689ab51a976166d6556d1f525ab763509d3bb82c43612849cdb2646f28dd1d52e3b6517c744c21', 'soporte', 'soporte', '20396747', 'General', 'soporte', TRUE, '2026-11-27T12:17:33.331908');

-- Tabla: vehiculos
-- (sin registros) vehiculos

-- Tabla: logs_actividad
INSERT INTO "logs_actividad" ("id", "usuario_id", "username", "accion", "detalle", "fecha") VALUES (1, 1, 'admin', 'inicio_sesion', 'Acceso de Coronel Jefe Administrador', '2026-11-27T12:16:16.362643');
INSERT INTO "logs_actividad" ("id", "usuario_id", "username", "accion", "detalle", "fecha") VALUES (2, 1, 'admin', 'inicio_sesion', 'Acceso de Coronel Jefe Administrador', '2026-11-27T12:20:48.262697');
INSERT INTO "logs_actividad" ("id", "usuario_id", "username", "accion", "detalle", "fecha") VALUES (3, 3, 'soporte', 'inicio_sesion', 'Acceso de General soporte soporte', '2026-11-27T12:24:54.183132');
INSERT INTO "logs_actividad" ("id", "usuario_id", "username", "accion", "detalle", "fecha") VALUES (4, 3, 'soporte', 'respaldo_creado', 'respaldo_20261127_123054.json (json, 3081 bytes)', '2026-11-27T12:30:54.722303');
INSERT INTO "logs_actividad" ("id", "usuario_id", "username", "accion", "detalle", "fecha") VALUES (5, 3, 'soporte', 'respaldo_descargado', 'respaldo_20261127_123054.json', '2026-11-27T12:30:58.320657');

-- Tabla: reportes
-- (sin registros) reportes

-- Tabla: respaldos
INSERT INTO "respaldos" ("id", "nombre_archivo", "tipo", "tamano_bytes", "fecha", "usuario_id") VALUES (1, 'respaldo_20261127_123054.json', 'json', 3081, '2026-11-27T12:30:54.707065', 3);

-- Tabla: reporte_otros_organismos
-- (sin registros) reporte_otros_organismos

-- Tabla: reporte_personal_actuante
-- (sin registros) reporte_personal_actuante

-- Tabla: reporte_personas_afectadas
-- (sin registros) reporte_personas_afectadas

-- Tabla: reporte_vehiculos_actuantes
-- (sin registros) reporte_vehiculos_actuantes

-- Tabla: reportes_apertura_puerta
-- (sin registros) reportes_apertura_puerta

-- Tabla: reportes_aph_interhospitalario
-- (sin registros) reportes_aph_interhospitalario

-- Tabla: reportes_aph_no_traslado
-- (sin registros) reportes_aph_no_traslado

-- Tabla: reportes_aph_sin_traslado
-- (sin registros) reportes_aph_sin_traslado

-- Tabla: reportes_aph_traslado
-- (sin registros) reportes_aph_traslado

-- Tabla: reportes_busqueda_rescate
-- (sin registros) reportes_busqueda_rescate

-- Tabla: reportes_falsa_alarma
-- (sin registros) reportes_falsa_alarma

-- Tabla: reportes_guardia_seguridad
-- (sin registros) reportes_guardia_seguridad

-- Tabla: reportes_incendio
-- (sin registros) reportes_incendio

-- Tabla: reportes_inspeccion_insectos
-- (sin registros) reportes_inspeccion_insectos

-- Tabla: reportes_matpel_combustible
-- (sin registros) reportes_matpel_combustible

-- Tabla: reportes_matpel_glp
-- (sin registros) reportes_matpel_glp

-- Tabla: reportes_matpel_otros
-- (sin registros) reportes_matpel_otros

-- Tabla: reportes_matpel_quimico
-- (sin registros) reportes_matpel_quimico

-- Tabla: reportes_pre_hospitalario
-- (sin registros) reportes_pre_hospitalario

-- Tabla: reportes_rescate_colision
-- (sin registros) reportes_rescate_colision

-- Tabla: reportes_rescate_especializado
-- (sin registros) reportes_rescate_especializado

-- Tabla: reportes_servicio_achicamiento
-- (sin registros) reportes_servicio_achicamiento

-- Tabla: reportes_servicio_agua
-- (sin registros) reportes_servicio_agua

-- Tabla: reportes_servicio_animal
-- (sin registros) reportes_servicio_animal

-- Tabla: reportes_servicio_baldeo
-- (sin registros) reportes_servicio_baldeo

-- Tabla: reportes_servicio_insectos
-- (sin registros) reportes_servicio_insectos

-- Tabla: reportes_servicio_lluvias
-- (sin registros) reportes_servicio_lluvias

-- Tabla: reportes_servicio_piscinas
-- (sin registros) reportes_servicio_piscinas

-- Tabla: reportes_servicio_tendido_electrico
-- (sin registros) reportes_servicio_tendido_electrico

-- Tabla: reportes_tala_arbol
-- (sin registros) reportes_tala_arbol
