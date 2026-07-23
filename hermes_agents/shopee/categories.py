"""
Shopee Categories — tree cache and sync.
"""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core import log, run_async, get_db
from .auth import _request, AGENT

AGENT_CAT = "AG-03 | Shopee Categories"

_categorias_table_ok = False


def get_category(loja_id: int = None) -> dict:
    """Arvore completa de categorias da Shopee (raramente muda — cacheada em shopee_categorias)."""
    return _request("product/get_category", {}, loja_id=loja_id)


def get_attribute_tree(category_id: int, loja_id: int = None) -> dict:
    """Atributos (obrigatorios e opcionais) de uma categoria especifica.
    ponytail: category_id_list e' uma string simples/CSV (ex: "400358"), NAO um array
    JSON — validado ao vivo contra o sandbox (Shopee tentava fazer parse como uint e falhava com "[400358]")."""
    return _request("product/get_attribute_tree", {
        "category_id_list": str(category_id),
    }, loja_id=loja_id)


def get_brand_list(category_id: int, offset: int = 0, page_size: int = 50, loja_id: int = None) -> dict:
    """Marcas cadastradas na Shopee para uma categoria (algumas categorias exigem marca)."""
    return _request("product/get_brand_list", {
        "category_id": category_id, "offset": offset, "page_size": page_size, "status": 1,
    }, loja_id=loja_id)


def _ensure_categorias_table():
    global _categorias_table_ok
    if _categorias_table_ok:
        return
    async def _go():
        db = await get_db()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS shopee_categorias (
                category_id BIGINT PRIMARY KEY,
                parent_category_id BIGINT DEFAULT 0,
                nome VARCHAR(200) NOT NULL,
                tem_filhos BOOLEAN DEFAULT FALSE,
                atualizado_em TIMESTAMP DEFAULT NOW()
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_shopee_categorias_parent ON shopee_categorias (parent_category_id)")
        try:
            await db.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_shopee_categorias_nome_trgm ON shopee_categorias USING gin (nome gin_trgm_ops)")
        except Exception as e:
            log(AGENT, f"pg_trgm indisponivel para shopee_categorias: {e}")
    try:
        run_async(_go())
        _categorias_table_ok = True
    except Exception as e:
        log(AGENT, f"Erro tabela shopee_categorias: {e}")


def sincronizar_categorias(loja_id: int = None) -> dict:
    """Busca a arvore de categorias na Shopee e grava em cache local."""
    _ensure_categorias_table()
    r = get_category(loja_id)
    categorias = r.get("response", {}).get("category_list", [])
    if not categorias and r.get("error"):
        return {"total": 0, "erro": r["error"]}
    async def _go():
        db = await get_db()
        for c in categorias:
            await db.execute("""
                INSERT INTO shopee_categorias (category_id, parent_category_id, nome, tem_filhos, atualizado_em)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (category_id) DO UPDATE SET
                    parent_category_id = $2, nome = $3, tem_filhos = $4, atualizado_em = NOW()
            """, c.get("category_id"), c.get("parent_category_id", 0),
                c.get("display_category_name", c.get("original_category_name", "")),
                bool(c.get("has_children", False)))
        return len(categorias)
    try:
        total = run_async(_go())
        return {"total": total}
    except Exception as e:
        return {"total": 0, "erro": str(e)}


def listar_categorias_cache(busca: str = "", parent_id: int = None, apenas_folhas: bool = False) -> list:
    """Le a arvore de categorias do cache local. Sincroniza automaticamente na 1a vez."""
    _ensure_categorias_table()
    async def _go():
        db = await get_db()
        count = await db.fetchval("SELECT COUNT(*) FROM shopee_categorias")
        if count == 0:
            return None  # sinaliza que precisa sincronizar
        where = ["1=1"]
        params = []
        if busca:
            params.append(f"%{busca}%")
            where.append(f"nome ILIKE ${len(params)}")
        if parent_id is not None:
            params.append(parent_id)
            where.append(f"parent_category_id = ${len(params)}")
        if apenas_folhas:
            where.append("tem_filhos = FALSE")
        sql = f"SELECT category_id, parent_category_id, nome, tem_filhos FROM shopee_categorias WHERE {' AND '.join(where)} ORDER BY nome LIMIT 500"
        rows = await db.fetch(sql, *params)
        return [dict(r) for r in rows]
    try:
        resultado = run_async(_go())
        if resultado is None:
            sincronizar_categorias()
            return run_async(_go()) or []
        return resultado
    except Exception as e:
        log(AGENT, f"Erro listar_categorias_cache: {e}")
        return []
