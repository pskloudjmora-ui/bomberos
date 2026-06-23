import os
from app import create_app, db
from app.models import Usuario, Vehiculo

# Crear la instancia de la aplicación Flask
app = create_app()

@app.shell_context_processor
def make_shell_context():
    """
    Agrega elementos útiles al shell de Flask: 'flask shell'.
    """
    return {'db': db, 'Usuario': Usuario, 'Vehiculo': Vehiculo}

if __name__ == '__main__':
    # Ejecutar la aplicación en modo desarrollo
    app.run(host='0.0.0.0', port=5000, debug=True)
