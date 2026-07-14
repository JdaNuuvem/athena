p = r"D:\JORGE CHARME E LEON\SISTEMAS\N8N AUTOMACOES\hermes_agents\athena_bridge.py"
c = open(p, encoding="utf-8").read()

routes = """

# ── Fiscal Routes ──

@app.route('/api/fiscal/dashboard', methods=['GET'])
def fiscal_dashboard():
    from core.fiscal import dashboard
    return jsonify(dashboard())

@app.route('/api/fiscal/<tabela>', methods=['GET'])
def fiscal_list(tabela):
    from core.fiscal import list as fl, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify({"data": fl(tabela)})

@app.route('/api/fiscal/<tabela>', methods=['POST'])
def fiscal_create(tabela):
    from core.fiscal import create as fc, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(fc(tabela, request.json or {}))

@app.route('/api/fiscal/<tabela>/<int:id>', methods=['GET'])
def fiscal_get(tabela, id):
    from core.fiscal import get as fg, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(fg(tabela, id))

@app.route('/api/fiscal/<tabela>/<int:id>', methods=['PUT'])
def fiscal_update(tabela, id):
    from core.fiscal import update as fu, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(fu(tabela, id, request.json or {}))

@app.route('/api/fiscal/<tabela>/<int:id>', methods=['DELETE'])
def fiscal_delete(tabela, id):
    from core.fiscal import delete as fd, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(fd(tabela, id))

@app.route('/api/fiscal/tributos/calcular/<int:nota_id>', methods=['GET'])
def fiscal_calcular_tributos(nota_id):
    from core.fiscal import calcular_tributos_nota
    return jsonify(calcular_tributos_nota(nota_id))

@app.route('/api/fiscal/obrigacoes/proximas', methods=['GET'])
def fiscal_obrigacoes_proximas():
    from core.fiscal import obrigacoes_proximas
    dias = request.args.get('dias', 30, type=int)
    return jsonify({"data": obrigacoes_proximas(dias)})

@app.route('/api/fiscal/obrigacoes/atrasadas', methods=['GET'])
def fiscal_obrigacoes_atrasadas():
    from core.fiscal import obrigacoes_atrasadas
    return jsonify({"data": obrigacoes_atrasadas()})

@app.route('/api/fiscal/obrigacoes/<int:id>/baixar', methods=['POST'])
def fiscal_baixar_obrigacao(id):
    from core.fiscal import baixar_obrigacao
    return jsonify(baixar_obrigacao(id))

@app.route('/api/fiscal/sync/notas-fiscais', methods=['POST'])
def fiscal_sync_nf():
    from core.fiscal import sincronizar_notas_fiscais_bling
    data = request.json or {}
    return jsonify(sincronizar_notas_fiscais_bling(
        pagina=data.get("pagina", 1), limite=data.get("limite", 100)))

@app.route('/api/fiscal/sync/contas-receber', methods=['POST'])
def fiscal_sync_cr():
    from core.fiscal import sincronizar_contas_receber_bling
    data = request.json or {}
    return jsonify(sincronizar_contas_receber_bling(
        pagina=data.get("pagina", 1), limite=data.get("limite", 100)))

@app.route('/api/fiscal/sync/contas-pagar', methods=['POST'])
def fiscal_sync_cp():
    from core.fiscal import sincronizar_contas_pagar_bling
    data = request.json or {}
    return jsonify(sincronizar_contas_pagar_bling(
        pagina=data.get("pagina", 1), limite=data.get("limite", 100)))

@app.route('/api/fiscal/sync/tudo', methods=['POST'])
def fiscal_sync_tudo():
    from core.fiscal import sincronizar_tudo_bling
    return jsonify(sincronizar_tudo_bling())

@app.route('/api/fiscal/notas-fiscais/<int:id>/itens', methods=['GET'])
def fiscal_nf_itens(id):
    from core.fiscal import _list
    return jsonify({"data": _list("fiscal_nfe_itens", cols="*", order="numero_item")})

@app.route('/api/fiscal/notas-fiscais/<int:id>/impostos', methods=['GET'])
def fiscal_nf_impostos(id):
    from core.fiscal import _list
    return jsonify({"data": _list("fiscal_impostos_nota", cols="*", order="id")})
"""

insert = "# ── Automacoes Routes ──"
c = c.replace(insert, routes + "\n" + insert)

open(p, "w", encoding="utf-8", newline="\n").write(c)
print(f"Fiscal routes: {len(c)} bytes")
