from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao

rbac_bp = Blueprint("rbac", __name__, url_prefix="/api/rbac")


@rbac_bp.route("/roles", methods=["GET"])
def rbac_list_roles():
    from core.rbac import list_roles_com_permissoes
    return jsonify({"roles": list_roles_com_permissoes()})


@rbac_bp.route("/roles", methods=["POST"])
@requer_permissao("configuracoes.criar")
def rbac_create_role():
    data = request.json or {}
    from core.rbac import criar_role
    return jsonify(criar_role(data.get("nome", ""), data.get("descricao", ""), data.get("permissoes")))


@rbac_bp.route("/roles/<int:id>", methods=["PUT"])
@requer_permissao("configuracoes.editar")
def rbac_update_role(id):
    data = request.json or {}
    from core.rbac import atualizar_role
    return jsonify(atualizar_role(id, data.get("nome"), data.get("descricao"), data.get("permissoes")))


@rbac_bp.route("/roles/<int:id>", methods=["DELETE"])
@requer_permissao("configuracoes.excluir")
def rbac_delete_role(id):
    from core.rbac import deletar_role
    return jsonify(deletar_role(id))


@rbac_bp.route("/permissoes", methods=["GET"])
def rbac_list_permissoes():
    from core.rbac import list_permissoes
    return jsonify({"permissoes": list_permissoes()})


@rbac_bp.route("/usuarios", methods=["GET"])
@requer_permissao("configuracoes.ver")
def rbac_list_usuarios():
    from core.rbac import list_usuarios
    return jsonify({"usuarios": list_usuarios()})


@rbac_bp.route("/usuarios", methods=["POST"])
@requer_permissao("configuracoes.criar")
def rbac_create_usuario():
    data = request.json or {}
    from core.rbac import criar_usuario
    return jsonify(criar_usuario(data.get("nome", ""), data.get("email", ""), data.get("senha", ""), data.get("role", "")))


@rbac_bp.route("/usuarios/<int:id>", methods=["PUT"])
@requer_permissao("configuracoes.editar")
def rbac_update_usuario(id):
    data = request.json or {}
    from core.rbac import atualizar_usuario
    return jsonify(atualizar_usuario(id, data.get("nome"), data.get("role"), data.get("ativo")))


@rbac_bp.route("/usuarios/<int:id>/pin", methods=["PUT"])
@requer_permissao("configuracoes.editar")
def rbac_definir_pin(id):
    data = request.json or {}
    from core.rbac import definir_pin
    return jsonify(definir_pin(id, str(data.get("pin", ""))))


@rbac_bp.route("/usuarios/<int:id>/codigo-barras", methods=["POST"])
@requer_permissao("configuracoes.editar")
def rbac_gerar_codigo_barras(id):
    from core.rbac import gerar_codigo_barras_usuario
    return jsonify(gerar_codigo_barras_usuario(id))


@rbac_bp.route("/autorizar", methods=["POST"])
def rbac_autorizar():
    """Resolve uma autorizacao gerencial (PIN ou cracha) para uma permissao
    especifica, sem aplicar nenhuma acao — usado pelo frontend para confirmar
    'autorizado por Fulano' antes de submeter uma operacao sensivel (ex:
    aprovar pagamento acima do limite no financeiro)."""
    data = request.json or {}
    from core.rbac import autorizar_com_permissao
    return jsonify(autorizar_com_permissao(
        str(data.get("permissao", "")),
        data.get("usuario_pin_id"),
        str(data.get("pin", "")),
        str(data.get("codigo_barras", "")),
    ))
