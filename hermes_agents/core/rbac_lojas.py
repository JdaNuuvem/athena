"""RBAC por loja (Fase 4, modo suave) — restringe visao de dados por loja
SO' quando o usuario tem pelo menos um vinculo ativo em loja_responsaveis.
Sem vinculo = sem restricao (comportamento identico ao de antes desta fase).
Nunca bloqueia com 403 por falta de vinculo — filtra, no maximo."""
from core import get_db, run_async
from core.lojas import _log_erro


def lojas_permitidas(user_id) -> list:
    """None = sem restricao (usuario sem vinculo, ou token master/sem
    user_id). Lista = ids das lojas com vinculo ATIVO (data_fim nulo ou no
    futuro) — usuario so' deve ver dado dessas lojas quando nenhum filtro
    especifico de loja for pedido."""
    if not user_id:
        return None
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT DISTINCT loja_id FROM loja_responsaveis
            WHERE usuario_id = $1 AND (data_fim IS NULL OR data_fim >= CURRENT_DATE)
        """, user_id)
        return [r["loja_id"] for r in rows]
    try:
        ids = run_async(_go())
    except Exception as e:
        _log_erro("lojas_permitidas", e)
        return None
    return ids if ids else None
