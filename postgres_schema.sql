-- ========================================================
-- SCHEMA FOR POSTGRESQL - CUERPO DE BOMBEROS
-- Generated from SQLAlchemy Models
-- ========================================================

-- Table: usuarios
CREATE TABLE usuarios (
	id SERIAL NOT NULL, 
	username VARCHAR(50) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	nombre VARCHAR(100) NOT NULL, 
	apellido VARCHAR(100) NOT NULL, 
	cedula VARCHAR(20) NOT NULL, 
	rango VARCHAR(50), 
	rol VARCHAR(20) NOT NULL, 
	activo BOOLEAN DEFAULT TRUE, 
	fecha_registro TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (username), 
	UNIQUE (cedula)
);

-- Table: vehiculos
CREATE TABLE vehiculos (
	id SERIAL NOT NULL, 
	unidad VARCHAR(20) NOT NULL, 
	placa VARCHAR(20) NOT NULL, 
	marca VARCHAR(50) NOT NULL, 
	modelo VARCHAR(50) NOT NULL, 
	color VARCHAR(30), 
	tipo VARCHAR(50) NOT NULL, 
	activo BOOLEAN DEFAULT TRUE, 
	PRIMARY KEY (id), 
	UNIQUE (unidad), 
	UNIQUE (placa)
);

-- Table: reportes
CREATE TABLE reportes (
	id SERIAL NOT NULL, 
	nro_control VARCHAR(30) NOT NULL, 
	fecha DATE NOT NULL, 
	clase_aviso VARCHAR(50) NOT NULL, 
	hora_aviso TIME WITHOUT TIME ZONE NOT NULL, 
	hora_salida TIME WITHOUT TIME ZONE NOT NULL, 
	hora_llegada TIME WITHOUT TIME ZONE NOT NULL, 
	hora_regreso TIME WITHOUT TIME ZONE NOT NULL, 
	solicitante_nombre VARCHAR(150), 
	solicitante_cedula VARCHAR(20), 
	solicitante_telefono VARCHAR(30), 
	receptor_aviso VARCHAR(150) NOT NULL, 
	direccion TEXT NOT NULL, 
	punto_referencia VARCHAR(255), 
	creador_id INTEGER NOT NULL, 
	estado VARCHAR(20) DEFAULT 'Borrador', 
	observaciones_generales TEXT, 
	fecha_creacion TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	fecha_modificacion TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP, 
	tipo_reporte VARCHAR(50) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (nro_control), 
	FOREIGN KEY(creador_id) REFERENCES usuarios (id)
);

-- Table: reporte_otros_organismos
CREATE TABLE reporte_otros_organismos (
	id SERIAL NOT NULL, 
	reporte_id INTEGER NOT NULL, 
	nombre_organismo VARCHAR(100) NOT NULL, 
	jefe_unidad VARCHAR(150), 
	matricula_unidad VARCHAR(50), 
	cantidad_unidades INTEGER DEFAULT 1, 
	PRIMARY KEY (id), 
	FOREIGN KEY(reporte_id) REFERENCES reportes (id) ON DELETE CASCADE
);

-- Table: reporte_personal_actuante
CREATE TABLE reporte_personal_actuante (
	id SERIAL NOT NULL, 
	reporte_id INTEGER NOT NULL, 
	usuario_id INTEGER, 
	nombre_completo VARCHAR(150) NOT NULL, 
	cedula VARCHAR(20), 
	rango VARCHAR(50), 
	rol_en_servicio VARCHAR(50) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(reporte_id) REFERENCES reportes (id) ON DELETE CASCADE, 
	FOREIGN KEY(usuario_id) REFERENCES usuarios (id)
);

-- Table: reporte_vehiculos_actuantes
CREATE TABLE reporte_vehiculos_actuantes (
	id SERIAL NOT NULL, 
	reporte_id INTEGER NOT NULL, 
	vehiculo_id INTEGER NOT NULL, 
	km_salida NUMERIC(10, 2), 
	km_llegada NUMERIC(10, 2), 
	conductor_nombre VARCHAR(150) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(reporte_id) REFERENCES reportes (id) ON DELETE CASCADE, 
	FOREIGN KEY(vehiculo_id) REFERENCES vehiculos (id)
);

-- Table: reportes_matpel_combustible
CREATE TABLE reportes_matpel_combustible (
	id INTEGER NOT NULL, 
	tipo_combustible VARCHAR(100), 
	tipo_almacenamiento VARCHAR(100), 
	vehiculos_involucrados TEXT, 
	mitigacion_efectuada TEXT, 
	cantidad_estimada_derrame NUMERIC(10, 2), 
	PRIMARY KEY (id), 
	FOREIGN KEY(id) REFERENCES reportes (id) ON DELETE CASCADE
);

-- Table: reportes_matpel_glp
CREATE TABLE reportes_matpel_glp (
	id INTEGER NOT NULL, 
	clasificacion_servicio VARCHAR(100), 
	nombre_producto VARCHAR(150), 
	un_numero VARCHAR(10), 
	tipo_almacenamiento VARCHAR(100), 
	certificado_bomberil BOOLEAN DEFAULT FALSE, 
	nro_certificado VARCHAR(50), 
	propietario_nombre VARCHAR(150), 
	propietario_rif_ci VARCHAR(30), 
	empresa_distribuidora VARCHAR(150), 
	vehiculo_marca VARCHAR(50), 
	vehiculo_placa VARCHAR(20), 
	vehiculo_color VARCHAR(30), 
	hoja_seguridad BOOLEAN DEFAULT FALSE, 
	extintor BOOLEAN DEFAULT FALSE, 
	equipo_derrame BOOLEAN DEFAULT FALSE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(id) REFERENCES reportes (id) ON DELETE CASCADE
);

-- Table: reportes_matpel_otros
CREATE TABLE reportes_matpel_otros (
	id INTEGER NOT NULL, 
	descripcion_sustancia TEXT, 
	riesgos_identificados TEXT, 
	medidas_seguridad_adoptadas TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(id) REFERENCES reportes (id) ON DELETE CASCADE
);

-- Table: reportes_matpel_quimico
CREATE TABLE reportes_matpel_quimico (
	id INTEGER NOT NULL, 
	nombre_sustancia VARCHAR(150), 
	un_numero VARCHAR(10), 
	riesgos_especificos TEXT, 
	materiales_absorbentes_usados VARCHAR(255), 
	materiales_neutralizantes_usados VARCHAR(255), 
	acciones_mitigacion TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(id) REFERENCES reportes (id) ON DELETE CASCADE
);

-- Table: reportes_pre_hospitalario
CREATE TABLE reportes_pre_hospitalario (
	id INTEGER NOT NULL, 
	paciente_nombre VARCHAR(150), 
	paciente_edad INTEGER, 
	paciente_genero VARCHAR(20), 
	paciente_cedula VARCHAR(20), 
	condicion_paciente TEXT, 
	signos_vitales_tension VARCHAR(20), 
	signos_vitales_pulso INTEGER, 
	signos_vitales_fr INTEGER, 
	centro_traslado VARCHAR(150), 
	material_medico_utilizado TEXT, 
	recomendaciones TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(id) REFERENCES reportes (id) ON DELETE CASCADE
);

-- Table: reportes_servicio_achicamiento
CREATE TABLE reportes_servicio_achicamiento (
	id INTEGER NOT NULL, 
	condicion_inmueble TEXT, 
	causa_inundacion VARCHAR(150), 
	bombas_usadas VARCHAR(150), 
	tiempo_operacion VARCHAR(50), 
	nivel_agua_inicial VARCHAR(50), 
	nivel_agua_final VARCHAR(50), 
	inspeccion_tecnica_observaciones TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(id) REFERENCES reportes (id) ON DELETE CASCADE
);

-- Table: reportes_servicio_agua
CREATE TABLE reportes_servicio_agua (
	id INTEGER NOT NULL, 
	clasificacion_servicio VARCHAR(100), 
	material_usado TEXT, 
	litros_distribuidos INTEGER NOT NULL DEFAULT 0, 
	beneficiarios_estimados INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(id) REFERENCES reportes (id) ON DELETE CASCADE
);

-- Table: reportes_servicio_animal
CREATE TABLE reportes_servicio_animal (
	id INTEGER NOT NULL, 
	tipo_animal VARCHAR(100), 
	raza_descripcion VARCHAR(150), 
	condicion_animal VARCHAR(255), 
	destino_animal VARCHAR(150), 
	recomendaciones_tecnicas TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(id) REFERENCES reportes (id) ON DELETE CASCADE
);

-- Table: reportes_servicio_baldeo
CREATE TABLE reportes_servicio_baldeo (
	id INTEGER NOT NULL, 
	motivo_baldeo VARCHAR(150), 
	area_afectada VARCHAR(255), 
	limpieza_vias_efectuada BOOLEAN DEFAULT TRUE, 
	litros_agua_utilizados INTEGER NOT NULL DEFAULT 0, 
	observaciones_baldeo TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(id) REFERENCES reportes (id) ON DELETE CASCADE
);

-- Table: reportes_servicio_insectos
CREATE TABLE reportes_servicio_insectos (
	id INTEGER NOT NULL, 
	tipo_insecto VARCHAR(100), 
	clasificacion_riesgo VARCHAR(50), 
	condicion_actual TEXT, 
	metodo_control VARCHAR(150), 
	materiales_utilizados VARCHAR(255), 
	recomendaciones TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(id) REFERENCES reportes (id) ON DELETE CASCADE
);

-- ========================================================
-- SEED DATA (DEFAULT USERS)
-- ========================================================

-- Inserta los usuarios por defecto (admin / admin123 y bombero / bombero123)
INSERT INTO usuarios (id, username, password_hash, nombre, apellido, cedula, rango, rol, activo, fecha_registro) VALUES 
(1, 'admin', 'scrypt:32768:8:1$Oq4p8vckAmefeTA7$9fae21ce189bb39173b448b17a5cde9d39769a533a95f6cb2122a84504315d04f5770b654f117a53d2a4d6830f5807b96c89e728018b1db199cb7824b1c7cd53', 'Jefe', 'Administrador', 'V-12345678', 'Coronel', 'administrador', TRUE, CURRENT_TIMESTAMP),
(2, 'bombero', 'scrypt:32768:8:1$dgb9rt6mj7fnSk6H$8ed3d01b087250acae588f4bdbf8c2e1d44940da22eee6251d1456adba6b7e28f0e05e547d66e51427adfdd263ced6eaaa0508b5b9a900a1756fc4e17f924550', 'Juan', 'Pérez', 'V-87654321', 'Cabo Primero', 'bombero', TRUE, CURRENT_TIMESTAMP);

-- Ajusta la secuencia de ID para la tabla usuarios
SELECT setval(pg_get_serial_sequence('usuarios', 'id'), COALESCE((SELECT MAX(id) FROM usuarios), 1), true);
