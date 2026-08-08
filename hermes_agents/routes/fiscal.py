from flask import Blueprint, request, jsonify
from core import run_async, get_db
from core.rbac import requer_permissao

fiscal_bp = Blueprint("fiscal", __name__, url_prefix="/api/fiscal")


@fiscal_bp.route("/dashboard", methods=["GET"])
def fiscal_dashboard():
    from core.fiscal import dashboard

    @requer_permissao("fiscal.ver")
    def _go():
        return jsonify(dashboard())
    return _go()


@fiscal_bp.route("/<tabela>", methods=["GET"])
def fiscal_list(tabela):
    from core.fiscal import list as fl, listar_filtrado, TABLES
    from core.rbac import requer_permissao
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    # ponytail: nenhuma rota de LEITURA deste blueprint checava permissao —
    # so' create/update/delete usavam requer_permissao. Qualquer usuario
    # autenticado (vendedor, atendente, operador PDV) podia listar notas
    # fiscais, tributos e contas a receber/pagar do Bling — dado financeiro
    # sensivel. "fiscal.ver", mesmo padrao usado em crm.ver/estoque.ver.
    @requer_permissao("fiscal.ver")
    def _go():
        data_inicio = request.args.get("data_inicio", "")
        data_fim = request.args.get("data_fim", "")
        dias = request.args.get("dias", 0, type=int)
        if data_inicio or data_fim or dias:
            return jsonify(listar_filtrado(tabela, data_inicio, data_fim, dias))
        return jsonify({"data": fl(tabela)})
    return _go()


@fiscal_bp.route("/<tabela>", methods=["POST"])
def fiscal_create(tabela):
    from core.fiscal import create as fc, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}

    @requer_permissao("fiscal.criar")
    def _go():
        return jsonify(fc(tabela, data))
    return _go()


@fiscal_bp.route("/<tabela>/<int:id>", methods=["GET"])
def fiscal_get(tabela, id):
    from core.fiscal import get as fg, TABLES
    from core.rbac import requer_permissao
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    @requer_permissao("fiscal.ver")
    def _go():
        return jsonify(fg(tabela, id))
    return _go()


@fiscal_bp.route("/<tabela>/<int:id>", methods=["PUT"])
def fiscal_update(tabela, id):
    from core.fiscal import update as fu, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}

    @requer_permissao("fiscal.editar")
    def _go():
        return jsonify(fu(tabela, id, data))
    return _go()


@fiscal_bp.route("/<tabela>/<int:id>", methods=["DELETE"])
def fiscal_delete(tabela, id):
    from core.fiscal import get as fg, delete as fd, TABLES
    if tabela not in TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    @requer_permissao("fiscal.excluir")
    def _go():
        from core.seguranca import auditar_exclusao
        dados_antes = fg(tabela, id)
        resultado = fd(tabela, id)
        if not resultado.get("error"):
            auditar_exclusao("fiscal", tabela, id, dados_antes if not dados_antes.get("error") else None)
        return jsonify(resultado)
    return _go()


@fiscal_bp.route("/obrigacoes/proximas", methods=["GET"])
def fiscal_obrigacoes_proximas():
    from core.fiscal import obrigacoes_proximas

    @requer_permissao("fiscal.ver")
    def _go():
        dias = request.args.get("dias", 30, type=int)
        return jsonify({"data": obrigacoes_proximas(dias)})
    return _go()


@fiscal_bp.route("/obrigacoes/atrasadas", methods=["GET"])
def fiscal_obrigacoes_atrasadas():
    from core.fiscal import obrigacoes_atrasadas

    @requer_permissao("fiscal.ver")
    def _go():
        return jsonify({"data": obrigacoes_atrasadas()})
    return _go()


@fiscal_bp.route("/obrigacoes/<int:id>/baixar", methods=["POST"])
def fiscal_baixar_obrigacao(id):
    from core.fiscal import baixar_obrigacao

    @requer_permissao("fiscal.editar")
    def _go():
        return jsonify(baixar_obrigacao(id))
    return _go()


@fiscal_bp.route("/sync/notas-fiscais", methods=["POST"])
def fiscal_sync_nf():
    from core.fiscal import sincronizar_notas_fiscais_bling
    from core.rbac import requer_permissao
    # ponytail: sem NENHUMA checagem — qualquer usuario autenticado podia
    # disparar sync com o Bling via chamada direta a API (o botao "Sync Bling"
    # do frontend ja tentava um <Can permission="fiscal:edit">, mas o codigo
    # nao batia com o formato real de permissao — "fiscal.editar" — entao o
    # botao ficava invisivel pra todo mundo, mas a rota continuava aberta).
    @requer_permissao("fiscal.editar")
    def _go():
        data = request.json or {}
        return jsonify(sincronizar_notas_fiscais_bling(
            pagina=data.get("pagina", 1), limite=data.get("limite", 100),
            pular=data.get("pular", 0)))
    return _go()


@fiscal_bp.route("/sync/contas-receber", methods=["POST"])
def fiscal_sync_cr():
    from core.fiscal import sincronizar_contas_receber_bling

    @requer_permissao("fiscal.editar")
    def _go():
        data = request.json or {}
        return jsonify(sincronizar_contas_receber_bling(
            pagina=data.get("pagina", 1), limite=data.get("limite", 100)))
    return _go()


@fiscal_bp.route("/sync/contas-pagar", methods=["POST"])
def fiscal_sync_cp():
    from core.fiscal import sincronizar_contas_pagar_bling

    @requer_permissao("fiscal.editar")
    def _go():
        data = request.json or {}
        return jsonify(sincronizar_contas_pagar_bling(
            pagina=data.get("pagina", 1), limite=data.get("limite", 100)))
    return _go()


@fiscal_bp.route("/sync/tudo", methods=["POST"])
def fiscal_sync_tudo():
    from core.fiscal import sincronizar_tudo_bling

    @requer_permissao("fiscal.editar")
    def _go():
        return jsonify(sincronizar_tudo_bling())
    return _go()


@fiscal_bp.route("/notas-fiscais/<int:id>/itens", methods=["GET"])
def fiscal_nf_itens(id):
    from core.fiscal import itens_da_nota
    from core.rbac import requer_permissao

    @requer_permissao("fiscal.ver")
    def _go():
        return jsonify({"data": itens_da_nota(id)})
    return _go()


@fiscal_bp.route("/notas-fiscais/<int:id>/impostos", methods=["GET"])
def fiscal_nf_impostos(id):
    from core.fiscal import impostos_da_nota
    from core.rbac import requer_permissao

    @requer_permissao("fiscal.ver")
    def _go():
        return jsonify({"data": impostos_da_nota(id)})
    return _go()


@fiscal_bp.route("/apuracao", methods=["GET"])
def fiscal_apuracao():
    from core.fiscal import apuracao_impostos

    @requer_permissao("fiscal.ver")
    def _go():
        ano = request.args.get("ano", type=int)
        mes = request.args.get("mes", type=int)
        dias = request.args.get("dias", 365, type=int)
        return jsonify(apuracao_impostos(ano, mes, dias))
    return _go()


@fiscal_bp.route("/apuracao/fechar", methods=["POST"])
def fiscal_apuracao_fechar():
    from core.fiscal import fechar_apuracao
    from core.rbac import usuario_atual_da_request
    data = request.json or {}
    ano = data.get("ano")
    mes = data.get("mes")

    @requer_permissao("fiscal.editar")
    def _go():
        if not ano or not mes:
            return jsonify({"error": "ano e mes sao obrigatorios"}), 400
        usuario = usuario_atual_da_request()
        resultado = fechar_apuracao(int(ano), int(mes), usuario.get("email") or usuario.get("nome") or "")
        return jsonify(resultado), (400 if resultado.get("error") else 200)
    return _go()


@fiscal_bp.route("/apuracao/reabrir", methods=["POST"])
def fiscal_apuracao_reabrir():
    from core.fiscal import reabrir_apuracao
    data = request.json or {}
    ano = data.get("ano")
    mes = data.get("mes")

    # reabrir desfaz um fechamento fiscal ja registrado — mais sensivel que
    # uma edicao comum, mesmo nivel de permissao usado pra excluir registros.
    @requer_permissao("fiscal.excluir")
    def _go():
        if not ano or not mes:
            return jsonify({"error": "ano e mes sao obrigatorios"}), 400
        resultado = reabrir_apuracao(int(ano), int(mes))
        return jsonify(resultado), (400 if resultado.get("error") else 200)
    return _go()


@fiscal_bp.route("/apuracao/fechamentos", methods=["GET"])
def fiscal_apuracao_fechamentos():
    from core.fiscal import listar_fechamentos

    @requer_permissao("fiscal.ver")
    def _go():
        return jsonify({"data": listar_fechamentos()})
    return _go()


@fiscal_bp.route("/obrigacoes/alertas", methods=["GET"])
def fiscal_alertas():
    from core.entidades import gerar_alertas_obrigacoes

    @requer_permissao("fiscal.ver")
    def _go():
        return jsonify(gerar_alertas_obrigacoes())
    return _go()
