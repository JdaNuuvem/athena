"""Estoque por loja — CRUD local + movimentacoes + Bling sync."""
from core import get_db, run_async, log
from core.estoque_saldos import (
    mover_saldo, saldo as saldo_bucket,
    _mover_saldo_async, _saldo_async, _ensure_async as _ensure_saldos_async,
    SaldoError,
)

AGENT = "Estoque"

# Limite acima do qual saida/transferencia exige aprovacao de Gerente/Admin
# (ver core/estoque_aprovacoes.py e core/estoque_transferencias.py). Entrada
# de mercadoria fica de fora — recebimento de fornecedor costuma vir em lotes
# grandes e e' baixo risco de fraude (o risco esta em TIRAR estoque, nao receber).
LIMITE_APROVACAO_UNIDADES = 10

# Motivos de lista fechada — texto livre vira ruido que ninguem analisa depois;
# lista fechada permite relatorio de discrepancia por motivo/loja/operador.
MOTIVOS_ENTRADA = ["compra_fornecedor", "devolucao_cliente", "producao_interna", "ajuste_inventario", "outro"]
MOTIVOS_SAIDA = ["quebra", "perda", "devolucao_fornecedor", "uso_interno", "furto_identificado", "ajuste_inventario", "outro"]
MOTIVOS_TRANSFERENCIA = ["reposicao_entre_lojas", "redistribuicao_estoque_parado", "solicitacao_loja_destino", "outro"]

# O schema de estoque_movimentacoes (colunas de auditoria + a coluna aditiva
# loja_id da Fase 3) passou a ser criado por core/estoque_saldos.py::
# _ensure_async(), junto de estoque_saldos e do trigger de espelho: desde a
# Fase 1 este modulo nao escreve mais direto naquela tabela, entao nao faz
# sentido continuar dono do DDL dela. O _ensure()/_ok locais sairam.

# Mapeia os motivos de negocio (lista fechada acima) para o tipo_movimento
# do ledger segregado (core/estoque_saldos.TIPOS_MOVIMENTO).
_MAPA_MOVIMENTO_ENTRADA = {
    "compra_fornecedor": "compra",
    "devolucao_cliente": "devolucao",
    "producao_interna": "recebimento",
    "ajuste_inventario": "ajuste",
    "outro": "ajuste",
}
_MAPA_MOVIMENTO_SAIDA = {
    "quebra": "perda",
    "perda": "perda",
    "devolucao_fornecedor": "devolucao",
    "uso_interno": "ajuste",
    "furto_identificado": "roubo",
    "ajuste_inventario": "ajuste",
    "outro": "ajuste",
}


def _where_loja_param(loja: str) -> tuple:
    """Retorna (sql, params) com placeholder parametrizado — sem SQL injection."""
    if loja.isdigit():
        return "e.loja = (SELECT nome FROM lojas WHERE id = $1)", [int(loja)]
    return "e.loja = $1", [loja]

def listar(loja: str = "", busca: str = "", pagina: int = 1, por_pagina: int = 30, loja_ids: list = None) -> dict:
    """loja_ids (Fase 4, RBAC por loja): quando o pedido nao especifica uma
    loja exata ("todas"/vazio) e o usuario tem restricao de loja, filtra so'
    pelas lojas permitidas. Um filtro explicito de loja (id ou nome) sempre
    tem prioridade — modo suave, nao bloqueia."""
    async def _go():
        db = await get_db()
        where = ["1=1"]
        params = []
        if loja and loja != "todas":
            w, p = _where_loja_param(loja)
            where.append(w); params.extend(p)
        elif loja_ids is not None:
            params.append(loja_ids)
            where.append(f"e.loja_id = ANY(${len(params)})")
        if busca:
            n = len(params) + 1
            where.append(f"(c.sku ILIKE ${n} OR c.descricao ILIKE ${n + 1})")
            params.extend([f"%{busca}%", f"%{busca}%"])
        sql_where = " AND ".join(where)
        total = await db.fetchval(
            f"SELECT COUNT(*) FROM estoque_lojas e JOIN catalogo_produtos c ON c.sku = e.sku WHERE {sql_where}", *params)
        offset = (pagina - 1) * por_pagina
        n = len(params) + 1
        rows = await db.fetch(f"""
            SELECT e.id, e.sku, c.descricao AS nome, e.loja, e.quantidade, e.data_atualizacao,
                   COALESCE(c.imagem_url, '') AS imagem_url, c.situacao
            FROM estoque_lojas e
            JOIN catalogo_produtos c ON c.sku = e.sku
            WHERE {sql_where}
            ORDER BY c.descricao ASC, e.loja ASC
            LIMIT ${n} OFFSET ${n + 1}
        """, *params, por_pagina, offset)
        return {"estoque": [dict(r) for r in rows], "total": total, "pagina": pagina}
    try:
        return run_async(_go())
    except Exception as e:
        return {"erro": str(e), "estoque": [], "total": 0}


# `atualizar()` saiu na Fase 1: era um SET absoluto por SQL cru em
# estoque_lojas (proibido agora — estoque_lojas e' espelho de estoque_saldos).
# O substituto e' `ajustar_absoluto()`/`ajustar_absoluto_async()` mais abaixo,
# que calcula o delta e aplica via mover_saldo (e portanto tambem grava
# loja_id no ledger, como o dual-write da Fase 3 exigia).


def entrada(sku: str, loja: str, quantidade: float, motivo: str = "",
            usuario_id: int = None, usuario_nome: str = "",
            ip: str = None, dispositivo: str = None) -> dict:
    if motivo not in MOTIVOS_ENTRADA:
        motivo = "outro"
    tipo_movimento = _MAPA_MOVIMENTO_ENTRADA[motivo]
    r = mover_saldo(sku, loja, None, "disponivel", quantidade, tipo_movimento, motivo,
                     usuario_id, usuario_nome, ip, dispositivo)
    if r.get("erro"):
        return r
    d = r["saldo_destino"]
    return {"ok": True, "sku": sku, "loja": loja, "quantidade": quantidade,
            "anterior": d["anterior"], "atual": d["atual"]}


def saida(sku: str, loja: str, quantidade: float, motivo: str = "",
          usuario_id: int = None, usuario_nome: str = "",
          ip: str = None, dispositivo: str = None) -> dict:
    """Aplica a saida diretamente. Nao decide alcada de aprovacao — quem chama
    (routes/estoque.py ou core/estoque_aprovacoes.py) decide se a quantidade
    exige aprovacao antes de chegar aqui."""
    if motivo not in MOTIVOS_SAIDA:
        return {"erro": f"Motivo invalido. Use um de: {', '.join(MOTIVOS_SAIDA)}"}
    tipo_movimento = _MAPA_MOVIMENTO_SAIDA[motivo]
    r = mover_saldo(sku, loja, "disponivel", None, quantidade, tipo_movimento, motivo,
                     usuario_id, usuario_nome, ip, dispositivo)
    if r.get("erro"):
        return r
    o = r["saldo_origem"]
    return {"ok": True, "sku": sku, "loja": loja, "quantidade": quantidade,
            "anterior": o["anterior"], "atual": o["atual"]}


async def entrada_async(conn, sku: str, loja: str, quantidade: float, motivo: str = "",
                        usuario_id: int = None, usuario_nome: str = "",
                        ip: str = None, dispositivo: str = None) -> dict:
    """Versao async-native de entrada(): usa a conexao/transacao ja aberta pelo
    caller. Use em qualquer codigo que ja esteja dentro de um `async def`
    (core/entidades.py, bling_erp.py, ratear...) — chamar entrada() la dentro
    faz run_async abrir um event loop novo e vazar um pool asyncpg."""
    if motivo not in MOTIVOS_ENTRADA:
        motivo = "outro"
    tipo_movimento = _MAPA_MOVIMENTO_ENTRADA[motivo]
    r = await _mover_saldo_async(conn, sku, loja, None, "disponivel", quantidade,
                                 tipo_movimento, motivo, usuario_id, usuario_nome, ip, dispositivo)
    if r.get("erro"):
        return r
    d = r["saldo_destino"]
    return {"ok": True, "sku": sku, "loja": loja, "quantidade": quantidade,
            "anterior": d["anterior"], "atual": d["atual"]}


async def saida_async(conn, sku: str, loja: str, quantidade: float, motivo: str = "",
                      usuario_id: int = None, usuario_nome: str = "",
                      ip: str = None, dispositivo: str = None) -> dict:
    """Versao async-native de saida() — ver nota em entrada_async()."""
    if motivo not in MOTIVOS_SAIDA:
        return {"erro": f"Motivo invalido. Use um de: {', '.join(MOTIVOS_SAIDA)}"}
    tipo_movimento = _MAPA_MOVIMENTO_SAIDA[motivo]
    r = await _mover_saldo_async(conn, sku, loja, "disponivel", None, quantidade,
                                 tipo_movimento, motivo, usuario_id, usuario_nome, ip, dispositivo)
    if r.get("erro"):
        return r
    o = r["saldo_origem"]
    return {"ok": True, "sku": sku, "loja": loja, "quantidade": quantidade,
            "anterior": o["anterior"], "atual": o["atual"]}


async def ajustar_absoluto_async(conn, sku: str, loja: str, quantidade_absoluta: float,
                                 motivo: str = "ajuste_inventario",
                                 usuario_id: int = None, usuario_nome: str = "",
                                 ip: str = None, dispositivo: str = None) -> dict:
    """Versao async-native de ajustar_absoluto() — ver nota em entrada_async()."""
    atual = await _saldo_async(conn, sku, loja, "disponivel")
    delta = round(float(quantidade_absoluta) - atual, 3)
    if delta == 0:
        return {"ok": True, "sku": sku, "loja": loja, "quantidade": quantidade_absoluta,
                "anterior": atual, "atual": atual, "sem_alteracao": True}
    if delta > 0:
        return await entrada_async(conn, sku, loja, delta, motivo, usuario_id, usuario_nome, ip, dispositivo)
    return await saida_async(conn, sku, loja, abs(delta), motivo, usuario_id, usuario_nome, ip, dispositivo)


def transferir(sku: str, origem: str, destino: str, quantidade: float, motivo: str = "",
               usuario_id: int = None, usuario_nome: str = "",
               ip: str = None, dispositivo: str = None) -> dict:
    """Transferencia instantanea, sem aprovacao/estado pendente — nao passa
    pelo bucket 'transito' (esse e' exclusivo do fluxo com aprovacao em
    core/estoque_transferencias.py).

    Atomica (fix review final #7): as duas pernas (debito da origem + credito
    do destino) rodam na MESMA transacao. Antes eram dois mover_saldo()
    independentes — se a segunda falhasse, a origem ficava debitada sem
    ninguem creditado (perda silenciosa de estoque)."""
    async def _go():
        await _ensure_saldos_async()
        db = await get_db()
        async with db.acquire() as conn:
            async with conn.transaction():
                r1 = await _mover_saldo_async(conn, sku, origem, "disponivel", None, quantidade,
                                              "transferencia_saida", motivo,
                                              usuario_id, usuario_nome, ip, dispositivo)
                if r1.get("erro"):
                    # Nada escrito ainda — pode retornar sem precisar de rollback.
                    return {"erro": r1["erro"] if "insuficiente" in r1["erro"]
                            else f"Saldo insuficiente na origem: {r1['erro']}"}
                r2 = await _mover_saldo_async(conn, sku, destino, None, "disponivel", quantidade,
                                              "transferencia_recebida", motivo,
                                              usuario_id, usuario_nome, ip, dispositivo)
                if r2.get("erro"):
                    # Perna 1 ja escreveu: precisa levantar pra abortar a transacao.
                    raise SaldoError(r2["erro"])
                return {"ok": True, "sku": sku, "origem": origem, "destino": destino,
                        "quantidade": quantidade,
                        "saldo_origem": r1["saldo_origem"]["atual"],
                        "saldo_destino": r2["saldo_destino"]["atual"]}
    try:
        return run_async(_go())
    except SaldoError as e:
        return {"erro": str(e)}
    except Exception as e:
        return {"erro": str(e)}


def ajustar_absoluto(sku: str, loja: str, quantidade_absoluta: float, motivo: str = "ajuste_inventario",
                      usuario_id: int = None, usuario_nome: str = "",
                      ip: str = None, dispositivo: str = None) -> dict:
    """Para integracoes que mandam o valor final, nao um delta (Bling, PUT manual
    de loja). Calcula o delta contra o disponivel atual e aplica como entrada/saida.
    Leitura e escrita na MESMA transacao — antes eram duas chamadas separadas
    (saldo() + entrada()), o que abria janela de corrida entre ler o atual e
    gravar o delta."""
    async def _go():
        await _ensure_saldos_async()
        db = await get_db()
        async with db.acquire() as conn:
            async with conn.transaction():
                return await ajustar_absoluto_async(conn, sku, loja, quantidade_absoluta, motivo,
                                                    usuario_id, usuario_nome, ip, dispositivo)
    try:
        return run_async(_go())
    except Exception as e:
        return {"erro": str(e)}


def movimentacoes(sku: str = "", loja: str = "", limite: int = 50, loja_ids: list = None) -> list:
    """loja_ids (Fase 4, RBAC por loja): mesma semantica de listar() — so'
    restringe quando nao ha filtro explicito de loja."""
    async def _go():
        db = await get_db()
        where = ["1=1"]
        params = []
        if sku:
            params.append(sku)
            where.append(f"m.sku = ${len(params)}")
        if loja:
            params.append(loja)
            where.append(f"m.loja = ${len(params)}")
        elif loja_ids is not None:
            params.append(loja_ids)
            where.append(f"m.loja_id = ANY(${len(params)})")
        sql_where = " AND ".join(where)
        params.append(int(limite))
        rows = await db.fetch(f"""
            SELECT m.*, c.descricao AS produto_nome
            FROM estoque_movimentacoes m
            LEFT JOIN catalogo_produtos c ON c.sku = m.sku
            WHERE {sql_where}
            ORDER BY m.data DESC LIMIT ${len(params)}
        """, *params)
        return [dict(r) for r in rows]
    try:
        return run_async(_go())
    except Exception as e:
        return []


def ratear(sku: str, total: float, modo: str = "igual", lojas: list = None,
           periodo_dias: int = 30, percentuais: dict = None) -> dict:
    percentuais = percentuais or {}
    async def _go():
        await _ensure_saldos_async()
        db = await get_db()
        if lojas:
            lojas_validas = [l for l in lojas if l.strip()]
        else:
            rows = await db.fetch("SELECT nome FROM lojas ORDER BY nome")
            lojas_validas = [r["nome"] for r in rows]
        if not lojas_validas:
            return {"erro": "Nenhuma loja ativa encontrada"}
        n = len(lojas_validas)
        if modo == "igual":
            pcts = {l: round(100.0 / n, 4) for l in lojas_validas}
        elif modo == "proporcional":
            if percentuais:
                pcts = {}
                resto_pct = 100.0
                for l in lojas_validas:
                    p = percentuais.get(l)
                    if p is not None:
                        pcts[l] = float(p)
                        resto_pct -= float(p)
                    else:
                        pcts[l] = None
                na = [l for l in lojas_validas if pcts[l] is None]
                if na:
                    share = round(resto_pct / len(na), 4) if na else 0
                    for l in na:
                        pcts[l] = share
            else:
                rows = await db.fetch(
                    f"SELECT COALESCE(l.nome, 'Venda direta') AS loja, SUM(v.quantidade) AS qtd "
                    f"FROM vendas v LEFT JOIN lojas l ON l.id = v.loja_id "
                    f"WHERE v.sku = $1 AND v.data >= CURRENT_DATE - {periodo_dias} "
                    f"GROUP BY COALESCE(l.nome, 'Venda direta') ORDER BY qtd DESC", sku)
                vendas_map = {r["loja"]: float(r["qtd"]) for r in rows}
                total_vendido = sum(vendas_map.values())
                if total_vendido > 0:
                    pcts = {}
                    for l in lojas_validas:
                        v = vendas_map.get(l, 0)
                        pcts[l] = round(v / total_vendido * 100, 4) if total_vendido else 0
                    resto = 100 - sum(pcts.values())
                    if lojas_validas and abs(resto) > 0.001:
                        pcts[lojas_validas[0]] = round(pcts.get(lojas_validas[0], 0) + resto, 4)
                else:
                    pcts = {l: round(100.0 / n, 4) for l in lojas_validas}
        else:
            return {"erro": f"Modo desconhecido: {modo}"}
        soma = sum(pcts.values())
        if abs(soma - 100) > 0.01:
            pcts[lojas_validas[0]] = round(pcts.get(lojas_validas[0], 0) + (100 - soma), 4)
        resultados = []
        distribuido = 0
        # Fix review final #3: rateio e' um SET ABSOLUTO, nao um credito. O
        # codigo pre-existente fazia `ON CONFLICT DO UPDATE SET quantidade =
        # $3`; rodar o mesmo rateio duas vezes tem que dar o mesmo estado
        # final, nao o dobro. Fix #6: tudo numa conexao/transacao so' —
        # chamar as versoes sincronas aqui dentro vazava um pool asyncpg por
        # loja.
        async with db.acquire() as conn:
            async with conn.transaction():
                for i, loja in enumerate(lojas_validas):
                    qtd = round(total * pcts[loja] / 100, 3)
                    if i == n - 1:
                        qtd = round(total - distribuido, 3)
                    distribuido += qtd
                    r = await ajustar_absoluto_async(conn, sku, loja, qtd, "ajuste_inventario")
                    if r.get("erro"):
                        raise SaldoError(f"{loja}: {r['erro']}")
                    resultados.append({"loja": loja, "quantidade": qtd, "percentual": pcts[loja]})
        return {"ok": True, "sku": sku, "total": total, "modo": modo,
                "lojas": resultados, "percentuais": pcts}
    try:
        return run_async(_go())
    except Exception as e:
        return {"erro": str(e)}

def sync_bling(sku: str, loja: str) -> dict:
    try:
        async def _go():
            db = await get_db()
            return await db.fetchval(
                "SELECT quantidade FROM estoque_lojas WHERE sku = $1 AND loja = $2", sku, loja)
        qtd = float(run_async(_go()) or 0)
        from bling_erp import sincronizar_estoque_para_bling
        return sincronizar_estoque_para_bling(sku, loja, qtd)
    except Exception as e:
        return {"erro": str(e)}

# ── Rotacao / Sugestao de Transferencia ──

def _sugestao_rotacao_via_repo(repo) -> list:
    """Implementacao usando Repository Pattern — isolada do banco."""
    async def _go():
        rows = await repo.listar_estoque_por_loja()
        por_sku = {}
        for r in rows:
            sku = r.sku
            if sku not in por_sku:
                por_sku[sku] = {"sku": sku, "nome": r.nome_produto, "lojas": []}
            por_sku[sku]["lojas"].append({"loja": r.loja, "quantidade": r.quantidade})
        sugestoes = []
        for sku, data in por_sku.items():
            lojas_data = data["lojas"]
            if len(lojas_data) < 2: continue
            lojas_data.sort(key=lambda x: x["quantidade"], reverse=True)
            excesso = lojas_data[0]; escassez = lojas_data[-1]
            if excesso["quantidade"] >= 5 and escassez["quantidade"] <= 2 and excesso["loja"] != escassez["loja"]:
                sugestoes.append({
                    "sku": sku, "nome": data["nome"],
                    "loja_excesso": excesso["loja"], "qtd_excesso": excesso["quantidade"],
                    "loja_escassez": escassez["loja"], "qtd_escassez": escassez["quantidade"],
                    "sugerir_transferir": max(1, min(excesso["quantidade"] // 2, excesso["quantidade"] - 5)),
                })
        sugestoes.sort(key=lambda x: x["qtd_excesso"], reverse=True)
        return sugestoes[:30]
    try: return run_async(_go())
    except Exception as e: return []


# fallback legacy: query direta se repo falhar
async def _legacy_sugestao_rotacao(db) -> list:
    rows = await db.fetch("""
        SELECT e.sku, e.loja, e.quantidade,
               COALESCE(c.descricao, e.sku) AS nome
        FROM estoque_lojas e
        LEFT JOIN catalogo_produtos c ON c.sku = e.sku
        WHERE e.quantidade > 0
        ORDER BY e.sku, e.quantidade DESC
    """)
    por_sku = {}
    for r in rows:
        sku = r["sku"]
        if sku not in por_sku:
            por_sku[sku] = {"sku": sku, "nome": r["nome"], "lojas": []}
        por_sku[sku]["lojas"].append({"loja": r["loja"], "quantidade": int(r["quantidade"])})
    sugestoes = []
    for sku, data in por_sku.items():
        lojas_data = data["lojas"]
        if len(lojas_data) < 2: continue
        lojas_data.sort(key=lambda x: x["quantidade"], reverse=True)
        excesso = lojas_data[0]; escassez = lojas_data[-1]
        if excesso["quantidade"] >= 5 and escassez["quantidade"] <= 2 and excesso["loja"] != escassez["loja"]:
            sugestoes.append({
                "sku": sku, "nome": data["nome"],
                "loja_excesso": excesso["loja"], "qtd_excesso": excesso["quantidade"],
                "loja_escassez": escassez["loja"], "qtd_escassez": escassez["quantidade"],
                "sugerir_transferir": max(1, min(excesso["quantidade"] // 2, excesso["quantidade"] - 5)),
            })
    sugestoes.sort(key=lambda x: x["qtd_excesso"], reverse=True)
    return sugestoes[:30]


def sugestao_rotacao() -> list:
    """Produtos com estoque desbalanceado entre lojas. Sugere transferencia.
    SOLID: DIP via EstoqueRepository — trocar Postgres por mock em testes."""
    try:
        from core.repositories_postgres import get_estoque_repo
        return _sugestao_rotacao_via_repo(get_estoque_repo())
    except Exception:
        pass
    # fallback: query direta
    async def _go():
        db = await get_db()
        return await _legacy_sugestao_rotacao(db)
    try: return run_async(_go())
    except Exception as e: return []


def _ensure_sugestoes_rotacao_table():
    async def _go():
        db = await get_db()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS estoque_sugestoes_rotacao (
                id SERIAL PRIMARY KEY,
                sku VARCHAR(50), nome VARCHAR(300),
                loja_excesso VARCHAR(50), qtd_excesso DECIMAL(12,3),
                loja_escassez VARCHAR(50), qtd_escassez DECIMAL(12,3),
                sugerir_transferir DECIMAL(12,3),
                gerado_em TIMESTAMP DEFAULT NOW()
            )
        """)
    try: run_async(_go())
    except Exception as e: log(AGENT, f"Erro tabela sugestoes rotacao: {e}")


def persistir_sugestoes_rotacao() -> dict:
    """Recalcula sugestao_rotacao() e persiste, substituindo as anteriores —
    antes era so' um GET recalculado sob demanda; agora fica pronto quando o
    gerente abre a tela, e dispara webhook se houver algum configurado.
    Chamado pelo job diario em core/scheduler.py."""
    _ensure_sugestoes_rotacao_table()
    sugestoes = sugestao_rotacao()
    async def _go():
        db = await get_db()
        await db.execute("DELETE FROM estoque_sugestoes_rotacao")
        for s in sugestoes:
            await db.execute("""
                INSERT INTO estoque_sugestoes_rotacao
                    (sku, nome, loja_excesso, qtd_excesso, loja_escassez, qtd_escassez, sugerir_transferir)
                VALUES ($1,$2,$3,$4,$5,$6,$7)
            """, s["sku"], s["nome"], s["loja_excesso"], s["qtd_excesso"],
                s["loja_escassez"], s["qtd_escassez"], s["sugerir_transferir"])
    try:
        run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro ao persistir sugestoes rotacao: {e}")
        return {"total": 0, "erro": str(e)}
    if sugestoes:
        try:
            from core.automacoes import disparar_webhooks
            disparar_webhooks("rotacao_sugerida", {"total": str(len(sugestoes))})
        except Exception:
            pass
    return {"total": len(sugestoes)}


def sugestoes_rotacao_persistidas() -> list:
    """Le as sugestoes ja calculadas pelo job diario, sem recalcular na hora."""
    _ensure_sugestoes_rotacao_table()
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT * FROM estoque_sugestoes_rotacao ORDER BY qtd_excesso DESC")
        return [dict(r, qtd_excesso=float(r["qtd_excesso"] or 0), qtd_escassez=float(r["qtd_escassez"] or 0),
                     sugerir_transferir=float(r["sugerir_transferir"] or 0)) for r in rows]
    try: return run_async(_go())
    except Exception as e: return []


# ── Fase 3: reconciliacao periodica loja (texto) -> loja_id ──

def reconciliar_loja_id() -> dict:
    """Preenche loja_id nas linhas que ainda so' tem o nome da loja (coluna
    texto) — cobre write-paths que nao dao pra dual-write direto (ex: o
    webhook do Bling em bling_erp.py, fora dos limites de edicao desta
    sessao). Chamado pelo job diario em core/scheduler.py. Idempotente:
    so' atualiza linhas com loja_id NULL."""
    async def _go():
        db = await get_db()
        totais = {}
        totais["estoque_lojas"] = await db.execute("""
            UPDATE estoque_lojas e SET loja_id = l.id
            FROM lojas l WHERE l.nome = e.loja AND e.loja_id IS NULL
        """)
        totais["estoque_movimentacoes"] = await db.execute("""
            UPDATE estoque_movimentacoes m SET loja_id = l.id
            FROM lojas l WHERE l.nome = m.loja AND m.loja_id IS NULL
        """)
        totais["estoque_contagens"] = await db.execute("""
            UPDATE estoque_contagens c SET loja_id = l.id
            FROM lojas l WHERE l.nome = c.loja AND c.loja_id IS NULL
        """)
        totais["estoque_transferencias_origem"] = await db.execute("""
            UPDATE estoque_transferencias t SET loja_origem_id = l.id
            FROM lojas l WHERE l.nome = t.loja_origem AND t.loja_origem_id IS NULL
        """)
        totais["estoque_transferencias_destino"] = await db.execute("""
            UPDATE estoque_transferencias t SET loja_destino_id = l.id
            FROM lojas l WHERE l.nome = t.loja_destino AND t.loja_destino_id IS NULL
        """)
        return totais
    try:
        return {"ok": True, "resultado": run_async(_go())}
    except Exception as e:
        log(AGENT, f"Erro reconciliar_loja_id: {e}")
        return {"ok": False, "erro": str(e)}
