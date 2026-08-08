"""Rotas REST da Reconciliacao i9Logic — /api/integrations/i9logic/*"""
from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao, usuario_atual_da_request
from core.i9logic import (
    criar_mapeamento, listar_mapeamentos, executar_matching_automatico,
    executar_coleta_todas_filiais, listar_itens_para_revisao, marcar_revisado,
    aplicar_ajuste_divergencia, comparar_com_athena, seed_inicial,
    estoque_fisico_por_loja,
)
from core.i9logic_catalogo import sincronizar_catalogo_i9logic
from core.i9logic_vendas import sincronizar_pedidos_i9logic
from core.lojas import obter as obter_loja

i9logic_bp = Blueprint("i9logic", __name__, url_prefix="/api/integrations/i9logic")


@i9logic_bp.route("/depara", methods=["GET"])
def i9logic_listar_depara():
    @requer_permissao("estoque.ver")
    def _go():
        return jsonify({"data": listar_mapeamentos(request.args.get("tipo"))})
    return _go()


@i9logic_bp.route("/depara", methods=["POST"])
def i9logic_criar_depara():
    @requer_permissao("estoque.editar")
    def _go():
        dados = request.json or {}
        return jsonify(criar_mapeamento(
            dados.get("tipo", ""), dados.get("id_i9logic", ""), dados.get("codigo_athena", "")))
    return _go()


@i9logic_bp.route("/depara/matching", methods=["POST"])
def i9logic_matching_automatico():
    @requer_permissao("estoque.editar")
    def _go():
        dados = request.json or {}
        return jsonify(executar_matching_automatico(
            dados.get("tipo", ""), dados.get("pares", [])))
    return _go()


@i9logic_bp.route("/coletar", methods=["POST"])
def i9logic_coletar():
    @requer_permissao("estoque.editar")
    def _go():
        return jsonify(executar_coleta_todas_filiais())
    return _go()


@i9logic_bp.route("/divergencias", methods=["GET"])
def i9logic_listar_divergencias():
    @requer_permissao("estoque.ver")
    def _go():
        return jsonify({"data": listar_itens_para_revisao()})
    return _go()


@i9logic_bp.route("/divergencias/<int:snapshot_id>/resolver", methods=["POST"])
def i9logic_resolver_divergencia(snapshot_id):
    """Aceita a divergencia como conhecida — so' marca revisado, nunca ajusta saldo."""
    @requer_permissao("estoque.editar")
    def _go():
        return jsonify(marcar_revisado(snapshot_id))
    return _go()


@i9logic_bp.route("/divergencias/<int:snapshot_id>/ajustar", methods=["POST"])
def i9logic_ajustar_divergencia(snapshot_id):
    """Ajusta o saldo Athena pro fisico coletado, via ledger formal (Fase 1)."""
    @requer_permissao("estoque.editar")
    def _go():
        dados = request.get_json(silent=True) or {}
        usuario = usuario_atual_da_request()
        resultado = aplicar_ajuste_divergencia(
            snapshot_id, usuario.get("user_id"), usuario.get("nome", ""),
            confirmar_zerar=bool(dados.get("confirmar_zerar", False)))
        if resultado.get("erro"):
            erro = resultado["erro"]
            eh_nao_encontrado = "nao encontrado" in erro or "sem snapshot" in erro
            return jsonify(resultado), (404 if eh_nao_encontrado else 400)
        return jsonify(resultado)
    return _go()


@i9logic_bp.route("/comparar", methods=["GET"])
def i9logic_comparar():
    @requer_permissao("estoque.ver")
    def _go():
        return jsonify(comparar_com_athena(request.args.get("sku", ""), request.args.get("loja", "")))
    return _go()


@i9logic_bp.route("/divergencias-athena", methods=["GET"])
def i9logic_divergencias_athena():
    """Comparacao Athena x i9Logic EM LOTE — diferente de /divergencias
    (fisico x contabil, interno ao i9Logic). Ver core.i9logic.listar_divergencias_athena."""
    @requer_permissao("estoque.ver")
    def _go():
        from core.i9logic import listar_divergencias_athena
        return jsonify(listar_divergencias_athena(request.args.get("loja", "")))
    return _go()


@i9logic_bp.route("/divergencias-athena/ajustar", methods=["POST"])
def i9logic_divergencias_athena_ajustar():
    """Ajusta o saldo Athena pro fisico i9Logic coletado — mesma direcao de
    aplicar_ajuste_divergencia, mas por (sku, loja) direto (esta comparacao
    nao tem snapshot_id proprio, e' calculada em memoria)."""
    @requer_permissao("estoque.editar")
    def _go():
        from core.estoque import ajustar_absoluto
        dados = request.get_json(silent=True) or {}
        sku = str(dados.get("sku", "")).strip()
        loja = str(dados.get("loja", "")).strip()
        quantidade = dados.get("quantidade")
        if not sku or not loja or quantidade is None:
            return jsonify({"erro": "sku, loja e quantidade sao obrigatorios"}), 400
        try:
            quantidade_float = float(quantidade)
        except (TypeError, ValueError):
            return jsonify({"erro": "quantidade deve ser um numero"}), 400
        # Guarda de frescor: `quantidade` vem da lista em cache no navegador e
        # pode estar horas desatualizada. O lado Shopee tem a guarda equivalente
        # (shopee.divergencia._snapshot_mais_recente_id); aqui nao ha' snapshot_id
        # pra comparar, entao rele' o fisico do snapshot e confere. Fail-closed:
        # erro de banco bloqueia o ajuste, nunca aplica sem ter checado.
        from core.i9logic import qtd_fisico_mais_recente
        try:
            qtd_snapshot = qtd_fisico_mais_recente(sku, loja)
        except Exception as e:
            return jsonify({"erro": f"falha ao verificar frescor do snapshot i9Logic: {e}"}), 400
        if qtd_snapshot is None:
            return jsonify({"erro": f"sem snapshot i9Logic para o sku '{sku}' na loja '{loja}' - "
                                    f"recarregue a pagina"}), 400
        if round(float(qtd_snapshot), 3) != round(quantidade_float, 3):
            return jsonify({"erro": f"dados desatualizados: o fisico i9Logic de '{sku}' agora e' "
                                    f"{float(qtd_snapshot)} (a tela enviou {quantidade_float}) - "
                                    f"recarregue a pagina e tente de novo"}), 409
        usuario = usuario_atual_da_request()
        resultado = ajustar_absoluto(
            sku, loja, quantidade_float, motivo="ajuste_inventario",
            usuario_id=usuario.get("user_id"), usuario_nome=usuario.get("nome", ""))
        if resultado.get("erro"):
            return jsonify(resultado), 400
        return jsonify(resultado)
    return _go()


@i9logic_bp.route("/seed", methods=["POST"])
def i9logic_seed():
    @requer_permissao("estoque.editar")
    def _go():
        dados = request.json or {}
        usuario = usuario_atual_da_request()
        resultado = seed_inicial(
            dados.get("sku", ""), dados.get("loja", ""),
            usuario.get("user_id"), usuario.get("nome", ""))
        if resultado.get("erro"):
            erro = resultado["erro"]
            eh_nao_encontrado = "nao encontrado" in erro or "sem snapshot" in erro
            return jsonify(resultado), (404 if eh_nao_encontrado else 400)
        return jsonify(resultado)
    return _go()


@i9logic_bp.route("/produtos/importar", methods=["POST"])
def i9logic_importar_produtos():
    """Importacao unica do catalogo inteiro (22k+ produtos) - disparo manual,
    nao entra no job recorrente do scheduler."""
    @requer_permissao("produtos.editar")
    def _go():
        return jsonify(sincronizar_catalogo_i9logic())
    return _go()


@i9logic_bp.route("/vendas/sincronizar", methods=["POST"])
def i9logic_sincronizar_vendas():
    """Dispara um ciclo de sync de vendas PDV. Sem data_de/data_ate no corpo,
    usa a janela rolante padrao (mesma que o job recorrente do scheduler);
    com data_de/data_ate, serve de backfill manual de historico."""
    @requer_permissao("vendas.editar")
    def _go():
        dados = request.get_json(silent=True) or {}
        return jsonify(sincronizar_pedidos_i9logic(
            data_de=dados.get("data_de"), data_ate=dados.get("data_ate")))
    return _go()


@i9logic_bp.route("/estoque/<int:loja_id>", methods=["GET"])
def i9logic_estoque_por_loja(loja_id):
    """Estoque fisico ao vivo (i9Logic) de uma loja fisica — usado pela tela
    /estoque quando a loja selecionada e' do tipo 'fisica'. Lojas virtuais
    nao tem filial i9Logic; a tela deve usar o estoque local (Athena) pra
    elas, nao este endpoint."""
    @requer_permissao("estoque.ver")
    def _go():
        loja = obter_loja(loja_id)
        if not loja:
            return jsonify({"erro": "loja nao encontrada"}), 404
        if loja.get("tipo") != "fisica":
            return jsonify({"erro": "estoque i9Logic so' se aplica a lojas do tipo fisica"}), 400
        resultado = estoque_fisico_por_loja(loja["nome"])
        if resultado.get("erro"):
            eh_nao_encontrado = "nao encontrado" in resultado["erro"]
            return jsonify(resultado), (404 if eh_nao_encontrado else 400)
        return jsonify(resultado)
    return _go()
