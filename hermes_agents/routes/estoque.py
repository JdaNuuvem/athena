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


def _origem_requisicao() -> tuple:
    return request.remote_addr, request.headers.get("User-Agent", "")[:300]


# -- Estoque por loja/deposito --

@estoque_bp.route('/lojas', methods=['GET'])
def estoque_por_loja():
    """Lista estoque por deposito com filtro de loja e busca."""
    from core.rbac import usuario_atual_da_request
    from core.rbac_lojas import lojas_permitidas
    loja = request.args.get("loja", "")
    busca = request.args.get("busca", "").strip()
    pagina = request.args.get("pagina", 1, type=int)
    por_pagina = request.args.get("por_pagina", 30, type=int)
    try:
        conn = _db_sync()
        cur = conn.cursor()
        where = ["1=1"]
        params = []
        if loja and loja != "todas":
            from core.lojas import loja_efetiva_sync
            loja = loja_efetiva_sync(cur, loja)
            where.append("e.loja = %s")
            params.append(loja)
        else:
            # Fase 4 (RBAC por loja, modo suave): so' restringe quando o
            # usuario tem vinculo ativo em loja_responsaveis. Sem vinculo,
            # comportamento identico ao de antes (ve tudo).
            permitidas = lojas_permitidas(usuario_atual_da_request().get("user_id"))
            if permitidas is not None:
                where.append("e.loja_id = ANY(%s)")
                params.append(permitidas)
        if busca:
            where.append("(c.sku ILIKE %s OR c.descricao ILIKE %s)")
            params.extend([f"%{busca}%", f"%{busca}%"])
        sql_where = " AND ".join(where)
        cur.execute(f"SELECT COUNT(*) FROM estoque_lojas e JOIN catalogo_produtos c ON c.sku = e.sku WHERE {sql_where}", params)
        total = cur.fetchone()[0]
        offset = (pagina - 1) * por_pagina
        cur.execute(f"""
            SELECT e.id, e.sku, c.descricao AS nome, e.loja, e.quantidade, e.data_atualizacao, e.sync_status
            FROM estoque_lojas e
            JOIN catalogo_produtos c ON c.sku = e.sku
            WHERE {sql_where}
            ORDER BY e.data_atualizacao DESC
            LIMIT %s OFFSET %s
        """, params + [por_pagina, offset])
        rows = _dicts(cur)
        cur.close(); conn.close()
        return jsonify({"estoque": rows, "total": total, "pagina": pagina})
    except Exception as e:
        return jsonify({"erro": str(e), "estoque": [], "total": 0})


@estoque_bp.route('/lojas', methods=['PUT'])
def atualizar_estoque_loja():
    """Atualiza quantidade de estoque em uma loja/deposito. Two-way sync via fila offline."""
    from core.estoque import ajustar_absoluto
    from core.rbac import usuario_atual_da_request
    dados = request.json or {}
    sku = dados.get("sku", "").strip()
    loja_nome = str(dados.get("loja", "")).strip()
    quantidade = dados.get("quantidade")
    sync_bling = str(dados.get("sync_bling", "1")) == "1"
    if not sku or not loja_nome or quantidade is None:
        return jsonify({"erro": "sku, loja e quantidade obrigatorios"}), 400
    # A alteracao de saldo e o sync com marketplaces sao tratados em blocos
    # separados de proposito: um erro de sync NAO pode parecer com um erro de
    # saldo pro cliente — o ajuste ja foi commitado nesse ponto (review #4).
    try:
        # Esta rota gravava estoque_lojas por SQL cru (psycopg2), bypassando
        # core.estoque — era por isso que a Fase 3 precisou repetir aqui a
        # resolucao loja->loja_id. Com a Fase 1 ela passa por
        # ajustar_absoluto -> mover_saldo, que ja grava loja_id no ledger, e o
        # trigger de espelho propaga loja_id pra estoque_lojas: o dual-write
        # continua acontecendo, so nao e' mais responsabilidade da rota.
        usuario = usuario_atual_da_request()
        ip, dispositivo = _origem_requisicao()
        resultado = ajustar_absoluto(sku, loja_nome, float(quantidade), "ajuste_inventario",
                                      usuario["user_id"], usuario["nome"], ip, dispositivo)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    if resultado.get("erro"):
        return jsonify(resultado), 500
    if sync_bling:
        # `core.estoque.sync_para_bling` nunca existiu (ImportError em toda PUT
        # normal, ja que sync_bling default e' "1"). A funcao real e'
        # bling_erp.sincronizar_estoque_para_bling(sku, loja, quantidade) —
        # note tambem a ordem dos argumentos, que estava trocada na chamada
        # antiga.
        try:
            from bling_erp import sincronizar_estoque_para_bling
            resultado["bling_sync"] = sincronizar_estoque_para_bling(sku, loja_nome, float(quantidade))
        except Exception as e:
            resultado["bling_sync"] = {"erro": str(e)}
    try:
        from shopee import sincronizar_estoque_todas_lojas_automatico
        Thread(target=lambda: sincronizar_estoque_todas_lojas_automatico(sku, float(quantidade)), daemon=True).start()
    except Exception:
        pass
    return jsonify(resultado)


@estoque_bp.route('/sync/processar', methods=['POST'])
def processar_fila_estoque():
    """Fila de sync offline nunca foi implementada — `core.estoque.processar_fila_sync`
    nao existe (e nunca existiu; o endpoint quebrava com ImportError/500 HTML).
    Responde 501 explicito ate que a fila seja implementada de fato.
    TODO(follow-up): implementar fila de retry de sync de estoque."""
    return jsonify({"erro": "fila de sync de estoque nao implementada",
                    "detalhe": "endpoint reservado; nenhuma fila offline existe hoje"}), 501


@estoque_bp.route('/sync/status/<sku>', methods=['GET'])
def status_sync_sku(sku):
    """Idem processar_fila_estoque: `core.estoque.status_sync_sku` nao existe.
    TODO(follow-up): expor status real quando a fila de sync existir."""
    return jsonify({"sku": sku, "erro": "status de sync de estoque nao implementado",
                    "detalhe": "endpoint reservado; nenhuma fila offline existe hoje"}), 501


@estoque_bp.route('/buscar-codigo', methods=['GET'])
def estoque_buscar_codigo():
    """Localiza um produto por codigo de barras OU sku exato — usado pelo fluxo
    de entrada de estoque via leitor de codigo de barras (bipa e localiza)."""
    codigo = request.args.get("codigo", "").strip()
    if not codigo:
        return jsonify({"erro": "codigo obrigatorio"}), 400
    conn = _db_sync()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT sku, descricao, codigo_barras,
               COALESCE((SELECT SUM(quantidade) FROM estoque_lojas WHERE sku = c.sku), 0) AS estoque_total
        FROM catalogo_produtos c
        WHERE codigo_barras = %s OR sku = %s
        LIMIT 1
    """, (codigo, codigo))
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row:
        return jsonify({"erro": "produto nao encontrado", "codigo": codigo}), 404
    return jsonify(dict(row, estoque_total=float(row["estoque_total"])))


def _sync_shopee_async(sku, atual):
    try:
        from shopee import sincronizar_estoque_todas_lojas_automatico
        # ponytail: usa o saldo TOTAL apos o movimento, nunca o delta — a Shopee
        # espera o estoque absoluto, nao um incremento.
        Thread(target=lambda: sincronizar_estoque_todas_lojas_automatico(sku, atual), daemon=True).start()
    except Exception:
        pass


@estoque_bp.route('/motivos', methods=['GET'])
def estoque_motivos():
    """Listas fechadas de motivo por tipo de movimento — usadas para popular
    os dropdowns no frontend (texto livre vira ruido que ninguem analisa)."""
    from core.estoque import MOTIVOS_ENTRADA, MOTIVOS_SAIDA, MOTIVOS_TRANSFERENCIA, LIMITE_APROVACAO_UNIDADES
    return jsonify({
        "entrada": MOTIVOS_ENTRADA, "saida": MOTIVOS_SAIDA, "transferencia": MOTIVOS_TRANSFERENCIA,
        "limite_aprovacao_unidades": LIMITE_APROVACAO_UNIDADES,
    })


@estoque_bp.route('/entrada', methods=['POST'])
def estoque_entrada():
    """Registra entrada de estoque em uma loja. Sempre livre (sem alcada) —
    recebimento de fornecedor costuma vir em lotes grandes e e' baixo risco."""
    from core.estoque import entrada as est_entrada
    from core.rbac import usuario_atual_da_request
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
    usuario = usuario_atual_da_request()
    ip, dispositivo = _origem_requisicao()
    resultado = est_entrada(sku, loja, qtd, motivo, usuario["user_id"], usuario["nome"], ip, dispositivo)
    if not resultado.get("erro") and "atual" in resultado:
        _sync_shopee_async(sku, resultado["atual"])
    return jsonify(resultado)


@estoque_bp.route('/saida', methods=['POST'])
def estoque_saida():
    """Registra saida de estoque de uma loja. Acima do limite de unidades,
    fica pendente ate um Gerente/Admin aprovar (ver /aprovacoes)."""
    from core.estoque import saida as est_saida
    from core.estoque_aprovacoes import precisa_aprovacao, solicitar as solicitar_aprovacao
    from core.rbac import usuario_atual_da_request
    dados = request.json or {}
    sku = str(dados.get("sku", "")).strip()
    loja = str(dados.get("loja", "")).strip()
    quantidade = dados.get("quantidade")
    motivo = str(dados.get("motivo", "")).strip()
    if not sku or not loja or quantidade is None or not motivo:
        return jsonify({"erro": "sku, loja, quantidade e motivo sao obrigatorios"}), 400
    try:
        qtd = float(quantidade)
        if qtd <= 0:
            return jsonify({"erro": "quantidade deve ser > 0"}), 400
    except (ValueError, TypeError):
        return jsonify({"erro": "quantidade invalida"}), 400
    usuario = usuario_atual_da_request()
    ip, dispositivo = _origem_requisicao()
    if precisa_aprovacao(qtd):
        return jsonify(solicitar_aprovacao(sku, loja, qtd, motivo, usuario["user_id"], usuario["nome"], ip, dispositivo))
    resultado = est_saida(sku, loja, qtd, motivo, usuario["user_id"], usuario["nome"], ip, dispositivo)
    if not resultado.get("erro") and "atual" in resultado:
        _sync_shopee_async(sku, resultado["atual"])
    return jsonify(resultado)


@estoque_bp.route('/aprovacoes', methods=['GET'])
def estoque_listar_aprovacoes():
    from core.estoque_aprovacoes import listar
    status = request.args.get("status", "pendente")
    loja = request.args.get("loja", "")
    return jsonify({"aprovacoes": listar(status, loja)})


@estoque_bp.route('/aprovacoes/<int:aprovacao_id>/aprovar', methods=['POST'])
def estoque_aprovar(aprovacao_id):
    from core.estoque_aprovacoes import aprovar as aprovar_saida
    from core.rbac import requer_permissao, usuario_atual_da_request
    @requer_permissao("estoque.aprovar")
    def _go():
        usuario = usuario_atual_da_request()
        ip, dispositivo = _origem_requisicao()
        resultado = aprovar_saida(aprovacao_id, usuario["user_id"], usuario["nome"], ip, dispositivo)
        if not resultado.get("erro") and "atual" in resultado:
            _sync_shopee_async(resultado["sku"], resultado["atual"])
        return jsonify(resultado)
    return _go()


@estoque_bp.route('/aprovacoes/<int:aprovacao_id>/rejeitar', methods=['POST'])
def estoque_rejeitar(aprovacao_id):
    from core.estoque_aprovacoes import rejeitar as rejeitar_saida
    from core.rbac import requer_permissao, usuario_atual_da_request
    @requer_permissao("estoque.aprovar")
    def _go():
        dados = request.json or {}
        usuario = usuario_atual_da_request()
        return jsonify(rejeitar_saida(aprovacao_id, usuario["user_id"], usuario["nome"], str(dados.get("motivo_rejeicao", ""))))
    return _go()


@estoque_bp.route('/transferir', methods=['POST'])
def estoque_transferir():
    """Solicita transferencia entre duas lojas. Acima do limite de unidades,
    fica pendente de aprovacao antes de debitar a origem. Sempre exige
    confirmacao da loja destino antes de creditar (ver /transferencias/<id>/confirmar)."""
    from core.estoque_transferencias import solicitar as solicitar_transferencia
    from core.rbac import usuario_atual_da_request
    dados = request.json or {}
    sku = str(dados.get("sku", "")).strip()
    origem = str(dados.get("origem", "")).strip()
    destino = str(dados.get("destino", "")).strip()
    quantidade = dados.get("quantidade")
    motivo = str(dados.get("motivo", "")).strip()
    if not sku or not origem or not destino or quantidade is None or not motivo:
        return jsonify({"erro": "sku, origem, destino, quantidade e motivo sao obrigatorios"}), 400
    try:
        qtd = float(quantidade)
        if qtd <= 0:
            return jsonify({"erro": "quantidade deve ser > 0"}), 400
    except (ValueError, TypeError):
        return jsonify({"erro": "quantidade invalida"}), 400
    usuario = usuario_atual_da_request()
    ip, dispositivo = _origem_requisicao()
    return jsonify(solicitar_transferencia(sku, origem, destino, qtd, motivo, usuario["user_id"], usuario["nome"], ip, dispositivo))


@estoque_bp.route('/transferencias', methods=['GET'])
def estoque_listar_transferencias():
    from core.estoque_transferencias import listar
    from core.rbac import usuario_atual_da_request
    from core.rbac_lojas import lojas_permitidas
    status = request.args.get("status", "")
    loja = request.args.get("loja", "")
    permitidas = None if loja else lojas_permitidas(usuario_atual_da_request().get("user_id"))
    return jsonify({"transferencias": listar(status, loja, loja_ids=permitidas)})


@estoque_bp.route('/transferencias/<int:transferencia_id>/aprovar', methods=['POST'])
def estoque_transferencia_aprovar(transferencia_id):
    from core.estoque_transferencias import aprovar as aprovar_transf
    from core.rbac import requer_permissao, usuario_atual_da_request
    @requer_permissao("estoque.aprovar")
    def _go():
        usuario = usuario_atual_da_request()
        ip, dispositivo = _origem_requisicao()
        return jsonify(aprovar_transf(transferencia_id, usuario["user_id"], usuario["nome"], ip, dispositivo))
    return _go()


@estoque_bp.route('/transferencias/<int:transferencia_id>/rejeitar', methods=['POST'])
def estoque_transferencia_rejeitar(transferencia_id):
    from core.estoque_transferencias import rejeitar as rejeitar_transf
    from core.rbac import requer_permissao, usuario_atual_da_request
    @requer_permissao("estoque.aprovar")
    def _go():
        dados = request.json or {}
        usuario = usuario_atual_da_request()
        ip, dispositivo = _origem_requisicao()
        return jsonify(rejeitar_transf(transferencia_id, usuario["user_id"], usuario["nome"], str(dados.get("motivo_rejeicao", "")), ip, dispositivo))
    return _go()


@estoque_bp.route('/transferencias/<int:transferencia_id>/confirmar', methods=['POST'])
def estoque_transferencia_confirmar(transferencia_id):
    """A loja destino confirma quanto realmente chegou — pode ser diferente
    do solicitado (extravio/erro no caminho vira discrepancia registrada)."""
    from core.estoque_transferencias import confirmar as confirmar_transf
    from core.rbac import usuario_atual_da_request
    dados = request.json or {}
    quantidade_recebida = dados.get("quantidade_recebida")
    if quantidade_recebida is None:
        return jsonify({"erro": "quantidade_recebida obrigatoria"}), 400
    try:
        qtd = float(quantidade_recebida)
        if qtd < 0:
            return jsonify({"erro": "quantidade_recebida nao pode ser negativa"}), 400
    except (ValueError, TypeError):
        return jsonify({"erro": "quantidade_recebida invalida"}), 400
    usuario = usuario_atual_da_request()
    ip, dispositivo = _origem_requisicao()
    return jsonify(confirmar_transf(transferencia_id, usuario["user_id"], usuario["nome"], qtd, ip, dispositivo))


@estoque_bp.route('/contagem/sugestoes', methods=['GET'])
def estoque_contagem_sugestoes():
    from core.estoque_contagem import sugestoes
    loja = request.args.get("loja", "")
    return jsonify({"sugestoes": sugestoes(loja)})


@estoque_bp.route('/contagem/registrar', methods=['POST'])
def estoque_contagem_registrar():
    from core.estoque_contagem import registrar
    from core.rbac import usuario_atual_da_request
    dados = request.json or {}
    sku = str(dados.get("sku", "")).strip()
    loja = str(dados.get("loja", "")).strip()
    quantidade_contada = dados.get("quantidade_contada")
    if not sku or not loja or quantidade_contada is None:
        return jsonify({"erro": "sku, loja e quantidade_contada sao obrigatorios"}), 400
    try:
        qtd = float(quantidade_contada)
        if qtd < 0:
            return jsonify({"erro": "quantidade_contada nao pode ser negativa"}), 400
    except (ValueError, TypeError):
        return jsonify({"erro": "quantidade_contada invalida"}), 400
    usuario = usuario_atual_da_request()
    return jsonify(registrar(sku, loja, qtd, usuario["user_id"], usuario["nome"]))


@estoque_bp.route('/contagem/historico', methods=['GET'])
def estoque_contagem_historico():
    from core.estoque_contagem import historico
    from core.rbac import usuario_atual_da_request
    from core.rbac_lojas import lojas_permitidas
    loja = request.args.get("loja", "")
    permitidas = None if loja else lojas_permitidas(usuario_atual_da_request().get("user_id"))
    return jsonify({"historico": historico(loja, loja_ids=permitidas)})


@estoque_bp.route('/relatorio-discrepancias', methods=['GET'])
def estoque_relatorio_discrepancias():
    from core.estoque_relatorios import por_loja, por_operador
    dias = request.args.get("dias", 30, type=int)
    return jsonify({"por_loja": por_loja(dias), "por_operador": por_operador(dias)})


@estoque_bp.route('/sugestao-rotacao', methods=['GET'])
def estoque_sugestao_rotacao():
    """Sugere transferencias de estoque entre lojas com desbalanceamento (recalcula na hora)."""
    from core.estoque import sugestao_rotacao
    return jsonify({"data": sugestao_rotacao()})


@estoque_bp.route('/sugestao-rotacao/persistidas', methods=['GET'])
def estoque_sugestao_rotacao_persistidas():
    """Le as sugestoes ja calculadas pelo job diario (nao recalcula na hora)."""
    from core.estoque import sugestoes_rotacao_persistidas
    return jsonify({"data": sugestoes_rotacao_persistidas()})


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
    from core.rbac import usuario_atual_da_request
    from core.rbac_lojas import lojas_permitidas
    sku = request.args.get("sku", "")
    loja = request.args.get("loja", "")
    limite = request.args.get("limite", 50, type=int)
    permitidas = None if loja else lojas_permitidas(usuario_atual_da_request().get("user_id"))
    return jsonify({"movimentacoes": est_movs(sku, loja, limite, loja_ids=permitidas)})


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
