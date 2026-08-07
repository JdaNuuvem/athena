from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao
from core.api_utils import status_for_resultado as _status_for

crm_bp = Blueprint("crm", __name__, url_prefix="/api/crm")


_LEADS_QUERY_PARAMS = ("page", "page_size", "sort", "order", "status", "funil_etapa",
                        "origem", "empresa_id", "com_telefone", "q", "export")


def _tem_filtro_leads(args) -> bool:
    return any(p in args for p in _LEADS_QUERY_PARAMS)


def _int_ou(args, nome, default):
    try:
        return int(args.get(nome, default))
    except (TypeError, ValueError):
        return default


def _int_ou_none(args, nome):
    bruto = args.get(nome)
    if not bruto:
        return None
    try:
        return int(bruto)
    except ValueError:
        return None


def _parse_filtro_leads(args) -> dict:
    com_telefone_bruto = args.get("com_telefone")
    return {
        "page": _int_ou(args, "page", 1),
        "page_size": _int_ou(args, "page_size", 25),
        "sort": args.get("sort", "id"),
        "order": args.get("order", "desc"),
        "status": args.get("status") or None,
        "funil_etapa": args.get("funil_etapa") or None,
        "origem": args.get("origem") or None,
        "empresa_id": _int_ou_none(args, "empresa_id"),
        "com_telefone": (com_telefone_bruto.lower() == "true") if com_telefone_bruto is not None else None,
        "q": args.get("q") or None,
        "export": args.get("export", "").lower() == "true",
    }


@crm_bp.route("/funil", methods=["GET"])
def crm_funil():
    from core.crm import funil as crm_funil_fn

    @requer_permissao("crm.ver")
    def _go():
        return jsonify(crm_funil_fn())
    return _go()


@crm_bp.route("/importar-bling", methods=["POST"])
def crm_importar_bling():
    from core.crm import importar_contatos_bling

    @requer_permissao("crm.criar")
    def _go():
        resultado = importar_contatos_bling()
        return jsonify(resultado), _status_for(resultado)
    return _go()


@crm_bp.route("/<tabela>", methods=["GET"])
def crm_list(tabela):
    from core.crm import list as crm_list_fn, CRM_TABLES
    if tabela not in CRM_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    @requer_permissao("crm.ver")
    def _go():
        if tabela == "leads" and _tem_filtro_leads(request.args):
            from core.crm import listar_leads_filtrado
            return jsonify(listar_leads_filtrado(**_parse_filtro_leads(request.args)))
        return jsonify({"data": crm_list_fn(tabela)})
    return _go()


@crm_bp.route("/<tabela>", methods=["POST"])
def crm_create(tabela):
    from core.crm import create as crm_create_fn, CRM_TABLES
    if tabela not in CRM_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}
    if not data:
        return jsonify({"error": "Dados obrigatorios"}), 400

    @requer_permissao("crm.criar")
    def _go():
        resultado = crm_create_fn(tabela, data)
        return jsonify(resultado), _status_for(resultado)
    return _go()


@crm_bp.route("/<tabela>/<int:id>", methods=["GET"])
def crm_get(tabela, id):
    from core.crm import get as crm_get_fn, CRM_TABLES
    if tabela not in CRM_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    @requer_permissao("crm.ver")
    def _go():
        resultado = crm_get_fn(tabela, id)
        return jsonify(resultado), _status_for(resultado)
    return _go()


@crm_bp.route("/<tabela>/<int:id>", methods=["PUT"])
def crm_update(tabela, id):
    from core.crm import update as crm_update_fn, CRM_TABLES
    if tabela not in CRM_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}

    @requer_permissao("crm.editar")
    def _go():
        resultado = crm_update_fn(tabela, id, data)
        return jsonify(resultado), _status_for(resultado)
    return _go()


@crm_bp.route("/<tabela>/<int:id>", methods=["DELETE"])
def crm_delete(tabela, id):
    from core.crm import get as crm_get_fn, delete as crm_delete_fn, CRM_TABLES
    if tabela not in CRM_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404

    @requer_permissao("crm.excluir")
    def _go():
        from core.seguranca import auditar_exclusao
        dados_antes = crm_get_fn(tabela, id)
        resultado = crm_delete_fn(tabela, id)
        if not resultado.get("error"):
            auditar_exclusao("crm", tabela, id, dados_antes if not dados_antes.get("error") else None)
        return jsonify(resultado), _status_for(resultado)
    return _go()
