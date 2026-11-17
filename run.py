import os

from app import app, db
from app.models import Usuario, Vehiculo


@app.shell_context_processor
def make_shell_context():
    """
    Agrega elementos útiles al shell de Flask: 'flask shell'.
    """
    return {'db': db, 'Usuario': Usuario, 'Vehiculo': Vehiculo}


if __name__ == '__main__':
    # En desarrollo se puede activar el depurador con FLASK_DEBUG=1.
    # Nunca debe quedar activo por defecto: el depurador permite ejecutar
    # código arbitrario desde el navegador.
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=debug)
