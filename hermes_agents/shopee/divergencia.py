"""Divergencia de Saldo — Athena x Shopee. Mesmo principio do
core/i9logic.py: guarda so' o saldo externo bruto no snapshot (nunca o
saldo Athena, que muda a cada venda — comparacao e' sempre calculada ao
vivo na leitura, ver listar_divergencias em divergencia.py parte 2)."""
import sys, threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime
from core import get_db, run_async, log
from core.lojas import obter as obter_loja
from .products import sync_all_items

AGENT = "Shopee Divergencia"

FRESCOR_MAXIMO_MINUTOS = 30  # mesmo valor do i9Logic — snapshot mais velho que isso dispara nova coleta

_coleta_em_andamento = set()  # loja_id -> coleta rodando agora, evita disparo duplicado
_coleta_erro_recente = {}  # loja_id -> mensagem de erro da ultima tentativa
_coleta_lock = threading.Lock()


def _ensure_tables():
    async def _go():
        db = await get_db()
        await db.execute("""CREATE TABLE IF NOT EXISTS shopee_estoque_snapshot (
            id SERIAL PRIMARY KEY,
            sku VARCHAR(50) NOT NULL,
            loja_id INT NOT NULL REFERENCES lojas(id),
            item_id_shopee VARCHAR(100),
            qtd_shopee DECIMAL(12,3),
            data_coleta TIMESTAMP DEFAULT NOW(),
            revisado BOOLEAN DEFAULT FALSE,
            UNIQUE(sku, loja_id, data_coleta)
        )""")
    try:
        run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro ao criar tabela shopee_estoque_snapshot: {e}")

_ensure_tables()


def executar_coleta_loja(loja_id: int) -> dict:
    """Chama sync_all_items(loja_id) e grava um snapshot por sku com o
    saldo Shopee bruto. Item com sku == str(item_id) (fallback da propria
    Shopee quando nao ha' item_sku real) ainda e' gravado — o pareamento
    com o saldo Athena na leitura (listar_divergencias) e' quem trata a
    ausencia de produto correspondente, nao a coleta."""
    inicio_corrida = datetime.now()
    try:
        itens = sync_all_items(loja_id)
    except Exception as e:
        log(AGENT, f"Erro ao sincronizar itens da loja {loja_id}: {e}")
        return {"erro": str(e)}
    async def _go():
        db = await get_db()
        gravados, erros = 0, 0
        for item in itens:
            try:
                await db.fetchrow("""
                    INSERT INTO shopee_estoque_snapshot (sku, loja_id, item_id_shopee, qtd_shopee, data_coleta)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (sku, loja_id, data_coleta) DO UPDATE SET qtd_shopee = $4
                    RETURNING id
                """, item["sku"], loja_id, str(item["item_id"]), item.get("stock", 0), inicio_corrida)
                gravados += 1
            except Exception:
                erros += 1
        return gravados, erros
    try:
        gravados, erros = run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro ao gravar snapshot da loja {loja_id}: {e}")
        return {"erro": str(e)}
    return {"ok": True, "loja_id": loja_id, "itens": len(itens), "gravados": gravados, "erros": erros, "data_coleta": inicio_corrida}


def snapshot_mais_recente(loja_id: int):
    """(data_coleta, itens) da corrida mais recente da loja. (None, []) se
    essa loja nunca foi coletada. Identico em forma a
    core.i9logic.snapshot_mais_recente."""
    async def _go():
        db = await get_db()
        data_coleta = await db.fetchval(
            "SELECT MAX(data_coleta) FROM shopee_estoque_snapshot WHERE loja_id=$1", loja_id)
        if data_coleta is None:
            return None, []
        rows = await db.fetch(
            "SELECT id, sku, item_id_shopee, qtd_shopee FROM shopee_estoque_snapshot "
            "WHERE loja_id=$1 AND data_coleta=$2", loja_id, data_coleta)
        return data_coleta, [dict(r) for r in rows]
    try:
        return run_async(_go())
    except Exception:
        return None, []


def _coleta_em_background(loja_id: int):
    """Roda a coleta completa fora do request. Sempre libera o lock ao
    final, mesmo em erro — senao a loja fica presa em 'processando'."""
    try:
        executar_coleta_loja(loja_id)
        _coleta_erro_recente.pop(loja_id, None)
    except Exception as e:
        _coleta_erro_recente[loja_id] = str(e)
        log(AGENT, f"Erro na coleta em background da loja {loja_id}: {e}")
    finally:
        with _coleta_lock:
            _coleta_em_andamento.discard(loja_id)


def disparar_coleta_se_necessario(loja_id: int, data_coleta) -> bool:
    """Dispara coleta em background se nao houver uma rodando e o snapshot
    estiver ausente ou mais velho que FRESCOR_MAXIMO_MINUTOS. Retorna True
    se a loja ficou (ou ja estava) em processamento. Identico em forma a
    core.i9logic._disparar_coleta_se_necessario."""
    precisa_coletar = data_coleta is None or (
        (datetime.now() - data_coleta).total_seconds() / 60 > FRESCOR_MAXIMO_MINUTOS)
    with _coleta_lock:
        ja_rodando = loja_id in _coleta_em_andamento
        deve_iniciar = precisa_coletar and not ja_rodando
        if deve_iniciar:
            _coleta_em_andamento.add(loja_id)
    if deve_iniciar:
        threading.Thread(target=_coleta_em_background, args=(loja_id,), daemon=True).start()
    return ja_rodando or deve_iniciar
