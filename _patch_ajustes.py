# -*- coding: utf-8 -*-
"""Ajustes: correlativo con año visible, renombres, campos condicionales arbol caido,
tala arbol/escombro, Ofidios, rescate ascensor/inmueble, Glasgow APH traslado,
'Tipo de Instalacion -> Otro' en piscinas/lluvias."""
import re, io, sys

def patch(path, pairs):
    s = io.open(path, encoding='utf-8').read()
    orig = s
    for old, new in pairs:
        if old not in s:
            print('  !! NO ENCONTRADO en %s: %r' % (path, old[:70]))
            continue
        s = s.replace(old, new, 1)
    if s != orig:
        io.open(path, 'w', encoding='utf-8', newline='').write(s)
        print('  OK', path)

def remove_fields_in_pdf_section(src, key, fields):
    start = src.index("'%s': [" % key)
    end = src.index('],', start)
    block = src[start:end]
    for f in fields:
        block2 = re.sub(r"\n[^\n]*'%s'[^\n]*" % re.escape(f), '', block)
        if block2 == block:
            print('  !! pdf field no hallado:', key, f)
        block = block2
    return src[:start] + block + src[end:]

# ============ 1. pdf_service.py ============
p = 'app/services/pdf_service.py'
s = io.open(p, encoding='utf-8').read()

# 1a. Mostrar año en nro_control del PDF
old = "'nro_control': re.sub(r'^\\d{7}-\\d{4}$', lambda m: m.group(0).split('-')[0], reporte.nro_control or ''),"
new = "'nro_control': reporte.nro_control or '',"
assert old in s, 'nro_control strip no hallado'
s = s.replace(old, new, 1)

# 1b. Renombres en NOMBRE_SERVICIO y TITULO_SECCION_2
s = s.replace("'incendio_arbol_caido': 'CONTROL DE PELIGRO POR ÁRBOL CAÍDO',",
              "'incendio_arbol_caido': 'CONTROL Y ELIMINACIÓN DE PELIGRO POR ÁRBOL CAÍDO SOBRE ESTRUCTURA O VEHÍCULO',", 1)
s = s.replace("'tala_arbol': 'REPORTE TALA DE ÁRBOL',",
              "'tala_arbol': 'DESPEJE DE VÍA POR ÁRBOL CAÍDO O ESCOMBRO',", 1)
s = s.replace("'incendio_arbol_caido': '2. DETALLE DEL ÁRBOL CAÍDO',",
              "'incendio_arbol_caido': '2. CONTROL Y ELIMINACIÓN DE PELIGRO POR ÁRBOL CAÍDO',", 1)
s = s.replace("'tala_arbol': '2. DATOS DEL ÁRBOL',",
              "'tala_arbol': '2. DATOS DEL DESPEJE',", 1)

# 1c. Quitar filas de SECCIONES (solo dentro del bloque del tipo)
for key, fields in [
    ('incendio_arbol_caido', [
        'tipo_estructura', 'presunto_punto_origen', 'porcentaje_perdida_total',
        'litros_agua_utilizados', 'hubo_propagacion', 'propagacion_donde',
        'metodos_extincion', 'poseia_equipos', 'fue_usado', 'por_quien_uso',
        'por_quien_ci', 'tipo_equipo_contra_incendio',
    ]),
    ('rescate_ascensor', ['tipo_servicio']),
    ('rescate_inmueble', ['tipo_servicio']),
]:
    s = remove_fields_in_pdf_section(s, key, fields)

# 1d. tala_arbol: agregar Tipo de Despeje como primera fila
anchor = "'tala_arbol': [\n        ('Especie', 'especie', 'plain'),"
assert anchor in s
s = s.replace(anchor,
    "'tala_arbol': [\n        ('Tipo de Despeje', 'tipo_despeje', 'plain'),\n        ('Especie', 'especie', 'plain'),", 1)

io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('OK', p)

# ============ 2. reportes.py ============
p = 'app/routes/reportes.py'
s = io.open(p, encoding='utf-8').read()

s = s.replace("'incendio_arbol_caido': 'Control de Peligro por Árbol Caído',",
              "'incendio_arbol_caido': 'Control y Eliminación de Peligro por Árbol Caído Sobre Estructura o Vehículo',", 1)
s = s.replace("'tala_arbol': 'Reporte Tala de Árbol',",
              "'tala_arbol': 'Despeje de Vía por Árbol Caído o Escombro',", 1)

# fields map rescate_ascensor / rescate_inmueble: quitar tipo_servicio
for t in ('rescate_ascensor', 'rescate_inmueble'):
    old = "'%s': [\n        'subtipo_rescate', 'tipo_servicio', 'despliegue_material_usado', 'salida_ambulancia'\n    ]," % t
    new = "'%s': [\n        'subtipo_rescate', 'despliegue_material_usado', 'salida_ambulancia'\n    ]," % t
    assert old in s, t
    s = s.replace(old, new, 1)

# fields map incendio_arbol_caido: quitar campos eliminados
old = """        'subtipo_incendio', 'arbol_afecto', 'tipo_estructura', 'lugar_desarrollo',
        'presunto_punto_origen',
        'hora_control', 'hora_extincion_total',
        'porcentaje_perdida_total',
        'litros_agua_utilizados', 'hubo_propagacion', 'propagacion_donde',
        'metodos_extincion', 'tecnicas_extincion',
        'poseia_equipos', 'fue_usado', 'por_quien_uso', 'por_quien_ci',
        'tipo_equipo_contra_incendio', 'evaluacion_preliminar',"""
new = """        'subtipo_incendio', 'arbol_afecto', 'lugar_desarrollo',
        'hora_control', 'hora_extincion_total', 'tecnicas_extincion',
        'evaluacion_preliminar',"""
assert old in s
s = s.replace(old, new, 1)

# fields map tala_arbol: agregar tipo_despeje
old = """    'tala_arbol': [
        'especie', 'tamano', 'edad', 'material_usado'
    ],"""
new = """    'tala_arbol': [
        'tipo_despeje', 'especie', 'tamano', 'edad', 'material_usado'
    ],"""
assert old in s
s = s.replace(old, new, 1)

io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('OK', p)

# ============ 3. models.py ============
p = 'app/models.py'
s = io.open(p, encoding='utf-8').read()
old = """    especie = db.Column(db.String(100), nullable=True)
    tamano = db.Column(db.String(50), nullable=True)
    edad = db.Column(db.String(50), nullable=True)
    material_usado = db.Column(db.Text, nullable=True)

    __mapper_args__ = {
        'polymorphic_identity': 'tala_arbol',"""
new = """    tipo_despeje = db.Column(db.String(20), nullable=True)  # Árbol / Escombro
    especie = db.Column(db.String(100), nullable=True)
    tamano = db.Column(db.String(50), nullable=True)
    edad = db.Column(db.String(50), nullable=True)
    material_usado = db.Column(db.Text, nullable=True)

    __mapper_args__ = {
        'polymorphic_identity': 'tala_arbol',"""
assert old in s
s = s.replace(old, new, 1)
io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('OK', p)

# ============ 4. __init__.py (migración) ============
p = 'app/__init__.py'
s = io.open(p, encoding='utf-8').read()
old = """    'reportes_aph_sin_traslado': {
        'conducta_adoptada': 'TEXT',
        'indicaciones_dejadas': 'TEXT',
    },
}"""
new = """    'reportes_aph_sin_traslado': {
        'conducta_adoptada': 'TEXT',
        'indicaciones_dejadas': 'TEXT',
    },
    'reportes_tala_arbol': {
        'tipo_despeje': 'VARCHAR(20)',
    },
}"""
assert old in s, 'init anchor'
s = s.replace(old, new, 1)
io.open(p, 'w', encoding='utf-8', newline='').write(s)
print('OK', p)

# ============ 5. etiquetas.py ============
patch('app/etiquetas.py', [
    ("'tala_arbol': 'Tala de Árbol',", "'tala_arbol': 'Despeje de Vía',"),
    ("'incendio_arbol_caido': 'Árbol Caído',", "'incendio_arbol_caido': 'Control Peligro Árbol Caído',"),
])
