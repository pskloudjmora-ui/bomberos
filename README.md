# bomberos

Sistema de gestión de reportes operativos del Cuerpo de Bomberos y Bomberas, Municipalidad de San Diego, Estado Carabobo.

## Generación de PDF de reportes

Cada reporte puede descargarse en PDF (tamaño Carta) desde su vista de detalle
(`/reportes/pdf/<id>`).

- **Plantilla:** `app/templates/reportes/reporte_pdf.html` (formulario oficial con
  logotipo, encabezado institucional, N° de control, secciones por tipo de servicio
  y firmas).
- **Motor dual** (`app/services/pdf_service.py`): usa **WeasyPrint** si está
  disponible (Linux: `apt install libpango-1.0-0 libpangoft2-1.0-0` para mejor
  fidelidad CSS) y cae automáticamente a **xhtml2pdf** (100% Python, sin
  dependencias nativas) en cualquier plataforma.
- **Logotipo:** se lee de `app/static/imagen/logo-bomberos.png` y se incrusta como
  Data URI base64 directamente en el HTML (se re-dimensiona a máx. 220px). No
  depende de URLs externas ni de la carpeta estática, por lo que no falla al
  renderizar. Para cambiar el logo, solo hay que reemplazar ese archivo.
- **DTO:** `serializar_reporte()` en `app/services/pdf_service.py` convierte el
  reporte ORM en un dict plano (JSON-friendly) consumido por la plantilla,
  desacoplando la base de datos del renderizador.

