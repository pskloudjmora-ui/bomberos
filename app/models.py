from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Usuario(db.Model, UserMixin):
    """
    Representa a los usuarios del sistema (Bomberos y Administradores).
    Implementa el Control de Acceso Basado en Roles (RBAC).
    """
    __tablename__ = 'usuarios'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    cedula = db.Column(db.String(20), unique=True, nullable=False)
    rango = db.Column(db.String(50), nullable=True)  # Ej: Distinguido, Sargento, Teniente, etc.
    rol = db.Column(db.String(20), nullable=False, default='bombero')  # 'bombero' o 'administrador'
    activo = db.Column(db.Boolean, default=True)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)

    # Relaciones de auditoría
    reportes_creados = db.relationship('Reporte', backref='creador', foreign_keys='Reporte.creador_id', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def es_admin(self):
        return self.rol == 'administrador'

    def __repr__(self):
        return f'<Usuario {self.rango} {self.nombre} {self.apellido}>'


class Vehiculo(db.Model):
    """
    Flota de vehículos y unidades móviles del Cuerpo de Bomberos.
    """
    __tablename__ = 'vehiculos'
    
    id = db.Column(db.Integer, primary_key=True)
    unidad = db.Column(db.String(20), unique=True, nullable=False)  # Ej: B-05, M-15, A-02
    placa = db.Column(db.String(20), unique=True, nullable=False)
    marca = db.Column(db.String(50), nullable=False)
    modelo = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(30), nullable=True)
    tipo = db.Column(db.String(50), nullable=False)  # Ej: Unidad de Supresión de Incendios, Ambulancia, Cisterna
    activo = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<Vehiculo {self.unidad} ({self.tipo})>'


class Reporte(db.Model):
    """
    Modelo Base para todos los tipos de reportes de actuaciones/incidencias.
    Implementa Joined Table Inheritance para evitar redundancia de campos comunes.
    """
    __tablename__ = 'reportes'
    
    id = db.Column(db.Integer, primary_key=True)
    nro_control = db.Column(db.String(30), unique=True, nullable=False)  # Nro de control único secuencial
    fecha = db.Column(db.Date, nullable=False)
    clase_aviso = db.Column(db.String(50), nullable=False)  # Ej: Radial, Telefónico, Personal, Prensa, etc.
    
    # Tiempos de actuación
    hora_aviso = db.Column(db.Time, nullable=False)
    hora_salida = db.Column(db.Time, nullable=False)
    hora_llegada = db.Column(db.Time, nullable=False)
    hora_regreso = db.Column(db.Time, nullable=False)
    
    # Solicitante y Receptor del aviso
    solicitante_nombre = db.Column(db.String(150), nullable=True)
    solicitante_cedula = db.Column(db.String(20), nullable=True)
    solicitante_telefono = db.Column(db.String(30), nullable=True)
    receptor_aviso = db.Column(db.String(150), nullable=False)  # Nombre o cargo de quien recibió el reporte radial/telefónico
    receptor_cedula = db.Column(db.String(20), nullable=True)  # Cédula o RIF del receptor
    
    # Ubicación del evento
    direccion = db.Column(db.Text, nullable=False)
    punto_referencia = db.Column(db.String(255), nullable=True)
    
    # Auditoría y Estados
    creador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    estado = db.Column(db.String(20), default='Borrador')  # Borrador, Enviado, Validado, Rechazado
    observaciones_generales = db.Column(db.Text, nullable=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_modificacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Columnas para la herencia polimórfica
    tipo_reporte = db.Column(db.String(50), nullable=False)

    # Relaciones 1-a-N secundarias comunes a todos los reportes
    vehiculos_actuantes = db.relationship('ReporteVehiculoActuante', backref='reporte', cascade='all, delete-orphan', lazy=True)
    personal_actuante = db.relationship('ReportePersonalActuante', backref='reporte', cascade='all, delete-orphan', lazy=True)
    otros_organismos = db.relationship('ReporteOtroOrganismo', backref='reporte', cascade='all, delete-orphan', lazy=True)

    __mapper_args__ = {
        'polymorphic_on': tipo_reporte,
        'polymorphic_identity': 'general'
    }

    def __repr__(self):
        return f'<Reporte {self.nro_control} [{self.tipo_reporte}]>'


# ==========================================
# TABLAS INTERMEDIAS Y RELACIONES COMPLEJAS
# ==========================================

class ReporteVehiculoActuante(db.Model):
    """
    Detalle de los vehículos que actuaron en una incidencia.
    Registra datos específicos del uso del vehículo.
    """
    __tablename__ = 'reporte_vehiculos_actuantes'
    
    id = db.Column(db.Integer, primary_key=True)
    reporte_id = db.Column(db.Integer, db.ForeignKey('reportes.id', ondelete='CASCADE'), nullable=False)
    vehiculo_id = db.Column(db.Integer, db.ForeignKey('vehiculos.id'), nullable=False)
    
    # Información de recorrido del servicio
    km_salida = db.Column(db.Numeric(10, 2), nullable=True)
    km_llegada = db.Column(db.Numeric(10, 2), nullable=True)
    
    # Conductor del vehículo
    conductor_nombre = db.Column(db.String(150), nullable=False)
    
    # Relación directa con el objeto Vehiculo
    vehiculo = db.relationship('Vehiculo', lazy=True)


class ReportePersonalActuante(db.Model):
    """
    Bomberos vinculados con la actuación de un reporte.
    Define quién fue Jefe de Comisión, Conductor, Combatiente o quién elaboró el reporte.
    """
    __tablename__ = 'reporte_personal_actuante'
    
    id = db.Column(db.Integer, primary_key=True)
    reporte_id = db.Column(db.Integer, db.ForeignKey('reportes.id', ondelete='CASCADE'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)  # Si está registrado
    
    # Campos de respaldo en caso de que no tenga usuario en el sistema
    nombre_completo = db.Column(db.String(150), nullable=False)
    cedula = db.Column(db.String(20), nullable=True)
    rango = db.Column(db.String(50), nullable=True)
    
    # Rol que desempeñó en este servicio en particular
    rol_en_servicio = db.Column(db.String(50), nullable=False)  # Ej: 'Jefe de Comisión', 'Conductor', 'Combatiente', 'Reporte Elaborado Por'


class ReporteOtroOrganismo(db.Model):
    """
    Organismos externos que actuaron en el sitio de la incidencia (CICPC, PC, GNB, Policía, etc.)
    """
    __tablename__ = 'reporte_otros_organismos'
    
    id = db.Column(db.Integer, primary_key=True)
    reporte_id = db.Column(db.Integer, db.ForeignKey('reportes.id', ondelete='CASCADE'), nullable=False)
    nombre_organismo = db.Column(db.String(100), nullable=False)  # Ej: CICPC, GNB, Policía Nacional, Protección Civil
    jefe_unidad = db.Column(db.String(150), nullable=True)
    matricula_unidad = db.Column(db.String(50), nullable=True)
    cantidad_unidades = db.Column(db.Integer, default=1)


# ========================================================
# SUBCLASES ESPECÍFICAS DE REPORTES (JOINED TABLE INHERITANCE)
# ========================================================

# -----------------
# CATEGORÍA: MATPEL (Materiales Peligrosos)
# -----------------

class ReporteMatpelGLP(Reporte):
    """
    1. Reporte MATPEL - Control de Escape de Gas Licuado de Petróleo (GLP).
    """
    __tablename__ = 'reportes_matpel_glp'
    
    id = db.Column(db.Integer, db.ForeignKey('reportes.id', ondelete='CASCADE'), primary_key=True)
    
    clasificacion_servicio = db.Column(db.String(100), nullable=True)  # Residencial, Comercial, Industrial, Transporte
    nombre_producto = db.Column(db.String(150), nullable=True)  # GLP, Propano, Butano, etc.
    un_numero = db.Column(db.String(10), nullable=True)  # Ej: UN 1075
    riesgo_producto = db.Column(db.String(150), nullable=True)  # Inflamable, Explosivo, Asfixiante, etc.
    tipo_almacenamiento = db.Column(db.String(100), nullable=True)  # Cilindro, Tanque Estacionario, Cisterna
    
    # Certificaciones y Permisologías
    certificado_bomberil = db.Column(db.Boolean, default=False)
    nro_certificado = db.Column(db.String(50), nullable=True)
    
    # Datos de Propietarios y Terceros Involucrados
    propietario_nombre = db.Column(db.String(150), nullable=True)
    propietario_rif_ci = db.Column(db.String(30), nullable=True)
    empresa_distribuidora = db.Column(db.String(150), nullable=True)
    
    # Datos del vehículo involucrado si aplica (transporte de GLP)
    vehiculo_marca = db.Column(db.String(50), nullable=True)
    vehiculo_modelo = db.Column(db.String(50), nullable=True)
    vehiculo_placa = db.Column(db.String(20), nullable=True)
    vehiculo_color = db.Column(db.String(30), nullable=True)
    vehiculo_afecto = db.Column(db.Boolean, default=False)  # Si el vehículo afectó el inmueble
    
    # Controles técnicos
    hoja_seguridad = db.Column(db.Boolean, default=False)
    extintor = db.Column(db.Boolean, default=False)
    equipo_derrame = db.Column(db.Boolean, default=False)

    __mapper_args__ = {
        'polymorphic_identity': 'matpel_glp',
    }


class ReporteMatpelCombustible(Reporte):
    """
    2. Reporte MATPEL - Derrame de Combustible.
    """
    __tablename__ = 'reportes_matpel_combustible'
    
    id = db.Column(db.Integer, db.ForeignKey('reportes.id', ondelete='CASCADE'), primary_key=True)
    
    tipo_combustible = db.Column(db.String(100), nullable=True)  # Gasolina, Diésel, Kerosén, etc.
    tipo_almacenamiento = db.Column(db.String(100), nullable=True)  # Tanque subterráneo, Superficial, Vehicular, etc.
    un_numero = db.Column(db.String(10), nullable=True)  # Código ONU del combustible (ej: UN 1203 Gasolina)
    capacidad_tanque_litros = db.Column(db.Numeric(10, 2), nullable=True)  # Capacidad total del tanque en litros
    vehiculos_involucrados = db.Column(db.Text, nullable=True)  # Descripción de vehículos implicados
    mitigacion_efectuada = db.Column(db.Text, nullable=True)  # Ej: Capa de espuma, lavado con detergente, dispersión
    cantidad_estimada_derrame = db.Column(db.Numeric(10, 2), nullable=True)  # En Litros
    vehiculo_marca = db.Column(db.String(50), nullable=True)  # Marca del vehículo que causó el derrame
    vehiculo_modelo = db.Column(db.String(50), nullable=True)  # Modelo del vehículo
    vehiculo_placa = db.Column(db.String(20), nullable=True)  # Placa del vehículo
    vehiculo_color = db.Column(db.String(30), nullable=True)  # Color del vehículo
    vehiculo_afecto = db.Column(db.Boolean, default=False)  # Si el vehículo afectó/causó el derrame

    __mapper_args__ = {
        'polymorphic_identity': 'matpel_combustible',
    }


class ReporteMatpelQuimico(Reporte):
    """
    3. Reporte MATPEL - Derrame de Sustancia Química.
    """
    __tablename__ = 'reportes_matpel_quimico'
    
    id = db.Column(db.Integer, db.ForeignKey('reportes.id', ondelete='CASCADE'), primary_key=True)
    
    nombre_sustancia = db.Column(db.String(150), nullable=True)
    un_numero = db.Column(db.String(10), nullable=True)
    riesgos_especificos = db.Column(db.Text, nullable=True)  # Inflamable, Tóxico, Corrosivo, Reactivo
    materiales_absorbentes_usados = db.Column(db.String(255), nullable=True)  # Arena, Aserrín, Cal, etc.
    materiales_neutralizantes_usados = db.Column(db.String(255), nullable=True)
    acciones_mitigacion = db.Column(db.Text, nullable=True)
    vehiculo_marca = db.Column(db.String(50), nullable=True)
    vehiculo_modelo = db.Column(db.String(50), nullable=True)
    vehiculo_placa = db.Column(db.String(20), nullable=True)
    vehiculo_color = db.Column(db.String(30), nullable=True)
    vehiculo_afecto = db.Column(db.Boolean, default=False)

    __mapper_args__ = {
        'polymorphic_identity': 'matpel_quimico',
    }


class ReporteMatpelOtros(Reporte):
    """
    4. Reporte MATPEL - Otras Sustancias Peligrosas.
    """
    __tablename__ = 'reportes_matpel_otros'
    
    id = db.Column(db.Integer, db.ForeignKey('reportes.id', ondelete='CASCADE'), primary_key=True)
    
    descripcion_sustancia = db.Column(db.Text, nullable=True)
    riesgos_identificados = db.Column(db.Text, nullable=True)
    medidas_seguridad_adoptadas = db.Column(db.Text, nullable=True)

    __mapper_args__ = {
        'polymorphic_identity': 'matpel_otros',
    }


# -----------------
# CATEGORÍA: SALUD
# -----------------

class ReportePreHospitalario(Reporte):
    """
    5. Reporte de Atención Pre-Hospitalaria / Traslado de Emergencia.
    """
    __tablename__ = 'reportes_pre_hospitalario'
    
    id = db.Column(db.Integer, db.ForeignKey('reportes.id', ondelete='CASCADE'), primary_key=True)
    
    # Datos del paciente
    paciente_nombre = db.Column(db.String(150), nullable=True)
    paciente_edad = db.Column(db.Integer, nullable=True)
    paciente_genero = db.Column(db.String(20), nullable=True)
    paciente_cedula = db.Column(db.String(20), nullable=True)
    
    # Estado clínico
    condicion_paciente = db.Column(db.Text, nullable=True)  # Diagnóstico preliminar o trauma
    signos_vitales_tension = db.Column(db.String(20), nullable=True)  # TA
    signos_vitales_pulso = db.Column(db.Integer, nullable=True)  # ppm
    signos_vitales_fr = db.Column(db.Integer, nullable=True)  # rpm
    
    # Logística y Tratamiento
    centro_traslado = db.Column(db.String(150), nullable=True)  # Ej: Hospital Central, IVSS, etc.
    material_medico_utilizado = db.Column(db.Text, nullable=True)  # Inmovilizadores, oxígeno, gasas, etc.
    recomendaciones = db.Column(db.Text, nullable=True)

    __mapper_args__ = {
        'polymorphic_identity': 'pre_hospitalario',
    }


# -----------------
# CATEGORÍA: SERVICIOS ESPECIALES
# -----------------

class ReporteServicioAgua(Reporte):
    """
    6. Reporte de Servicios Especiales - Abastecimiento de Agua.
    """
    __tablename__ = 'reportes_servicio_agua'
    
    id = db.Column(db.Integer, db.ForeignKey('reportes.id', ondelete='CASCADE'), primary_key=True)
    
    clasificacion_servicio = db.Column(db.String(100), nullable=True)  # Gubernamental, Comunidad, Institución Pública, Institución Privada, etc.
    material_usado = db.Column(db.Text, nullable=True)  # Mangueras de 2.5", acoples, etc.
    litros_distribuidos = db.Column(db.Integer, nullable=False, default=0)
    beneficiarios_estimados = db.Column(db.Integer, nullable=True)

    __mapper_args__ = {
        'polymorphic_identity': 'servicio_agua',
    }


class ReporteServicioInsectos(Reporte):
    """
    7. Reporte de Servicios Especiales - Control y Re-ubicación de Insectos (Ponzoñosos/No Ponzoñosos).
    """
    __tablename__ = 'reportes_servicio_insectos'
    
    id = db.Column(db.Integer, db.ForeignKey('reportes.id', ondelete='CASCADE'), primary_key=True)
    
    tipo_insecto = db.Column(db.String(100), nullable=True)  # Abejas, Avispas, Meliponini, Otros
    clasificacion_riesgo = db.Column(db.String(50), nullable=True)  # Ponzoñoso, No Ponzoñoso
    condicion_actual = db.Column(db.Text, nullable=True)  # Ubicación del panal, altura, agresividad
    metodo_control = db.Column(db.String(150), nullable=True)  # Exterminio, Reubicación, Captura
    materiales_utilizados = db.Column(db.String(255), nullable=True)  # Traje de apicultura, humo, insecticidas
    recomendaciones = db.Column(db.Text, nullable=True)

    __mapper_args__ = {
        'polymorphic_identity': 'servicio_insectos',
    }


class ReporteServicioAnimal(Reporte):
    """
    8. Reporte de Servicios Especiales - Control de Animal Doméstico.
    """
    __tablename__ = 'reportes_servicio_animal'
    
    id = db.Column(db.Integer, db.ForeignKey('reportes.id', ondelete='CASCADE'), primary_key=True)
    
    tipo_animal = db.Column(db.String(100), nullable=True)  # Canino, Felino, Otro
    raza_descripcion = db.Column(db.String(150), nullable=True)
    condicion_animal = db.Column(db.String(255), nullable=True)  # Atrapado, herido, agresivo, etc.
    destino_animal = db.Column(db.String(150), nullable=True)  # Entregado a dueño, refugio, liberado
    recomendaciones_tecnicas = db.Column(db.Text, nullable=True)

    __mapper_args__ = {
        'polymorphic_identity': 'servicio_animal',
    }


class ReporteServicioAchicamiento(Reporte):
    """
    9. Reporte de Servicios Especiales - Achicamiento por Aguas Estancadas.
    """
    __tablename__ = 'reportes_servicio_achicamiento'
    
    id = db.Column(db.Integer, db.ForeignKey('reportes.id', ondelete='CASCADE'), primary_key=True)
    
    condicion_inmueble = db.Column(db.Text, nullable=True)  # Vivienda inundada, sótano de edificio, etc.
    causa_inundacion = db.Column(db.String(150), nullable=True)  # Lluvias, tubería rota, colapso de cloacas
    bombas_usadas = db.Column(db.String(150), nullable=True)  # Ej: Motobomba de 3", Electrobomba sumergible
    tiempo_operacion = db.Column(db.String(50), nullable=True)  # Duración de la succión
    nivel_agua_inicial = db.Column(db.String(50), nullable=True)  # En centímetros/metros
    nivel_agua_final = db.Column(db.String(50), nullable=True)
    inspeccion_tecnica_observaciones = db.Column(db.Text, nullable=True)

    __mapper_args__ = {
        'polymorphic_identity': 'servicio_achicamiento',
    }


class ReporteServicioBaldeo(Reporte):
    """
    10. Reporte de Servicios Especiales - Baldeo de Agua.
    """
    __tablename__ = 'reportes_servicio_baldeo'
    
    id = db.Column(db.Integer, db.ForeignKey('reportes.id', ondelete='CASCADE'), primary_key=True)
    
    motivo_baldeo = db.Column(db.String(150), nullable=True)  # Despeje de vía por derrame menor, limpieza post-incendio, eventos públicos
    area_afectada = db.Column(db.String(255), nullable=True)  # Av. Principal, Plaza Bolívar, etc.
    limpieza_vias_efectuada = db.Column(db.Boolean, default=True)
    litros_agua_utilizados = db.Column(db.Integer, nullable=False, default=0)
    observaciones_baldeo = db.Column(db.Text, nullable=True)

    __mapper_args__ = {
        'polymorphic_identity': 'servicio_baldeo',
    }


# ========================================================
# NUEVOS FORMULARIOS - PERSONA AFECTADA COMPARTIDA
# ========================================================

class ReportePersonaAfectada(db.Model):
    """
    Personas afectadas en reportes de Atención Pre-Hospitalaria y Rescate.
    Tabla compartida para múltiples tipos de reportes.
    """
    __tablename__ = 'reporte_personas_afectadas'

    id = db.Column(db.Integer, primary_key=True)
    reporte_id = db.Column(db.Integer, db.ForeignKey('reportes.id', ondelete='CASCADE'), nullable=False)
    nombre_apellido = db.Column(db.String(200), nullable=False)
    cedula_pasaporte = db.Column(db.String(30), nullable=True)
    edad = db.Column(db.Integer, nullable=True)
    sexo = db.Column(db.String(20), nullable=True)
    lesion = db.Column(db.String(255), nullable=True)
    residencia = db.Column(db.String(255), nullable=True)

    reporte = db.relationship('Reporte', backref=db.backref('personas_afectadas', cascade='all, delete-orphan', lazy=True))


# ========================================================
# SUBCLASES: ATENCIÓN PRE-HOSPITALARIA (4 TIPOS)
# ========================================================

class ReporteAPHTraslado(Reporte):
    """
    Reporte de Atención Pre-Hospitalaria: Traslado de Emergencia.
    """
    __tablename__ = 'reportes_aph_traslado'

    id = db.Column(db.Integer, db.ForeignKey('reportes.id', ondelete='CASCADE'), primary_key=True)

    # Signos Vitales
    signos_vitales_pa = db.Column(db.String(20), nullable=True)
    signos_vitales_fc = db.Column(db.Integer, nullable=True)
    signos_vitales_fr = db.Column(db.Integer, nullable=True)
    signos_vitales_temperatura = db.Column(db.String(10), nullable=True)

    # Escala de Coma de Glasgow
    glasgow_apertura_ocular = db.Column(db.Integer, nullable=True)
    glasgow_respuesta_verbal = db.Column(db.Integer, nullable=True)
    glasgow_respuesta_motora = db.Column(db.Integer, nullable=True)
    glasgow_total = db.Column(db.Integer, nullable=True)

    # Regla de los 9 para Quemaduras
    regla_9_cabeza = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_torax = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_abdomen = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_miembro_superior_d = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_miembro_superior_i = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_miembro_inferior_d = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_miembro_inferior_i = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_total = db.Column(db.Numeric(5, 2), nullable=True)

    # Procedimientos y Tratamiento
    procedimiento_paraclinico = db.Column(db.Text, nullable=True)
    medicinas_usadas = db.Column(db.Text, nullable=True)
    material_medico_usado = db.Column(db.Text, nullable=True)

    # Datos del Centro Hospitalario
    centro_hospitalario = db.Column(db.String(200), nullable=True)
    medico_recibe = db.Column(db.String(150), nullable=True)
    medico_cedula = db.Column(db.String(20), nullable=True)
    medico_msds = db.Column(db.String(50), nullable=True)
    medico_firma = db.Column(db.Boolean, default=False)

    # Rechazo a la Atención y Traslado
    rechazo_nombre = db.Column(db.String(200), nullable=True)
    rechazo_cedula = db.Column(db.String(20), nullable=True)
    rechazo_firma = db.Column(db.Boolean, default=False)

    __mapper_args__ = {
        'polymorphic_identity': 'aph_traslado',
    }


class ReporteAPHNoTraslado(Reporte):
    """
    Reporte de Atención Pre-Hospitalaria: Traslado No Realizado.
    """
    __tablename__ = 'reportes_aph_no_traslado'

    id = db.Column(db.Integer, db.ForeignKey('reportes.id', ondelete='CASCADE'), primary_key=True)

    # Signos Vitales
    signos_vitales_pa = db.Column(db.String(20), nullable=True)
    signos_vitales_fc = db.Column(db.Integer, nullable=True)
    signos_vitales_fr = db.Column(db.Integer, nullable=True)
    signos_vitales_temperatura = db.Column(db.String(10), nullable=True)

    # Escala de Coma de Glasgow
    glasgow_apertura_ocular = db.Column(db.Integer, nullable=True)
    glasgow_respuesta_verbal = db.Column(db.Integer, nullable=True)
    glasgow_respuesta_motora = db.Column(db.Integer, nullable=True)
    glasgow_total = db.Column(db.Integer, nullable=True)

    # Regla de los 9 para Quemaduras
    regla_9_cabeza = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_torax = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_abdomen = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_miembro_superior_d = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_miembro_superior_i = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_miembro_inferior_d = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_miembro_inferior_i = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_total = db.Column(db.Numeric(5, 2), nullable=True)

    # Procedimientos y Tratamiento
    procedimiento_paraclinico = db.Column(db.Text, nullable=True)
    medicinas_usadas = db.Column(db.Text, nullable=True)
    material_medico_usado = db.Column(db.Text, nullable=True)

    # Datos del Centro Hospitalario
    centro_hospitalario = db.Column(db.String(200), nullable=True)
    medico_recibe = db.Column(db.String(150), nullable=True)
    medico_cedula = db.Column(db.String(20), nullable=True)
    medico_msds = db.Column(db.String(50), nullable=True)
    medico_firma = db.Column(db.Boolean, default=False)

    # Motivo del No Traslado
    motivo_no_traslado = db.Column(db.Text, nullable=True)
    indicaciones_dejadas = db.Column(db.Text, nullable=True)

    # Rechazo a la Atención y Traslado
    rechazo_nombre = db.Column(db.String(200), nullable=True)
    rechazo_cedula = db.Column(db.String(20), nullable=True)
    rechazo_firma = db.Column(db.Boolean, default=False)

    __mapper_args__ = {
        'polymorphic_identity': 'aph_no_traslado',
    }


class ReporteAPHInterhospitalario(Reporte):
    """
    Reporte de Atención Pre-Hospitalaria: Traslados Interhospitalarios.
    """
    __tablename__ = 'reportes_aph_interhospitalario'

    id = db.Column(db.Integer, db.ForeignKey('reportes.id', ondelete='CASCADE'), primary_key=True)

    # Signos Vitales
    signos_vitales_pa = db.Column(db.String(20), nullable=True)
    signos_vitales_fc = db.Column(db.Integer, nullable=True)
    signos_vitales_fr = db.Column(db.Integer, nullable=True)
    signos_vitales_temperatura = db.Column(db.String(10), nullable=True)

    # Escala de Coma de Glasgow
    glasgow_apertura_ocular = db.Column(db.Integer, nullable=True)
    glasgow_respuesta_verbal = db.Column(db.Integer, nullable=True)
    glasgow_respuesta_motora = db.Column(db.Integer, nullable=True)
    glasgow_total = db.Column(db.Integer, nullable=True)

    # Regla de los 9 para Quemaduras
    regla_9_cabeza = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_torax = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_abdomen = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_miembro_superior_d = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_miembro_superior_i = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_miembro_inferior_d = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_miembro_inferior_i = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_total = db.Column(db.Numeric(5, 2), nullable=True)

    # Procedimientos y Tratamiento
    procedimiento_paraclinico = db.Column(db.Text, nullable=True)
    medicinas_usadas = db.Column(db.Text, nullable=True)
    material_medico_usado = db.Column(db.Text, nullable=True)

    # Datos Centro de Origen
    centro_origen = db.Column(db.String(200), nullable=True)
    medico_origen = db.Column(db.String(150), nullable=True)

    # Datos Centro de Destino
    centro_destino = db.Column(db.String(200), nullable=True)
    medico_recibe = db.Column(db.String(150), nullable=True)
    medico_cedula = db.Column(db.String(20), nullable=True)
    medico_msds = db.Column(db.String(50), nullable=True)
    medico_firma = db.Column(db.Boolean, default=False)

    # Rechazo a la Atención y Traslado
    rechazo_nombre = db.Column(db.String(200), nullable=True)
    rechazo_cedula = db.Column(db.String(20), nullable=True)
    rechazo_firma = db.Column(db.Boolean, default=False)

    __mapper_args__ = {
        'polymorphic_identity': 'aph_interhospitalario',
    }


class ReporteAPHSinTraslado(Reporte):
    """
    Reporte de Atención Pre-Hospitalaria Sin Traslado.
    """
    __tablename__ = 'reportes_aph_sin_traslado'

    id = db.Column(db.Integer, db.ForeignKey('reportes.id', ondelete='CASCADE'), primary_key=True)

    # Signos Vitales
    signos_vitales_pa = db.Column(db.String(20), nullable=True)
    signos_vitales_fc = db.Column(db.Integer, nullable=True)
    signos_vitales_fr = db.Column(db.Integer, nullable=True)
    signos_vitales_temperatura = db.Column(db.String(10), nullable=True)

    # Escala de Coma de Glasgow
    glasgow_apertura_ocular = db.Column(db.Integer, nullable=True)
    glasgow_respuesta_verbal = db.Column(db.Integer, nullable=True)
    glasgow_respuesta_motora = db.Column(db.Integer, nullable=True)
    glasgow_total = db.Column(db.Integer, nullable=True)

    # Regla de los 9 para Quemaduras
    regla_9_cabeza = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_torax = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_abdomen = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_miembro_superior_d = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_miembro_superior_i = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_miembro_inferior_d = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_miembro_inferior_i = db.Column(db.Numeric(5, 2), nullable=True)
    regla_9_total = db.Column(db.Numeric(5, 2), nullable=True)

    # Procedimientos y Tratamiento
    procedimiento_paraclinico = db.Column(db.Text, nullable=True)
    medicinas_usadas = db.Column(db.Text, nullable=True)
    material_medico_usado = db.Column(db.Text, nullable=True)

    # Conducta Adoptada
    conducta_adoptada = db.Column(db.Text, nullable=True)
    indicaciones_dejadas = db.Column(db.Text, nullable=True)

    # Rechazo a la Atención y Traslado
    rechazo_nombre = db.Column(db.String(200), nullable=True)
    rechazo_cedula = db.Column(db.String(20), nullable=True)
    rechazo_firma = db.Column(db.Boolean, default=False)

    __mapper_args__ = {
        'polymorphic_identity': 'aph_sin_traslado',
    }


# ========================================================
# SUBCLASES: INCENDIOS (1 MODELO PARA 6 SUBTIPOS)
# ========================================================

class ReporteIncendio(Reporte):
    """
    Reporte unificado para incendios: Estructura, Apoyo por Incendios,
    Equipos Eléctricos, Vehículo, Desechos Sólidos, Vegetación/Forestal, Árbol.
    Se diferencia por el campo subtipo_incendio.
    """
    __tablename__ = 'reportes_incendio'

    id = db.Column(db.Integer, db.ForeignKey('reportes.id', ondelete='CASCADE'), primary_key=True)

    # Subtipo de incendio
    subtipo_incendio = db.Column(db.String(50), nullable=False)  # estructura, apoyo, electrico, vehiculo, desechos, vegetacion, arbol

    # Tipo de incendio (para vegetación/forestal: Vegetación o Forestal)
    tipo_incendio = db.Column(db.String(100), nullable=True)

    # Características del incendio
    clase_incendio = db.Column(db.String(20), nullable=True)  # 1era, 2da, 3era
    intensidad = db.Column(db.String(20), nullable=True)  # 1era, 2da, 3era
    lugar_desarrollo = db.Column(db.String(255), nullable=True)
    presunto_punto_origen = db.Column(db.String(255), nullable=True)
    tipo_equipo_contra_incendio = db.Column(db.String(255), nullable=True)
    hora_control = db.Column(db.Time, nullable=True)
    hora_extincion_total = db.Column(db.Time, nullable=True)
    porcentaje_perdida_fuego = db.Column(db.Numeric(5, 2), nullable=True)
    porcentaje_perdida_humo = db.Column(db.Numeric(5, 2), nullable=True)
    porcentaje_perdida_total = db.Column(db.Numeric(5, 2), nullable=True)
    litros_agua_utilizados = db.Column(db.Integer, nullable=True)
    hubo_propagacion = db.Column(db.Boolean, default=False)
    propagacion_donde = db.Column(db.String(255), nullable=True)
    metodos_extincion = db.Column(db.Text, nullable=True)
    tecnicas_extincion = db.Column(db.Text, nullable=True)
    poseia_equipos = db.Column(db.Boolean, default=False)
    fue_usado = db.Column(db.Boolean, default=False)
    por_quien_uso = db.Column(db.String(150), nullable=True)
    por_quien_ci = db.Column(db.String(20), nullable=True)
    evaluacion_preliminar = db.Column(db.Text, nullable=True)

    # Características del terreno (vegetación/forestal/árbol)
    tipo_terreno = db.Column(db.String(100), nullable=True)
    tipo_vegetacion = db.Column(db.String(100), nullable=True)
    extension_terreno = db.Column(db.String(100), nullable=True)
    extension_terreno_afectada = db.Column(db.String(100), nullable=True)
    coordenadas = db.Column(db.String(100), nullable=True)

    # Datos del vehículo (solo para subtipo vehiculo)
    vehiculo_marca = db.Column(db.String(50), nullable=True)
    vehiculo_modelo = db.Column(db.String(50), nullable=True)
    vehiculo_placa = db.Column(db.String(20), nullable=True)
    vehiculo_color = db.Column(db.String(30), nullable=True)
    vehiculo_anio = db.Column(db.String(10), nullable=True)
    vehiculo_tipo = db.Column(db.String(50), nullable=True)
    propietario_nombre = db.Column(db.String(150), nullable=True)
    propietario_cedula = db.Column(db.String(20), nullable=True)
    propietario_edad = db.Column(db.Integer, nullable=True)
    propietario_telefono = db.Column(db.String(30), nullable=True)

    # Datos del propietario/habitante del inmueble (estructura)
    inmueble_propietario_nombre = db.Column(db.String(150), nullable=True)
    inmueble_propietario_cedula = db.Column(db.String(20), nullable=True)
    inmueble_propietario_telefono = db.Column(db.String(30), nullable=True)

    __mapper_args__ = {
        'polymorphic_identity': 'incendio',
    }


# ========================================================
# SUBCLASES: RESCATE POR COLISIÓN/VOLCAMIENTO
# ========================================================

class ReporteRescateColision(Reporte):
    """
    Reporte unificado para rescate por Colisión/Volcamiento con/sin lesionado.
    Se diferencia por el campo subtipo_rescate.
    """
    __tablename__ = 'reportes_rescate_colision'

    id = db.Column(db.Integer, db.ForeignKey('reportes.id', ondelete='CASCADE'), primary_key=True)

    # Subtipo: colision_con_lesionado, colision_sin_lesionado, volcamiento_con_lesionado, volcamiento_sin_lesionado
    subtipo_rescate = db.Column(db.String(50), nullable=False)

    # Datos de vehículos involucrados (JSON serializado)
    vehiculos_involucrados_json = db.Column(db.Text, nullable=True)

    # Observaciones del custodio/responsable
    observaciones_custodio = db.Column(db.Text, nullable=True)
    vehiculo_cargo_nombre = db.Column(db.String(150), nullable=True)
    vehiculo_cargo_cedula = db.Column(db.String(20), nullable=True)
    vehiculo_cargo_telefono = db.Column(db.String(30), nullable=True)

    __mapper_args__ = {
        'polymorphic_identity': 'rescate_colision',
    }


# ========================================================
# SUBCLASES: RESCATE ESPECIALIZADO (6 SUBTIPOS)
# ========================================================

class ReporteRescateEspecializado(Reporte):
    """
    Reporte unificado para rescate especializado: Ascensor, Inmueble,
    Altura, Tapiada, Golpeada, Caída.
    Se diferencia por el campo subtipo_rescate.
    """
    __tablename__ = 'reportes_rescate_especializado'

    id = db.Column(db.Integer, db.ForeignKey('reportes.id', ondelete='CASCADE'), primary_key=True)

    # Subtipo: ascensor, inmueble, altura, tapiada, golpeada, caida
    subtipo_rescate = db.Column(db.String(50), nullable=False)

    # Tipo de servicio específico (para tapiada, golpeada, caída)
    tipo_servicio = db.Column(db.String(150), nullable=True)

    # Despliegue operacional
    despliegue_vehiculos = db.Column(db.Text, nullable=True)
    despliegue_conductor_nombre = db.Column(db.String(150), nullable=True)
    despliegue_conductor_ci = db.Column(db.String(20), nullable=True)
    despliegue_jefe_nombre = db.Column(db.String(150), nullable=True)
    despliegue_jefe_ci = db.Column(db.String(20), nullable=True)
    despliegue_cantidad_bomberos = db.Column(db.Integer, nullable=True)
    despliegue_material_usado = db.Column(db.Text, nullable=True)

    __mapper_args__ = {
        'polymorphic_identity': 'rescate_especializado',
    }


RANGOS_BOMBERILES = [
    'Primer General', 'General', 'Mayor', 'Teniente Coronel', 'Coronel', 'Capitán', 'Teniente',
    'Primer Teniente', 'Sargento Segundo', 'Sargento Primero', 'Sargento Mayor', 'Cabo Segundo',
    'Cabo Primero', 'Distinguido', 'Bombero Raso'
]
