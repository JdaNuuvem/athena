p = r"D:\JORGE CHARME E LEON\SISTEMAS\N8N AUTOMACOES\hermes_agents\athena_bridge.py"
c = open(p, encoding="utf-8").read()

routes = """

# ── Vendas Routes ──

@app.route('/api/vendas/dashboard', methods=['GET'])
def vendas_dashboard():
    from core.vendas import dashboard
    dias = request.args.get('dias', 30, type=int)
    return jsonify(dashboard(dias))

@app.route('/api/vendas/<tabela>', methods=['GET'])
def vendas_list(tabela):
    from core.vendas import list as vl, listar_filtrado, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    data_inicio = request.args.get("data_inicio", "")
    data_fim = request.args.get("data_fim", "")
    dias = request.args.get("dias", 0, type=int)
    status = request.args.get("status", "")
    if data_inicio or data_fim or dias or status:
        return jsonify(listar_filtrado(tabela, data_inicio, data_fim, dias, status))
    return jsonify({"data": vl(tabela)})

@app.route('/api/vendas/<tabela>', methods=['POST'])
def vendas_create(tabela):
    from core.vendas import create as vc, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(vc(tabela, request.json or {}))

@app.route('/api/vendas/<tabela>/<int:id>', methods=['GET'])
def vendas_get(tabela, id):
    from core.vendas import get as vg, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(vg(tabela, id))

@app.route('/api/vendas/<tabela>/<int:id>', methods=['PUT'])
def vendas_update(tabela, id):
    from core.vendas import update as vu, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(vu(tabela, id, request.json or {}))

@app.route('/api/vendas/<tabela>/<int:id>', methods=['DELETE'])
def vendas_delete(tabela, id):
    from core.vendas import delete as vd, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(vd(tabela, id))

@app.route('/api/vendas/pedido', methods=['POST'])
def vendas_criar_pedido():
    data = request.json or {}
    from core.vendas import criar_pedido
    return jsonify(criar_pedido(
        cliente=data.get("cliente",""),
        itens=data.get("itens",[]),
        pagamentos=data.get("pagamentos",[]),
        desconto=float(data.get("desconto",0)),
        frete=float(data.get("frete",0)),
        vendedor=data.get("vendedor",""),
        marketplace=data.get("marketplace","manual"),
        loja_id=data.get("loja_id"),
        observacoes=data.get("observacoes",""),
    ))

@app.route('/api/vendas/pedido/<int:id>', methods=['GET'])
def vendas_detalhe_pedido(id):
    from core.vendas import detalhe_pedido
    return jsonify(detalhe_pedido(id))

@app.route('/api/vendas/pedido/<int:id>/status', methods=['PUT'])
def vendas_atualizar_status(id):
    data = request.json or {}
    from core.vendas import atualizar_status
    return jsonify(atualizar_status(id, data.get("status",""), data.get("usuario","")))

@app.route('/api/vendas/sync/bling', methods=['POST'])
def vendas_sync_bling():
    from core.vendas import sincronizar_pedidos_bling
    data = request.json or {}
    return jsonify(sincronizar_pedidos_bling(
        pagina=data.get("pagina", 1), limite=data.get("limite", 100)))
"""

insert = "# ── Relatorios Routes ──"
c = c.replace(insert, routes + "\n" + insert)

open(p, "w", encoding="utf-8", newline="\n").write(c)
print(f"Vendas routes: {len(c)} bytes")
