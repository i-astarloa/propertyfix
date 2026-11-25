"""Servidor MCP de Google Drive: crea el documento con el presupuesto (Google Docs) y su PDF."""
from __future__ import annotations

import io
import uuid
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from mcp_servers.comun import modo, servicio
from propertyfix.config import DOCS_DIR

mcp = FastMCP("drive")


@mcp.tool()
def crear_documento(titulo: str, html: str) -> dict:
    """Crea un documento de Google Docs a partir de HTML y descarga su versión PDF.
    Permiso: ESCRITURA (solo ficheros creados por la propia app, alcance drive.file).

    Args:
        titulo: título del documento.
        html: contenido del documento en HTML.
    """
    nombre_local = f"{uuid.uuid4().hex[:8]}"
    if modo() == "real":
        from googleapiclient.http import MediaIoBaseUpload

        drive = servicio("drive", "v3")
        media = MediaIoBaseUpload(io.BytesIO(html.encode("utf-8")), mimetype="text/html", resumable=False)
        meta = {"name": titulo, "mimeType": "application/vnd.google-apps.document"}
        f = drive.files().create(body=meta, media_body=media, fields="id, webViewLink").execute()
        pdf = drive.files().export(fileId=f["id"], mimeType="application/pdf").execute()
        ruta_pdf = DOCS_DIR / f"{_seguro(titulo)}_{nombre_local}.pdf"
        ruta_pdf.write_bytes(pdf)
        return {"ok": True, "modo": "real", "id": f["id"], "enlace": f["webViewLink"], "pdf": str(ruta_pdf)}

    ruta = DOCS_DIR / f"{_seguro(titulo)}_{nombre_local}.html"
    ruta.write_text(html, encoding="utf-8")
    return {"ok": True, "modo": "simulado", "id": nombre_local, "enlace": f"/documentos/{ruta.name}", "pdf": str(ruta)}


def _seguro(t: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in t)[:50]


if __name__ == "__main__":
    mcp.run()
