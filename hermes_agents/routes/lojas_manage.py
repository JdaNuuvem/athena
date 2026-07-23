from flask import Blueprint, request, jsonify

lojas_bp = Blueprint("lojas_manage", __name__, url_prefix="/api/lojas")


@lojas_bp.route("/manage", methods=["GET"])
def listar_lojas_manage():
    from core.lojas import listar as listar_lojas_fn
    return jsonify({"lojas": listar_lojas_fn()})


@lojas_bp.route("/manage", methods=["POST"])
def criar_loja_manage():
    data = request.json or {}
    nome = (data.get("nome") or "").strip()
    if not nome:
        return jsonify({"error": "Nome e obrigatorio"}), 400
    result = None
    from core.lojas import criar as criar_loja_fn
    result = criar_loja_fn(nome)
    return jsonify({"loja": result}) if result else jsonify({"error": "Erro ao criar"}), 500


@lojas_bp.route("/manage/<int:id>", methods=["PUT"])
def atualizar_loja_manage(id):
    data = request.json or {}
    nome = (data.get("nome") or "").strip()
    markup = data.get("shopee_markup_pct")
    grupos = data.get("grupos_publicacao")
    if not nome:
        return jsonify({"error": "Nome e obrigatorio"}), 400
    from core.lojas import atualizar as atualizar_loja_fn
    ok = atualizar_loja_fn(id, nome, shopee_markup_pct=markup, grupos_publicacao=grupos)
    return jsonify({"success": ok}) if ok else jsonify({"error": "Loja nao encontrada"}), 404


@lojas_bp.route("/manage/<int:id>", methods=["DELETE"])
def deletar_loja_manage(id):
    from core.lojas import deletar as deletar_loja_fn
    ok = deletar_loja_fn(id)
    return jsonify({"success": ok}) if ok else jsonify({"error": "Loja nao encontrada"}), 404


@lojas_bp.route("/sync/bling", methods=["POST"])
def lojas_sync_bling():
    from core.lojas import sincronizar_bling
    return jsonify(sincronizar_bling())


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
