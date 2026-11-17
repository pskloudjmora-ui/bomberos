from functools import wraps

from flask import flash, redirect, request, url_for
from flask_login import current_user


def solo_administrador(vista):
    """Restringe una vista a usuarios con rol de administrador."""
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.path))
        if not current_user.es_admin:
            flash('Acceso denegado: Se requieren permisos de administrador.', 'danger')
            return redirect(url_for('main.index'))
        return vista(*args, **kwargs)

    return envoltura
