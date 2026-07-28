"""Saldos segregados de estoque (Fase 1 da revisao de arquitetura multilojas).
estoque_saldos e' a fonte de verdade; estoque_lojas.quantidade vira espelho do
saldo 'disponivel', mantido por trigger no banco (defesa em profundidade caso
algum caller ainda nao migrado escreva direto em estoque_lojas)."""
from core import get_db, run_async, log

AGENT = "Estoque Saldos"

TIPOS_SALDO = (
    "disponivel", "reservado", "separacao", "transito", "bloqueado",
    "devolucao", "danificado", "perdido", "consignado", "inventario", "virtual",
)

TIPOS_MOVIMENTO = (
    "compra", "venda", "ajuste", "inventario", "transferencia_saida",
    "transferencia_transito", "transferencia_recebida", "reserva",
    "liberacao_reserva", "separacao", "expedicao", "recebimento", "devolucao",
    "troca", "perda", "roubo", "extravio", "bonificacao", "cancelamento", "estorno",
)

_ok = False


def _ensure():
    global _ok
    if _ok:
        return
    async def _go():
        db = await get_db()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS estoque_saldos (
                id SERIAL PRIMARY KEY,
                sku VARCHAR(50) NOT NULL,
                loja VARCHAR(50) NOT NULL,
                tipo VARCHAR(20) NOT NULL,
                quantidade DECIMAL(12,3) NOT NULL DEFAULT 0,
                data_atualizacao TIMESTAMP DEFAULT NOW(),
                UNIQUE(sku, loja, tipo)
            )
        """)
        # Defensivo: garante que estoque_lojas existe mesmo se core/catalogo.py
        # (dono original) ainda nao rodou nesta conexao.
        await db.execute("""
            CREATE TABLE IF NOT EXISTS estoque_lojas (
                id SERIAL PRIMARY KEY, sku VARCHAR(50) NOT NULL, loja VARCHAR(50) NOT NULL,
                quantidade DECIMAL(12,3) DEFAULT 0, data_atualizacao TIMESTAMP DEFAULT NOW(),
                UNIQUE (sku, loja)
            )
        """)
        # Defensivo: garante estoque_movimentacoes com as colunas novas de
        # auditoria mesmo se core/estoque.py ainda nao rodou nesta conexao.
        await db.execute("""
            CREATE TABLE IF NOT EXISTS estoque_movimentacoes (
                id SERIAL PRIMARY KEY,
                sku VARCHAR(50) NOT NULL,
                loja VARCHAR(50) NOT NULL,
                tipo VARCHAR(30) NOT NULL,
                quantidade DECIMAL(12,3) NOT NULL,
                loja_relacionada VARCHAR(50),
                motivo VARCHAR(200),
                data TIMESTAMP DEFAULT NOW()
            )
        """)
        await db.execute("ALTER TABLE estoque_movimentacoes ADD COLUMN IF NOT EXISTS usuario_id INT")
        await db.execute("ALTER TABLE estoque_movimentacoes ADD COLUMN IF NOT EXISTS usuario_nome VARCHAR(100)")
        await db.execute("ALTER TABLE estoque_movimentacoes ADD COLUMN IF NOT EXISTS tipo_saldo VARCHAR(20)")
        await db.execute("ALTER TABLE estoque_movimentacoes ADD COLUMN IF NOT EXISTS saldo_anterior DECIMAL(12,3)")
        await db.execute("ALTER TABLE estoque_movimentacoes ADD COLUMN IF NOT EXISTS saldo_posterior DECIMAL(12,3)")
        await db.execute("ALTER TABLE estoque_movimentacoes ADD COLUMN IF NOT EXISTS ip VARCHAR(45)")
        await db.execute("ALTER TABLE estoque_movimentacoes ADD COLUMN IF NOT EXISTS dispositivo VARCHAR(300)")
        # Espelho: estoque_lojas.quantidade sempre reflete estoque_saldos
        # (tipo='disponivel') — defesa em profundidade pra callers nao migrados.
        await db.execute("""
            CREATE OR REPLACE FUNCTION fn_espelhar_saldo_disponivel() RETURNS TRIGGER AS $$
            BEGIN
                IF NEW.tipo = 'disponivel' THEN
                    INSERT INTO estoque_lojas (sku, loja, quantidade, data_atualizacao)
                    VALUES (NEW.sku, NEW.loja, NEW.quantidade, NOW())
                    ON CONFLICT (sku, loja) DO UPDATE
                        SET quantidade = NEW.quantidade, data_atualizacao = NOW();
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """)
        await db.execute("DROP TRIGGER IF EXISTS trg_espelhar_saldo_disponivel ON estoque_saldos")
        await db.execute("""
            CREATE TRIGGER trg_espelhar_saldo_disponivel
            AFTER INSERT OR UPDATE ON estoque_saldos
            FOR EACH ROW EXECUTE FUNCTION fn_espelhar_saldo_disponivel()
        """)
    try:
        run_async(_go())
        _ok = True
    except Exception as e:
        log(AGENT, f"Erro tabela/trigger: {e}")


def saldo(sku: str, loja: str, tipo: str = "disponivel") -> float:
    _ensure()
    async def _go():
        db = await get_db()
        v = await db.fetchval(
            "SELECT quantidade FROM estoque_saldos WHERE sku = $1 AND loja = $2 AND tipo = $3",
            sku, loja, tipo)
        return float(v or 0)
    try:
        return run_async(_go())
    except Exception:
        return 0.0


def mover_saldo(sku: str, loja: str, tipo_origem, tipo_destino, quantidade: float,
                tipo_movimento: str, motivo: str = "", usuario_id: int = None, usuario_nome: str = "",
                ip: str = None, dispositivo: str = None) -> dict:
    """Unica funcao que escreve em estoque_saldos + estoque_movimentacoes, na
    mesma transacao logica. tipo_origem=None => credito puro (entrada).
    tipo_destino=None => debito puro (saida). Pelo menos um dos dois precisa
    estar presente. Nunca chamar UPDATE/INSERT em estoque_saldos fora daqui."""
    _ensure()
    if tipo_origem is None and tipo_destino is None:
        return {"erro": "tipo_origem e tipo_destino nao podem ser ambos None"}
    if tipo_origem is not None and tipo_origem not in TIPOS_SALDO:
        return {"erro": f"tipo_origem invalido: {tipo_origem}"}
    if tipo_destino is not None and tipo_destino not in TIPOS_SALDO:
        return {"erro": f"tipo_destino invalido: {tipo_destino}"}
    if tipo_movimento not in TIPOS_MOVIMENTO:
        return {"erro": f"tipo_movimento invalido: {tipo_movimento}"}
    if quantidade <= 0:
        return {"erro": "quantidade deve ser maior que zero"}

    async def _go():
        db = await get_db()
        resultado = {"ok": True, "sku": sku, "loja": loja, "quantidade": quantidade}

        if tipo_origem is not None:
            atual = await db.fetchval(
                "SELECT quantidade FROM estoque_saldos WHERE sku = $1 AND loja = $2 AND tipo = $3",
                sku, loja, tipo_origem)
            atual = float(atual or 0)
            if atual < quantidade:
                return {"erro": f"Saldo insuficiente em '{tipo_origem}' ({atual} disponivel, {quantidade} solicitado)"}
            nova_origem = atual - quantidade
            await db.execute("""
                INSERT INTO estoque_saldos (sku, loja, tipo, quantidade, data_atualizacao)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (sku, loja, tipo) DO UPDATE SET quantidade = $4, data_atualizacao = NOW()
            """, sku, loja, tipo_origem, nova_origem)
            await db.execute("""
                INSERT INTO estoque_movimentacoes
                    (sku, loja, tipo, quantidade, motivo, usuario_id, usuario_nome,
                     tipo_saldo, saldo_anterior, saldo_posterior, ip, dispositivo)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            """, sku, loja, tipo_movimento, quantidade, motivo, usuario_id, usuario_nome,
                tipo_origem, atual, nova_origem, ip, dispositivo)
            resultado["saldo_origem"] = {"tipo": tipo_origem, "anterior": atual, "atual": nova_origem}

        if tipo_destino is not None:
            atual_d = await db.fetchval(
                "SELECT quantidade FROM estoque_saldos WHERE sku = $1 AND loja = $2 AND tipo = $3",
                sku, loja, tipo_destino)
            atual_d = float(atual_d or 0)
            nova_destino = atual_d + quantidade
            await db.execute("""
                INSERT INTO estoque_saldos (sku, loja, tipo, quantidade, data_atualizacao)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (sku, loja, tipo) DO UPDATE SET quantidade = $4, data_atualizacao = NOW()
            """, sku, loja, tipo_destino, nova_destino)
            await db.execute("""
                INSERT INTO estoque_movimentacoes
                    (sku, loja, tipo, quantidade, motivo, usuario_id, usuario_nome,
                     tipo_saldo, saldo_anterior, saldo_posterior, ip, dispositivo)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            """, sku, loja, tipo_movimento, quantidade, motivo, usuario_id, usuario_nome,
                tipo_destino, atual_d, nova_destino, ip, dispositivo)
            resultado["saldo_destino"] = {"tipo": tipo_destino, "anterior": atual_d, "atual": nova_destino}

        return resultado
    try:
        return run_async(_go())
    except Exception as e:
        return {"erro": str(e)}
