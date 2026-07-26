"""Alcada de aprovacao para sangria de caixa (dinheiro em especie e' o vetor
de fraude mais direto em loja fisica). Limite configuravel em runtime via
core.config (tela Configuracoes), nao hardcoded — cada operacao pode ter
volume de caixa diferente."""
from core import get_db, run_async, log
from core.config import get_config, set_config

AGENT = "PDV Aprovacoes"

MOTIVOS_SANGRIA = ["troco", "deposito_banco", "pagamento_fornecedor", "despesa_operacional", "outro"]

_LIMITE_PADRAO = 200.0

_ok = False

def _ensure():
    global _ok
    if _ok: return
    async def _go():
        db = await get_db()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pdv_sangria_aprovacoes (
                id SERIAL PRIMARY KEY,
                caixa_id INT REFERENCES pdv_caixas(id),
                valor DECIMAL(12,2) NOT NULL,
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


def limite_aprovacao() -> float:
    valor = get_config("pdv", "limite_sangria_aprovacao")
    try:
        return float(valor) if valor else _LIMITE_PADRAO
    except (TypeError, ValueError):
        return _LIMITE_PADRAO


def definir_limite_aprovacao(valor: float) -> dict:
    set_config("pdv", "limite_sangria_aprovacao", str(valor))
    return {"ok": True, "limite": valor}


def precisa_aprovacao(valor: float) -> bool:
    return valor > limite_aprovacao()


def solicitar(caixa_id: int, valor: float, motivo: str, usuario_id: int = None, usuario_nome: str = "") -> dict:
    _ensure()
    if motivo not in MOTIVOS_SANGRIA:
        return {"erro": f"Motivo invalido. Use um de: {', '.join(MOTIVOS_SANGRIA)}"}
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""
            INSERT INTO pdv_sangria_aprovacoes
                (caixa_id, valor, motivo, usuario_solicitante_id, usuario_solicitante_nome)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """, caixa_id, valor, motivo, usuario_id, usuario_nome)
        return {"pendente": True, "aprovacao_id": row["id"], "caixa_id": caixa_id, "valor": valor}
    try:
        return run_async(_go())
    except Exception as e:
        return {"erro": str(e)}


def aprovar(aprovacao_id: int, aprovador_id: int, aprovador_nome: str) -> dict:
    _ensure()
    async def _buscar():
        db = await get_db()
        row = await db.fetchrow("SELECT * FROM pdv_sangria_aprovacoes WHERE id = $1", aprovacao_id)
        if not row:
            return {"erro": "aprovacao nao encontrada"}
        if row["status"] != "pendente":
            return {"erro": f"aprovacao ja resolvida (status: {row['status']})"}
        return dict(row)
    pendencia = run_async(_buscar())
    if pendencia.get("erro"):
        return pendencia

    from core.pdv import _aplicar_sangria
    resultado = _aplicar_sangria(pendencia["caixa_id"], float(pendencia["valor"]), pendencia["motivo"],
                                  pendencia["usuario_solicitante_nome"] or "")
    if resultado.get("error"):
        return resultado

    async def _marcar():
        db = await get_db()
        await db.execute("""
            UPDATE pdv_sangria_aprovacoes SET status = 'aprovada',
                usuario_aprovador_id = $1, usuario_aprovador_nome = $2, resolvido_em = NOW()
            WHERE id = $3
        """, aprovador_id, aprovador_nome, aprovacao_id)
    try:
        run_async(_marcar())
    except Exception as e:
        log(AGENT, f"Sangria aplicada mas erro ao marcar aprovacao {aprovacao_id}: {e}")
    resultado["aprovacao_id"] = aprovacao_id
    return resultado


def rejeitar(aprovacao_id: int, aprovador_id: int, aprovador_nome: str, motivo_rejeicao: str = "") -> dict:
    _ensure()
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT status FROM pdv_sangria_aprovacoes WHERE id = $1", aprovacao_id)
        if not row:
            return {"erro": "aprovacao nao encontrada"}
        if row["status"] != "pendente":
            return {"erro": f"aprovacao ja resolvida (status: {row['status']})"}
        await db.execute("""
            UPDATE pdv_sangria_aprovacoes SET status = 'rejeitada',
                usuario_aprovador_id = $1, usuario_aprovador_nome = $2,
                motivo_rejeicao = $3, resolvido_em = NOW()
            WHERE id = $4
        """, aprovador_id, aprovador_nome, motivo_rejeicao, aprovacao_id)
        return {"ok": True, "aprovacao_id": aprovacao_id, "status": "rejeitada"}
    try:
        return run_async(_go())
    except Exception as e:
        return {"erro": str(e)}


def listar(status: str = "pendente") -> list:
    _ensure()
    async def _go():
        db = await get_db()
        where = "1=1"
        params = []
        if status:
            where = "status = $1"
            params.append(status)
        rows = await db.fetch(f"""
            SELECT a.*, c.numero AS caixa_numero
            FROM pdv_sangria_aprovacoes a
            LEFT JOIN pdv_caixas c ON c.id = a.caixa_id
            WHERE {where}
            ORDER BY a.criado_em DESC LIMIT 100
        """, *params)
        return [dict(r) for r in rows]
    try:
        return run_async(_go())
    except Exception as e:
        return []
