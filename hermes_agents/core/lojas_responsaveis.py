"""Responsaveis de uma loja (proprietario/gerentes/etc) — vinculo informativo
entre usuario ja cadastrado (rbac_usuarios) e uma loja, com cargo e periodo
de vigencia. NAO controla acesso (RBAC continua global) — e' so' registro
de "quem responde por essa loja", exibido nas telas de gestao."""
from core import get_db, run_async
from core.lojas import _log_erro

_table_ok = False

CARGOS_VALIDOS = (
    "proprietario", "gerente_geral", "gerente_financeiro", "gerente_comercial",
    "gerente_estoque", "responsavel_fiscal", "responsavel_pdv", "administrador",
)


def _ensure_table():
    global _table_ok
    if _table_ok: return
    async def _go():
        db = await get_db()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS loja_responsaveis (
                id SERIAL PRIMARY KEY,
                loja_id INT NOT NULL REFERENCES lojas(id) ON DELETE CASCADE,
                usuario_id INT NOT NULL REFERENCES rbac_usuarios(id),
                cargo VARCHAR(50) NOT NULL,
                permissoes VARCHAR(300),
                data_inicio DATE NOT NULL DEFAULT CURRENT_DATE,
                data_fim DATE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_loja_responsaveis_loja ON loja_responsaveis (loja_id)")
    try:
        run_async(_go())
        _table_ok = True
    except Exception as e:
        _log_erro("lojas_responsaveis._ensure_table", e)


def vincular(loja_id: int, usuario_id: int, cargo: str, permissoes: str = None,
             data_inicio: str = None, data_fim: str = None) -> dict:
    _ensure_table()
    if cargo not in CARGOS_VALIDOS:
        return {"error": f"cargo invalido. Use um de: {', '.join(CARGOS_VALIDOS)}"}
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""
            INSERT INTO loja_responsaveis (loja_id, usuario_id, cargo, permissoes, data_inicio, data_fim)
            VALUES ($1, $2, $3, $4, COALESCE($5, CURRENT_DATE), $6)
            RETURNING id, loja_id, usuario_id, cargo, permissoes, data_inicio, data_fim
        """, loja_id, usuario_id, cargo, permissoes, data_inicio, data_fim)
        return dict(row) if row else {"error": "falha ao vincular responsavel"}
    try: return run_async(_go())
    except Exception as e: _log_erro("lojas_responsaveis.vincular", e); return {"error": str(e)}


def listar(loja_id: int) -> list:
    _ensure_table()
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT r.id, r.loja_id, r.usuario_id, u.nome AS usuario_nome, u.email AS usuario_email,
                   r.cargo, r.permissoes, r.data_inicio, r.data_fim
            FROM loja_responsaveis r JOIN rbac_usuarios u ON u.id = r.usuario_id
            WHERE r.loja_id = $1 ORDER BY r.data_inicio DESC
        """, loja_id)
        return [dict(r) for r in rows]
    try: return run_async(_go())
    except Exception as e: _log_erro("lojas_responsaveis.listar", e); return []


def atualizar(vinculo_id: int, cargo: str = None, permissoes: str = None, loja_id: int = None) -> bool:
    """loja_id (quando informado) escopa o UPDATE — sem isso, quem tem
    configuracoes.editar consegue editar o vinculo de responsavel de
    QUALQUER loja so' sabendo o vinculo_id, mesmo restrito por usuario_lojas
    a uma loja especifica (IDOR)."""
    _ensure_table()
    if cargo is not None and cargo not in CARGOS_VALIDOS:
        return False
    async def _go():
        db = await get_db()
        r = None
        extra_where = " AND loja_id = $3" if loja_id is not None else ""
        extra_args = [loja_id] if loja_id is not None else []
        if cargo is not None:
            r = await db.execute(f"UPDATE loja_responsaveis SET cargo = $1 WHERE id = $2{extra_where}", cargo, vinculo_id, *extra_args)
        if permissoes is not None:
            r = await db.execute(f"UPDATE loja_responsaveis SET permissoes = $1 WHERE id = $2{extra_where}", permissoes, vinculo_id, *extra_args)
        return r != "UPDATE 0" if r else False
    try: return run_async(_go())
    except Exception as e: _log_erro("lojas_responsaveis.atualizar", e); return False


def encerrar(vinculo_id: int, data_fim: str = None, loja_id: int = None) -> bool:
    """Marca o fim da vigencia (nao apaga o historico). loja_id escopa o
    UPDATE — mesma razao do IDOR documentado em atualizar()."""
    _ensure_table()
    async def _go():
        db = await get_db()
        if loja_id is not None:
            r = await db.execute(
                "UPDATE loja_responsaveis SET data_fim = COALESCE($1, CURRENT_DATE) WHERE id = $2 AND loja_id = $3",
                data_fim, vinculo_id, loja_id)
        else:
            r = await db.execute(
                "UPDATE loja_responsaveis SET data_fim = COALESCE($1, CURRENT_DATE) WHERE id = $2",
                data_fim, vinculo_id)
        return r != "UPDATE 0"
    try: return run_async(_go())
    except Exception as e: _log_erro("lojas_responsaveis.encerrar", e); return False


def remover(vinculo_id: int, loja_id: int = None) -> bool:
    """Apaga o vinculo (uso p/ corrigir erro de cadastro, nao pra encerrar
    vigencia). loja_id escopa o DELETE — mesma razao do IDOR documentado em
    atualizar()."""
    _ensure_table()
    async def _go():
        db = await get_db()
        if loja_id is not None:
            r = await db.execute("DELETE FROM loja_responsaveis WHERE id = $1 AND loja_id = $2", vinculo_id, loja_id)
        else:
            r = await db.execute("DELETE FROM loja_responsaveis WHERE id = $1", vinculo_id)
        return r != "DELETE 0"
    try: return run_async(_go())
    except Exception as e: _log_erro("lojas_responsaveis.remover", e); return False
