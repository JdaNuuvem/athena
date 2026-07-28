from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao

produtos_bp = Blueprint("produtos_organizacao", __name__, url_prefix="/api/produtos")


@produtos_bp.route("/marcas", methods=["GET"])
@requer_permissao("produtos.ver")
def listar_marcas_route():
    from core.catalogo import listar_marcas
    return jsonify({"data": listar_marcas()})


@produtos_bp.route("/marcas", methods=["POST"])
@requer_permissao("produtos.editar")
def criar_marca_route():
    from core.catalogo import criar_marca
    from core.seguranca import auditar_alteracao
    nome = (request.json or {}).get("nome", "").strip()
    if not nome:
        return jsonify({"error": "nome e obrigatorio"}), 400
    resultado = criar_marca(nome)
    if not resultado.get("error"):
        auditar_alteracao("criar", "produtos", "catalogo_marcas", resultado.get("id"), dados_depois=resultado)
    return jsonify(resultado)


@produtos_bp.route("/fabricantes", methods=["GET"])
@requer_permissao("produtos.ver")
def listar_fabricantes_route():
    from core.catalogo import listar_fabricantes
    return jsonify({"data": listar_fabricantes()})


@produtos_bp.route("/fabricantes", methods=["POST"])
@requer_permissao("produtos.editar")
def criar_fabricante_route():
    from core.catalogo import criar_fabricante
    from core.seguranca import auditar_alteracao
    nome = (request.json or {}).get("nome", "").strip()
    if not nome:
        return jsonify({"error": "nome e obrigatorio"}), 400
    resultado = criar_fabricante(nome)
    if not resultado.get("error"):
        auditar_alteracao("criar", "produtos", "catalogo_fabricantes", resultado.get("id"), dados_depois=resultado)
    return jsonify(resultado)


@produtos_bp.route("/categorias", methods=["GET"])
@requer_permissao("produtos.ver")
def listar_categorias_route():
    from core.catalogo import listar_categorias
    return jsonify({"data": listar_categorias()})


@produtos_bp.route("/categorias", methods=["POST"])
@requer_permissao("produtos.editar")
def criar_categoria_route():
    from core.catalogo import criar_categoria
    from core.seguranca import auditar_alteracao
    data = request.json or {}
    nome = data.get("nome", "").strip()
    if not nome:
        return jsonify({"error": "nome e obrigatorio"}), 400
    categoria_pai_id = data.get("categoria_pai_id")
    resultado = criar_categoria(nome, categoria_pai_id)
    if not resultado.get("error"):
        auditar_alteracao("criar", "produtos", "catalogo_categorias", resultado.get("id"), dados_depois=resultado)
    return jsonify(resultado)


@produtos_bp.route("/tags", methods=["GET"])
@requer_permissao("produtos.ver")
def listar_tags_route():
    from core.catalogo import listar_tags
    return jsonify({"data": listar_tags()})


@produtos_bp.route("/tags", methods=["POST"])
@requer_permissao("produtos.editar")
def criar_tag_route():
    from core.catalogo import criar_tag
    from core.seguranca import auditar_alteracao
    nome = (request.json or {}).get("nome", "").strip()
    if not nome:
        return jsonify({"error": "nome e obrigatorio"}), 400
    resultado = criar_tag(nome)
    if not resultado.get("error"):
        auditar_alteracao("criar", "produtos", "catalogo_tags", resultado.get("id"), dados_depois=resultado)
    return jsonify(resultado)


@produtos_bp.route("/<int:produto_id>/tags", methods=["POST"])
@requer_permissao("produtos.editar")
def vincular_tag_route(produto_id):
    from core.catalogo import vincular_tag
    tag_id = (request.json or {}).get("tag_id")
    if not tag_id:
        return jsonify({"error": "tag_id e obrigatorio"}), 400
    return jsonify(vincular_tag(produto_id, int(tag_id)))


@produtos_bp.route("/<int:produto_id>/tags/<int:tag_id>", methods=["DELETE"])
@requer_permissao("produtos.editar")
def desvincular_tag_route(produto_id, tag_id):
    from core.catalogo import desvincular_tag
    return jsonify(desvincular_tag(produto_id, tag_id))
