"""
Servicio de generación de PDFs para los reportes operativos del Cuerpo de Bomberos.

El flujo es:
  1. serializar_reporte() convierte un objeto ORM en un DTO plano (dict) apto
     para la plantilla. Esto desacopla la base de datos del renderizador.
  2. generar_pdf_reporte() renderiza la plantilla reporte_pdf.html y la
     convierte a PDF usando WeasyPrint si está disponible (mejor fidelidad
     CSS) o xhtml2pdf como motor de respaldo puro-Python (sin dependencias
     nativas, ideal para Windows).

El logotipo se incrusta como Data URI (base64) directamente en el HTML para
que la conversión a PDF nunca dependa de servidores/URLs externas.
"""
import base64
import io
import os
from datetime import datetime
from functools import lru_cache

RUTA_LOGO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'static', 'imagen', 'logo-bomberos.png'
)

# Títulos legibles de cada tipo de servicio (se usan en el encabezado del PDF)
NOMBRE_SERVICIO = {
    'matpel_glp': 'CONTROL DE ESCAPE DE GAS LICUADO DE PETRÓLEO (GLP)',
    'matpel_combustible': 'DERRAME DE COMBUSTIBLE',
    'matpel_quimico': 'DERRAME DE SUSTANCIA QUÍMICA',
    'matpel_otros': 'OTRAS SUSTANCIAS PELIGROSAS',
    'pre_hospitalario': 'ATENCIÓN PRE-HOSPITALARIA / TRASLADO DE EMERGENCIA',
    'servicio_agua': 'ABASTECIMIENTO DE AGUA',
    'servicio_insectos': 'CONTROL Y REUBICACIÓN DE INSECTOS',
    'servicio_animal': 'CONTROL DE ANIMAL DOMÉSTICO',
    'servicio_achicamiento': 'ACHICAMIENTO POR AGUAS ESTANCADAS',
    'servicio_baldeo': 'BALDEO DE AGUA',
}

# Título de la sección 2 (detalle específico) según el tipo de reporte
TITULO_SECCION_2 = {
    'matpel_glp': '2. DETALLE TÉCNICO - ESCAPE DE GLP (MATPEL)',
    'matpel_combustible': '2. DETALLE TÉCNICO - DERRAME DE COMBUSTIBLE (MATPEL)',
    'matpel_quimico': '2. DETALLE TÉCNICO - DERRAME DE SUSTANCIA QUÍMICA (MATPEL)',
    'matpel_otros': '2. DETALLE TÉCNICO - OTRAS SUSTANCIAS PELIGROSAS (MATPEL)',
    'pre_hospitalario': '2. FICHA DE ATENCIÓN PRE-HOSPITALARIA / TRASLADO',
    'servicio_agua': '2. PARÁMETROS DEL ABASTECIMIENTO DE AGUA',
    'servicio_insectos': '2. PARÁMETROS DEL CONTROL Y REUBICACIÓN DE INSECTOS',
    'servicio_animal': '2. PARÁMETROS DEL CONTROL DE ANIMAL DOMÉSTICO',
    'servicio_achicamiento': '2. PARÁMETROS DEL ACHICAMIENTO POR AGUAS ESTANCADAS',
    'servicio_baldeo': '2. PARÁMETROS DEL BALDEO DE AGUA',
}

# Campos específicos por tipo de reporte: (Etiqueta del formulario, atributo del modelo, tipo de dato)
SECCIONES_ESPECIFICAS = {
    'matpel_glp': [
        ('Clasificación del Servicio', 'clasificacion_servicio', 'plain'),
        ('Nombre del Producto', 'nombre_producto', 'plain'),
        ('Número UN', 'un_numero', 'plain'),
        ('Tipo de Almacenamiento', 'tipo_almacenamiento', 'plain'),
        ('Riesgo del Producto', 'riesgo_producto', 'plain'),
        ('Certificado Bomberil', 'certificado_bomberil', 'bool'),
        ('N° Certificado Bomberil', 'nro_certificado', 'plain'),
        ('Propietario / Responsable del Inmueble', 'propietario_nombre', 'plain'),
        ('C.I. / RIF del Propietario', 'propietario_rif_ci', 'plain'),
        ('Empresa / Distribuidor', 'empresa_distribuidora', 'plain'),
        ('Vehículo de Carga - Marca', 'vehiculo_marca', 'plain'),
        ('Vehículo de Carga - Placa', 'vehiculo_placa', 'plain'),
        ('Vehículo de Carga - Color', 'vehiculo_color', 'plain'),
        ('Hoja de Seguridad (HDS) en Sitio', 'hoja_seguridad', 'bool'),
        ('Extintor en el Sitio', 'extintor', 'bool'),
        ('Equipo para Control de Derrames', 'equipo_derrame', 'bool'),
    ],
    'matpel_combustible': [
        ('Tipo de Combustible', 'tipo_combustible', 'plain'),
        ('Tipo de Almacenamiento', 'tipo_almacenamiento', 'plain'),
        ('Cantidad Estimada de Derrame', 'cantidad_estimada_derrame', 'plain'),
        ('Vehículos Involucrados', 'vehiculos_involucrados', 'plain'),
        ('Mitigación Efectuada', 'mitigacion_efectuada', 'plain'),
    ],
    'matpel_quimico': [
        ('Nombre de la Sustancia', 'nombre_sustancia', 'plain'),
        ('Número UN', 'un_numero', 'plain'),
        ('Riesgos Específicos del Producto', 'riesgos_especificos', 'plain'),
        ('Materiales Absorbentes Utilizados', 'materiales_absorbentes_usados', 'plain'),
        ('Materiales Neutralizantes Utilizados', 'materiales_neutralizantes_usados', 'plain'),
        ('Acciones de Mitigación', 'acciones_mitigacion', 'plain'),
    ],
    'matpel_otros': [
        ('Descripción de la Sustancia', 'descripcion_sustancia', 'plain'),
        ('Riesgos Identificados', 'riesgos_identificados', 'plain'),
        ('Medidas de Seguridad Adoptadas', 'medidas_seguridad_adoptadas', 'plain'),
    ],
    'pre_hospitalario': [
        ('Nombre del Paciente', 'paciente_nombre', 'plain'),
        ('Cédula del Paciente', 'paciente_cedula', 'plain'),
        ('Edad', 'paciente_edad', 'plain'),
        ('Género', 'paciente_genero', 'plain'),
        ('Signos Vitales - Tensión Arterial', 'signos_vitales_tension', 'plain'),
        ('Signos Vitales - Pulso', 'signos_vitales_pulso', 'plain'),
        ('Signos Vitales - Frecuencia Respiratoria', 'signos_vitales_fr', 'plain'),
        ('Condición / Diagnóstico Clínico', 'condicion_paciente', 'plain'),
        ('Centro de Traslado (Destino)', 'centro_traslado', 'plain'),
        ('Material Médico Utilizado', 'material_medico_utilizado', 'plain'),
        ('Recomendaciones', 'recomendaciones', 'plain'),
    ],
    'servicio_agua': [
        ('Clasificación del Servicio', 'clasificacion_servicio', 'plain'),
        ('Litros Suministrados (Lts.)', 'litros_distribuidos', 'plain'),
        ('Beneficiarios Estimados', 'beneficiarios_estimados', 'plain'),
    ],
    'servicio_insectos': [
        ('Tipo de Insecto', 'tipo_insecto', 'plain'),
        ('Clasificación de Riesgo', 'clasificacion_riesgo', 'plain'),
        ('Condición Actual y Ubicación', 'condicion_actual', 'plain'),
        ('Método de Control', 'metodo_control', 'plain'),
        ('Materiales Utilizados', 'materiales_utilizados', 'plain'),
        ('Recomendaciones', 'recomendaciones', 'plain'),
    ],
    'servicio_animal': [
        ('Tipo de Animal', 'tipo_animal', 'plain'),
        ('Raza / Descripción', 'raza_descripcion', 'plain'),
        ('Condición del Animal', 'condicion_animal', 'plain'),
        ('Destino del Animal', 'destino_animal', 'plain'),
        ('Recomendaciones Técnicas', 'recomendaciones_tecnicas', 'plain'),
    ],
    'servicio_achicamiento': [
        ('Causa de la Inundación', 'causa_inundacion', 'plain'),
        ('Condición del Inmueble', 'condicion_inmueble', 'plain'),
        ('Bombas / Equipos Utilizados', 'bombas_usadas', 'plain'),
        ('Tiempo de Operación', 'tiempo_operacion', 'plain'),
        ('Nivel de Agua Inicial', 'nivel_agua_inicial', 'plain'),
        ('Nivel de Agua Final', 'nivel_agua_final', 'plain'),
        ('Observaciones / Inspección Técnica', 'inspeccion_tecnica_observaciones', 'plain'),
    ],
    'servicio_baldeo': [
        ('Motivo del Baldeo', 'motivo_baldeo', 'plain'),
        ('Área / Vía Afectada', 'area_afectada', 'plain'),
        ('Limpieza de Vías Efectuada', 'limpieza_vias_efectuada', 'bool'),
        ('Litros de Agua Utilizados (Lts.)', 'litros_agua_utilizados', 'plain'),
        ('Observaciones del Baldeo', 'observaciones_baldeo', 'plain'),
    ],
}

# Campo del modelo que describe el material/equipos usados en la actuación, según el tipo
MATERIAL_ATTR = {
    'matpel_glp': None,
    'matpel_combustible': 'mitigacion_efectuada',
    'matpel_quimico': 'materiales_absorbentes_usados',
    'matpel_otros': 'medidas_seguridad_adoptadas',
    'pre_hospitalario': 'material_medico_utilizado',
    'servicio_agua': 'material_usado',
    'servicio_insectos': 'materiales_utilizados',
    'servicio_animal': None,
    'servicio_achicamiento': 'bombas_usadas',
    'servicio_baldeo': None,
}


def _formatear_valor(valor, tipo):
    """
    Normaliza el valor de un campo para mostrarlo en el PDF.
    Los booleanos se imprimen como SÍ/NO; los nulos como '—'.
    """
    if valor is None or valor == '':
        return '—'
    if tipo == 'bool':
        return 'SÍ' if valor else 'NO'
    return str(valor)


def _formatear_fecha(fecha):
    return fecha.strftime('%d/%m/%Y') if fecha else '—'


def _formatear_hora(hora):
    return hora.strftime('%H:%M') if hora else '—'


def _formatear_personal(persona):
    """
    Convierte un ReportePersonalActuante en un mini-DTO de firmas.
    Evita duplicar el rango si ya viene incluido en el nombre.
    """
    if persona is None:
        return None
    nombre = (persona.nombre_completo or '').strip()
    rango = (persona.rango or '').strip()
    if rango and nombre and not nombre.lower().startswith(rango.lower()):
        nombre = f'{rango} {nombre}'
    return {
        'nombre': nombre or '—',
        'cedula': persona.cedula or '—',
    }


def _nl2br_html(texto):
    """
    Escapa el texto y convierte saltos de línea en <br> para renderizarlo
    con |safe en la plantilla (compatible con xhtml2pdf y WeasyPrint).
    """
    if not texto:
        return '—'
    return texto.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')


@lru_cache(maxsize=1)
def obtener_logo_data_uri():
    """
    Lee el logotipo oficial desde app/static/imagen/logo-bomberos.png y lo
    devuelve como Data URI (data:image/png;base64,...) para incrustarlo
    directamente en el HTML del PDF.

    Ventajas de este enfoque frente a una URL:
      - No falla si el servidor web no puede resolver URLs absolutas.
      - No depende de autenticación ni de la carpeta /static en producción.
      - WeasyPrint y xhtml2pdf incrustan la imagen sin conexión a internet.

    La imagen se re-dimensiona (máx. 220px de ancho) para reducir el peso
    final del PDF. Si el archivo no existe, se devuelve '' y la plantilla
    muestra un recuadro de respaldo.
    """
    try:
        with open(RUTA_LOGO, 'rb') as f:
            data = f.read()
        try:
            from PIL import Image
            imagen = Image.open(io.BytesIO(data))
            if imagen.width > 220:
                alto = int(imagen.height * 220 / imagen.width)
                imagen = imagen.resize((220, alto), Image.LANCZOS)
            if imagen.mode not in ('RGB', 'RGBA'):
                imagen = imagen.convert('RGBA')
            buffer = io.BytesIO()
            imagen.save(buffer, format='PNG', optimize=True)
            data = buffer.getvalue()
        except Exception:
            pass
        return 'data:image/png;base64,' + base64.b64encode(data).decode('ascii')
    except Exception:
        return ''


def serializar_reporte(reporte):
    """
    Convierte un Reporte (SQLAlchemy) en el DTO plano que consume la plantilla
    reporte_pdf.html.

    Estructura del DTO (JSON-friendly):
    {
      "logo":                "data:image/png;base64,...",
      "nro_control":         "GLP-2026-0001",
      "nombre_servicio":     "CONTROL DE ESCAPE DE GAS LICUADO...",
      "titulo_seccion_2":    "2. DETALLE TÉCNICO - ...",
      "fecha_incidente":     "17/08/2026",
      "fecha_emision":       "17/08/2026 14:30",
      "clase_aviso":         "Radial",
      "receptor_aviso":      "Cabo Pérez",
      "horas":               [{"etiqueta": "Hora de Aviso",  "valor": "08:30"}, ...],
      "solicitante_nombre":  "...", "solicitante_cedula": "...", "solicitante_telefono": "...",
      "direccion":           "...", "punto_referencia": "...",
      "especifico":          [{"etiqueta": "Número UN", "valor": "UN 1075"}, ...],
      "vehiculos":           [{"unidad","tipo","placa","conductor","km_salida","km_llegada","recorrido"}, ...],
      "material_bomberil":   "...",
      "total_efectivos":     4,
      "jefe_comision":       {"nombre","cedula"} | None,
      "conductor_unidad":    {"nombre","cedula"} | None,
      "elaborado_por":       {"nombre","cedula"} | None,
      "combatientes":        [{"nombre","cedula"}, ...],
      "otros_organismos":    [{"nombre","jefe","matricula","cantidad"}, ...],
      "observaciones":       "...",
      "estado":              "Enviado"
    }
    """
    tipo = reporte.tipo_reporte

    especifico = []
    for etiqueta, attr, tipo_dato in SECCIONES_ESPECIFICAS.get(tipo, []):
        especifico.append({
            'etiqueta': etiqueta,
            'valor': _formatear_valor(getattr(reporte, attr, None), tipo_dato),
        })

    vehiculos = []
    for va in reporte.vehiculos_actuantes:
        vehiculo = va.vehiculo
        km_salida = float(va.km_salida or 0)
        km_llegada = float(va.km_llegada or 0)
        vehiculos.append({
            'unidad': vehiculo.unidad if vehiculo else '—',
            'tipo': vehiculo.tipo if vehiculo else '—',
            'placa': vehiculo.placa if vehiculo else '—',
            'conductor': va.conductor_nombre or '—',
            'km_salida': f'{km_salida:.2f}',
            'km_llegada': f'{km_llegada:.2f}',
            'recorrido': f'{km_llegada - km_salida:.2f}',
        })

    personal = list(reporte.personal_actuante)
    jefe = next((p for p in personal if p.rol_en_servicio == 'Jefe de Comisión'), None)
    conductor = next((p for p in personal if p.rol_en_servicio == 'Conductor Unidad'), None)
    elaborado = next((p for p in personal if 'Elaborado' in (p.rol_en_servicio or '')), None)
    combatientes = [_formatear_personal(p) for p in personal if p.rol_en_servicio == 'Combatiente']

    otros_organismos = [{
        'nombre': org.nombre_organismo,
        'jefe': org.jefe_unidad or '—',
        'matricula': org.matricula_unidad or '—',
        'cantidad': org.cantidad_unidades or 1,
    } for org in reporte.otros_organismos]

    attr_material = MATERIAL_ATTR.get(tipo)
    material = getattr(reporte, attr_material, None) if attr_material else None
    material = str(material).strip() if material else 'No registrado'

    fecha_emision = reporte.fecha_creacion or datetime.utcnow()

    return {
        'logo': '',
        'reporte_id': reporte.id,
        'nro_control': reporte.nro_control,
        'nombre_servicio': NOMBRE_SERVICIO.get(tipo, tipo.upper()),
        'titulo_seccion_2': TITULO_SECCION_2.get(tipo, '2. DETALLE DEL SERVICIO'),
        'fecha_incidente': _formatear_fecha(reporte.fecha),
        'fecha_emision': fecha_emision.strftime('%d/%m/%Y %H:%M'),
        'clase_aviso': reporte.clase_aviso or '—',
        'receptor_aviso': reporte.receptor_aviso or '—',
        'horas': [
            {'etiqueta': 'Hora de Aviso', 'valor': _formatear_hora(reporte.hora_aviso)},
            {'etiqueta': 'Hora de Salida', 'valor': _formatear_hora(reporte.hora_salida)},
            {'etiqueta': 'Hora de Llegada', 'valor': _formatear_hora(reporte.hora_llegada)},
            {'etiqueta': 'Hora de Regreso', 'valor': _formatear_hora(reporte.hora_regreso)},
        ],
        'solicitante_nombre': reporte.solicitante_nombre or '—',
        'solicitante_cedula': reporte.solicitante_cedula or '—',
        'solicitante_telefono': reporte.solicitante_telefono or '—',
        'direccion': reporte.direccion or '—',
        'punto_referencia': reporte.punto_referencia or '—',
        'especifico': especifico,
        'vehiculos': vehiculos,
        'material_bomberil': material,
        'total_efectivos': len(personal),
        'jefe_comision': _formatear_personal(jefe),
        'conductor_unidad': _formatear_personal(conductor),
        'elaborado_por': _formatear_personal(elaborado),
        'combatientes': combatientes,
        'otros_organismos': otros_organismos,
        'observaciones': _nl2br_html(reporte.observaciones_generales),
        'estado': reporte.estado or '—',
    }


def renderizar_html_reporte(reporte):
    """
    Renderiza el documento oficial del reporte como HTML plano (la misma
    plantilla usada para el PDF). Se usa en la vista de impresión/reimpresión
    del navegador y como insumo para la conversión a PDF.
    """
    from flask import render_template

    dto = serializar_reporte(reporte)
    dto['logo'] = obtener_logo_data_uri()
    return render_template('reportes/reporte_pdf.html', dto=dto)


def generar_pdf_reporte(reporte):
    """
    Genera los bytes del PDF del reporte.

    Estrategia de motores:
      1. WeasyPrint: mejor soporte de CSS Paged Media (usa @page, bordes,
         control de saltos de página). Requiere Pango en el servidor (Linux).
      2. xhtml2pdf: motor 100% Python (reportlab) que funciona en cualquier
         plataforma (incluido Windows sin GTK). Se usa como respaldo.

    Devuelve una tupla (bytes_pdf, nombre_del_motor_utilizado).
    """
    html = renderizar_html_reporte(reporte)

    weasyprint = _cargar_weasyprint()
    if weasyprint is not None:
        try:
            pdf = weasyprint.HTML(string=html).write_pdf()
            return pdf, 'WeasyPrint'
        except Exception:
            pass

    from xhtml2pdf import pisa

    buffer = io.BytesIO()
    resultado = pisa.CreatePDF(html, dest=buffer, encoding='utf-8')
    if resultado.err:
        raise RuntimeError('No fue posible generar el PDF del reporte.')
    return buffer.getvalue(), 'xhtml2pdf'


@lru_cache(maxsize=1)
def _cargar_weasyprint():
    """
    Importa WeasyPrint una sola vez (se cachea el resultado). Devuelve el
    módulo si está disponible o None si la plataforma no tiene sus
    dependencias nativas (GTK/Pango en Windows), en cuyo caso se usa
    xhtml2pdf como motor de respaldo.
    """
    try:
        import weasyprint
        return weasyprint
    except Exception:
        return None


def motor_pdf_disponible():
    """
    Indica qué motor de PDF está disponible actualmente en el servidor.
    """
    return 'WeasyPrint' if _cargar_weasyprint() is not None else 'xhtml2pdf'