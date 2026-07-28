"""Transferencia de estoque entre lojas — fluxo com alcada de aprovacao (>10un)
e confirmacao obrigatoria de quem recebe (protege contra extravio/erro no caminho).

Estados: pendente_aprovacao -> em_transito -> confirmada | com_discrepancia
                            -> rejeitada
Se a quantidade solicitada estiver dentro do limite livre, pula direto para
em_transito (debita a origem, via bucket 'transito', na hora, sem esperar
aprovacao de gerente). Quando exige aprovacao, NENHUM saldo se move em
solicitar() — o debito disponivel->transito so acontece em aprovar(). Isso
elimina por construcao o bug antigo de "rejeitar nao devolvia saldo": uma
transferencia so pode ser rejeitada a partir de pendente_aprovacao, estado em
que a origem nunca chegou a ser debitada."""
from core import get_db, run_async, log
from core.estoque import MOTIVOS_TRANSFERENCIA, LIMITE_APROVACAO_UNIDADES
from core.estoque_saldos import (
    mover_saldo, _mover_saldo_async, _ensure_async as _ensure_saldos_async, SaldoError,
)

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


def solicitar(sku: str, origem: str, destino: str, quantidade: float, motivo: str,
              usuario_id: int = None, usuario_nome: str = "",
              ip: str = None, dispositivo: str = None) -> dict:
    _ensure()
    if motivo not in MOTIVOS_TRANSFERENCIA:
        return {"erro": f"Motivo invalido. Use um de: {', '.join(MOTIVOS_TRANSFERENCIA)}"}
    if origem == destino:
        return {"erro": "Loja de origem e destino nao podem ser iguais"}
    precisa_aprovacao = quantidade > LIMITE_APROVACAO_UNIDADES
    status_inicial = "pendente_aprovacao" if precisa_aprovacao else "em_transito"

    if not precisa_aprovacao:
        r = mover_saldo(sku, origem, "disponivel", "transito", quantidade,
                         "transferencia_saida", motivo, usuario_id, usuario_nome, ip, dispositivo)
        if r.get("erro"):
            return {"erro": r["erro"]}

    async def _go():
        db = await get_db()
        row = await db.fetchrow("""
            INSERT INTO estoque_transferencias
                (sku, loja_origem, loja_destino, quantidade_solicitada, motivo, status,
                 usuario_solicitante_id, usuario_solicitante_nome)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id
        """, sku, origem, destino, quantidade, motivo, status_inicial, usuario_id, usuario_nome)
        return row["id"]
    try:
        transferencia_id = run_async(_go())
    except Exception as e:
        return {"erro": str(e)}
    return {"transferencia_id": transferencia_id, "status": status_inicial,
            "pendente_aprovacao": precisa_aprovacao, "sku": sku,
            "origem": origem, "destino": destino, "quantidade": quantidade}


def aprovar(transferencia_id: int, aprovador_id: int, aprovador_nome: str,
            ip: str = None, dispositivo: str = None) -> dict:
    """Libera uma transferencia pendente_aprovacao para em_transito. So aqui
    e' que o debito disponivel->transito acontece quando a transferencia
    precisou de alcada (ver nota de modulo)."""
    _ensure()
    async def _buscar():
        db = await get_db()
        return await db.fetchrow("SELECT * FROM estoque_transferencias WHERE id = $1", transferencia_id)
    try:
        row = run_async(_buscar())
    except Exception as e:
        return {"erro": str(e)}
    if not row:
        return {"erro": "transferencia nao encontrada"}
    if row["status"] != "pendente_aprovacao":
        return {"erro": f"transferencia ja resolvida (status: {row['status']})"}

    r = mover_saldo(row["sku"], row["loja_origem"], "disponivel", "transito",
                     float(row["quantidade_solicitada"]), "transferencia_saida", row["motivo"],
                     aprovador_id, aprovador_nome, ip, dispositivo)
    if r.get("erro"):
        return {"erro": r["erro"]}

    async def _marcar():
        db = await get_db()
        await db.execute("""
            UPDATE estoque_transferencias SET status = 'em_transito',
                usuario_aprovador_id = $1, usuario_aprovador_nome = $2, aprovado_em = NOW()
            WHERE id = $3
        """, aprovador_id, aprovador_nome, transferencia_id)
    try:
        run_async(_marcar())
    except Exception as e:
        return {"erro": str(e)}
    return {"ok": True, "transferencia_id": transferencia_id, "status": "em_transito"}


def rejeitar(transferencia_id: int, aprovador_id: int, aprovador_nome: str, motivo_rejeicao: str = "",
             ip: str = None, dispositivo: str = None) -> dict:
    """Rejeitar so e' valido a partir de pendente_aprovacao — estado em que a
    origem nunca foi debitada (ver nota de modulo). Por isso nao ha saldo
    para devolver aqui; nao precisa chamar mover_saldo. ip/dispositivo
    aceitos por simetria com as outras acoes de alcada (Task 2/3), sem uso
    hoje pois esta acao nao move saldo nem grava ledger."""
    _ensure()
    async def _buscar():
        db = await get_db()
        return await db.fetchrow("SELECT status FROM estoque_transferencias WHERE id = $1", transferencia_id)
    try:
        row = run_async(_buscar())
    except Exception as e:
        return {"erro": str(e)}
    if not row:
        return {"erro": "transferencia nao encontrada"}
    if row["status"] != "pendente_aprovacao":
        return {"erro": f"transferencia ja resolvida (status: {row['status']})"}
    async def _marcar():
        db = await get_db()
        await db.execute("""
            UPDATE estoque_transferencias SET status = 'rejeitada',
                usuario_aprovador_id = $1, usuario_aprovador_nome = $2, motivo_rejeicao = $3
            WHERE id = $4
        """, aprovador_id, aprovador_nome, motivo_rejeicao, transferencia_id)
    try:
        run_async(_marcar())
    except Exception as e:
        return {"erro": str(e)}
    return {"ok": True, "transferencia_id": transferencia_id, "status": "rejeitada"}


def confirmar(transferencia_id: int, confirmador_id: int, confirmador_nome: str, quantidade_recebida: float,
              ip: str = None, dispositivo: str = None) -> dict:
    """Loja destino confirma o recebimento fisico. Credita a quantidade REALMENTE
    recebida (protege contra extravio/erro no caminho) — se diferente do
    solicitado, marca como discrepancia em vez de silenciosamente igualar."""
    _ensure()
    async def _buscar():
        db = await get_db()
        return await db.fetchrow("SELECT * FROM estoque_transferencias WHERE id = $1", transferencia_id)
    try:
        row = run_async(_buscar())
    except Exception as e:
        return {"erro": str(e)}
    if not row:
        return {"erro": "transferencia nao encontrada"}
    if row["status"] != "em_transito":
        return {"erro": f"transferencia nao esta em transito (status: {row['status']})"}

    discrepancia = abs(float(quantidade_recebida) - float(row["quantidade_solicitada"])) > 0.001
    status_final = "com_discrepancia" if discrepancia else "confirmada"

    # Fix review final #7: as duas pernas (baixa do 'transito' da origem +
    # credito no 'disponivel' do destino) E a mudanca de status rodam na MESMA
    # transacao. Antes eram tres operacoes independentes: se a segunda perna
    # falhasse, o estoque sumia do transito sem chegar no destino e a
    # transferencia continuava 'em_transito' — um retry debitava o transito de
    # novo (perda dupla).
    async def _confirmar():
        await _ensure_saldos_async()
        db = await get_db()
        async with db.acquire() as conn:
            async with conn.transaction():
                r1 = await _mover_saldo_async(
                    conn, row["sku"], row["loja_origem"], "transito", None, quantidade_recebida,
                    "transferencia_recebida", row["motivo"], confirmador_id, confirmador_nome, ip, dispositivo)
                if r1.get("erro"):
                    return {"erro": r1["erro"]}  # nada escrito ainda
                r2 = await _mover_saldo_async(
                    conn, row["sku"], row["loja_destino"], None, "disponivel", quantidade_recebida,
                    "transferencia_recebida", row["motivo"], confirmador_id, confirmador_nome, ip, dispositivo)
                if r2.get("erro"):
                    raise SaldoError(r2["erro"])
                await conn.execute("""
                    UPDATE estoque_transferencias SET status = $1, quantidade_recebida = $2,
                        usuario_confirmador_id = $3, usuario_confirmador_nome = $4, confirmado_em = NOW()
                    WHERE id = $5
                """, status_final, quantidade_recebida, confirmador_id, confirmador_nome, transferencia_id)
                return {"ok": True}
    try:
        r = run_async(_confirmar())
    except SaldoError as e:
        return {"erro": str(e)}
    except Exception as e:
        return {"erro": str(e)}
    if r.get("erro"):
        return {"erro": r["erro"]}
    return {"ok": True, "transferencia_id": transferencia_id, "status": status_final,
            "quantidade_solicitada": float(row["quantidade_solicitada"]),
            "quantidade_recebida": float(quantidade_recebida), "discrepancia": discrepancia}


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
