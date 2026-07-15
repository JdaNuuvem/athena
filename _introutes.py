p = r"D:\JORGE CHARME E LEON\SISTEMAS\N8N AUTOMACOES\hermes_agents\athena_bridge.py"
c = open(p, encoding="utf-8").read()

routes = """

# ── Integracoes / SSOT Routes ──

@app.route('/api/catalogo', methods=['GET'])
def catalogo_listar():
    from core.catalogo import listar
    return jsonify({"data": listar()})

@app.route('/api/catalogo', methods=['POST'])
def catalogo_criar():
    from core.catalogo import criar
    return jsonify(criar(request.json or {}))

@app.route('/api/catalogo/<int:id>', methods=['GET'])
def catalogo_obter(id):
    from core.catalogo import obter
    return jsonify(obter(id))

@app.route('/api/catalogo/sku/<sku>', methods=['GET'])
def catalogo_buscar_sku(sku):
    from core.catalogo import buscar_por_sku
    return jsonify(buscar_por_sku(sku))

@app.route('/api/integracoes/vincular-clientes', methods=['POST'])
def int_vincular_clientes():
    from core.entidades import vincular_todos_clientes
    return jsonify(vincular_todos_clientes())

@app.route('/api/integracoes/migrar-fornecedores', methods=['POST'])
def int_migrar_fornecedores():
    from core.entidades import migrar_fornecedores_compras
    return jsonify(migrar_fornecedores_compras())

@app.route('/api/integracoes/migrar-contas', methods=['POST'])
def int_migrar_contas():
    from core.entidades import migrar_contas_fiscal_para_financeiro
    return jsonify(migrar_contas_fiscal_para_financeiro())

@app.route('/api/integracoes/migrar-tudo', methods=['POST'])
def int_migrar_tudo():
    from core.entidades import vincular_todos_clientes, migrar_fornecedores_compras, migrar_contas_fiscal_para_financeiro
    r1 = vincular_todos_clientes()
    r2 = migrar_fornecedores_compras()
    r3 = migrar_contas_fiscal_para_financeiro()
    return jsonify({"clientes": r1, "fornecedores": r2, "contas": r3})

@app.route('/api/eventos/venda/<int:id>/faturar', methods=['POST'])
def ev_venda_faturar(id):
    from core.vendas import atualizar_status
    from core.entidades import ao_faturar_pedido, publicar_evento
    r1 = atualizar_status(id, "faturado")
    r2 = ao_faturar_pedido(id)
    publicar_evento("venda.faturada", "vendas_pedidos", id, {"pedido_id": id})
    return jsonify({"status": r1, "downstream": r2})

@app.route('/api/eventos/compra/<int:id>/receber', methods=['POST'])
def ev_compra_receber(id):
    from core.entidades import ao_receber_compra, publicar_evento
    r = ao_receber_compra(id)
    publicar_evento("compra.recebida", "compras_recebimentos", id, {"recebimento_id": id})
    return jsonify(r)

@app.route('/api/eventos/producao/<int:id>/finalizar', methods=['POST'])
def ev_producao_finalizar(id):
    from core.producao import finalizar_op
    from core.entidades import ao_finalizar_producao, publicar_evento
    r1 = finalizar_op(id)
    r2 = ao_finalizar_producao(id)
    publicar_evento("producao.finalizada", "producao_ops", id, {"op_id": id})
    return jsonify({"status": r1, "downstream": r2})

@app.route('/api/eventos/pdv/<int:id>/fechar-caixa', methods=['POST'])
def ev_pdv_fechar_caixa(id):
    from core.pdv import fechar_caixa
    from core.entidades import ao_fechar_caixa_pdv
    data = request.json or {}
    r1 = fechar_caixa(id, float(data.get("saldo_final", 0)))
    r2 = ao_fechar_caixa_pdv(id)
    return jsonify({"caixa": r1, "fluxo": r2})

@app.route('/api/eventos/crm/lead/<int:id>/converter', methods=['POST'])
def ev_crm_converter_lead(id):
    from core.entidades import ao_converter_lead
    return jsonify(ao_converter_lead(id))

@app.route('/api/eventos/crm/negociacao/<int:id>/ganha', methods=['POST'])
def ev_crm_negociacao_ganha(id):
    from core.entidades import ao_converter_negociacao
    return jsonify(ao_converter_negociacao(id))

@app.route('/api/eventos/processar', methods=['POST'])
def ev_processar_fila():
    from core.entidades import processar_eventos_pendentes
    limit = request.args.get('limit', 10, type=int)
    return jsonify(processar_eventos_pendentes(limit))

@app.route('/api/fiscal/obrigacoes/alertas', methods=['GET'])
def fiscal_alertas():
    from core.entidades import gerar_alertas_obrigacoes
    return jsonify(gerar_alertas_obrigacoes())

@app.route('/webhook/bling/completo', methods=['POST'])
def bling_webhook_completo():
    from core.entidades import processar_webhook_bling_completo
    payload = request.json or {}
    evento = payload.get("evento", request.args.get("evento", "desconhecido"))
    return jsonify(processar_webhook_bling_completo(evento, payload))
"""

insert = "# ── Seguranca / Auditoria Routes ──"
c = c.replace(insert, routes + "\n" + insert)

open(p, "w", encoding="utf-8", newline="\n").write(c)
print(f"Integration routes: {len(c)} bytes")
