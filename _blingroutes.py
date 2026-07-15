p = r"D:\JORGE CHARME E LEON\SISTEMAS\N8N AUTOMACOES\hermes_agents\athena_bridge.py"
c = open(p, encoding="utf-8").read()

routes = """

# ── Bling Portuguese Routes (alias para rotas inglesas existentes) ──

@app.route('/api/bling/produtos', methods=['GET'])
def bling_pt_produtos():
    from bling_erp import listar_produtos
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 100, type=int)
    return jsonify(listar_produtos(pagina, limite))

@app.route('/api/bling/produtos', methods=['POST'])
def bling_pt_criar_produto():
    from bling_erp import criar_produto
    return jsonify(criar_produto(request.json or {}))

@app.route('/api/bling/produtos/<int:id>', methods=['PUT'])
def bling_pt_atualizar_produto(id):
    from bling_erp import atualizar_produto
    return jsonify(atualizar_produto(id, request.json or {}))

@app.route('/api/bling/produtos/<int:id>', methods=['DELETE'])
def bling_pt_deletar_produto(id):
    from bling_erp import deletar_produto
    return jsonify(deletar_produto(id))

@app.route('/api/bling/produtos/situacoes', methods=['POST'])
def bling_pt_situacoes():
    from bling_erp import atualizar_situacao_produtos
    data = request.json or {}
    return jsonify(atualizar_situacao_produtos(data.get("ids", data.get("idsProdutos", [])), data.get("situacao", "")))

@app.route('/api/bling/produtos/sincronizar', methods=['POST'])
def bling_pt_sync_produtos():
    from bling_erp import sincronizar_produtos
    return jsonify(sincronizar_produtos())

@app.route('/api/bling/produtos/agrupados', methods=['GET'])
def bling_agrupados():
    # Produtos agrupados por nome base (variacoes) + avulsos, direto da API Bling
    from bling_erp import listar_produtos, get_access_token, get_auth_url
    token = get_access_token()
    if not token: return jsonify({"error": "Bling nao autenticado", "auth_url": get_auth_url()}), 401
    limite = request.args.get("limite", 200, type=int)
    r = listar_produtos(limite=limite)
    dados = r.get("data", [])
    grupos_map = {}
    avulsos = []
    for p in dados:
        nome = p.get("descricao", "")
        # Agrupa por palavras iniciais (base name sem variacao)
        base = nome.split(" - ")[0].split(" | ")[0].strip()
        if base not in grupos_map:
            grupos_map[base] = {"nome_base": base, "sku_pai": "", "variacoes": [], "total_estoque": 0}
        estoque = 0
        g = grupos_map[base]
        g["variacoes"].append({"id": p.get("id"), "codigo": p.get("codigo",""), "nome": nome, "preco": p.get("preco",0), "estoque": estoque})
        if not g["sku_pai"] and len(g["variacoes"]) == 1:
            g["sku_pai"] = p.get("codigo","")
    avulsos = [{"id": p.get("id"), "codigo": p.get("codigo",""), "nome": p.get("descricao",""), "preco": p.get("preco",0)} for p in dados]
    return jsonify({"grupos": list(grupos_map.values()), "avulsos": avulsos})

@app.route('/api/bling/depositos', methods=['GET'])
def bling_pt_depositos():
    from bling_erp import listar_depositos
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 100, type=int)
    return jsonify(listar_depositos(pagina, limite))

@app.route('/api/bling/estoque/<int:id_deposito>', methods=['GET'])
def bling_pt_estoque_saldo(id_deposito):
    from bling_erp import obter_saldo_deposito
    ids_produtos = request.args.getlist("idsProdutos[]", type=int) or None
    return jsonify(obter_saldo_deposito(id_deposito, ids_produtos))

@app.route('/api/bling/estoque', methods=['PUT'])
def bling_pt_estoque_update():
    from bling_erp import atualizar_estoque_deposito
    return jsonify(atualizar_estoque_deposito(request.json or {}))

@app.route('/api/bling/vendas', methods=['GET'])
def bling_pt_vendas():
    from bling_erp import listar_pedidos
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 100, type=int)
    return jsonify(listar_pedidos(pagina, limite))

@app.route('/api/bling/vendas/resumo', methods=['GET'])
def bling_pt_vendas_resumo():
    from bling_erp import resumo_vendas
    dias = request.args.get("dias", 30, type=int)
    return jsonify(resumo_vendas(dias))

@app.route('/api/bling/vendas/sincronizar', methods=['POST'])
def bling_pt_sync_vendas():
    from bling_erp import sincronizar_pedidos
    return jsonify(sincronizar_pedidos())

@app.route('/api/bling/financeiro/contas-receber', methods=['GET'])
def bling_pt_contas_receber():
    from bling_erp import listar_contas_receber
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 100, type=int)
    return jsonify(listar_contas_receber(pagina, limite))

@app.route('/api/bling/financeiro/notas-fiscais', methods=['GET'])
def bling_pt_notas_fiscais():
    from bling_erp import listar_notas_fiscais
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 100, type=int)
    return jsonify(listar_notas_fiscais(pagina, limite))

@app.route('/api/bling/financeiro/notas-fiscais/<int:id>/xml', methods=['GET'])
def bling_pt_nf_xml(id):
    from bling_erp import get_nfe_xml
    xml, ct = get_nfe_xml(id)
    if not xml: return jsonify({"error": "XML nao encontrado"}), 404
    return xml, 200, {"Content-Type": ct or "application/xml"}

@app.route('/api/bling/financeiro/notas-fiscais/<int:id>/danfe', methods=['GET'])
def bling_pt_nf_danfe(id):
    from bling_erp import get_nfe_detail
    r = get_nfe_detail(id)
    danfe_url = (r.get("data", {}) or {}).get("danfe", "")
    if danfe_url:
        from flask import redirect
        return redirect(danfe_url)
    return jsonify({"error": "DANFE nao encontrada"}), 404

@app.route('/api/bling/webhooks', methods=['GET'])
def bling_pt_webhooks():
    from bling_erp import listar_webhooks
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 100, type=int)
    return jsonify(listar_webhooks(pagina, limite))

@app.route('/api/bling/webhooks', methods=['POST'])
def bling_pt_criar_webhook():
    from bling_erp import criar_webhook
    data = request.json or {}
    return jsonify(criar_webhook(data.get("evento",""), data.get("url","")))

@app.route('/api/bling/webhooks/<int:id>', methods=['DELETE'])
def bling_pt_deletar_webhook(id):
    from bling_erp import deletar_webhook
    return jsonify(deletar_webhook(id))

@app.route('/api/bling/notificacoes', methods=['GET'])
def bling_pt_notificacoes():
    from bling_erp import listar_notificacoes
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 100, type=int)
    return jsonify(listar_notificacoes(pagina, limite))

@app.route('/api/bling/notificacoes/<int:id>', methods=['PATCH'])
def bling_pt_notificacao_lida(id):
    from bling_erp import confirmar_leitura_notificacao
    return jsonify(confirmar_leitura_notificacao(id))

@app.route('/api/bling/contatos', methods=['GET'])
def bling_pt_contatos():
    from bling_erp import listar_contatos
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 100, type=int)
    tipo = request.args.get("tipo", "")
    return jsonify(listar_contatos(pagina, limite, tipo))

@app.route('/api/bling/categorias', methods=['GET'])
def bling_pt_categorias():
    from bling_erp import listar_categorias
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 100, type=int)
    return jsonify(listar_categorias(pagina, limite))

@app.route('/api/bling/financeiro/contas-pagar', methods=['GET'])
def bling_pt_contas_pagar():
    from bling_erp import listar_contas_pagar
    pagina = request.args.get("pagina", 1, type=int)
    limite = request.args.get("limite", 100, type=int)
    return jsonify(listar_contas_pagar(pagina, limite))
"""

insert = "# Workflows Cross-Agent"
c = c.replace(insert, routes + "\n" + insert)

open(p, "w", encoding="utf-8", newline="\n").write(c)
print(f"Bling routes: {len(c)} bytes")
