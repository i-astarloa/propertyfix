"""Aplicación web (FastAPI): login, panel, incidencias, aprobaciones, proveedores y analítica."""
from __future__ import annotations

import secrets
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import buzon, db, dominio
from .agents import orquestador
from .config import (DOCS_DIR, OLLAMA_MODEL, RUNTIME_DIR, UMBRAL_GASTO_REFORZADO, google_disponible)

BASE = Path(__file__).parent
EN_PROCESO = {"recibida", "clasificando", "buscando_proveedor", "reservando"}


def _clave_sesion() -> str:
    ruta = RUNTIME_DIR / "clave_sesion.txt"
    if not ruta.exists():
        ruta.write_text(secrets.token_hex(32), encoding="utf-8")
    return ruta.read_text(encoding="utf-8").strip()


app = FastAPI(title="PropertyFix")
app.add_middleware(SessionMiddleware, secret_key=_clave_sesion(), same_site="lax")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
plantillas = Jinja2Templates(directory=BASE / "templates")


def _fecha(iso: str | None, formato: str = "%d/%m %H:%M") -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso.replace("Z", "")).strftime(formato)
    except ValueError:
        return iso


def _fecha_larga(iso: str | None) -> str:
    if not iso:
        return ""
    d = datetime.fromisoformat(iso)
    meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    return f"{dominio.DIAS[d.weekday()].capitalize()} {d.day} {meses[d.month - 1]} · {d:%H:%M}"


plantillas.env.filters["fecha"] = _fecha
plantillas.env.filters["fecha_larga"] = _fecha_larga
plantillas.env.filters["eur"] = lambda x: f"{(x or 0):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
plantillas.env.globals["ESTADOS"] = orquestador.ESTADOS
plantillas.env.globals["CATALOGO"] = dominio.catalogo


@app.on_event("startup")
def _inicio() -> None:
    db.iniciar()
    buzon.arrancar()


def _usuario(request: Request) -> dict | None:
    return request.session.get("usuario")


def _render(request: Request, plantilla: str, **ctx) -> HTMLResponse:
    ok, texto = orquestador.estado_modelo()
    ctx.update(request=request, usuario=_usuario(request), modelo_ok=ok, modelo_texto=texto,
               google=google_disponible(), modelo=OLLAMA_MODEL)
    if ctx["usuario"]:
        incs = db.incidencias(ctx["usuario"]["email"])
        ctx["n_pendientes"] = sum(1 for i in incs if i["estado"] == "pendiente_aprobacion")
    return plantillas.TemplateResponse(request, plantilla, ctx)


def _requiere_login(request: Request):
    return None if _usuario(request) else RedirectResponse("/login", status_code=303)


def _propia(request: Request, iid: str) -> dict | None:
    inc = db.incidencia(iid)
    u = _usuario(request)
    return inc if inc and u and inc["usuario"] == u["email"] else None


# ---------------------------------------------------------------- acceso
@app.get("/login", response_class=HTMLResponse)
def login(request: Request, error: str = ""):
    return _render(request, "login.html", error=error)


@app.post("/login/demo")
def login_demo(request: Request, email: str = Form(...), nombre: str = Form("")):
    email = email.strip().lower()
    if "@" not in email:
        return RedirectResponse("/login?error=Introduce+un+email+válido", status_code=303)
    request.session["usuario"] = {"email": email, "nombre": nombre.strip() or email.split("@")[0], "modo": "demo"}
    buzon.usuarios_activos.add(email)
    return RedirectResponse("/", status_code=303)


@app.get("/auth/google")
def auth_google(request: Request):
    from . import google_auth
    url, state, verificador = google_auth.url_autorizacion()
    request.session["oauth"] = {"state": state, "verificador": verificador}
    return RedirectResponse(url, status_code=303)


@app.get("/auth/callback")
def auth_callback(request: Request):
    from . import google_auth
    datos = request.session.pop("oauth", None)
    if not datos or request.query_params.get("error"):
        return RedirectResponse("/login?error=No+se+completó+el+inicio+de+sesión+con+Google", status_code=303)
    try:
        info = google_auth.completar(str(request.url), datos["state"], datos["verificador"])
    except Exception as e:
        return RedirectResponse(f"/login?error=Error+de+Google:+{type(e).__name__}", status_code=303)
    request.session["usuario"] = {**info, "modo": "google"}
    buzon.usuarios_activos.add(info["email"])
    return RedirectResponse("/", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


# ---------------------------------------------------------------- panel
@app.get("/", response_class=HTMLResponse)
def panel(request: Request):
    if r := _requiere_login(request):
        return r
    incs = db.incidencias(_usuario(request)["email"])
    c = Counter(i["estado"] for i in incs)
    abiertas = [i for i in incs if i["estado"] not in ("cerrada", "rechazada")]
    reservadas = [i for i in incs if i.get("propuesta") and i["estado"] in ("reservada", "cerrada")]
    gasto = sum(i["propuesta"]["presupuesto"]["total"] for i in reservadas)
    urgentes = sum(1 for i in abiertas if (i.get("clasificacion") or {}).get("urgencia") in ("alta", "urgente"))
    proximas = sorted([i for i in incs if i["estado"] == "reservada"], key=lambda i: i["propuesta"]["cita"]["inicio"])
    return _render(request, "panel.html", incidencias=incs, conteo=c, n_abiertas=len(abiertas), urgentes=urgentes,
                   gasto=gasto, proximas=proximas[:4], buzon=buzon.estado)


@app.get("/incidencias/nueva", response_class=HTMLResponse)
def nueva(request: Request):
    if r := _requiere_login(request):
        return r
    return _render(request, "nueva.html")


@app.post("/incidencias")
def crear(request: Request, descripcion: str = Form(...), contacto_nombre: str = Form(""), telefono: str = Form(""),
          direccion: str = Form(""), cp: str = Form(""), municipio: str = Form(""), franja: str = Form("completa")):
    if r := _requiere_login(request):
        return r
    iid = db.crear_incidencia(usuario=_usuario(request)["email"], origen="web", descripcion=descripcion.strip()[:3000],
                              contacto_nombre=contacto_nombre.strip(), telefono=telefono.strip(),
                              direccion=direccion.strip(), cp=cp.strip(), municipio=municipio.strip(), franja=franja)
    orquestador.lanzar(orquestador.fase_analisis, iid)
    return RedirectResponse(f"/incidencias/{iid}", status_code=303)


@app.get("/incidencias/{iid}", response_class=HTMLResponse)
def detalle(request: Request, iid: str):
    if r := _requiere_login(request):
        return r
    inc = _propia(request, iid)
    if not inc:
        return RedirectResponse("/", status_code=303)
    return _render(request, "detalle.html", **_ctx_detalle(inc))


@app.get("/incidencias/{iid}/fragmento", response_class=HTMLResponse)
def fragmento(request: Request, iid: str):
    inc = _propia(request, iid)
    if not inc:
        return HTMLResponse("", status_code=404)
    return _render(request, "_detalle_cuerpo.html", **_ctx_detalle(inc))


def _ctx_detalle(inc: dict) -> dict:
    traza = db.traza(inc["id"])
    procesando = inc["estado"] in EN_PROCESO or orquestador.en_curso(inc["id"])
    return {"inc": inc, "traza": traza, "procesando": procesando, "umbral": UMBRAL_GASTO_REFORZADO,
            "tokens_total": (inc["tokens_entrada"] or 0) + (inc["tokens_salida"] or 0)}


@app.post("/incidencias/{iid}/aprobar")
def aprobar(request: Request, iid: str, confirmacion: str = Form("")):
    inc = _propia(request, iid)
    if inc and inc["estado"] == "pendiente_aprobacion":
        if inc["propuesta"].get("aprobacion_reforzada") and confirmacion != "si":
            return RedirectResponse(f"/incidencias/{iid}?aviso=confirmacion", status_code=303)
        orquestador.lanzar(orquestador.fase_reserva, iid)
    return RedirectResponse(f"/incidencias/{iid}", status_code=303)


@app.post("/incidencias/{iid}/cambiar")
def cambiar(request: Request, iid: str, proveedor_id: str = Form(...)):
    inc = _propia(request, iid)
    if inc and inc["estado"] == "pendiente_aprobacion" and any(c["proveedor_id"] == proveedor_id for c in inc["candidatos"]):
        async def _f(i: str) -> None:
            await orquestador.fase_cambio_proveedor(i, proveedor_id)
        db.actualizar(iid, mensaje_agente="Recalculando la cita con el proveedor elegido…")
        orquestador.lanzar(_f, iid)
    return RedirectResponse(f"/incidencias/{iid}", status_code=303)


@app.post("/incidencias/{iid}/rechazar")
def rechazar(request: Request, iid: str):
    inc = _propia(request, iid)
    if inc and inc["estado"] in ("pendiente_aprobacion", "escalada", "necesita_info"):
        db.actualizar(iid, estado="rechazada", mensaje_agente="Propuesta rechazada por el gestor.")
        db.registrar_traza(iid, "gestor", "decision", detalle="El gestor rechaza la propuesta")
        orquestador.lanzar(orquestador.fase_rechazo, iid)
    return RedirectResponse(f"/incidencias/{iid}", status_code=303)


@app.post("/incidencias/{iid}/completar")
def completar(request: Request, iid: str, aclaracion: str = Form(""), direccion: str = Form(""), cp: str = Form(""),
              municipio: str = Form("")):
    inc = _propia(request, iid)
    if inc and inc["estado"] in ("necesita_info", "escalada"):
        cambios: dict = {}
        if aclaracion.strip():
            cambios["descripcion"] = f"{inc['descripcion']}\n\nAclaración del gestor: {aclaracion.strip()[:1000]}"
        for k, v in (("direccion", direccion), ("cp", cp), ("municipio", municipio)):
            if v.strip():
                cambios[k] = v.strip()
                cambios["lat"] = None
        db.actualizar(iid, **cambios, estado="recibida", mensaje_agente="Información añadida. Reanalizando…")
        db.registrar_traza(iid, "gestor", "decision", detalle="El gestor completa la información y relanza el análisis")
        orquestador.lanzar(orquestador.fase_analisis, iid)
    return RedirectResponse(f"/incidencias/{iid}", status_code=303)


@app.post("/incidencias/{iid}/cerrar")
def cerrar(request: Request, iid: str, valoracion: int = Form(5)):
    inc = _propia(request, iid)
    if inc and inc["estado"] == "reservada":
        db.actualizar(iid, estado="cerrada", valoracion=max(1, min(5, valoracion)),
                      mensaje_agente="Reparación completada y archivada en el historial.")
        db.registrar_traza(iid, "gestor", "decision", detalle=f"Cierre confirmado. Valoración {valoracion}/5")
        orquestador.lanzar(orquestador.fase_cierre, iid)
    return RedirectResponse(f"/incidencias/{iid}", status_code=303)


# ---------------------------------------------------------------- otras vistas
@app.get("/aprobaciones", response_class=HTMLResponse)
def aprobaciones(request: Request):
    if r := _requiere_login(request):
        return r
    incs = [i for i in db.incidencias(_usuario(request)["email"]) if i["estado"] in ("pendiente_aprobacion", "escalada", "necesita_info")]
    return _render(request, "aprobaciones.html", incidencias=incs)


@app.get("/proveedores", response_class=HTMLResponse)
def directorio(request: Request):
    if r := _requiere_login(request):
        return r
    return _render(request, "proveedores.html", proveedores=dominio.proveedores())


@app.get("/analitica", response_class=HTMLResponse)
def analitica(request: Request):
    if r := _requiere_login(request):
        return r
    incs = db.incidencias(_usuario(request)["email"])
    ids = {i["id"] for i in incs}
    traza = [t for t in db.traza_global() if t["incidencia"] in ids]
    por_agente: dict[str, dict] = defaultdict(lambda: {"llamadas": 0, "entrada": 0, "salida": 0, "ms": 0})
    por_herramienta: dict[str, dict] = defaultdict(lambda: {"llamadas": 0, "fallos": 0, "ms": 0})
    for t in traza:
        if t["tipo"] == "llm":
            a = por_agente[t["agente"]]
            a["llamadas"] += 1
            a["entrada"] += t["tokens_entrada"]
            a["salida"] += t["tokens_salida"]
            a["ms"] += t["ms"]
        elif t["tipo"] == "mcp":
            h = por_herramienta[t["herramienta"]]
            h["llamadas"] += 1
            h["fallos"] += 0 if t["ok"] else 1
            h["ms"] += t["ms"]
    procesadas = [i for i in incs if i["llamadas_llm"]]
    n = len(procesadas) or 1
    medias = {"entrada": sum(i["tokens_entrada"] for i in procesadas) / n,
              "salida": sum(i["tokens_salida"] for i in procesadas) / n,
              "llm_s": sum(i["segundos_llm"] for i in procesadas) / n,
              "mcp": sum(i["llamadas_mcp"] for i in procesadas) / n}
    reservadas = [i for i in incs if i.get("propuesta") and i["estado"] in ("reservada", "cerrada")]
    por_tipo: dict[str, dict] = defaultdict(lambda: {"n": 0, "gasto": 0.0})
    por_prov: dict[str, dict] = defaultdict(lambda: {"n": 0, "gasto": 0.0, "valoraciones": []})
    for i in reservadas:
        t = i["clasificacion"]["tipo_nombre"]
        por_tipo[t]["n"] += 1
        por_tipo[t]["gasto"] += i["propuesta"]["presupuesto"]["total"]
        p = por_prov[i["propuesta"]["proveedor"]["nombre"]]
        p["n"] += 1
        p["gasto"] += i["propuesta"]["presupuesto"]["total"]
        if i.get("valoracion"):
            p["valoraciones"].append(i["valoracion"])
    desvios = sum(1 for i in incs if i.get("propuesta") and i["propuesta"].get("ranking", 1) != 1)
    return _render(request, "analitica.html", por_agente=dict(por_agente), por_herramienta=dict(por_herramienta),
                   medias=medias, n_procesadas=len(procesadas), por_tipo=dict(por_tipo), por_prov=dict(por_prov),
                   desvios=desvios, n_propuestas=sum(1 for i in incs if i.get("propuesta")), incidencias=procesadas)


@app.get("/demo/google", response_class=HTMLResponse)
def demo_google(request: Request):
    """Bandeja simulada: lo que la app habría hecho en Gmail, Calendar, Drive y Sheets en modo demo."""
    if r := _requiere_login(request):
        return r
    from mcp_servers import comun
    u = _usuario(request)["email"]
    ctx = {"enviados": list(reversed(comun.leer_mock("gmail_enviados", [], u))),
           "entrada": list(reversed(comun.leer_mock("gmail_entrada", [], u))),
           "eventos": sorted(comun.leer_mock("calendar_eventos", [], u) or [], key=lambda e: e["inicio"]),
           "hoja": comun.leer_mock("sheets_registro", [], u), "buzon": buzon.estado}
    return _render(request, "demo_google.html", **ctx)


@app.post("/demo/google/email")
def demo_email(request: Request, asunto: str = Form(...), texto: str = Form(...), de: str = Form("inquilino@ejemplo.es")):
    """Simula que un inquilino envía un correo a la bandeja (para probar la tarea en bucle sin Google)."""
    if r := _requiere_login(request):
        return r
    import uuid
    from mcp_servers import comun
    u = _usuario(request)["email"]
    entrada = comun.leer_mock("gmail_entrada", [], u)
    entrada.append({"id": f"sim-in-{uuid.uuid4().hex[:8]}", "de": de, "asunto": asunto, "texto": texto,
                    "fecha": datetime.now().isoformat(timespec="seconds"), "leido": False})
    comun.guardar_mock("gmail_entrada", entrada, u)
    buzon.usuarios_activos.add(_usuario(request)["email"])
    return RedirectResponse("/demo/google?enviado=1#entrada", status_code=303)


@app.post("/buzon/reanudar")
def buzon_reanudar(request: Request):
    buzon.reanudar()
    return RedirectResponse("/", status_code=303)


@app.get("/documentos/{nombre}")
def documento(request: Request, nombre: str):
    ruta = (DOCS_DIR / nombre).resolve()
    if not _usuario(request) or ruta.parent != DOCS_DIR.resolve() or not ruta.exists():
        return HTMLResponse("No encontrado", status_code=404)
    return FileResponse(ruta)
