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
        data.get("operador_id"), data.get("senha",""),
        data.get("gerente_pin_id"), data.get("pin",""), data.get("codigo_barras","")))

@pdv_bp.route('/venda/<int:id>/devolver-item', methods=['POST'])
def pdv_devolver_item(id):
    data = request.json or {}; from core.pdv import devolver_item_venda
    return jsonify(devolver_item_venda(id, float(data.get("quantidade",1)), data.get("motivo",""),
        data.get("operador",""), data.get("operador_id"), data.get("senha",""),
        data.get("gerente_pin_id"), data.get("pin",""), data.get("codigo_barras","")))

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
        data.get("operador_id"), data.get("senha",""), data.get("loja_id")))

@pdv_bp.route('/caixa/<int:id>/fechar', methods=['POST'])
def pdv_fechar_caixa(id):
    data = request.json or {}
    from core.pdv import fechar_caixa
    return jsonify(fechar_caixa(id, float(data.get("saldo_final",0)), data.get("operador_id"), data.get("senha",""),
        data.get("gerente_pin_id"), data.get("pin",""), data.get("codigo_barras","")))

@pdv_bp.route('/operadores/<int:id>/pin', methods=['PUT'])
def pdv_definir_pin(id):
    from core.rbac import requer_permissao
    from core.pdv import definir_pin
    @requer_permissao("configuracoes.editar")
    def _go():
        data = request.json or {}
        return jsonify(definir_pin(id, str(data.get("pin", ""))))
    return _go()

@pdv_bp.route('/operadores/<int:id>/codigo-barras', methods=['POST'])
def pdv_gerar_codigo_barras(id):
    """Gera um codigo de barras novo (cracha fisico) para o operador — o
    codigo em texto so' vem nesta resposta, para imprimir na hora; depois so'
    o hash fica salvo (mesmo padrao de senha/PIN)."""
    from core.rbac import requer_permissao
    from core.pdv import gerar_codigo_barras
    @requer_permissao("configuracoes.editar")
    def _go():
        return jsonify(gerar_codigo_barras(id))
    return _go()

@pdv_bp.route('/autorizar-codigo-barras', methods=['POST'])
def pdv_autorizar_codigo_barras():
    """Resolve um codigo de barras bipado para o gerente correspondente, sem
    aplicar nenhuma acao — usado pelo frontend para mostrar 'autorizado por
    Fulano' antes de confirmar a operacao sensivel."""
    from core.pdv import verificar_codigo_barras_gerencial, _ROLES_GERENCIAIS
    data = request.json or {}
    return jsonify(verificar_codigo_barras_gerencial(str(data.get("codigo", "")), _ROLES_GERENCIAIS))

@pdv_bp.route('/caixa/<int:id>/resumo', methods=['GET'])
def pdv_resumo_caixa(id):
    from core.pdv import resumo_fechamento
    return jsonify(resumo_fechamento(id))

@pdv_bp.route('/relatorio-descontos', methods=['GET'])
def pdv_relatorio_descontos():
    from core.pdv import relatorio_descontos_por_operador
    dias = request.args.get("dias", 30, type=int)
    return jsonify({"operadores": relatorio_descontos_por_operador(dias)})

@pdv_bp.route('/quebras-caixa', methods=['GET'])
def pdv_quebras_caixa():
    from core.rbac import requer_acesso_loja
    @requer_acesso_loja
    def _handler():
        return _pdv_quebras_caixa_impl()
    return _handler()

def _pdv_quebras_caixa_impl():
    from core.pdv import historico_quebras
    from core.rbac import usuario_atual_da_request
    from core.rbac_lojas import lojas_permitidas
    loja_id = request.args.get("loja_id", type=int)
    operador = request.args.get("operador", "")
    dias = request.args.get("dias", 90, type=int)
    permitidas = None if loja_id else lojas_permitidas(usuario_atual_da_request().get("user_id"))
    return jsonify({"quebras": historico_quebras(loja_id, operador, dias, loja_ids=permitidas)})

@pdv_bp.route('/sangria/limite', methods=['GET'])
def pdv_sangria_limite_get():
    from core.pdv_aprovacoes import limite_aprovacao, MOTIVOS_SANGRIA
    return jsonify({"limite": limite_aprovacao(), "motivos": MOTIVOS_SANGRIA})

@pdv_bp.route('/sangria/limite', methods=['PUT'])
def pdv_sangria_limite_put():
    from core.rbac import requer_permissao
    from core.pdv_aprovacoes import definir_limite_aprovacao
    @requer_permissao("configuracoes.editar")
    def _go():
        data = request.json or {}
        try:
            valor = float(data.get("limite"))
        except (TypeError, ValueError):
            return jsonify({"error": "limite invalido"}), 400
        if valor < 0:
            return jsonify({"error": "limite nao pode ser negativo"}), 400
        return jsonify(definir_limite_aprovacao(valor))
    return _go()

@pdv_bp.route('/sangria/aprovacoes', methods=['GET'])
def pdv_sangria_aprovacoes_listar():
    from core.pdv_aprovacoes import listar
    status = request.args.get("status", "pendente")
    return jsonify({"aprovacoes": listar(status)})

@pdv_bp.route('/sangria/aprovacoes/<int:aprovacao_id>/aprovar', methods=['POST'])
def pdv_sangria_aprovar(aprovacao_id):
    from core.rbac import requer_permissao, usuario_atual_da_request
    from core.pdv_aprovacoes import aprovar as aprovar_sangria
    @requer_permissao("pdv.aprovar")
    def _go():
        usuario = usuario_atual_da_request()
        return jsonify(aprovar_sangria(aprovacao_id, usuario["user_id"], usuario["nome"]))
    return _go()

@pdv_bp.route('/sangria/aprovacoes/<int:aprovacao_id>/rejeitar', methods=['POST'])
def pdv_sangria_rejeitar(aprovacao_id):
    from core.rbac import requer_permissao, usuario_atual_da_request
    from core.pdv_aprovacoes import rejeitar as rejeitar_sangria
    @requer_permissao("pdv.aprovar")
    def _go():
        data = request.json or {}
        usuario = usuario_atual_da_request()
        return jsonify(rejeitar_sangria(aprovacao_id, usuario["user_id"], usuario["nome"], str(data.get("motivo_rejeicao", ""))))
    return _go()

@pdv_bp.route('/caixa/<int:id>/sangria', methods=['POST'])
def pdv_sangria(id):
    data = request.json or {}
    from core.pdv import sangria
    return jsonify(sangria(id, float(data.get("valor",0)), data.get("motivo",""), data.get("operador",""),
        data.get("operador_id"), data.get("senha",""), data.get("gerente_pin_id"), data.get("pin",""),
        data.get("codigo_barras","")))

@pdv_bp.route('/caixa/<int:id>/suprimento', methods=['POST'])
def pdv_suprimento(id):
    data = request.json or {}
    from core.pdv import suprimento
    return jsonify(suprimento(id, float(data.get("valor",0)), data.get("motivo",""), data.get("operador",""),
        data.get("operador_id"), data.get("senha",""), data.get("gerente_pin_id"), data.get("pin",""),
        data.get("codigo_barras","")))

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
        desconto=float(data.get("desconto",0)),
        gerente_pin_id=data.get("gerente_pin_id"),
        pin=data.get("pin",""),
        codigo_barras=data.get("codigo_barras","")
    ))

@pdv_bp.route('/orcamento', methods=['POST'])
def pdv_criar_orcamento():
    data = request.json or {}
    from core.pdv import criar_orcamento
    return jsonify(criar_orcamento(
        cliente=data.get("cliente",""), cliente_id=data.get("cliente_id"),
        itens=data.get("itens",[]), operador=data.get("operador",""),
        operador_id=data.get("operador_id"), desconto=float(data.get("desconto",0)),
        gerente_pin_id=data.get("gerente_pin_id"), pin=data.get("pin",""),
        codigo_barras=data.get("codigo_barras","")
    ))

@pdv_bp.route('/orcamento/<int:id>/converter', methods=['POST'])
def pdv_converter_orcamento(id):
    data = request.json or {}
    from core.pdv import converter_orcamento
    return jsonify(converter_orcamento(id, data.get("caixa_id",0), data.get("pagamentos",[]),
        data.get("operador",""), data.get("operador_id"),
        data.get("gerente_pin_id"), data.get("pin",""), data.get("codigo_barras","")))

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

# ponytail: sangrias/suprimentos/caixas ja tem rotas dedicadas com senha +
# role gerencial via _exigir_operador (e agora alcada de aprovacao para
# sangria) — o CRUD generico abaixo NAO pode tocar nelas, senao vira uma
# porta lateral que contorna toda a validacao.
TABELAS_BLOQUEADAS = {"caixas", "sangrias", "suprimentos"}
# operadores precisa de CRUD (cadastrar/editar funcionarios), mas protegido
# pela sessao RBAC principal (nao pelo sistema de senha interno do PDV).
TABELAS_SO_RBAC = {"operadores"}


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
    if tabela in TABELAS_BLOQUEADAS:
        return jsonify({"error": f"Use a rota dedicada para '{tabela}' — este CRUD generico nao valida operador/senha"}), 403
    if tabela in TABELAS_SO_RBAC:
        from core.rbac import requer_permissao
        @requer_permissao("configuracoes.editar")
        def _go(): return jsonify(pc(tabela, request.json or {}))
        return _go()
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
    if tabela in TABELAS_BLOQUEADAS:
        return jsonify({"error": f"Use a rota dedicada para '{tabela}' — este CRUD generico nao valida operador/senha"}), 403
    if tabela in TABELAS_SO_RBAC:
        from core.rbac import requer_permissao
        @requer_permissao("configuracoes.editar")
        def _go(): return jsonify(pu(tabela, id, request.json or {}))
        return _go()
    return jsonify(pu(tabela, id, request.json or {}))

@pdv_bp.route('/<tabela>/<int:id>', methods=['DELETE'])
def pdv_delete(tabela, id):
    from core.pdv import delete as pd, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    if tabela in TABELAS_BLOQUEADAS:
        return jsonify({"error": f"Use a rota dedicada para '{tabela}' — este CRUD generico nao valida operador/senha"}), 403
    if tabela in TABELAS_SO_RBAC:
        from core.rbac import requer_permissao
        @requer_permissao("configuracoes.editar")
        def _go(): return jsonify(pd(tabela, id))
        return _go()
    return jsonify(pd(tabela, id))
