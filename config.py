import os
from datetime import timedelta

from dotenv import load_dotenv

# Cargar variables de entorno desde .env si existe
load_dotenv()


class Config:
    # Entorno: Render define RENDER=true; también se admite FLASK_ENV=production
    ES_PRODUCCION = bool(
        os.environ.get('RENDER')
        or os.environ.get('FLASK_ENV', '').lower() == 'production'
    )

    # La clave de sesión NO puede tener un valor por defecto en producción:
    # con una clave conocida cualquiera podría falsificar la cookie de sesión
    # y hacerse pasar por un administrador.
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        if ES_PRODUCCION:
            raise RuntimeError(
                'Falta la variable de entorno SECRET_KEY. '
                'Defínala con un valor aleatorio antes de iniciar en producción '
                '(por ejemplo: python -c "import secrets; print(secrets.token_hex(32))").'
            )
        # Solo para desarrollo local
        SECRET_KEY = 'dev-only-secret-key-bomberos'

    # Intentar obtener la URL de conexión completa directamente
    DATABASE_URL = os.environ.get('DATABASE_URL') or os.environ.get('RENDER_DATABASE_URL')

    # Render y algunos servicios pueden proporcionar postgres:// en lugar de postgresql://
    if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

    # Render exige conexiones SSL con PostgreSQL remoto: forzarlo si la URL no
    # lo define. No aplica a PostgreSQL local (localhost/127.0.0.1/::1), que
    # normalmente no soporta SSL.
    if DATABASE_URL and DATABASE_URL.startswith('postgresql://') and 'sslmode' not in DATABASE_URL:
        from urllib.parse import urlparse
        host = (urlparse(DATABASE_URL).hostname or '').lower()
        if host not in ('localhost', '127.0.0.1', '::1'):
            separador = '&' if '?' in DATABASE_URL else '?'
            DATABASE_URL = f'{DATABASE_URL}{separador}sslmode=require'

    if DATABASE_URL:
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        # Si el usuario definió explícitamente variables de PostgreSQL en el entorno, las usamos
        if os.environ.get('DB_NAME') or os.environ.get('DB_USER'):
            db_user = os.environ.get('DB_USER', 'postgres')
            db_password = os.environ.get('DB_PASSWORD', 'postgres')
            db_host = os.environ.get('DB_HOST', 'localhost')
            db_port = os.environ.get('DB_PORT', '5432')
            db_name = os.environ.get('DB_NAME', 'bomberos_db')
            SQLALCHEMY_DATABASE_URI = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
        else:
            # Fallback seguro por defecto para desarrollo local sin configurar nada: SQLite
            basedir = os.path.abspath(os.path.dirname(__file__))
            SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(basedir, "bomberos.db")}'

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Evita conexiones muertas en PostgreSQL (Render corta conexiones inactivas)
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True, 'pool_recycle': 280}

    # Flask-Login config
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = ES_PRODUCCION

    # Cookies de sesión endurecidas
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = ES_PRODUCCION
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # Los usuarios de prueba (admin/admin123) solo se crean en desarrollo.
    SEED_DEMO_USERS = not ES_PRODUCCION and os.environ.get('SEED_DEMO_USERS', '1') != '0'

    # CSRF: Flask-WTF lo valida en todos los POST. Se mantiene activo siempre.
    WTF_CSRF_TIME_LIMIT = None
