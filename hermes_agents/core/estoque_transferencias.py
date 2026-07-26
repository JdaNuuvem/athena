"""Transferencia de estoque entre lojas — fluxo com alcada de aprovacao (>10un)
e confirmacao obrigatoria de quem recebe (protege contra extravio/erro no caminho).

Estados: pendente_aprovacao -> aprovada -> em_transito -> confirmada | com_discrepancia
                            -> rejeitada
Se a quantidade solicitada estiver dentro do limite livre, pula direto para
em_transito (debita a origem na hora, sem esperar aprovacao de gerente)."""
from core import get_db, run_async, log
from core.estoque import MOTIVOS_TRANSFERENCIA, LIMITE_APROVACAO_UNIDADES

AGENT = "Estoque Transferencias"

_ok = False

def _ensure():
    global _ok
    if _ok: return
    async def _go():
        db = await get_db()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS estoque_transferencias (
                id SERIAL PRIMARY KEY,
                sku VARCHAR(50) NOT NULL,
                loja_origem VARCHAR(50) NOT NULL,
                loja_destino VARCHAR(50) NOT NULL,
                quantidade_solicitada DECIMAL(12,3) NOT NULL,
                quantidade_recebida DECIMAL(12,3),
                motivo VARCHAR(100) NOT NULL,
                status VARCHAR(30) NOT NULL DEFAULT 'pendente_aprovacao',
                usuario_solicitante_id INT, usuario_solicitante_nome VARCHAR(100),
                usuario_aprovador_id INT, usuario_aprovador_nome VARCHAR(100),
                usuario_confirmador_id INT, usuario_confirmador_nome VARCHAR(100),
                motivo_rejeicao VARCHAR(200),
                criado_em TIMESTAMP DEFAULT NOW(),
                aprovado_em TIMESTAMP,
                confirmado_em TIMESTAMP
            )
        """)
    try:
        run_async(_go())
        _ok = True
    except Exception as e:
        log(AGENT, f"Erro tabela: {e}")


async def _debitar_origem(db, sku, origem, quantidade):
    await db.execute(
        "UPDATE estoque_lojas SET quantidade = quantidade - $1, data_atualizacao = NOW() WHERE sku = $2 AND loja = $3",
        quantidade, sku, origem)


async def _creditar_destino(db, sku, destino, quantidade):
    await db.execute("""
        INSERT INTO estoque_lojas (sku, loja, quantidade, data_atualizacao)
        VALUES ($1, $2, $3, NOW())
        ON CONFLICT (sku, loja) DO UPDATE SET quantidade = estoque_lojas.quantidade + $3, data_atualizacao = NOW()
    """, sku, destino, quantidade)


def solicitar(sku: str, origem: str, destino: str, quantidade: float, motivo: str,
              usuario_id: int = None, usuario_nome: str = "") -> dict:
    _ensure()
    if motivo not in MOTIVOS_TRANSFERENCIA:
        return {"erro": f"Motivo invalido. Use um de: {', '.join(MOTIVOS_TRANSFERENCIA)}"}
    if origem == destino:
        return {"erro": "Loja de origem e destino nao podem ser iguais"}
    precisa_aprovacao = quantidade > LIMITE_APROVACAO_UNIDADES
    async def _go():
        db = await get_db()
        saldo_origem = await db.fetchval(
            "SELECT quantidade FROM estoque_lojas WHERE sku = $1 AND loja = $2", sku, origem)
        saldo_origem = float(saldo_origem or 0)
        if saldo_origem < quantidade:
            return {"erro": f"Saldo insuficiente na origem ({saldo_origem} em {origem})"}

        status_inicial = "pendente_aprovacao" if precisa_aprovacao else "em_transito"
        row = await db.fetchrow("""
            INSERT INTO estoque_transferencias
                (sku, loja_origem, loja_destino, quantidade_solicitada, motivo, status,
                 usuario_solicitante_id, usuario_solicitante_nome, aprovado_em)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, CASE WHEN $6 = 'em_transito' THEN NOW() END)
            RETURNING id
        """, sku, origem, destino, quantidade, motivo, status_inicial, usuario_id, usuario_nome)
        transferencia_id = row["id"]
        if not precisa_aprovacao:
            await _debitar_origem(db, sku, origem, quantidade)
        return {"transferencia_id": transferencia_id, "status": status_inicial,
                "pendente_aprovacao": precisa_aprovacao, "sku": sku,
                "origem": origem, "destino": destino, "quantidade": quantidade}
    try:
        return run_async(_go())
    except Exception as e:
        return {"erro": str(e)}


def aprovar(transferencia_id: int, aprovador_id: int, aprovador_nome: str) -> dict:
    _ensure()
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT * FROM estoque_transferencias WHERE id = $1", transferencia_id)
        if not row:
            return {"erro": "transferencia nao encontrada"}
        if row["status"] != "pendente_aprovacao":
            return {"erro": f"transferencia ja resolvida (status: {row['status']})"}
        saldo_origem = await db.fetchval(
            "SELECT quantidade FROM estoque_lojas WHERE sku = $1 AND loja = $2", row["sku"], row["loja_origem"])
        saldo_origem = float(saldo_origem or 0)
        if saldo_origem < float(row["quantidade_solicitada"]):
            return {"erro": f"Saldo insuficiente na origem no momento da aprovacao ({saldo_origem} em {row['loja_origem']})"}
        await _debitar_origem(db, row["sku"], row["loja_origem"], float(row["quantidade_solicitada"]))
        await db.execute("""
            UPDATE estoque_transferencias SET status = 'em_transito',
                usuario_aprovador_id = $1, usuario_aprovador_nome = $2, aprovado_em = NOW()
            WHERE id = $3
        """, aprovador_id, aprovador_nome, transferencia_id)
        return {"ok": True, "transferencia_id": transferencia_id, "status": "em_transito"}
    try:
        return run_async(_go())
    except Exception as e:
        return {"erro": str(e)}


def rejeitar(transferencia_id: int, aprovador_id: int, aprovador_nome: str, motivo_rejeicao: str = "") -> dict:
    _ensure()
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT status FROM estoque_transferencias WHERE id = $1", transferencia_id)
        if not row:
            return {"erro": "transferencia nao encontrada"}
        if row["status"] != "pendente_aprovacao":
            return {"erro": f"transferencia ja resolvida (status: {row['status']})"}
        await db.execute("""
            UPDATE estoque_transferencias SET status = 'rejeitada',
                usuario_aprovador_id = $1, usuario_aprovador_nome = $2, motivo_rejeicao = $3
            WHERE id = $4
        """, aprovador_id, aprovador_nome, motivo_rejeicao, transferencia_id)
        return {"ok": True, "transferencia_id": transferencia_id, "status": "rejeitada"}
    try:
        return run_async(_go())
    except Exception as e:
        return {"erro": str(e)}


def confirmar(transferencia_id: int, confirmador_id: int, confirmador_nome: str, quantidade_recebida: float) -> dict:
    """Loja destino confirma o recebimento fisico. Credita a quantidade REALMENTE
    recebida (protege contra extravio/erro no caminho) — se diferente do
    solicitado, marca como discrepancia em vez de silenciosamente igualar."""
    _ensure()
    async def _go():
        db = await get_db()
        row = await db.fetchrow("SELECT * FROM estoque_transferencias WHERE id = $1", transferencia_id)
        if not row:
            return {"erro": "transferencia nao encontrada"}
        if row["status"] != "em_transito":
            return {"erro": f"transferencia nao esta em transito (status: {row['status']})"}
        await _creditar_destino(db, row["sku"], row["loja_destino"], quantidade_recebida)
        discrepancia = abs(float(quantidade_recebida) - float(row["quantidade_solicitada"])) > 0.001
        status_final = "com_discrepancia" if discrepancia else "confirmada"
        await db.execute("""
            UPDATE estoque_transferencias SET status = $1, quantidade_recebida = $2,
                usuario_confirmador_id = $3, usuario_confirmador_nome = $4, confirmado_em = NOW()
            WHERE id = $5
        """, status_final, quantidade_recebida, confirmador_id, confirmador_nome, transferencia_id)
        return {"ok": True, "transferencia_id": transferencia_id, "status": status_final,
                "quantidade_solicitada": float(row["quantidade_solicitada"]),
                "quantidade_recebida": float(quantidade_recebida), "discrepancia": discrepancia}
    try:
        return run_async(_go())
    except Exception as e:
        return {"erro": str(e)}


def listar(status: str = "", loja: str = "") -> list:
    _ensure()
    async def _go():
        db = await get_db()
        where = ["1=1"]
        params = []
        if status:
            where.append(f"status = ${len(params) + 1}")
            params.append(status)
        if loja:
            where.append(f"(loja_origem = ${len(params) + 1} OR loja_destino = ${len(params) + 1})")
            params.append(loja)
        sql_where = " AND ".join(where)
        rows = await db.fetch(f"""
            SELECT t.*, c.descricao AS produto_nome
            FROM estoque_transferencias t
            LEFT JOIN catalogo_produtos c ON c.sku = t.sku
            WHERE {sql_where}
            ORDER BY t.criado_em DESC LIMIT 100
        """, *params)
        return [dict(r) for r in rows]
    try:
        return run_async(_go())
    except Exception as e:
        return []
