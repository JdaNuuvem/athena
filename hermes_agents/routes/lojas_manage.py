from flask import Blueprint, request, jsonify
from core.rbac import requer_permissao
from core.lojas import CAMPOS_GERAIS, STATUS_VALIDOS
from core.validadores import validar_cnpj_cpf, validar_cep, validar_email

lojas_bp = Blueprint("lojas_manage", __name__, url_prefix="/api/lojas")


def _extrair_campos_gerais(data: dict):
    """Filtra do body so' os campos conhecidos de identificacao/endereco/
    contatos e valida formato. Retorna (campos, erro)."""
    campos = {k: v for k, v in data.items() if k in CAMPOS_GERAIS}
    if "status" in campos and campos["status"] not in STATUS_VALIDOS:
        return None, f"status invalido. Use um de: {', '.join(STATUS_VALIDOS)}"
    if "cnpj_cpf" in campos and not validar_cnpj_cpf(campos["cnpj_cpf"]):
        return None, "CNPJ/CPF invalido"
    if "cep" in campos and not validar_cep(campos["cep"]):
        return None, "CEP invalido"
    if "email" in campos and not validar_email(campos["email"]):
        return None, "E-mail invalido"
    return campos, None


@lojas_bp.route("/manage", methods=["GET"])
def listar_lojas_manage():
    from core.lojas import listar as listar_lojas_fn
    return jsonify({"lojas": listar_lojas_fn()})


@lojas_bp.route("/manage/<int:id>", methods=["GET"])
def obter_loja_manage(id):
    from core.lojas import obter as obter_loja_fn
    loja = obter_loja_fn(id)
    if not loja:
        return jsonify({"error": "Loja nao encontrada"}), 404
    return jsonify({"loja": loja})


@lojas_bp.route("/manage", methods=["POST"])
def criar_loja_manage():
    data = request.json or {}
    nome = (data.get("nome") or "").strip()
    tipo = data.get("tipo", "fisica")
    if not nome:
        return jsonify({"error": "Nome e obrigatorio"}), 400
    campos, erro = _extrair_campos_gerais(data)
    if erro:
        return jsonify({"error": erro}), 400

    @requer_permissao("configuracoes.criar")
    def _go():
        from core.lojas import criar as criar_loja_fn, atualizar_geral
        from core.seguranca import auditar_alteracao
        result = criar_loja_fn(nome, tipo=tipo)
        if not result:
            return jsonify({"error": "Erro ao criar"}), 500
        if result.get("error"):
            return jsonify({"error": result["error"]}), 500
        if campos:
            atualizar_geral(result["id"], campos)
        auditar_alteracao("criar", "lojas", "manage", result["id"], dados_depois={**result, **campos})
        return jsonify({"loja": result})
    return _go()


@lojas_bp.route("/manage/<int:id>", methods=["PUT"])
def atualizar_loja_manage(id):
    data = request.json or {}
    nome = (data.get("nome") or "").strip()
    markup = data.get("shopee_markup_pct")
    grupos = data.get("grupos_publicacao")
    tipo = data.get("tipo")
    if not nome:
        return jsonify({"error": "Nome e obrigatorio"}), 400
    campos, erro = _extrair_campos_gerais(data)
    if erro:
        return jsonify({"error": erro}), 400

    @requer_permissao("configuracoes.editar")
    def _go():
        from core.lojas import atualizar as atualizar_loja_fn, atualizar_geral, obter
        from core.seguranca import auditar_alteracao
        dados_antes = obter(id)
        ok = atualizar_loja_fn(id, nome, shopee_markup_pct=markup, grupos_publicacao=grupos, tipo=tipo)
        if not ok:
            return jsonify({"error": "Loja nao encontrada"}), 404
        if campos:
            atualizar_geral(id, campos)
        auditar_alteracao("editar", "lojas", "manage", id, dados_antes=dados_antes, dados_depois=campos or None)
        return jsonify({"success": True})
    return _go()


@lojas_bp.route("/manage/<int:id>", methods=["DELETE"])
def deletar_loja_manage(id):
    @requer_permissao("configuracoes.excluir")
    def _go():
        from core.lojas import listar as listar_lojas_fn, deletar as deletar_loja_fn
        from core.seguranca import auditar_exclusao
        dados_antes = next((l for l in listar_lojas_fn() if l.get("id") == id), None)
        ok = deletar_loja_fn(id)
        if not ok:
            return jsonify({"error": "Loja nao encontrada"}), 404
        auditar_exclusao("lojas", "manage", id, dados_antes)
        return jsonify({"success": True})
    return _go()


@lojas_bp.route("/sync/bling", methods=["POST"])
def lojas_sync_bling():
    @requer_permissao("configuracoes.editar")
    def _go():
        from core.lojas import sincronizar_bling
        return jsonify(sincronizar_bling())
    return _go()


@lojas_bp.route("/deposito-map", methods=["GET"])
def lojas_deposito_map():
    from core import get_db, run_async
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT id, nome, bling_id FROM lojas WHERE bling_id IS NOT NULL AND ativa = TRUE ORDER BY id")
        return [{"loja_id": r["id"], "nome": r["nome"], "deposito_id": r["bling_id"]} for r in rows]
    try:
        return jsonify({"map": run_async(_go())})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
