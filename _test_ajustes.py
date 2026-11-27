# -*- coding: utf-8 -*-
import re
from app import create_app, db

app = create_app()
c = app.test_client()

r = c.get('/auth/login')
tok = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', r.data).group(1).decode()
r = c.post('/auth/login', data={'username': 'admin', 'password': 'admin123', 'csrf_token': tok}, follow_redirects=False)
print('login:', r.status_code, r.headers.get('Location'))

# token CSRF de sesión (reutilizable)
r = c.get('/reportes/crear/tala_arbol')
CSRF = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', r.data).group(1).decode()

CAB = {
    'csrf_token': CSRF,
    'fecha': '2026-11-27',
    'hora_aviso': '08:00:00', 'hora_salida': '08:05:00',
    'hora_llegada': '08:20:00', 'hora_regreso': '09:00:00',
    'clase_aviso': 'Ejercitación', 'receptor_aviso': 'Central 911',
    'direccion': 'Av. Principal, Caracas',
}

def post(tipo, extra):
    d = dict(CAB); d.update(extra)
    r = c.post('/reportes/crear/' + tipo, data=d, follow_redirects=False)
    loc = r.headers.get('Location') or ''
    ok = '/detalle/' in loc or '/reportes/' in loc
    print(tipo, '->', r.status_code, loc[:60])
    return r

post('tala_arbol', {'tipo_despeje': 'Árbol', 'especie': 'Samán', 'tamano': '20m', 'edad': '30', 'material_usado': 'Motosierra'})
post('tala_arbol', {'tipo_despeje': 'Escombro', 'material_usado': 'Retroexcavadora'})
post('incendio_arbol_caido', {'arbol_afecto': 'inmueble', 'lugar_desarrollo': 'Calle 1', 'hora_control': '08:30:00', 'hora_extincion_total': '09:00:00', 'evaluacion_preliminar': 'Daño leve', 'inmueble_descripcion': 'Propiedad'})
post('incendio_arbol_caido', {'arbol_afecto': 'vehiculo', 'lugar_desarrollo': 'Calle 2', 'tecnicas_extincion': 'Agua'})
post('servicio_animal', {'tipo_animal': 'Ofidios', 'raza_descripcion': 'Cascabel', 'condicion_animal': 'Atrapado / En peligro', 'destino_animal': 'Refugio'})
post('rescate_ascensor', {'subtipo_rescate': 'ascensor', 'despliegue_material_usado': 'Cuerdas'})
post('rescate_inmueble', {'subtipo_rescate': 'inmueble', 'despliegue_material_usado': 'Andamios'})
post('aph_traslado', {'causa_traslado': 'Trauma', 'centro_hospitalario': 'Hospital Central', 'signos_vitales_pa': '120/80', 'glasgow_apertura_ocular': '4', 'glasgow_respuesta_verbal': '5', 'glasgow_respuesta_motora': '6', 'glasgow_total': '15'})
post('servicio_piscinas', {'clasificacion_servicio': 'Otro', 'clasificacion_servicio_otro': 'Parque Acuático Municipal', 'litros_distribuidos': '5000', 'material_usado': 'Bombas'})
post('servicio_lluvias', {'clasificacion_servicio': 'Otro', 'clasificacion_servicio_otro': 'Monitoreo de Túneles', 'litros_distribuidos': '3000', 'material_usado': 'Bombas'})

from app.models import Reporte
with app.app_context():
    rs = Reporte.query.order_by(Reporte.id.desc()).limit(10).all()
    for r in rs:
        print(r.id, r.tipo_reporte, getattr(r, 'nro_control', ''),
              '| tipo_despeje:', getattr(r, 'tipo_despeje', '-'),
              '| clasif:', getattr(r, 'clasificacion_servicio', '-'),
              '| glasgow:', getattr(r, 'glasgow_total', '-'))
