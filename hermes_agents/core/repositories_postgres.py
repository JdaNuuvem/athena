"""
Repository Pattern — Postgres implementations.
SOLID: DIP — implementacao concreta, injetavel via constructor.
"""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from typing import Optional, List
from datetime import datetime
from core.repositories import (
    ProdutoRepository, LojaRepository, ConcorrenciaRepository, VendasRepository,
    EstoqueRepository, FinanceiroRepository,
    Produto, Loja, AnuncioConcorrente, ParVendas, EstoqueLoja, ReceitaLoja,
)
from core import get_db, run_async, log

AGENT = "Repository Postgres"


class PostgresProdutoRepository(ProdutoRepository):
    async def buscar_custo(self, sku: str) -> float:
        async def _go():
            db = await get_db()
            r = await db.fetchval("SELECT preco_custo FROM catalogo_produtos WHERE sku = $1 LIMIT 1", sku)
            return float(r or 0)
        try: return run_async(_go())
        except Exception: return 0.0

    async def buscar_grupo(self, sku: str) -> str:
        async def _go():
            db = await get_db()
            r = await db.fetchval("SELECT grupo FROM catalogo_produtos WHERE sku = $1 LIMIT 1", sku)
            return (r or "").strip()
        try: return run_async(_go())
        except Exception: return ""

    async def buscar_por_sku(self, sku: str) -> Optional[Produto]:
        async def _go():
            db = await get_db()
            r = await db.fetchrow("SELECT sku, descricao, COALESCE(preco_custo,0) AS preco_custo, COALESCE(grupo,'') AS grupo, situacao FROM catalogo_produtos WHERE sku = $1 LIMIT 1", sku)
            if not r: return None
            return Produto(sku=r["sku"], descricao=r["descricao"] or "", preco_custo=float(r["preco_custo"] or 0), grupo=r["grupo"] or "", situacao=r["situacao"] or "A")
        try: return run_async(_go())
        except Exception: return None


class PostgresLojaRepository(LojaRepository):
    async def listar_lojas_shopee(self) -> List[Loja]:
        async def _go():
            db = await get_db()
            rows = await db.fetch("SELECT id, nome, ativa, shopee_shop_id, shopee_access_token, shopee_shop_name, COALESCE(shopee_markup_pct,100) AS shopee_markup_pct, COALESCE(grupos_publicacao,'') AS grupos_publicacao, shopee_token_expira_em FROM lojas WHERE shopee_access_token IS NOT NULL AND ativa = TRUE ORDER BY nome")
            return [Loja(
                id=r["id"], nome=r["nome"], ativa=r["ativa"],
                shopee_shop_id=r["shopee_shop_id"] or "",
                shopee_access_token=r["shopee_access_token"] or "",
                shopee_shop_name=r["shopee_shop_name"] or "",
                shopee_markup_pct=float(r["shopee_markup_pct"] or 100),
                grupos_publicacao=r["grupos_publicacao"] or "",
                shopee_token_expira_em=r["shopee_token_expira_em"],
            ) for r in rows]
        try: return run_async(_go())
        except Exception: return []

    async def buscar_por_id(self, loja_id: int) -> Optional[Loja]:
        async def _go():
            db = await get_db()
            r = await db.fetchrow("SELECT id, nome, ativa, shopee_shop_id, shopee_access_token, shopee_shop_name, COALESCE(shopee_markup_pct,100) AS shopee_markup_pct, COALESCE(grupos_publicacao,'') AS grupos_publicacao, shopee_token_expira_em FROM lojas WHERE id = $1", loja_id)
            if not r: return None
            return Loja(
                id=r["id"], nome=r["nome"], ativa=r["ativa"],
                shopee_shop_id=r["shopee_shop_id"] or "",
                shopee_access_token=r["shopee_access_token"] or "",
                shopee_shop_name=r["shopee_shop_name"] or "",
                shopee_markup_pct=float(r["shopee_markup_pct"] or 100),
                grupos_publicacao=r["grupos_publicacao"] or "",
                shopee_token_expira_em=r["shopee_token_expira_em"],
            )
        try: return run_async(_go())
        except Exception: return None

    async def buscar_markup(self, loja_id: int) -> float:
        loja = await self.buscar_por_id(loja_id)
        return loja.shopee_markup_pct if loja else 100.0

    async def buscar_grupos_publicacao(self, loja_id: int) -> set:
        loja = await self.buscar_por_id(loja_id)
        if not loja or not loja.grupos_publicacao.strip():
            return set()
        return set(x.strip() for x in loja.grupos_publicacao.split(",") if x.strip())


class PostgresConcorrenciaRepository(ConcorrenciaRepository):
    async def listar_anuncios(self, sku: str, marketplace: str = "shopee") -> List[AnuncioConcorrente]:
        async def _go():
            db = await get_db()
            rows = await db.fetch("SELECT sku, marketplace, preco FROM anuncios WHERE sku = $1 AND marketplace = $2 AND preco > 0 ORDER BY preco", sku, marketplace)
            return [AnuncioConcorrente(sku=r["sku"], marketplace=r["marketplace"], preco=float(r["preco"])) for r in rows]
        try: return run_async(_go())
        except Exception: return []


class PostgresVendasRepository(VendasRepository):
    async def buscar_pares_comprados_juntos(self, dias: int, min_ocorrencias: int) -> List[ParVendas]:
        async def _go():
            db = await get_db()
            rows = await db.fetch("""
                SELECT a.sku AS sku_a, b.sku AS sku_b, COUNT(DISTINCT a.pedido_id) AS juntos
                FROM vendas_itens a
                JOIN vendas_itens b ON b.pedido_id = a.pedido_id AND b.sku != a.sku
                JOIN vendas_pedidos v ON v.id = a.pedido_id
                WHERE v.data >= CURRENT_DATE - $1 AND v.status != 'cancelado'
                GROUP BY a.sku, b.sku
                HAVING COUNT(DISTINCT a.pedido_id) >= $2
                ORDER BY juntos DESC LIMIT 50
            """, dias, min_ocorrencias)
            return [ParVendas(sku_a=r["sku_a"], sku_b=r["sku_b"], qtd_juntos=r["juntos"]) for r in rows]
        try: return run_async(_go())
        except Exception: return []

    async def buscar_nome_produto(self, sku: str) -> str:
        async def _go():
            db = await get_db()
            r = await db.fetchval("SELECT descricao FROM catalogo_produtos WHERE sku = $1", sku)
            return r or sku
        try: return run_async(_go())
        except Exception: return sku

    async def contar_vendas_sku(self, sku: str, dias: int) -> int:
        async def _go():
            db = await get_db()
            r = await db.fetchval("SELECT COUNT(DISTINCT pedido_id) FROM vendas_itens WHERE sku = $1", sku)
            return int(r or 0)
        try: return run_async(_go())
        except Exception: return 0


class PostgresEstoqueRepository(EstoqueRepository):
    async def listar_estoque_por_loja(self) -> List[EstoqueLoja]:
        async def _go():
            db = await get_db()
            rows = await db.fetch("""
                SELECT e.sku, e.loja, e.quantidade,
                       COALESCE(c.descricao, e.sku) AS nome
                FROM estoque_lojas e
                LEFT JOIN catalogo_produtos c ON c.sku = e.sku
                WHERE e.quantidade > 0
                ORDER BY e.sku, e.quantidade DESC
            """)
            return [EstoqueLoja(sku=r["sku"], loja=r["loja"], quantidade=int(r["quantidade"]), nome_produto=r["nome"]) for r in rows]
        try: return run_async(_go())
        except Exception: return []

    async def buscar_quantidade(self, sku: str, loja: str) -> int:
        async def _go():
            db = await get_db()
            r = await db.fetchval("SELECT SUM(quantidade) FROM estoque_lojas WHERE sku = $1 AND loja = $2", sku, loja)
            return int(r or 0)
        try: return run_async(_go())
        except Exception: return 0

    async def listar_lojas_com_estoque(self) -> List[str]:
        async def _go():
            db = await get_db()
            rows = await db.fetch("SELECT DISTINCT loja FROM estoque_lojas WHERE quantidade > 0 ORDER BY loja")
            return [r["loja"] for r in rows]
        try: return run_async(_go())
        except Exception: return []


class PostgresFinanceiroRepository(FinanceiroRepository):
    async def listar_receita_por_loja(self, dias: int) -> List[ReceitaLoja]:
        async def _go():
            db = await get_db()
            lojas = await db.fetch("SELECT id, nome FROM lojas WHERE ativa = TRUE ORDER BY nome")
            resultado = []
            for loja in lojas:
                lid = loja["id"]
                rec_online = await db.fetchval("SELECT COALESCE(SUM(total),0) FROM vendas_pedidos WHERE loja_id = $1 AND data >= CURRENT_DATE - $2 AND status != 'cancelado'", lid, dias)
                rec_pdv = await db.fetchval("SELECT COALESCE(SUM(v.total),0) FROM pdv_vendas v JOIN pdv_caixas c ON c.id = v.caixa_id WHERE c.loja_id = $1 AND DATE(v.data) >= CURRENT_DATE - $2 AND v.status = 'finalizada'", lid, dias)
                frete = await db.fetchval("SELECT COALESCE(SUM(frete),0) FROM vendas_pedidos WHERE loja_id = $1 AND data >= CURRENT_DATE - $2 AND status != 'cancelado'", lid, dias)
                custos = await db.fetchval("SELECT COALESCE(SUM(valor),0) FROM producao_custos WHERE loja_id = $1 AND data >= CURRENT_DATE - $2", lid, dias)
                qtd = await db.fetchval("SELECT COUNT(*) FROM vendas_pedidos WHERE loja_id = $1 AND data >= CURRENT_DATE - $2 AND status != 'cancelado'", lid, dias)
                resultado.append(ReceitaLoja(
                    loja_id=lid, loja_nome=loja["nome"],
                    receita_online=float(rec_online or 0), receita_pdv=float(rec_pdv or 0),
                    frete=float(frete or 0), custos_producao=float(custos or 0),
                    qtd_vendas=int(qtd or 0),
                ))
            resultado.sort(key=lambda x: (x.receita_online + x.receita_pdv), reverse=True)
            return resultado
        try: return run_async(_go())
        except Exception: return []

    async def listar_lojas_ativas(self) -> List[Loja]:
        async def _go():
            db = await get_db()
            rows = await db.fetch("SELECT id, nome, ativa FROM lojas WHERE ativa = TRUE ORDER BY nome")
            return [Loja(id=r["id"], nome=r["nome"], ativa=r["ativa"]) for r in rows]
        try: return run_async(_go())
        except Exception: return []


# ═══ Factory / Default instances ═══

_produto_repo: Optional[ProdutoRepository] = None
_loja_repo: Optional[LojaRepository] = None
_concorrencia_repo: Optional[ConcorrenciaRepository] = None
_vendas_repo: Optional[VendasRepository] = None
_estoque_repo: Optional[EstoqueRepository] = None
_financeiro_repo: Optional[FinanceiroRepository] = None

def get_produto_repo() -> ProdutoRepository:
    global _produto_repo
    if _produto_repo is None:
        _produto_repo = PostgresProdutoRepository()
    return _produto_repo

def get_loja_repo() -> LojaRepository:
    global _loja_repo
    if _loja_repo is None:
        _loja_repo = PostgresLojaRepository()
    return _loja_repo

def get_concorrencia_repo() -> ConcorrenciaRepository:
    global _concorrencia_repo
    if _concorrencia_repo is None:
        _concorrencia_repo = PostgresConcorrenciaRepository()
    return _concorrencia_repo

def get_vendas_repo() -> VendasRepository:
    global _vendas_repo
    if _vendas_repo is None:
        _vendas_repo = PostgresVendasRepository()
    return _vendas_repo

def get_estoque_repo() -> EstoqueRepository:
    global _estoque_repo
    if _estoque_repo is None:
        _estoque_repo = PostgresEstoqueRepository()
    return _estoque_repo

def get_financeiro_repo() -> FinanceiroRepository:
    global _financeiro_repo
    if _financeiro_repo is None:
        _financeiro_repo = PostgresFinanceiroRepository()
    return _financeiro_repo

def set_produto_repo(repo: ProdutoRepository):
    """Injeta repositorio customizado (ex: mock para testes)."""
    global _produto_repo; _produto_repo = repo

def set_loja_repo(repo: LojaRepository):
    global _loja_repo; _loja_repo = repo
