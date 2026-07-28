"""Alcada de aprovacao para saidas de estoque acima do limite (LIMITE_APROVACAO_UNIDADES).
Saida grande fica pendente ate um Gerente/Admin aprovar — nao aplica sozinha."""
from core import get_db, run_async, log
from core.estoque import saida as _aplicar_saida, MOTIVOS_SAIDA, LIMITE_APROVACAO_UNIDADES

AGENT = "Estoque Aprovacoes"

_ok = False

def _ensure():
    global _ok
    if _ok: return
    async def _go():
        db = await get_db()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS estoque_aprovacoes (
                id SERIAL PRIMARY KEY,
                tipo VARCHAR(20) NOT NULL DEFAULT 'saida',
                sku VARCHAR(50) NOT NULL,
                loja VARCHAR(50) NOT NULL,
                quantidade DECIMAL(12,3) NOT NULL,
                motivo VARCHAR(100) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pendente',
                usuario_solicitante_id INT, usuario_solicitante_nome VARCHAR(100),
                usuario_aprovador_id INT, usuario_aprovador_nome VARCHAR(100),
                motivo_rejeicao VARCHAR(200),
                criado_em TIMESTAMP DEFAULT NOW(),
                resolvido_em TIMESTAMP
            )
        """)
    try:
        run_async(_go())
        _ok = True
    except Exception as e:
        log(AGENT, f"Erro tabela: {e}")


def precisa_aprovacao(quantidade: float) -> bool:
    return quantidade > LIMITE_APROVACAO_UNIDADES


def solicitar(sku: str, loja: str, quantidade: float, motivo: str,
              usuario_id: int = None, usuario_nome: str = "",
              ip: str = None, dispositivo: str = None) -> dict:
    """ip/dispositivo aceitos por simetria com as demais acoes de alcada —
    solicitar() hoje so grava a pendencia em estoque_aprovacoes (sem tocar
    saldo/ledger), entao os parametros ficam sem uso ate uma fase futura que
    passe a auditar tambem a solicitacao."""
    _ensure()
    if motivo not in MOTIVOS_SAIDA:
        return {"erro": f"Motivo invalido. Use um de: {', '.join(MOTIVOS_SAIDA)}"}
    async def _go():
        db = await get_db()
        atual = await db.fetchval(
            "SELECT quantidade FROM estoque_lojas WHERE sku = $1 AND loja = $2", sku, loja)
        atual = float(atual or 0)
        if atual < quantidade:
            return {"erro": f"Saldo insuficiente ({atual} disponivel, {quantidade} solicitado)"}
        row = await db.fetchrow("""
            INSERT INTO estoque_aprovacoes
                (tipo, sku, loja, quantidade, motivo, usuario_solicitante_id, usuario_solicitante_nome)
            VALUES ('saida', $1, $2, $3, $4, $5, $6)
            RETURNING id
        """, sku, loja, quantidade, motivo, usuario_id, usuario_nome)
        return {"pendente": True, "aprovacao_id": row["id"], "sku": sku, "loja": loja, "quantidade": quantidade}
    try:
        return run_async(_go())
    except Exception as e:
        return {"erro": str(e)}


def aprovar(aprovacao_id: int, aprovador_id: int, aprovador_nome: str,
            ip: str = None, dispositivo: str = None) -> dict:
    _ensure()
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT * FROM estoque_aprovacoes WHERE id = $1", aprovacao_id)
        if not row:
            return {"erro": "aprovacao nao encontrada"}
        if row["status"] != "pendente":
            return {"erro": f"aprovacao ja resolvida (status: {row['status']})"}
        return dict(row)
    pendencia = run_async(_go())
    if pendencia.get("erro"):
        return pendencia

    resultado = _aplicar_saida(
        pendencia["sku"], pendencia["loja"], float(pendencia["quantidade"]), pendencia["motivo"],
        usuario_id=pendencia["usuario_solicitante_id"], usuario_nome=pendencia["usuario_solicitante_nome"],
        ip=ip, dispositivo=dispositivo)
    if resultado.get("erro"):
        return resultado

    async def _marcar():
        db = await get_db()
        await db.execute("""
            UPDATE estoque_aprovacoes SET status = 'aprovada',
                usuario_aprovador_id = $1, usuario_aprovador_nome = $2, resolvido_em = NOW()
            WHERE id = $3
        """, aprovador_id, aprovador_nome, aprovacao_id)
    try:
        run_async(_marcar())
    except Exception as e:
        log(AGENT, f"Saida aplicada mas erro ao marcar aprovacao {aprovacao_id}: {e}")
    resultado["aprovacao_id"] = aprovacao_id
    return resultado


def rejeitar(aprovacao_id: int, aprovador_id: int, aprovador_nome: str, motivo_rejeicao: str = "") -> dict:
    _ensure()
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT status FROM estoque_aprovacoes WHERE id = $1", aprovacao_id)
        if not row:
            return {"erro": "aprovacao nao encontrada"}
        if row["status"] != "pendente":
            return {"erro": f"aprovacao ja resolvida (status: {row['status']})"}
        await db.execute("""
            UPDATE estoque_aprovacoes SET status = 'rejeitada',
                usuario_aprovador_id = $1, usuario_aprovador_nome = $2,
                motivo_rejeicao = $3, resolvido_em = NOW()
            WHERE id = $4
        """, aprovador_id, aprovador_nome, motivo_rejeicao, aprovacao_id)
        return {"ok": True, "aprovacao_id": aprovacao_id, "status": "rejeitada"}
    try:
        return run_async(_go())
    except Exception as e:
        return {"erro": str(e)}


def listar(status: str = "pendente", loja: str = "") -> list:
    _ensure()
    async def _go():
        db = await get_db()
        where = ["1=1"]
        params = []
        if status:
            where.append(f"status = ${len(params) + 1}")
            params.append(status)
        if loja:
            where.append(f"loja = ${len(params) + 1}")
            params.append(loja)
        sql_where = " AND ".join(where)
        rows = await db.fetch(f"""
            SELECT a.*, c.descricao AS produto_nome
            FROM estoque_aprovacoes a
            LEFT JOIN catalogo_produtos c ON c.sku = a.sku
            WHERE {sql_where}
            ORDER BY a.criado_em DESC LIMIT 100
        """, *params)
        return [dict(r) for r in rows]
    try:
        return run_async(_go())
    except Exception as e:
        return []
