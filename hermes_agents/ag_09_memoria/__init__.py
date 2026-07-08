"""
AG-09: Memória Corporativa
Organiza e consulta todo o conhecimento da fábrica:
moldes, fichas técnicas, fornecedores, matérias-primas, histórico de custos,
problemas resolvidos, documentação técnica.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import get_db, run_async, log

AGENT = "AG-09 | Memória Corporativa"

# ===========================================================================
# Moldes
# ===========================================================================

def listar_moldes(status: str = "todos") -> list:
    """Lista todos os moldes cadastrados."""
    async def _go():
        db = await get_db()
        if status == "todos":
            rows = await db.fetch("SELECT * FROM moldes ORDER BY codigo")
        else:
            rows = await db.fetch("SELECT * FROM moldes WHERE status = $1 ORDER BY codigo", status)
        return [dict(r) for r in rows]
    return run_async(_go())

def buscar_molde(codigo: str) -> dict:
    """Busca um molde específico pelo código."""
    async def _go():
        db = await get_db()
        r = await db.fetchrow("SELECT * FROM moldes WHERE codigo = $1", codigo)
        return dict(r) if r else {}
    return run_async(_go())

def produtos_do_molde(codigo_molde: str) -> list:
    """Lista SKUs que usam determinado molde."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT ft.* FROM fichas_tecnicas ft
            JOIN moldes m ON m.id = ft.molde_id
            WHERE m.codigo = $1
        """, codigo_molde)
        return [dict(r) for r in rows]
    return run_async(_go())

# ===========================================================================
# Fichas Técnicas
# ===========================================================================

def buscar_ficha(sku: str) -> dict:
    """Busca ficha técnica completa de um SKU."""
    async def _go():
        db = await get_db()
        r = await db.fetchrow("""
            SELECT ft.*, m.codigo AS molde_codigo, m.material AS molde_material
            FROM fichas_tecnicas ft
            LEFT JOIN moldes m ON m.id = ft.molde_id
            WHERE ft.sku = $1
        """, sku)
        return dict(r) if r else {}
    return run_async(_go())

def listar_fichas(material: str = "") -> list:
    """Lista todas as fichas técnicas, opcionalmente por material."""
    async def _go():
        db = await get_db()
        if material:
            rows = await db.fetch("SELECT * FROM fichas_tecnicas WHERE material_principal ILIKE $1", f"%{material}%")
        else:
            rows = await db.fetch("SELECT * FROM fichas_tecnicas ORDER BY sku")
        return [dict(r) for r in rows]
    return run_async(_go())

# ===========================================================================
# Fornecedores
# ===========================================================================

def buscar_fornecedor(categoria: str = "") -> list:
    """Busca fornecedores, opcionalmente por categoria."""
    async def _go():
        db = await get_db()
        if categoria:
            rows = await db.fetch("SELECT * FROM fornecedores WHERE categoria = $1 AND status = 'ativo'", categoria)
        else:
            rows = await db.fetch("SELECT * FROM fornecedores WHERE status = 'ativo' ORDER BY nome")
        return [dict(r) for r in rows]
    return run_async(_go())

def fornecedor_mais_barato(materia_prima: str) -> dict:
    """Encontra o fornecedor mais barato para uma matéria-prima."""
    async def _go():
        db = await get_db()
        r = await db.fetchrow("""
            SELECT mp.nome, mp.preco_unitario, f.nome AS fornecedor, f.contato_email
            FROM materias_primas mp
            JOIN fornecedores f ON f.id = mp.fornecedor_id
            WHERE mp.nome ILIKE $1 AND f.status = 'ativo'
            ORDER BY mp.preco_unitario ASC
            LIMIT 1
        """, f"%{materia_prima}%")
        return dict(r) if r else {}
    return run_async(_go())

# ===========================================================================
# Matérias-primas
# ===========================================================================

def listar_materias_primas() -> list:
    """Lista matérias-primas com estoque e fornecedor."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT mp.*, f.nome AS fornecedor_nome
            FROM materias_primas mp
            LEFT JOIN fornecedores f ON f.id = mp.fornecedor_id
            ORDER BY mp.nome
        """)
        return [dict(r) for r in rows]
    return run_async(_go())

def alertas_estoque_baixo() -> list:
    """Retorna matérias-primas com estoque abaixo do mínimo."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT nome, estoque_atual_kg, estoque_minimo_kg,
                   (estoque_minimo_kg - estoque_atual_kg) AS deficit
            FROM materias_primas
            WHERE estoque_atual_kg <= estoque_minimo_kg
        """)
        return [dict(r) for r in rows]
    return run_async(_go())

# ===========================================================================
# Histórico de Custos
# ===========================================================================

def historico_custo_sku(sku: str, meses: int = 12) -> list:
    """Histórico de custo de produção de um SKU nos últimos meses."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT * FROM historico_custos
            WHERE sku = $1 AND data >= CURRENT_DATE - make_interval(months => $2)
            ORDER BY data
        """, sku, meses)
        return [dict(r) for r in rows]
    return run_async(_go())

# ===========================================================================
# Problemas Resolvidos (FAQ)
# ===========================================================================

def buscar_solucoes(palavra_chave: str) -> list:
    """Busca problemas já resolvidos por palavra-chave ou tag."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT * FROM problemas_resolvidos
            WHERE titulo ILIKE $1 OR descricao ILIKE $1
               OR EXISTS (SELECT 1 FROM unnest(tags) t WHERE t ILIKE $1)
            ORDER BY data_resolucao DESC
            LIMIT 20
        """, f"%{palavra_chave}%")
        return [dict(r) for r in rows]
    return run_async(_go())

# ===========================================================================
# Consulta inteligente — "Já fabricamos algo parecido?"
# ===========================================================================

def buscar_similar(descricao: str) -> list:
    """Busca produtos similares por descrição."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT ft.sku, ft.descricao, m.codigo AS molde,
                   hc.custo_total AS ultimo_custo
            FROM fichas_tecnicas ft
            LEFT JOIN moldes m ON m.id = ft.molde_id
            LEFT JOIN LATERAL (
                SELECT custo_total FROM historico_custos
                WHERE sku = ft.sku ORDER BY data DESC LIMIT 1
            ) hc ON true
            WHERE ft.descricao ILIKE $1 OR ft.material_principal ILIKE $1
        """, f"%{descricao}%")
        return [dict(r) for r in rows]
    return run_async(_go())

# ===========================================================================
# Stats
# ===========================================================================

def stats() -> dict:
    """Estatísticas da base de conhecimento."""
    async def _go():
        db = await get_db()
        total_moldes = await db.fetchval("SELECT COUNT(*) FROM moldes")
        total_fichas = await db.fetchval("SELECT COUNT(*) FROM fichas_tecnicas")
        total_fornecedores = await db.fetchval("SELECT COUNT(*) FROM fornecedores WHERE status = 'ativo'")
        total_faq = await db.fetchval("SELECT COUNT(*) FROM problemas_resolvidos")
        return {
            "moldes_ativos": total_moldes,
            "fichas_tecnicas": total_fichas,
            "fornecedores_ativos": total_fornecedores,
            "problemas_resolvidos": total_faq,
        }
    return run_async(_go())

if __name__ == "__main__":
    log(AGENT, "Auto-teste iniciado")
    for molde in listar_moldes("ativo"):
        print(f"  Molde: {molde['codigo']} → {molde['produto']} (status: {molde['status']})")
    log(AGENT, f"Stats: {stats()}")
