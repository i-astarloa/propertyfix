"""Servidor MCP de Gmail: enviar correos (con adjunto) y leer la bandeja de entrada.

Barandilla en el propio servidor: solo se puede enviar a destinatarios de la lista blanca
(el usuario que ha iniciado sesión y la bandeja sandbox del proyecto). Aunque un agente
fuera manipulado por una inyección de prompt, el servidor rechaza cualquier otro destino.
"""
from __future__ import annotations

import base64
import mimetypes
import os
import uuid
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from mcp_servers.comun import destinatarios_permitidos, guardar_mock, leer_mock, modo, servicio, usuario

mcp = FastMCP("gmail")


@mcp.tool()
def enviar_email(para: str, asunto: str, cuerpo_html: str, adjunto_ruta: str = "") -> dict:
    """Envía un correo. Permiso: ESCRITURA EXTERNA (requiere aprobación humana previa).

    Args:
        para: dirección del destinatario (debe estar en la lista blanca).
        asunto: asunto del correo.
        cuerpo_html: cuerpo en HTML.
        adjunto_ruta: ruta local de un fichero a adjuntar (opcional).
    """
    permitidos = destinatarios_permitidos()
    if para.strip().lower() not in permitidos:
        return {"ok": False, "error": f"Destinatario bloqueado por la lista blanca: {para}"}

    msg = EmailMessage()
    msg["To"] = para
    msg["Subject"] = asunto
    # Marca legible por máquina de contenido generado con IA (AI Act, art. 50.2)
    msg["X-PropertyFix-AI-Generated"] = "true; model=" + os.getenv("OLLAMA_MODEL", "qwen2.5:3b") + "; human-approved=true"
    msg.set_content("Este correo requiere un cliente compatible con HTML.")
    msg.add_alternative(cuerpo_html, subtype="html")
    if adjunto_ruta and Path(adjunto_ruta).exists():
        p = Path(adjunto_ruta)
        tipo, _ = mimetypes.guess_type(p.name)
        principal, sub = (tipo or "application/octet-stream").split("/", 1)
        msg.add_attachment(p.read_bytes(), maintype=principal, subtype=sub, filename=p.name)

    if modo() == "real":
        msg["From"] = "me"
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        r = servicio("gmail", "v1").users().messages().send(userId="me", body={"raw": raw}).execute()
        return {"ok": True, "modo": "real", "id": r.get("id")}

    salida = leer_mock("gmail_enviados", [])
    mid = f"sim-{uuid.uuid4().hex[:10]}"
    salida.append({"id": mid, "para": para, "asunto": asunto, "cuerpo_html": cuerpo_html,
                   "adjunto": adjunto_ruta, "fecha": datetime.now().isoformat(timespec="seconds")})
    guardar_mock("gmail_enviados", salida)
    return {"ok": True, "modo": "simulado", "id": mid}


@mcp.tool()
def buscar_emails(consulta: str = "is:unread", maximo: int = 10) -> dict:
    """Busca correos en la bandeja de entrada. Permiso: LECTURA.

    Args:
        consulta: consulta con la sintaxis de búsqueda de Gmail (p. ej. 'is:unread subject:incidencia').
        maximo: número máximo de correos a devolver.
    """
    if modo() == "real":
        g = servicio("gmail", "v1").users()
        r = g.messages().list(userId="me", q=consulta, maxResults=maximo).execute()
        correos = []
        for m in r.get("messages", []):
            d = g.messages().get(userId="me", id=m["id"], format="full").execute()
            cab = {h["name"].lower(): h["value"] for h in d["payload"].get("headers", [])}
            correos.append({"id": m["id"], "de": cab.get("from", ""), "asunto": cab.get("subject", ""),
                            "fecha": cab.get("date", ""), "texto": _texto_plano(d["payload"]) or d.get("snippet", "")})
        return {"ok": True, "modo": "real", "correos": correos}

    entrada = leer_mock("gmail_entrada", [])
    no_leidos = [c for c in entrada if not c.get("leido")][:maximo]
    return {"ok": True, "modo": "simulado", "correos": no_leidos}


@mcp.tool()
def marcar_procesado(email_id: str) -> dict:
    """Marca un correo de la bandeja como procesado para no volver a leerlo. Permiso: ESCRITURA INTERNA."""
    if modo() == "real":
        # Con el permiso gmail.readonly no se pueden cambiar etiquetas: la app recuerda los ids procesados.
        return {"ok": True, "modo": "real", "nota": "registrado en la base local"}
    entrada = leer_mock("gmail_entrada", [])
    for c in entrada:
        if c["id"] == email_id:
            c["leido"] = True
    guardar_mock("gmail_entrada", entrada)
    return {"ok": True, "modo": "simulado"}


def _texto_plano(payload: dict) -> str:
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", "ignore")
    for parte in payload.get("parts", []) or []:
        t = _texto_plano(parte)
        if t:
            return t
    return ""


if __name__ == "__main__":
    mcp.run()
