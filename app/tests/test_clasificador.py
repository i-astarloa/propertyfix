"""Tests del clasificador v2 con el modelo simulado (no necesitan Ollama)."""
import pytest

from propertyfix import db, dominio, llm
from propertyfix.agents import clasificador as cl


def _catalogo():
    return {t: {"nombre": c["nombre"], "trabajos": {k: v["descripcion"] for k, v in c["trabajos"].items()}}
            for t, c in dominio.catalogo().items()}


@pytest.fixture
def modelo(monkeypatch):
    """Permite fijar qué responde el «modelo» en cada paso."""
    respuestas = {}

    def falso(iid, agente, sistema, usuario, esquema, max_salida=400):
        paso = "trabajo" if "trabajo_id" in esquema["properties"] else "tipo"
        datos = respuestas.get(paso)
        if datos is None:
            return llm.RespuestaLLM(ok=False, error="sin respuesta")
        return llm.RespuestaLLM(datos=datos, tokens_entrada=100, tokens_salida=10)

    monkeypatch.setattr(llm, "chat_json", falso)
    db.iniciar()
    return respuestas


def _tipo(t, urg="media"):
    return {"tipo": t, "urgencia": urg, "resumen": "x", "datos_faltantes": [], "posible_inyeccion": False}


def test_verificador_corrige_lavavajillas_clasificado_como_pintura(modelo):
    modelo["tipo"] = _tipo("pintura")
    modelo["trabajo"] = {"trabajo_id": "pintar_habitacion"}
    c = cl.clasificar_texto("T1", "Se ha roto el lavavajillas y suelta agua", _catalogo())
    assert c["trabajo_id"] == "lavavajillas"
    assert c["fuente"] == "verificador (palabras clave)"
    assert c["urgencia"] == "alta"  # «suelta agua» sube la urgencia


def test_modelo_acierta_y_confianza_alta(modelo):
    modelo["tipo"] = _tipo("fontaneria")
    modelo["trabajo"] = {"trabajo_id": "atasco_inodoro"}
    c = cl.clasificar_texto("T2", "Se me ha atascado el retrete", _catalogo())
    assert c["trabajo_id"] == "atasco_inodoro" and c["confianza"] >= 0.9


def test_fuera_de_ambito(modelo):
    modelo["tipo"] = _tipo("no_es_averia", "baja")
    c = cl.clasificar_texto("T3", "¿Me recomendáis un restaurante?", _catalogo())
    assert c["tipo"] == "no_es_averia" and c["trabajo_id"] is None


def test_no_es_averia_pero_nombra_objeto_claro(modelo):
    modelo["tipo"] = _tipo("no_es_averia", "baja")
    c = cl.clasificar_texto("T4", "La persiana del salón está rota", _catalogo())
    assert c["trabajo_id"] == "ventana_persiana"


def test_sin_modelo_usa_palabras_clave(modelo):
    c = cl.clasificar_texto("T5", "La nevera no enfría", _catalogo())
    assert c["trabajo_id"] == "frigorifico" and c["fuente"] == "reglas (respaldo)"


def test_sin_modelo_y_sin_pistas_pide_informacion(modelo):
    c = cl.clasificar_texto("T6", "Se ha roto una cosa en casa", _catalogo())
    assert c["tipo"] is None and c["datos_faltantes"]


def test_inundacion_es_urgente():
    assert cl.urgencia_por_reglas("Se está inundando la cocina") == "urgente"
