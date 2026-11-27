# -*- coding: utf-8 -*-
"""Registro de actividades del sistema (auditoría para soporte/admin)."""
from flask_login import current_user

from app import db
from app.models import LogActividad


def registrar_log(accion, detalle=None):
    """
    Agrega un registro de actividad a la sesión actual.
    No hace commit: se confirma junto con la transacción principal.
    En acciones sin otra escritura, llamar a db.session.commit() después.
    """
    try:
        autenticado = current_user.is_authenticated
        db.session.add(LogActividad(
            usuario_id=current_user.id if autenticado else None,
            username=current_user.username if autenticado else None,
            accion=accion,
            detalle=detalle,
        ))
    except Exception:
        # El registro de auditoría nunca debe romper la operación principal.
        pass
