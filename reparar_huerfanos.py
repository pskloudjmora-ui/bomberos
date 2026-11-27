# -*- coding: utf-8 -*-
"""
Repara reportes "huérfanos": filas en `reportes` que no tienen su fila
correspondiente en la tabla de subtipo (herencia JOINED). Esos reportes
producen error 500 al abrir el detalle porque SQLAlchemy no puede cargar
los atributos diferidos de la subclase.

Modos:
    python reparar_huerfanos.py             # simulacro (no cambia nada)
    python reparar_huerfanos.py --reparar   # inserta la fila vacía del
                                            # subtipo y el reporte vuelve
                                            # a ser visible (recomendado)
    python reparar_huerfanos.py --aplicar   # elimina los huérfanos

En Render: súbelo al repo y ejecútalo en el shell del servicio
(Render Dashboard -> Shell) con el mismo entorno (DATABASE_URL) de la app.
"""
import sys

from sqlalchemy import text

from app import create_app, db
import app.models as modelos
from app.models import Reporte


def main():
    aplicar = '--aplicar' in sys.argv
    reparar = '--reparar' in sys.argv
    app = create_app()

    with app.app_context():
        # Clases hijas de Reporte con identidad polimórfica propia
        subclases = [
            c for c in vars(modelos).values()
            if isinstance(c, type)
            and issubclass(c, Reporte)
            and c is not Reporte
            and c.__mapper__.polymorphic_identity not in (None, 'general')
        ]

        huerfanos = []  # (reporte_id, nro_control, identidad, tabla)
        for cls in subclases:
            tabla = cls.__table__.name
            identidad = cls.__mapper__.polymorphic_identity
            filas = db.session.execute(text(
                f'SELECT r.id, r.nro_control FROM reportes r '
                f'LEFT JOIN {tabla} s ON s.id = r.id '
                f'WHERE r.tipo_reporte = :ident AND s.id IS NULL'
            ), {'ident': identidad}).fetchall()
            for rid, nro in filas:
                huerfanos.append((rid, nro, identidad, tabla))

        if not huerfanos:
            print('No se encontraron reportes huérfanos. Todo correcto.')
            return

        print(f'{len(huerfanos)} reporte(s) huérfano(s) encontrado(s):')
        for rid, nro, ident, _tabla in huerfanos:
            print(f'  - id={rid}  nro_control={nro}  tipo={ident}')

        if not aplicar and not reparar:
            print('\nSimulacro: no se modificó nada. Use --reparar para'
                  ' reconstruir las filas de subtipo o --aplicar para borrarlos.')
            return

        if reparar:
            for rid, _nro, _ident, tabla in huerfanos:
                db.session.execute(
                    text(f'INSERT INTO {tabla} (id) VALUES (:rid)'),
                    {'rid': rid},
                )
            db.session.commit()
            print(f'\n{len(huerfanos)} reporte(s) reparado(s): se insertó la'
                  ' fila de subtipo vacía. Los datos de cabecera y las'
                  ' relaciones (personal, vehículos) se conservan; los'
                  ' parámetros específicos que nunca se guardaron quedarán vacíos.')
            return

        for rid, _nro, _ident, _tabla in huerfanos:
            rep = db.session.get(Reporte, rid)
            if rep is not None:
                db.session.delete(rep)
        db.session.commit()
        print(f'\n{len(huerfanos)} reporte(s) huérfano(s) eliminados.')


if __name__ == '__main__':
    main()
