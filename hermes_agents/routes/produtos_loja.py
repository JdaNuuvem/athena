"""API HTTP de Produto da Loja — dados operacionais por loja, complementar
ao catalogo mestre (core/produtos_loja.py fara' o join com catalogo_produtos).

ponytail: a permissao de leitura usada aqui e' "produtos.ver" (nao
"produtos.visualizar") — o seed de permissoes em core/rbac.py gera os
codigos a partir de ACOES_PADRAO, que usa "ver" como acao, entao
"produtos.visualizar" nunca existe em rbac_permissoes; usar esse codigo
bloquearia todo mundo (exceto token master) sem nenhuma role conseguir a
permissao. As demais (produtos.criar/editar/excluir) batem com o seed.

ponytail: core.produtos_loja.excluir(loja, sku) tem apenas 2 parametros
(sem usuario_id/usuario_nome) — a auditoria de exclusao (auditar_exclusao)
ja resolve o usuario da request internamente (core/seguranca.py), entao nao
ha' porque nem como passar usuario_id/usuario_nome pra essa funcao aqui.
Mesma logica pra criar()/atualizar(): usuario_id/usuario_nome nao sao
parametros delas (auditar_alteracao tambem resolve o usuario sozinho)."""
from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao, usuario_atual_da_request
from core import produtos_loja as pl

produtos_loja_bp = Blueprint("produtos_loja", __name__, url_prefix="/api/produtos-loja")


@produtos_loja_bp.route("", methods=["GET"])
@requer_permissao("produtos.ver")
def listar():
    loja = request.args.get("loja", "")
    busca = request.args.get("busca", "")
    pagina = request.args.get("pagina", 1, type=int)
    por_pagina = request.args.get("por_pagina", 30, type=int)
    if not loja:
        return jsonify({"erro": "parametro loja obrigatorio"}), 400
    return jsonify(pl.listar_por_loja(loja, busca, pagina, por_pagina))


@produtos_loja_bp.route("/<loja>/<sku>", methods=["GET"])
@requer_permissao("produtos.ver")
def detalhe(loja, sku):
    row = pl.obter(loja, sku)
    if not row:
        return jsonify({"erro": "nao encontrado"}), 404
    return jsonify(row)


@produtos_loja_bp.route("", methods=["POST"])
@requer_permissao("produtos.criar")
def criar():
    dados = request.json or {}
    loja, sku = dados.get("loja", ""), dados.get("sku", "")
    resultado = pl.criar(loja, sku, produto_mestre_sku=dados.get("produto_mestre_sku"),
                          **{k: v for k, v in dados.items() if k not in ("loja", "sku", "produto_mestre_sku")})
    status = 201 if resultado.get("ok") else 400
    return jsonify(resultado), status


@produtos_loja_bp.route("/<loja>/<sku>", methods=["PUT"])
@requer_permissao("produtos.editar")
def editar(loja, sku):
    dados = request.json or {}
    resultado = pl.atualizar(loja, sku, **dados)
    status = 200 if resultado.get("ok") else 400
    return jsonify(resultado), status


@produtos_loja_bp.route("/<loja>/<sku>", methods=["DELETE"])
@requer_permissao("produtos.excluir")
def deletar(loja, sku):
    resultado = pl.excluir(loja, sku)
    status = 200 if resultado.get("ok") else 404
    return jsonify(resultado), status


@produtos_loja_bp.route("/replicar", methods=["POST"])
@requer_permissao("produtos.editar")
def replicar():
    dados = request.json or {}
    usuario = usuario_atual_da_request()
    resultado = pl.replicar_para_lojas(
        dados.get("loja_origem", ""), dados.get("sku", ""), dados.get("lojas_destino", []),
        usuario_id=usuario["user_id"], usuario_nome=usuario["nome"])
    status = 200 if resultado.get("ok") else 400
    return jsonify(resultado), status


@produtos_loja_bp.route("/<loja>/<sku>/sincronizar-mestre", methods=["POST"])
@requer_permissao("produtos.editar")
def sincronizar(loja, sku):
    dados = request.json or {}
    usuario = usuario_atual_da_request()
    resultado = pl.sincronizar_do_mestre(
        loja, sku, dados.get("campos", []),
        usuario_id=usuario["user_id"], usuario_nome=usuario["nome"])
    status = 200 if resultado.get("ok") else 400
    return jsonify(resultado), status
