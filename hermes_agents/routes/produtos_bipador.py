"""Rotas REST — import de produtos/estoque do app proprio de bipagem/
atualizacao de estoque (core/produtos_bipador.py). NAO fala com a API
i9Logic — ver docstring de core/produtos_bipador.py."""
from flask import Blueprint, jsonify
from core.rbac import requer_permissao
from core.produtos_bipador import sincronizar_catalogo_bipador, sincronizar_estoque_lojas_fisicas

produtos_bipador_bp = Blueprint("produtos_bipador", __name__, url_prefix="/api/integracoes/produtos-fisicos")


@produtos_bipador_bp.route("/importar", methods=["POST"])
def importar_produtos():
    """Importacao unica do catalogo inteiro (19k+ produtos) - disparo manual,
    nao entra no job recorrente do scheduler."""
    @requer_permissao("produtos.editar")
    def _go():
        return jsonify(sincronizar_catalogo_bipador())
    return _go()


@produtos_bipador_bp.route("/estoque-lojas/importar", methods=["POST"])
def importar_estoque_lojas():
    """Popula estoque_lojas (usado pela listagem /api/produtos filtrada por
    loja) para toda loja fisica ja mapeada em de_para_i9logic. Disparo manual
    - rode depois de /importar (o catalogo precisa existir primeiro pra
    listagem por loja fazer sentido)."""
    @requer_permissao("produtos.editar")
    def _go():
        return jsonify(sincronizar_estoque_lojas_fisicas())
    return _go()
