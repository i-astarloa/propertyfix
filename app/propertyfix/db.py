"""Base de datos local (SQLite): incidencias y traza de cada acción de los agentes."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

from .config import DB_PATH

ESQUEMA = """
CREATE TABLE IF NOT EXISTS incidencias (
    id TEXT PRIMARY KEY,
    usuario TEXT NOT NULL,
    origen TEXT DEFAULT 'web',
    creado TEXT, actualizado TEXT,
    estado TEXT,
    descripcion TEXT,
    contacto_nombre TEXT, telefono TEXT,
    direccion TEXT, cp TEXT, municipio TEXT, franja TEXT,
    lat REAL, lon REAL, geo_fuente TEXT,
    clasificacion TEXT, decision TEXT, candidatos TEXT, propuesta TEXT, reserva TEXT,
    mensaje_agente TEXT,
    valoracion INTEGER,
    tokens_entrada INTEGER DEFAULT 0, tokens_salida INTEGER DEFAULT 0,
    llamadas_llm INTEGER DEFAULT 0, llamadas_mcp INTEGER DEFAULT 0,
    segundos_llm REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS traza (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incidencia TEXT, ts TEXT, agente TEXT, tipo TEXT,
    herramienta TEXT, permiso TEXT, detalle TEXT,
    tokens_entrada INTEGER DEFAULT 0, tokens_salida INTEGER DEFAULT 0,
    ms INTEGER DEFAULT 0, ok INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS correos_procesados (id TEXT PRIMARY KEY, usuario TEXT, ts TEXT);
"""

CAMPOS_JSON = {"clasificacion", "decision", "candidatos", "propuesta", "reserva"}


@contextmanager
def conexion() -> Iterator[sqlite3.Connection]:
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def iniciar() -> None:
    with conexion() as c:
        c.executescript(ESQUEMA)


def ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def nuevo_id() -> str:
    with conexion() as c:
        n = c.execute("SELECT COUNT(*) FROM incidencias").fetchone()[0]
    return f"INC-{n + 1:04d}"


def crear_incidencia(**campos: Any) -> str:
    iid = nuevo_id()
    campos.update(id=iid, creado=ahora(), actualizado=ahora(), estado="recibida")
    cols = ", ".join(campos)
    with conexion() as c:
        c.execute(f"INSERT INTO incidencias ({cols}) VALUES ({', '.join('?' * len(campos))})", list(campos.values()))
    return iid


def actualizar(iid: str, **campos: Any) -> None:
    campos["actualizado"] = ahora()
    for k in CAMPOS_JSON & campos.keys():
        campos[k] = json.dumps(campos[k], ensure_ascii=False, default=str)
    sets = ", ".join(f"{k} = ?" for k in campos)
    with conexion() as c:
        c.execute(f"UPDATE incidencias SET {sets} WHERE id = ?", [*campos.values(), iid])


def _fila(r: sqlite3.Row | None) -> dict | None:
    if r is None:
        return None
    d = dict(r)
    for k in CAMPOS_JSON:
        d[k] = json.loads(d[k]) if d.get(k) else None
    return d


def incidencia(iid: str) -> dict | None:
    with conexion() as c:
        return _fila(c.execute("SELECT * FROM incidencias WHERE id = ?", (iid,)).fetchone())


def incidencias(usuario: str | None = None) -> list[dict]:
    with conexion() as c:
        if usuario:
            filas = c.execute("SELECT * FROM incidencias WHERE usuario = ? ORDER BY creado DESC", (usuario,)).fetchall()
        else:
            filas = c.execute("SELECT * FROM incidencias ORDER BY creado DESC").fetchall()
    return [_fila(f) for f in filas]


def registrar_traza(incidencia_id: str, agente: str, tipo: str, herramienta: str = "", permiso: str = "",
                    detalle: str = "", tokens_entrada: int = 0, tokens_salida: int = 0, ms: int = 0, ok: bool = True) -> None:
    with conexion() as c:
        c.execute("INSERT INTO traza (incidencia, ts, agente, tipo, herramienta, permiso, detalle, tokens_entrada, "
                  "tokens_salida, ms, ok) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (incidencia_id, ahora(), agente, tipo, herramienta, permiso, detalle[:2000],
                   tokens_entrada, tokens_salida, ms, int(ok)))
        if tipo == "llm":
            c.execute("UPDATE incidencias SET tokens_entrada = tokens_entrada + ?, tokens_salida = tokens_salida + ?, "
                      "llamadas_llm = llamadas_llm + 1, segundos_llm = segundos_llm + ? WHERE id = ?",
                      (tokens_entrada, tokens_salida, ms / 1000, incidencia_id))
        elif tipo == "mcp":
            c.execute("UPDATE incidencias SET llamadas_mcp = llamadas_mcp + 1 WHERE id = ?", (incidencia_id,))


def traza(incidencia_id: str) -> list[dict]:
    with conexion() as c:
        return [dict(r) for r in c.execute("SELECT * FROM traza WHERE incidencia = ? ORDER BY id", (incidencia_id,))]


def borrar_traza(incidencia_id: str) -> None:
    """Solo para evaluaciones (ids EVAL-…): limpia la traza antes de repetir un caso."""
    if not incidencia_id.startswith("EVAL-"):
        raise ValueError("Solo se puede borrar la traza de evaluaciones")
    with conexion() as c:
        c.execute("DELETE FROM traza WHERE incidencia = ?", (incidencia_id,))


def traza_global() -> list[dict]:
    with conexion() as c:
        return [dict(r) for r in c.execute("SELECT * FROM traza ORDER BY id")]


def correo_procesado(eid: str) -> bool:
    with conexion() as c:
        return c.execute("SELECT 1 FROM correos_procesados WHERE id = ?", (eid,)).fetchone() is not None


def marcar_correo(eid: str, usuario: str) -> None:
    with conexion() as c:
        c.execute("INSERT OR IGNORE INTO correos_procesados VALUES (?,?,?)", (eid, usuario, ahora()))
