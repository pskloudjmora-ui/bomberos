"""
Etiquetas legibles y colores de badge para los tipos de reporte.

La identidad polimórfica que guarda SQLAlchemy en ``tipo_reporte`` es genérica
('incendio', 'rescate_colision', 'rescate_especializado'); para mostrar o
filtrar se usa ``Reporte.tipo_especifico``, que incluye el subtipo real
('incendio_estructura', 'rescate_caida', ...).

Este módulo centraliza el texto y el color de cada tipo para que el dashboard,
el historial del bombero y la ficha de usuario muestren lo mismo.
"""

ETIQUETAS_TIPO = {
    # MATPEL
    'matpel_glp': 'MATPEL - GLP',
    'matpel_combustible': 'MATPEL - Combustible',
    'matpel_quimico': 'MATPEL - Químico',
    'matpel_otros': 'MATPEL - Gas Natural',
    'falsa_alarma': 'Falsa Alarma',
    # Atención pre-hospitalaria
    'pre_hospitalario': 'Atenc. Médica',
    'aph_traslado': 'APH - Traslado',
    'aph_no_traslado': 'APH - No Traslado',
    'aph_interhospitalario': 'APH - Interhospitalario',
    'aph_sin_traslado': 'APH - Sin Traslado',
    # Servicios especiales
    'servicio_agua': 'Serv. Especial - Agua',
    'servicio_insectos': 'Serv. Especial - Insectos',
    'servicio_animal': 'Serv. Especial - Animal',
    'servicio_achicamiento': 'Serv. Especial - Achicamiento',
    'servicio_baldeo': 'Serv. Especial - Baldeo',
    'servicio_piscinas': 'Serv. Especial - Piscinas',
    'servicio_lluvias': 'Serv. Especial - Lluvias',
    'inspeccion_insectos': 'Inspección - Insectos',
    'apertura_puerta': 'Apertura de Puerta',
    'servicio_tendido_electrico': 'Inspección y Control de Riesgo por Tendido Eléctrico Caído',
    'tala_arbol': 'Despeje de Vía',
    'guardia_seguridad': 'Guardia de Seguridad',
    # Incendios
    'incendio_estructura': 'Incendio - Estructura',
    'incendio_apoyo': 'Incendio - Apoyo',
    'incendio_electrico': 'Incendio - Eléctrico',
    'incendio_vehiculo': 'Incendio - Vehículo',
    'incendio_desechos': 'Incendio - Desechos',
    'incendio_vegetacion': 'Incendio - Vegetación',
    'incendio_arbol': 'Incendio - Árbol',
    'incendio_arbol_caido': 'Control Peligro Árbol Caído',
    # Rescates
    'rescate_colision_con_lesionado': 'Rescate - Colisión c/ Lesionado',
    'rescate_colision_sin_lesionado': 'Rescate - Colisión s/ Lesionado',
    'rescate_volcamiento_con_lesionado': 'Rescate - Volcamiento c/ Lesionado',
    'rescate_volcamiento_sin_lesionado': 'Rescate - Volcamiento s/ Lesionado',
    'rescate_ascensor': 'Rescate - Ascensor',
    'rescate_inmueble': 'Rescate - Inmueble',
    'rescate_tapiada': 'Rescate - Tapiada',
    'rescate_golpeada': 'Rescate - Golpeada',
    'rescate_caida': 'Rescate - Caída en Altura',
    'rescate_cadaver': 'Rescate de Cadáver',
    'siniestro_vial_con_lesionado': 'Siniestro Vial c/ Lesionado',
    'siniestro_vial_sin_lesionado': 'Siniestro Vial s/ Lesionado',
    'busqueda_rescate': 'Búsqueda y Rescate',
}

# Clases Tailwind del badge (fondo, borde y texto)
COLORES_TIPO = {
    'matpel': 'bg-red-500/10 border-red-500/20 text-red-400',
    'aph': 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400',
    'servicio': 'bg-blue-500/10 border-blue-500/20 text-blue-400',
    'inspeccion': 'bg-blue-500/10 border-blue-500/20 text-blue-400',
    'apertura': 'bg-cyan-500/10 border-cyan-500/20 text-cyan-400',
    'incendio': 'bg-orange-500/10 border-orange-500/20 text-orange-400',
    'rescate': 'bg-cyan-500/10 border-cyan-500/20 text-cyan-400',
    'siniestro': 'bg-red-500/10 border-red-500/20 text-red-400',
    'busqueda': 'bg-violet-500/10 border-violet-500/20 text-violet-400',
    'servicio_tendido_electrico': 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    'tala_arbol': 'bg-green-500/15 text-green-400 border-green-500/30',
    'guardia_seguridad': 'bg-sky-500/15 text-sky-400 border-sky-500/30',
}

COLOR_POR_DEFECTO = 'bg-slate-800 border-slate-700 text-slate-300'


def etiqueta_tipo(tipo):
    """Devuelve el nombre legible de un tipo de reporte (o el propio valor)."""
    if not tipo:
        return '—'
    if tipo in ETIQUETAS_TIPO:
        return ETIQUETAS_TIPO[tipo]
    return str(tipo).replace('_', ' ').title()


def color_tipo(tipo):
    """Devuelve las clases Tailwind del badge según la familia del reporte."""
    if not tipo:
        return COLOR_POR_DEFECTO
    familia = str(tipo).split('_', 1)[0]
    return COLORES_TIPO.get(familia, COLOR_POR_DEFECTO)
