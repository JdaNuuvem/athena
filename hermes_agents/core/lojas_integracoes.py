"""Slots de configuracao de integracoes por loja. Bling e Shopee ja tem
mecanismo proprio e funcional (core/lojas.py: bling_id, shopee_shop_id/
tokens) — este modulo NAO duplica isso, so' espelha o status deles pra
exibicao unificada. As demais 13 integracoes nao tem client real implementado
ainda: o slot existe pra guardar credenciais/status desde ja, sem exigir
migracao de schema quando forem implementadas de verdade."""
import json
from core import get_db, run_async
from core.lojas import _log_erro

_table_ok = False

INTEGRACOES_CONFIGURAVEIS = (
    "mercado_livre", "amazon", "magalu", "woocommerce", "shopify",
    "openpix", "asaas", "mercado_pago", "stripe",
    "meta_ads", "google_ads", "tiktok_ads", "kwai_ads",
    "whatsapp_business", "telegram",
)
STATUS_VALIDOS = ("ativa", "inativa", "nao_implementada", "nao_configurada", "erro")


def _ensure_table():
    global _table_ok
    if _table_ok: return
    async def _go():
        db = await get_db()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS loja_integracoes (
                id SERIAL PRIMARY KEY,
                loja_id INT NOT NULL REFERENCES lojas(id) ON DELETE CASCADE,
                integracao VARCHAR(30) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'nao_implementada',
                credenciais JSONB DEFAULT '{}'::jsonb,
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (loja_id, integracao)
            )
        """)
    try:
        run_async(_go())
        _table_ok = True
    except Exception as e:
        _log_erro("lojas_integracoes._ensure_table", e)


def _seed(loja_id: int):
    """Garante que as 15 chaves conhecidas existam pra essa loja (idempotente)."""
    _ensure_table()
    async def _go():
        db = await get_db()
        for chave in INTEGRACOES_CONFIGURAVEIS:
            await db.execute("""
                INSERT INTO loja_integracoes (loja_id, integracao, status)
                VALUES ($1, $2, 'nao_implementada')
                ON CONFLICT (loja_id, integracao) DO NOTHING
            """, loja_id, chave)
    try: run_async(_go())
    except Exception as e: _log_erro("lojas_integracoes._seed", e)


def listar(loja_id: int) -> list:
    """Retorna as 15 integracoes configuraveis + Bling/Shopee (espelhados a
    partir das colunas ja existentes em "lojas")."""
    _seed(loja_id)
    async def _go():
        db = await get_db()
        configuraveis = await db.fetch(
            "SELECT integracao, status, credenciais FROM loja_integracoes WHERE loja_id = $1 ORDER BY integracao",
            loja_id)
        loja = await db.fetchrow("SELECT bling_id, shopee_shop_id FROM lojas WHERE id = $1", loja_id)
        resultado = [dict(r) for r in configuraveis]
        if loja:
            resultado.insert(0, {
                "integracao": "shopee", "status": "ativa" if loja["shopee_shop_id"] else "nao_configurada",
                "credenciais": {},
            })
            resultado.insert(0, {
                "integracao": "bling", "status": "ativa" if loja["bling_id"] else "nao_configurada",
                "credenciais": {},
            })
        return resultado
    try: return run_async(_go())
    except Exception as e: _log_erro("lojas_integracoes.listar", e); return []


def atualizar_status(loja_id: int, integracao: str, status: str, credenciais: dict = None) -> dict:
    if integracao not in INTEGRACOES_CONFIGURAVEIS:
        return {"error": "essa integracao nao e' configuravel por aqui (bling/shopee tem fluxo proprio)"}
    if status not in STATUS_VALIDOS:
        return {"error": f"status invalido. Use um de: {', '.join(STATUS_VALIDOS)}"}
    _seed(loja_id)
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""
            UPDATE loja_integracoes SET status = $1, credenciais = $2::jsonb, updated_at = NOW()
            WHERE loja_id = $3 AND integracao = $4
            RETURNING integracao, status
        """, status, json.dumps(credenciais or {}, ensure_ascii=False), loja_id, integracao)
        return dict(row) if row else {"error": "integracao nao encontrada"}
    try: return run_async(_go())
    except Exception as e: _log_erro("lojas_integracoes.atualizar_status", e); return {"error": str(e)}
