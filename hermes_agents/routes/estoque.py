import psycopg2
import psycopg2.extras
from threading import Thread

from flask import Blueprint, request, jsonify
from core import FactoryConfig

estoque_bp = Blueprint("estoque", __name__, url_prefix="/api/estoque")
workflows_bp = Blueprint("workflows", __name__, url_prefix="/api/workflows")


def _db_sync():
    cfg = FactoryConfig.load()
    conn = psycopg2.connect(host=cfg.db_host, port=cfg.db_port, dbname=cfg.db_name,
                            user=cfg.db_user, password=cfg.db_password, connect_timeout=5)
    conn.set_session(autocommit=True)
    return conn


def _dicts(cur):
    cols = [d[0] for d in cur.description] if cur.description else []
    return [dict(zip(cols, row)) for row in cur.fetchall()]


# -- Estoque por loja/deposito --

@estoque_bp.route('/lojas', methods=['GET'])
def estoque_por_loja():
    """Lista estoque por deposito com filtro de loja e busca."""
    loja = request.args.get("loja", "")
    busca = request.args.get("busca", "").strip()
    pagina = request.args.get("pagina", 1, type=int)
    por_pagina = request.args.get("por_pagina", 30, type=int)
    try:
        conn = _db_sync()
        cur = conn.cursor()
        where = ["1=1"]
        if loja and loja != "todas":
            if loja.isdigit():
                where.append(f"e.loja = (SELECT nome FROM lojas WHERE id = {int(loja)})")
            else:
                where.append(f"e.loja = '{loja.replace(chr(39), chr(39)+chr(39))}'")
        if busca:
            where.append(f"(c.sku ILIKE '%{busca}%' OR c.descricao ILIKE '%{busca}%')")
        sql_where = " AND ".join(where)
        cur.execute(f"SELECT COUNT(*) FROM estoque_lojas e JOIN catalogo_produtos c ON c.sku = e.sku WHERE {sql_where}")
        total = cur.fetchone()[0]
        offset = (pagina - 1) * por_pagina
        cur.execute(f"""
            SELECT e.id, e.sku, c.descricao AS nome, e.loja, e.quantidade, e.data_atualizacao, e.sync_status
            FROM estoque_lojas e
            JOIN catalogo_produtos c ON c.sku = e.sku
            WHERE {sql_where}
            ORDER BY e.data_atualizacao DESC
            LIMIT {por_pagina} OFFSET {offset}
        """)
        rows = _dicts(cur)
        cur.close(); conn.close()
        return jsonify({"estoque": rows, "total": total, "pagina": pagina})
    except Exception as e:
        return jsonify({"erro": str(e), "estoque": [], "total": 0})


@estoque_bp.route('/lojas', methods=['PUT'])
def atualizar_estoque_loja():
    """Atualiza quantidade de estoque em uma loja/deposito. Two-way sync via fila offline."""
    dados = request.json or {}
    sku = dados.get("sku", "").strip()
    loja_nome = str(dados.get("loja", "")).strip()
    quantidade = dados.get("quantidade")
    sync_bling = str(dados.get("sync_bling", "1")) == "1"
    if not sku or not loja_nome or quantidade is None:
        return jsonify({"erro": "sku, loja e quantidade obrigatorios"}), 400
    try:
        conn = _db_sync()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO estoque_lojas (sku, loja, quantidade, data_atualizacao, sync_status)
            VALUES (%s, %s, %s, NOW(), 'pendente')
            ON CONFLICT (sku, loja) DO UPDATE SET quantidade = %s, data_atualizacao = NOW(), sync_status = 'pendente'
        """, (sku, loja_nome, float(quantidade), float(quantidade)))
        cur.close(); conn.close()
        result = {"ok": True, "sku": sku, "loja": loja_nome, "quantidade": quantidade}
        if sync_bling:
            from core.estoque import sync_para_bling
            bling_r = sync_para_bling(loja_nome, sku, float(quantidade))
            result["bling_sync"] = bling_r
        try:
            from shopee import sincronizar_estoque_todas_lojas_automatico
            Thread(target=lambda: sincronizar_estoque_todas_lojas_automatico(sku, float(quantidade)), daemon=True).start()
        except Exception:
            pass
        return jsonify(result)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@estoque_bp.route('/sync/processar', methods=['POST'])
def processar_fila_estoque():
    """Processa fila de sync pendente (retry offline)."""
    from core.estoque import processar_fila_sync
    limite = request.args.get("limite", 50, type=int)
    return jsonify(processar_fila_sync(limite))


@estoque_bp.route('/sync/status/<sku>', methods=['GET'])
def status_sync_sku(sku):
    """Status de sync para um SKU."""
    from core.estoque import status_sync_sku
    return jsonify(status_sync_sku(sku))


@estoque_bp.route('/entrada', methods=['POST'])
def estoque_entrada():
    """Registra entrada de estoque em uma loja."""
    from core.estoque import entrada as est_entrada
    dados = request.json or {}
    sku = str(dados.get("sku", "")).strip()
    loja = str(dados.get("loja", "")).strip()
    quantidade = dados.get("quantidade")
    motivo = str(dados.get("motivo", "")).strip()
    if not sku or not loja or quantidade is None:
        return jsonify({"erro": "sku, loja e quantidade obrigatorios"}), 400
    try:
        qtd = float(quantidade)
        if qtd <= 0:
            return jsonify({"erro": "quantidade deve ser > 0"}), 400
    except (ValueError, TypeError):
        return jsonify({"erro": "quantidade invalida"}), 400
    resultado = est_entrada(sku, loja, qtd, motivo)
    if not resultado.get("erro") and "atual" in resultado:
        try:
            from shopee import sincronizar_estoque_todas_lojas_automatico
            # ponytail: usa o saldo TOTAL apos o movimento (resultado["atual"]), nunca o
            # delta da entrada/saida — a Shopee espera o estoque absoluto, nao um incremento.
            Thread(target=lambda: sincronizar_estoque_todas_lojas_automatico(sku, resultado["atual"]), daemon=True).start()
        except Exception:
            pass
    return jsonify(resultado)


@estoque_bp.route('/saida', methods=['POST'])
def estoque_saida():
    """Registra saida de estoque de uma loja."""
    from core.estoque import saida as est_saida
    dados = request.json or {}
    sku = str(dados.get("sku", "")).strip()
    loja = str(dados.get("loja", "")).strip()
    quantidade = dados.get("quantidade")
    motivo = str(dados.get("motivo", "")).strip()
    if not sku or not loja or quantidade is None:
        return jsonify({"erro": "sku, loja e quantidade obrigatorios"}), 400
    try:
        qtd = float(quantidade)
        if qtd <= 0:
            return jsonify({"erro": "quantidade deve ser > 0"}), 400
    except (ValueError, TypeError):
        return jsonify({"erro": "quantidade invalida"}), 400
    resultado = est_saida(sku, loja, qtd, motivo)
    if not resultado.get("erro") and "atual" in resultado:
        try:
            from shopee import sincronizar_estoque_todas_lojas_automatico
            Thread(target=lambda: sincronizar_estoque_todas_lojas_automatico(sku, resultado["atual"]), daemon=True).start()
        except Exception:
            pass
    return jsonify(resultado)


@estoque_bp.route('/transferir', methods=['POST'])
def estoque_transferir():
    """Transfere estoque entre duas lojas/depositos."""
    from core.estoque import transferir as est_transferir
    dados = request.json or {}
    sku = str(dados.get("sku", "")).strip()
    origem = str(dados.get("origem", "")).strip()
    destino = str(dados.get("destino", "")).strip()
    quantidade = dados.get("quantidade")
    motivo = str(dados.get("motivo", "")).strip()
    if not sku or not origem or not destino or quantidade is None:
        return jsonify({"erro": "sku, origem, destino e quantidade obrigatorios"}), 400
    if origem == destino:
        return jsonify({"erro": "origem e destino devem ser diferentes"}), 400
    try:
        qtd = float(quantidade)
        if qtd <= 0:
            return jsonify({"erro": "quantidade deve ser > 0"}), 400
    except (ValueError, TypeError):
        return jsonify({"erro": "quantidade invalida"}), 400
    return jsonify(est_transferir(sku, origem, destino, qtd, motivo))


@estoque_bp.route('/sugestao-rotacao', methods=['GET'])
def estoque_sugestao_rotacao():
    """Sugere transferencias de estoque entre lojas com desbalanceamento."""
    from core.estoque import sugestao_rotacao
    return jsonify({"data": sugestao_rotacao()})


@estoque_bp.route('/ratear', methods=['POST'])
def estoque_ratear():
    from core.estoque import ratear as est_ratear
    dados = request.json or {}
    sku = str(dados.get("sku", "")).strip()
    total = dados.get("total")
    modo = str(dados.get("modo", "igual")).strip()
    lojas = dados.get("lojas")
    periodo_dias = dados.get("periodo_dias", 30)
    percentuais = dados.get("percentuais")
    if not sku or total is None:
        return jsonify({"erro": "sku e total obrigatorios"}), 400
    if modo not in ("igual", "proporcional"):
        return jsonify({"erro": "modo deve ser 'igual' ou 'proporcional'"}), 400
    try:
        return jsonify(est_ratear(sku, float(total), modo, lojas, int(periodo_dias), percentuais))
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@estoque_bp.route('/movimentacoes', methods=['GET'])
def estoque_movimentacoes():
    """Lista movimentacoes de estoque."""
    from core.estoque import movimentacoes as est_movs
    sku = request.args.get("sku", "")
    loja = request.args.get("loja", "")
    limite = request.args.get("limite", 50, type=int)
    return jsonify({"movimentacoes": est_movs(sku, loja, limite)})


@estoque_bp.route('/lote/<int:lote_id>/concluir', methods=['POST'])
def concluir_lote_estoque(lote_id):
    """Conclui lote e entra no estoque."""
    from ag_04_planejador import registrar_producao_concluida
    resultado = registrar_producao_concluida(lote_id)
    return jsonify(resultado)


# Workflows Fase 3

@workflows_bp.route('/lote_para_estoque/<int:lote_id>', methods=['POST'])
def workflow_lote_estoque(lote_id):
    """Workflow: Lote->Inspecao->Estoque."""
    from workflows_fase3 import workflow_lote_para_estoque
    resultado = workflow_lote_para_estoque(lote_id)
    return jsonify(resultado)


@workflows_bp.route('/defeito_para_capa', methods=['POST'])
def workflow_defeito_capa():
    """Workflow: Defeito->CAPA."""
    from workflows_fase3 import workflow_defeito_para_capa
    resultado = workflow_defeito_para_capa(
        request.json['inspecao_id'],
        request.json['defeito_codigo']
    )
    return jsonify(resultado)


@workflows_bp.route('/manutencao_molde/<int:molde_id>', methods=['POST'])
def workflow_manutencao_molde(molde_id):
    """Workflow: Manutencao->Producao."""
    from workflows_fase3 import workflow_manutencao_molde
    resultado = workflow_manutencao_molde(molde_id)
    return jsonify(resultado)


@workflows_bp.route('/cnc_concluido/<job_id>', methods=['POST'])
def workflow_cnc_concluido(job_id):
    """Workflow: CNC Job->Molde."""
    from workflows_fase3 import workflow_cnc_job_concluido
    resultado = workflow_cnc_job_concluido(job_id)
    return jsonify(resultado)


@workflows_bp.route('/agenda_manutencao', methods=['POST'])
def workflow_agenda_manutencao():
    """Workflow: Alertas->Agenda."""
    from workflows_fase3 import workflow_alerta_manutencao_para_agenda
    resultado = workflow_alerta_manutencao_para_agenda()
    return jsonify(resultado)
