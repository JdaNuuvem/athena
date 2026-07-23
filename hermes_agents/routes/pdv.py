from flask import Blueprint, request, jsonify
from core import run_async, get_db

pdv_bp = Blueprint("pdv", __name__, url_prefix="/api/pdv")


@pdv_bp.route('/login', methods=['POST'])
def pdv_login():
    data = request.json or {}
    from core.pdv import login_operador
    return jsonify(login_operador(data.get("nome",""), data.get("senha","")))

@pdv_bp.route('/dashboard', methods=['GET'])
def pdv_dashboard_api():
    from core.pdv import dashboard as pdv_dash
    return jsonify(pdv_dash())


@pdv_bp.route('/turno/abrir', methods=['POST'])
def pdv_abrir_turno():
    data = request.json or {}; from core.pdv import abrir_turno
    return jsonify(abrir_turno(data.get("caixa_id",0), data.get("operador_id"), data.get("operador",""), float(data.get("saldo_abertura",0))))

@pdv_bp.route('/turno/<int:id>/fechar', methods=['POST'])
def pdv_fechar_turno(id):
    data = request.json or {}; from core.pdv import fechar_turno
    return jsonify(fechar_turno(id, float(data.get("saldo_fechamento",0)), data.get("observacoes","")))

@pdv_bp.route('/clientes/buscar', methods=['GET'])
def pdv_buscar_clientes():
    from core.pdv import buscar_clientes
    return jsonify({"data": buscar_clientes(request.args.get("q",""))})

@pdv_bp.route('/produtos/buscar', methods=['GET'])
def pdv_buscar_produtos():
    from core.pdv import buscar_produtos
    return jsonify({"data": buscar_produtos(request.args.get("q",""))})

@pdv_bp.route('/venda/<int:id>/cancelar', methods=['POST'])
def pdv_cancelar_venda(id):
    data = request.json or {}; from core.pdv import cancelar_venda
    return jsonify(cancelar_venda(id, data.get("motivo",""), data.get("operador",""),
        data.get("operador_id"), data.get("senha","")))

@pdv_bp.route('/venda/<int:id>/devolver-item', methods=['POST'])
def pdv_devolver_item(id):
    data = request.json or {}; from core.pdv import devolver_item_venda
    return jsonify(devolver_item_venda(id, float(data.get("quantidade",1)), data.get("motivo",""),
        data.get("operador",""), data.get("operador_id"), data.get("senha","")))

@pdv_bp.route('/historico', methods=['GET'])
def pdv_historico():
    from core.pdv import historico_vendas
    caixa = request.args.get("caixa_id"); di = request.args.get("data_inicio"); df = request.args.get("data_fim")
    return jsonify({"data": historico_vendas(int(caixa) if caixa else None, di, df)})

@pdv_bp.route('/caixa/abrir', methods=['POST'])
def pdv_abrir_caixa():
    data = request.json or {}
    from core.pdv import abrir_caixa
    return jsonify(abrir_caixa(data.get("operador","Admin"), float(data.get("saldo_inicial",0)),
        data.get("operador_id"), data.get("senha","")))

@pdv_bp.route('/caixa/<int:id>/fechar', methods=['POST'])
def pdv_fechar_caixa(id):
    data = request.json or {}
    from core.pdv import fechar_caixa
    return jsonify(fechar_caixa(id, float(data.get("saldo_final",0)), data.get("operador_id"), data.get("senha","")))

@pdv_bp.route('/caixa/<int:id>/resumo', methods=['GET'])
def pdv_resumo_caixa(id):
    from core.pdv import resumo_fechamento
    return jsonify(resumo_fechamento(id))

@pdv_bp.route('/caixa/<int:id>/sangria', methods=['POST'])
def pdv_sangria(id):
    data = request.json or {}
    from core.pdv import sangria
    return jsonify(sangria(id, float(data.get("valor",0)), data.get("motivo",""), data.get("operador",""),
        data.get("operador_id"), data.get("senha","")))

@pdv_bp.route('/caixa/<int:id>/suprimento', methods=['POST'])
def pdv_suprimento(id):
    data = request.json or {}
    from core.pdv import suprimento
    return jsonify(suprimento(id, float(data.get("valor",0)), data.get("motivo",""), data.get("operador",""),
        data.get("operador_id"), data.get("senha","")))

@pdv_bp.route('/venda', methods=['POST'])
def pdv_venda():
    data = request.json or {}
    from core.pdv import realizar_venda
    return jsonify(realizar_venda(
        caixa_id=data.get("caixa_id",0),
        itens=data.get("itens",[]),
        pagamentos=data.get("pagamentos",[]),
        cliente=data.get("cliente",""),
        cliente_id=data.get("cliente_id"),
        operador=data.get("operador",""),
        operador_id=data.get("operador_id"),
        desconto=float(data.get("desconto",0))
    ))

@pdv_bp.route('/orcamento', methods=['POST'])
def pdv_criar_orcamento():
    data = request.json or {}
    from core.pdv import criar_orcamento
    return jsonify(criar_orcamento(
        cliente=data.get("cliente",""), cliente_id=data.get("cliente_id"),
        itens=data.get("itens",[]), operador=data.get("operador",""),
        operador_id=data.get("operador_id"), desconto=float(data.get("desconto",0))
    ))

@pdv_bp.route('/orcamento/<int:id>/converter', methods=['POST'])
def pdv_converter_orcamento(id):
    data = request.json or {}
    from core.pdv import converter_orcamento
    return jsonify(converter_orcamento(id, data.get("caixa_id",0), data.get("pagamentos",[]),
        data.get("operador",""), data.get("operador_id")))

@pdv_bp.route('/venda/<int:id>/cupom', methods=['GET'])
def pdv_cupom(id):
    async def _go():
        db = await get_db()
        v = await db.fetchrow("SELECT * FROM pdv_vendas WHERE id = $1", id)
        if not v: return {"error": "Venda nao encontrada"}
        itens = await db.fetch("SELECT * FROM pdv_itens WHERE venda_id = $1 ORDER BY id", id)
        pgts = await db.fetch("SELECT * FROM pdv_pagamentos WHERE venda_id = $1 ORDER BY id", id)
        return {
            "venda": dict(v),
            "itens": [dict(i) for i in itens],
            "pagamentos": [dict(p) for p in pgts],
        }
    try: return jsonify(run_async(_go()))
    except Exception as e: return jsonify({"error": str(e)})

@pdv_bp.route('/<tabela>', methods=['GET'])
def pdv_list(tabela):
    from core.pdv import list as pl, _list_filtro, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    if tabela == "itens" and request.args.get("venda_id"):
        return jsonify({"data": _list_filtro(tabela, f"venda_id = ${1}", [int(request.args.get("venda_id"))])})
    return jsonify({"data": pl(tabela)})

@pdv_bp.route('/<tabela>', methods=['POST'])
def pdv_create(tabela):
    from core.pdv import create as pc, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(pc(tabela, request.json or {}))

@pdv_bp.route('/<tabela>/<int:id>', methods=['GET'])
def pdv_get(tabela, id):
    from core.pdv import get as pg, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(pg(tabela, id))

@pdv_bp.route('/<tabela>/<int:id>', methods=['PUT'])
def pdv_update(tabela, id):
    from core.pdv import update as pu, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(pu(tabela, id, request.json or {}))

@pdv_bp.route('/<tabela>/<int:id>', methods=['DELETE'])
def pdv_delete(tabela, id):
    from core.pdv import delete as pd, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(pd(tabela, id))
