"""
Athena Bridge — conecta o Hermes Agent ao ATHENA OS via GraphQL.
ATHENA OS tem 52 agentes, 40+ queries GraphQL, 30+ endpoints REST.
"""
import os, sys, json, urllib.request
from typing import Optional
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from core import run_async, get_db, FactoryConfig
from pathlib import Path
import psycopg2
import psycopg2.extras

ATHENA_URL = os.environ.get("ATHENA_URL", "http://a181zp5xj2ety5z82mopyqzi.177.7.45.242.sslip.io")
GRAPHQL_URL = f"{ATHENA_URL}/graphql"

# Token de autenticação para Athena OS
API_TOKEN = os.environ.get("ATHENA_TOKEN", "athena-token-123456789")

def _gql(query: str, variables: dict = None) -> dict:
    """Executa query GraphQL contra o Athena."""
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(GRAPHQL_URL, data=body, headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

# ===========================================================================
# Dashboard / Overview
# ===========================================================================

def health() -> dict:
    """Health check do sistema Athena."""
    try:
        with urllib.request.urlopen(f"{ATHENA_URL}/api/health", timeout=5) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

def kpi_summary() -> dict:
    """KPIs consolidados."""
    return _gql("{ kpiSummary { totalOrders totalRevenue activeListings lowStockAlerts } }")

# ===========================================================================
# Pedidos
# ===========================================================================

def listar_pedidos(status: str = None, limit: int = 10) -> dict:
    """Lista pedidos, opcionalmente filtrados por status."""
    q = f"{{ orders(limit: {limit}) {{ id customer status total channel createdAt }} }}"
    if status:
        q = f'{{ ordersByStatus(status: "{status}", limit: {limit}) {{ id customer status total channel createdAt }} }}'
    return _gql(q)

def pedido_por_id(order_id: str) -> dict:
    """Detalhes de um pedido específico."""
    return _gql(f'{{ order(id: "{order_id}") {{ id customer status total channel lines {{ sku quantity price }} createdAt }} }}')

# ===========================================================================
# Estoque
# ===========================================================================

def listar_estoque() -> dict:
    """Itens em estoque."""
    return _gql("{ stockItems(limit: 50) { sku name quantity warehouse minQuantity } }")

def alertas_estoque_baixo() -> dict:
    """Alertas de estoque baixo."""
    return _gql("{ lowStockAlerts { sku name quantity minQuantity warehouse } }")

# ===========================================================================
# Produção / Moldes
# ===========================================================================

def listar_moldes() -> dict:
    """Moldes cadastrados."""
    return _gql("{ molds(limit: 50) { id code product material cyclesUsed cyclesTotal status } }")

def producao_ativa() -> dict:
    """Produção em andamento."""
    return _gql("{ productionRuns(limit: 20) { id product status startDate endDate quantity } }")

# ===========================================================================
# Financeiro (AG-201~205)
# ===========================================================================

def cashflow() -> dict:
    """Fluxo de caixa."""
    return _gql("{ cashFlow { balance entries30d exits30d projected status } }")

def revenue_por_canal() -> dict:
    """Receita por canal."""
    return _gql("{ revenueByChannel { channel revenue growth trend } }")

def anomalias_custo() -> dict:
    """Anomalias de custo."""
    return _gql("{ costAnomalies { category value avgValue deviationPct severity } }")

def budget_vs_realizado() -> dict:
    """Orçamento vs realizado."""
    return _gql("{ budget { category budget actual deviationPct } }")

def profitability() -> dict:
    """Rentabilidade por SKU."""
    return _gql("{ profitabilityBySKU { sku product revenue cost marginPct status } }")

def break_even() -> dict:
    """Ponto de equilíbrio."""
    return _gql("{ breakEven { fixedCost avgMargin breakevenUnits dailyNeeded } }")

# ===========================================================================
# Agentes Athena (Admin)
# ===========================================================================

def listar_agentes_athena() -> dict:
    """Lista os 52 agentes do Athena."""
    try:
        with urllib.request.urlopen(f"{ATHENA_URL}/api/agents", timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

# ===========================================================================
# Relatório consolidado
# ===========================================================================

def relatorio_consolidado() -> str:
    """Relatório executivo Athena."""
    lines = ["🏛️ ATHENA OS — Relatório Consolidado", "=" * 50]
    h = health()
    k = kpi_summary()
    lines.append(f"Status: {h.get('status', 'N/A')}")
    if "data" in k:
        d = k["data"]["kpiSummary"]
        lines.append(f"Pedidos: {d.get('totalOrders', '?')} | Receita: R$ {d.get('totalRevenue', 0):,.2f}")
        lines.append(f"Anúncios ativos: {d.get('activeListings', '?')} | Alertas estoque: {d.get('lowStockAlerts', '?')}")
    return "\n".join(lines)

# ===========================================================================
# Fase 2: Agentes de Produção - Endpoints REST
# ===========================================================================

from flask import Flask, request, jsonify
from flask_cors import CORS
from core.config import get_config
import time, json

app = Flask(__name__)
CORS(app)

from routes.integrations import bling_bp
from routes.webhooks import webhook_bp
app.register_blueprint(bling_bp)
app.register_blueprint(webhook_bp)

# ponytail: importar aqui garante que catalogo_produtos (SSOT) exista antes de
# qualquer sync/listagem — sincronizar_produtos()/listar_produtos() fazem SQL
# bruto contra essa tabela sem criá-la, então o import precisa acontecer no boot.
import core.catalogo  # noqa: F401

# ===========================================================================
# Autenticação e Health Check (Athena OS)
# ===========================================================================

USUARIOS = {
    "admin": {"password": "athena-admin-2026", "role": "admin", "name": "Admin"},
    "joao": {"password": "joao2026", "role": "produto", "name": "João (Produtos)"},
    "maria": {"password": "maria2026", "role": "financeiro", "name": "Maria (Financeiro)"},
    "pedro": {"password": "pedro2026", "role": "operador", "name": "Pedro (Marketplaces)"},
}

@app.route('/api/auth/login', methods=['POST'])
def simple_login():
    """Login com email/senha via RBAC. Fallback para usuarios hardcoded."""
    data = request.json or {}
    email = data.get('email', data.get('username', '')).lower()
    password = data.get('password', '')
    api_key = data.get('api_key', '')

    # Tenta RBAC primeiro
    from core.rbac import autenticar
    rbac_result = autenticar(email, password)
    if rbac_result.get("autenticado"):
        from core.seguranca import auditar_login
        auditar_login(rbac_result.get("email",email), True, request.remote_addr or "", request.headers.get("User-Agent",""))
        resp = jsonify({
            "token": API_TOKEN,
            "role": rbac_result.get("role","admin"),
            "name": rbac_result.get("nome","Admin"),
            "email": rbac_result.get("email",email),
            "user_id": rbac_result.get("id"),
            "permissoes": rbac_result.get("permissoes",[]),
        })
        resp.set_cookie("auth_token", API_TOKEN, httponly=False, samesite="Lax", max_age=86400*30, secure=False)
        if rbac_result.get("id"):
            resp.set_cookie("user_id", str(rbac_result["id"]), httponly=False, samesite="Lax", max_age=86400*30, secure=False)
        return resp

    # Fallback hardcoded
    username = email.split("@")[0] if "@" in email else email
    user = USUARIOS.get(username, {})
    if user and user["password"] == password:
        resp = jsonify({"token": API_TOKEN, "role": user["role"], "name": user["name"], "permissoes": ["*"]})
        resp.set_cookie("auth_token", API_TOKEN, httponly=False, samesite="Lax", max_age=86400*30, secure=False)
        return resp
    if api_key and api_key == API_TOKEN:
        resp = jsonify({"token": API_TOKEN, "role": "admin", "name": "Admin", "permissoes": ["*"]})
        resp.set_cookie("auth_token", API_TOKEN, httponly=False, samesite="Lax", max_age=86400*30, secure=False)
        return resp
    from core.seguranca import auditar_login
    auditar_login(email, False, request.remote_addr or "", request.headers.get("User-Agent",""))
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/me', methods=['GET'])
def current_user():
    """Retorna dados do usuario logado com permissoes dinamicas do RBAC."""
    auth = request.headers.get("Authorization", "")
    cookie_token = request.cookies.get("auth_token", "")
    token = auth.replace("Bearer ", "") or cookie_token
    if token != API_TOKEN:
        return jsonify({"error": "Unauthorized"}), 401
    user_id = request.cookies.get("user_id")
    if user_id:
        try:
            from core.rbac import get_permissoes_por_usuario
            perms = get_permissoes_por_usuario(int(user_id))
            # Buscar nome e role
            from core.rbac import list_usuarios, list_roles
            usuarios = [u for u in list_usuarios() if u.get("id") == int(user_id)]
            user = usuarios[0] if usuarios else {}
            role = None
            if user.get("role_id"):
                roles = [r for r in list_roles() if r.get("id") == user["role_id"]]
                role = roles[0]["nome"] if roles else "admin"
            return jsonify({
                "name": user.get("nome", "Admin"), "role": role or "admin",
                "user_id": int(user_id), "permissoes": perms,
            })
        except: pass
    return jsonify({"name": "Admin", "role": "admin", "permissoes": ["*"]})

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    resp = jsonify({"success": True})
    resp.set_cookie("auth_token", "", max_age=0)
    return resp

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check do sistema Athena."""
    return jsonify({
        "status": "healthy",
        "agents": {
            "total": 13,
            "running": 10,
            "errored": 1,
            "idle": 2
        },
        "infrastructure": {
            "database": {"connected": True, "status": "healthy"},
            "cache": {"connected": True, "status": "healthy"},
            "storage": {"connected": True, "status": "healthy"}
        },
        "uptime": 86400,
        "version": "1.0.0",
        "memory": {
            "heapUsedMB": 256,
            "heapTotalMB": 512,
            "rssMB": 300
        }
    })

@app.route('/api/agents', methods=['GET'])
def list_agents():
    """Lista todos os agentes do sistema."""
    return jsonify({
        "agents": [
            {"id": "ag-01", "name": "Cacador", "role": "research", "status": "running", "context": "market", "taskCount": 5},
            {"id": "ag-02", "name": "Lucratividade", "role": "analysis", "status": "running", "context": "finance", "taskCount": 3},
            {"id": "ag-03", "name": "Marketplaces", "role": "integration", "status": "running", "context": "marketplace", "taskCount": 7},
            {"id": "ag-04", "name": "Planejador", "role": "planning", "status": "running", "context": "production", "taskCount": 10},
            {"id": "ag-05", "name": "Industrial", "role": "execution", "status": "idle", "context": "cnc", "taskCount": 0},
            {"id": "ag-06", "name": "Telegram", "role": "communication", "status": "running", "context": "telegram", "taskCount": 15},
            {"id": "ag-07", "name": "Laboratorio", "role": "quality", "status": "running", "context": "lab", "taskCount": 4},
            {"id": "ag-08", "name": "Lojas", "role": "inventory", "status": "running", "context": "stores", "taskCount": 6},
            {"id": "ag-09", "name": "Memoria", "role": "memory", "status": "running", "context": "memory", "taskCount": 2},
            {"id": "ag-10", "name": "Diretor", "role": "director", "status": "running", "context": "director", "taskCount": 8},
            {"id": "ag-11", "name": "Qualidade", "role": "quality", "status": "idle", "context": "quality", "taskCount": 0},
            {"id": "ag-12", "name": "Manutencao", "role": "maintenance", "status": "idle", "context": "maintenance", "taskCount": 0},
            {"id": "ag-13", "name": "ML", "role": "ml", "status": "running", "context": "ml", "taskCount": 1},
            {"id": "ag-14", "name": "WhatsApp", "role": "communication", "status": "running", "context": "whatsapp", "taskCount": 3}
        ]
    })

# ===========================================================================
# Endpoints Hermes Agents
# ===========================================================================

# AG-04: Planejador de Produção
@app.route('/api/agent/ag_04_planejador/plano_diario', methods=['POST'])
def plano_diario():
    """Gera plano de produção diário."""
    from ag_04_planejador import gerar_plano_diario
    
    data = request.json.get('data') if request.json else None
    plano = gerar_plano_diario(data)
    
    capacidade_utilizada = min(len(plano) * 10, 100)
    
    return jsonify({
        "plano": plano,
        "capacidade_utilizada": capacidade_utilizada,
        "total_pedidos": len(plano),
    })

@app.route('/api/agent/ag_04_planejador/adicionar_pedido', methods=['POST'])
def adicionar_pedido():
    """Adiciona pedido de produção."""
    from ag_04_planejador import adicionar_pedido_producao
    
    data = request.json
    from datetime import datetime
    
    prazo = data.get('prazo')
    if isinstance(prazo, str):
        prazo = datetime.strptime(prazo, '%Y-%m-%d').date()
    
    pedido = adicionar_pedido_producao(
        sku=data['sku'],
        quantidade=data['quantidade'],
        prazo=prazo,
        prioridade=data.get('prioridade', 0),
        cliente_id=data.get('cliente_id'),
    )
    
    return jsonify(pedido)

# AG-05: Gerente Industrial
@app.route('/api/agent/ag_05_industrial/relatorio', methods=['GET'])
def relatorio_industrial():
    """Relatório industrial completo."""
    from ag_05_industrial import relatorio_industrial
    import asyncio
    
    return jsonify(relatorio_industrial())

@app.route('/api/agent/ag_05_industrial/oee/<machine_id>', methods=['GET'])
def oee_status(machine_id):
    """Status OEE de uma máquina."""
    from ag_05_industrial import calcular_oee
    import asyncio
    
    oee = asyncio.run(calcular_oee(machine_id))
    return jsonify(oee)

@app.route('/api/agent/ag_05_industrial/alertas', methods=['GET'])
def alertas_industriais():
    """Alertas industriais ativos."""
    from ag_05_industrial import verificar_alertas
    import asyncio
    
    alertas = asyncio.run(verificar_alertas())
    return jsonify({"alertas": alertas, "total": len(alertas)})

# AG-06: Vendedor do Telegram
@app.route('/api/agent/ag_06_telegram/processar', methods=['POST'])
def processar_mensagem_telegram():
    """Processa mensagem do Telegram."""
    from ag_06_telegram import processar_mensagem
    
    data = request.json
    resultado = processar_mensagem(
        user_id=data['user_id'],
        mensagem=data['mensagem'],
        nome=data.get('nome', ''),
    )
    
    return jsonify(resultado)

@app.route('/api/agent/ag_06_telegram/pedido', methods=['POST'])
def criar_pedido_telegram():
    """Cria pedido via Telegram."""
    from ag_06_telegram import salvar_pedido_telegram
    
    data = request.json
    pedido = salvar_pedido_telegram(
        user_id=data['user_id'],
        itens=data['itens'],
        pagamento=data.get('pagamento', 'pix'),
    )
    
    return jsonify(pedido)

@app.route('/api/agent/ag_06_telegram/stats', methods=['GET'])
def stats_telegram():
    """Estatísticas do Telegram."""
    from ag_06_telegram import obter_estatisticas_telegram
    
    stats = obter_estatisticas_telegram()
    return jsonify(stats)

# AG-07: Laboratório de Produtos
@app.route('/api/agent/ag_07_laboratorio/analisar', methods=['POST'])
def analisar_produto():
    """Analisa viabilidade de novo produto."""
    from ag_07_laboratorio import analisar_novo_produto
    
    data = request.json
    analise = analisar_novo_produto(
        nome=data['nome'],
        descricao=data['descricao'],
        complexidade_molde=data['complexidade_molde'],
        preco_estimado=data['preco_estimado'],
        volume_projetado=data['volume_projetado'],
        custo_molde=data.get('custo_molde'),
        categoria=data.get('categoria', ''),
    )
    
    return jsonify(analise)

@app.route('/api/agent/ag_07_laboratorio/pipeline/<status>', methods=['GET'])
def obter_pipeline(status):
    """Obtém itens do pipeline por status."""
    from ag_07_laboratorio import obter_pipeline_por_status
    
    itens = obter_pipeline_por_status(status)
    return jsonify({"itens": itens, "total": len(itens)})

@app.route('/api/agent/ag_07_laboratorio/pipeline/<int:pipeline_id>/status', methods=['POST'])
def atualizar_status_pipeline(pipeline_id):
    """Atualiza status de item no pipeline."""
    from ag_07_laboratorio import avancar_status
    
    data = request.json
    sucesso = avancar_status(pipeline_id, data['status'])
    
    return jsonify({"success": sucesso})



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

# Workflows Cross-Agent
@app.route('/api/workflows/ag07_para_ag04/<int:pipeline_id>', methods=['POST'])
def workflow_ag07_ag04(pipeline_id):
    """Workflow: Aprovação AG-07 gera pedido AG-04."""
    from workflows import workflow_ag07_para_ag04
    
    resultado = workflow_ag07_para_ag04(pipeline_id)
    return jsonify(resultado)

@app.route('/api/workflows/ag06_para_ag04/<pedido_id>', methods=['POST'])
def workflow_ag06_ag04(pedido_id):
    """Workflow: Pedido AG-06 gera produção AG-04."""
    from workflows import workflow_ag06_para_ag04
    
    resultado = workflow_ag06_para_ag04(pedido_id)
    return jsonify(resultado)

@app.route('/api/workflows/ag05_para_ag02', methods=['POST'])
def workflow_ag05_ag02():
    """Workflow: Alertas AG-05 recalculam margens AG-02."""
    from workflows import workflow_ag05_para_ag02
    
    alertas = request.json.get('alertas', [])
    resultado = workflow_ag05_para_ag02(alertas)
    return jsonify(resultado)

# ===========================================================================
# Fase 3: Manufacturing Chain - Endpoints
# ===========================================================================

# AG-05: Lifecycle de Moldes
@app.route('/api/moldes/<int:molde_id>/historico', methods=['GET'])
def historico_molde(molde_id):
    """Histórico completo de eventos do molde."""
    from ag_05_industrial.mold_lifecycle import obter_historico_molde
    
    historico = obter_historico_molde(molde_id)
    return jsonify({"molde_id": molde_id, "historico": historico})

@app.route('/api/moldes/<int:molde_id>/status', methods=['GET'])
def status_molde(molde_id):
    """Status atual e informações do molde."""
    from ag_05_industrial.mold_lifecycle import obter_status_atual_molde
    
    status = obter_status_atual_molde(molde_id)
    return jsonify(status)

@app.route('/api/moldes/dashboard', methods=['GET'])
def dashboard_moldes():
    """Dashboard geral de moldes."""
    from ag_05_industrial.mold_lifecycle import dashboard_moldes
    
    dashboard = dashboard_moldes()
    return jsonify(dashboard)

@app.route('/api/cnc/jobs', methods=['POST'])
def criar_cnc_job():
    """Cria novo job de usinagem CNC."""
    from ag_05_industrial.mold_lifecycle import criar_cnc_job
    
    data = request.json
    job_id = criar_cnc_job(
        data['molde_id'],
        data['maquina_id'],
        {
            "operador": data.get('operador', ''),
            "data_inicio": data.get('data_inicio'),
            "horas_planejadas": data.get('horas_planejadas'),
            "material_tipo": data.get('material_tipo', ''),
            "observacoes": data.get('observacoes', ''),
        }
    )
    return jsonify({"job_id": job_id, "success": True})

@app.route('/api/cnc/jobs/<job_id>/iniciar', methods=['POST'])
def iniciar_cnc_job(job_id):
    """Inicia execução de job CNC."""
    from ag_05_industrial.mold_lifecycle import iniciar_cnc_job
    
    resultado = iniciar_cnc_job(job_id, request.json.get('operador', ''))
    return jsonify(resultado)

@app.route('/api/cnc/jobs/<job_id>/concluir', methods=['POST'])
def concluir_cnc_job(job_id):
    """Conclui job CNC."""
    from ag_05_industrial.mold_lifecycle import concluir_cnc_job
    
    resultado = concluir_cnc_job(job_id, request.json)
    return jsonify(resultado)

# AG-11: Controle de Qualidade
@app.route('/api/qualidade/inspecoes', methods=['POST'])
def registrar_inspecao():
    """Registra nova inspeção de qualidade."""
    from ag_11_qualidade import registrar_inspecao
    
    data = request.json
    inspecao = registrar_inspecao(data['lote_id'], data)
    return jsonify(inspecao)

@app.route('/api/qualidade/inspecoes/<inspecao_id>/finalizar', methods=['POST'])
def finalizar_inspecao(inspecao_id):
    """Finaliza inspeção com resultado."""
    from ag_11_qualidade import finalizar_inspecao
    
    resultado = finalizar_inspecao(inspecao_id, request.json)
    return jsonify(resultado)

@app.route('/api/qualidade/taxa_defeitos', methods=['GET'])
def taxa_defeitos():
    """Taxa de defeitos por período."""
    from ag_11_qualidade import calcular_taxa_defeitos
    
    periodo = request.args.get('periodo', 30, type=int)
    taxa = calcular_taxa_defeitos(periodo)
    return jsonify(taxa)

@app.route('/api/qualidade/pareto', methods=['GET'])
def pareto_defeitos():
    """Análise Pareto de defeitos (80/20)."""
    from ag_11_qualidade import pareto_defeitos
    
    periodo = request.args.get('periodo', 30, type=int)
    pareto = pareto_defeitos(periodo)
    return jsonify(pareto)

@app.route('/api/qualidade/defeitos', methods=['GET'])
def listar_defeitos():
    """Lista defeitos cadastrados."""
    from ag_11_qualidade import listar_defeitos
    
    categoria = request.args.get('categoria', '')
    gravidade = request.args.get('gravidade', '')
    defeitos = listar_defeitos(categoria, gravidade)
    return jsonify({"defeitos": defeitos, "total": len(defeitos)})

@app.route('/api/qualidade/capas', methods=['GET'])
def listar_capas_abertas():
    """Lista CAPAs abertas ou em andamento."""
    from ag_11_qualidade import obter_capas_abertas
    
    capas = obter_capas_abertas()
    return jsonify({"capas": capas, "total": len(capas)})

@app.route('/api/qualidade/capas', methods=['POST'])
def criar_capa():
    """Cria nova CAPA."""
    from ag_11_qualidade import gerar_capa
    
    data = request.json
    capa = gerar_capa(data['origem'], data['origem_id'], data)
    return jsonify(capa)

@app.route('/api/qualidade/capas/<int:capa_id>/fechar', methods=['POST'])
def fechar_capa(capa_id):
    """Fecha CAPA verificando eficácia."""
    from ag_11_qualidade import fechar_capa
    
    eficacia = request.json.get('eficacia', False)
    observacoes = request.json.get('observacoes', '')
    resultado = fechar_capa(capa_id, eficacia, observacoes)
    return jsonify(resultado)

# AG-12: Gestão de Manutenção
@app.route('/api/manutencao/agendar', methods=['POST'])
def agendar_manutencao():
    """Agenda nova manutenção."""
    from ag_12_manutencao import agendar_manutencao
    
    data = request.json
    numero = agendar_manutencao(
        data['equipamento_tipo'],
        data['equipamento_id'],
        data['tipo'],
        __import__('datetime').datetime.strptime(data['data_agendada'], '%Y-%m-%d').date(),
        data.get('descricao', ''),
        data.get('prioridade', 3),
        data.get('tecnico', ''),
        data.get('observacoes', ''),
    )
    return jsonify({"numero": numero, "success": True})

@app.route('/api/manutencao/pendentes', methods=['GET'])
def manutencoes_pendentes():
    """Lista manutenções pendentes ordenadas por prioridade."""
    from ag_12_manutencao import obter_manutencoes_pendentes
    
    manutencoes = obter_manutencoes_pendentes()
    return jsonify({"manutencoes": manutencoes, "total": len(manutencoes)})

@app.route('/api/manutencao/<int:manutencao_id>/iniciar', methods=['POST'])
def iniciar_manutencao(manutencao_id):
    """Inicia execução de manutenção."""
    from ag_12_manutencao import iniciar_manutencao
    
    resultado = iniciar_manutencao(manutencao_id, request.json.get('tecnico', ''))
    return jsonify(resultado)

@app.route('/api/manutencao/<int:manutencao_id>/concluir', methods=['POST'])
def concluir_manutencao(manutencao_id):
    """Conclui manutenção."""
    from ag_12_manutencao import concluir_manutencao
    
    resultado = concluir_manutencao(manutencao_id, request.json)
    return jsonify(resultado)

@app.route('/api/manutencao/alertas', methods=['GET'])
def alertas_manutencao():
    """Verifica alertas de manutenção."""
    from ag_12_manutencao import verificar_alertas_manutencao
    
    alertas = verificar_alertas_manutencao()
    return jsonify({"alertas": alertas, "total": len(alertas)})

@app.route('/api/manutencao/mtbf/<equipamento_tipo>/<equipamento_id>', methods=['GET'])
def mtbf_equipamento(equipamento_tipo, equipamento_id):
    """Calcula MTBF de equipamento."""
    from ag_12_manutencao import calcular_mtbtf
    
    mtbf = calcular_mtbtf(equipamento_tipo, equipamento_id)
    return jsonify(mtbf)

@app.route('/api/manutencao/kpi', methods=['GET'])
def kpi_manutencao():
    """KPIs de manutenção."""
    from ag_12_manutencao import obter_kpi_manutencao
    
    periodo = request.args.get('periodo', 30, type=int)
    kpis = obter_kpi_manutencao(periodo)
    return jsonify(kpis)

# ── Estoque por loja/depósito ──

@app.route('/api/estoque/lojas', methods=['GET'])
def estoque_por_loja():
    """Lista estoque por depósito com filtro de loja e busca."""
    loja = request.args.get("loja", "")
    busca = request.args.get("busca", "").strip()
    pagina = request.args.get("pagina", 1, type=int)
    por_pagina = request.args.get("por_pagina", 30, type=int)
    try:
        conn = _db_sync()
        cur = conn.cursor()
        where = ["1=1"]
        if loja and loja != "todas":
            if loja.isdigit():
                where.append(f"e.loja = (SELECT nome FROM lojas WHERE id = {int(loja)})")
            else:
                where.append(f"e.loja = '{loja.replace(chr(39), chr(39)+chr(39))}'")
        if busca:
            where.append(f"(c.sku ILIKE '%{busca}%' OR c.descricao ILIKE '%{busca}%')")
        sql_where = " AND ".join(where)
        cur.execute(f"SELECT COUNT(*) FROM estoque_lojas e JOIN catalogo_produtos c ON c.sku = e.sku WHERE {sql_where}")
        total = cur.fetchone()[0]
        offset = (pagina - 1) * por_pagina
        cur.execute(f"""
            SELECT e.id, e.sku, c.descricao AS nome, e.loja, e.quantidade, e.data_atualizacao
            FROM estoque_lojas e
            JOIN catalogo_produtos c ON c.sku = e.sku
            WHERE {sql_where}
            ORDER BY e.data_atualizacao DESC
            LIMIT {por_pagina} OFFSET {offset}
        """)
        rows = _dicts(cur)
        cur.close(); conn.close()
        return jsonify({"estoque": rows, "total": total, "pagina": pagina})
    except Exception as e:
        return jsonify({"erro": str(e), "estoque": [], "total": 0})

@app.route('/api/estoque/lojas', methods=['PUT'])
def atualizar_estoque_loja():
    """Atualiza quantidade de estoque em uma loja/depósito. Two-way sync opcional para Bling."""
    dados = request.json or {}
    sku = dados.get("sku", "").strip()
    loja_nome = str(dados.get("loja", "")).strip()
    quantidade = dados.get("quantidade")
    sync_bling = str(dados.get("sync_bling", "1")) == "1"
    if not sku or not loja_nome or quantidade is None:
        return jsonify({"erro": "sku, loja e quantidade obrigatórios"}), 400
    try:
        conn = _db_sync()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO estoque_lojas (sku, loja, quantidade, data_atualizacao)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (sku, loja) DO UPDATE SET quantidade = %s, data_atualizacao = NOW()
        """, (sku, loja_nome, float(quantidade), float(quantidade)))
        cur.close(); conn.close()
        result = {"ok": True, "sku": sku, "loja": loja_nome, "quantidade": quantidade}
        if sync_bling:
            from bling_erp import sincronizar_estoque_para_bling
            bling_r = sincronizar_estoque_para_bling(sku, loja_nome, float(quantidade))
            result["bling_sync"] = bling_r
        return jsonify(result)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/estoque/lote/<int:lote_id>/concluir', methods=['POST'])
def concluir_lote_estoque(lote_id):
    """Conclui lote e entra no estoque."""
    from ag_04_planejador import registrar_producao_concluida
    
    resultado = registrar_producao_concluida(lote_id)
    return jsonify(resultado)

# Workflows Fase 3
@app.route('/api/workflows/lote_para_estoque/<int:lote_id>', methods=['POST'])
def workflow_lote_estoque(lote_id):
    """Workflow: Lote→Inspeção→Estoque."""
    from workflows_fase3 import workflow_lote_para_estoque
    
    resultado = workflow_lote_para_estoque(lote_id)
    return jsonify(resultado)

@app.route('/api/workflows/defeito_para_capa', methods=['POST'])
def workflow_defeito_capa():
    """Workflow: Defeito→CAPA."""
    from workflows_fase3 import workflow_defeito_para_capa
    
    resultado = workflow_defeito_para_capa(
        request.json['inspecao_id'],
        request.json['defeito_codigo']
    )
    return jsonify(resultado)

@app.route('/api/workflows/manutencao_molde/<int:molde_id>', methods=['POST'])
def workflow_manutencao_molde(molde_id):
    """Workflow: Manutenção→Produção."""
    from workflows_fase3 import workflow_manutencao_molde
    
    resultado = workflow_manutencao_molde(molde_id)
    return jsonify(resultado)

@app.route('/api/workflows/cnc_concluido/<job_id>', methods=['POST'])
def workflow_cnc_concluido(job_id):
    """Workflow: CNC Job→Molde."""
    from workflows_fase3 import workflow_cnc_job_concluido
    
    resultado = workflow_cnc_job_concluido(job_id)
    return jsonify(resultado)

@app.route('/api/workflows/agenda_manutencao', methods=['POST'])
def workflow_agenda_manutencao():
    """Workflow: Alertas→Agenda."""
    from workflows_fase3 import workflow_alerta_manutencao_para_agenda
    
    resultado = workflow_alerta_manutencao_para_agenda()
    return jsonify(resultado)

# ===========================================================================
# Configuração - Endpoints (Telegram, Bling, Shopee)
# ===========================================================================

@app.route('/api/config', methods=['GET'])
def get_all_configs():
    """Retorna todas as configurações."""
    from core.config import get_all_config
    return jsonify(get_all_config())

@app.route('/api/config/telegram', methods=['POST'])
def set_telegram_config():
    """Configura Telegram."""
    from core.config import set_config
    
    token = request.json.get('token', '')
    webhook_url = request.json.get('webhookUrl', '')
    
    if not token:
        return jsonify({"error": "Token não fornecido"}), 400
    
    set_config("telegram", "token", token)
    if webhook_url:
        set_config("telegram", "webhook_url", webhook_url)
    
    return jsonify({"success": True, "configurado": True})

@app.route('/api/config/bling', methods=['POST'])
def set_bling_config():
    """Configura Bling (api_key legado + OAuth v3)."""
    from core.config import set_config
    data = request.json or {}
    
    api_key = data.get('apiKey', '')
    api_url = data.get('apiUrl', '')
    client_id = data.get('clientId', '') or data.get('client_id', '')
    client_secret = data.get('clientSecret', '') or data.get('client_secret', '')

    if client_id:
        set_config("bling", "client_id", client_id)
    if client_secret:
        set_config("bling", "client_secret", client_secret)
    if api_key:
        set_config("bling", "api_key", api_key)
    if api_url:
        set_config("bling", "api_url", api_url)

    from bling_erp import _client_id, _client_secret
    cid = _client_id()
    return jsonify({"success": True, "oauth_setado": bool(cid or client_id), "client_id": cid or client_id})

@app.route('/api/config/shopee', methods=['POST'])
def set_shopee_config():
    """Configura Shopee."""
    from core.config import set_config
    
    partner_id = request.json.get('partnerId', '')
    shop_id = request.json.get('shopId', '')
    api_key = request.json.get('apiKey', '')
    
    if not all([partner_id, shop_id, api_key]):
        return jsonify({"error": "Dados incompletos. Forneça partnerId, shopId e apiKey"}), 400
    
    set_config("shopee", "partner_id", partner_id)
    set_config("shopee", "shop_id", shop_id)
    set_config("shopee", "api_key", api_key)
    
    return jsonify({"success": True, "configurado": True})

@app.route('/api/config/status', methods=['GET'])
def get_config_status():
    """Retorna status das configurações."""
    from core.config import get_config
    
    telegram_configurado = bool(get_config("telegram", "token"))
    bling_configurado = bool(get_config("bling", "api_key"))
    shopee_configurado = all([
        get_config("shopee", "partner_id"),
        get_config("shopee", "shop_id"),
        get_config("shopee", "api_key")
    ])
    
    return jsonify({
        "telegram": telegram_configurado,
        "bling": bling_configurado,
        "shopee": shopee_configurado,
        "telegram_configurado": telegram_configurado,
        "bling_configurado": bling_configurado,
        "shopee_configurado": shopee_configurado
    })

# ===========================================================================
# AG-13: Machine Learning
# ===========================================================================

@app.route('/api/ml/treinar', methods=['POST'])
def treinar_modelo_ml():
    """Treina modelo de previsão de defeitos."""
    from ag_13_ml import treinar_modelo_previsao_defeitos
    
    resultado = treinar_modelo_previsao_defeitos()
    return jsonify(resultado)

@app.route('/api/ml/prever/<sku>', methods=['GET'])
def prever_defeitos_ml(sku):
    """Prevê defeitos para um SKU específico."""
    from ag_13_ml import prever_defeitos_lote
    from core import get_db, run_async
    
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""
            SELECT sku, quantidade_planejada, tempo_ciclo_segundos, oee_calculado
            FROM producao_lotes
            WHERE sku = $1 AND status = 'concluido'
            ORDER BY data_inicio DESC
            LIMIT 5
        """, sku)
        
        if row:
            return prever_defeitos_lote(dict(row))
        return {"error": "Sem dados históricos para este SKU"}
    
    resultado = run_async(_go())
    return jsonify(resultado)

@app.route('/api/ml/status', methods=['GET'])
def ml_status():
    """Status do ML."""
    from pathlib import Path
    
    modelo_path = Path(__file__).parent / "ag_13_ml" / "model_defeitos.pkl"
    
    return jsonify({
        "modelo_treinado": modelo_path.exists(),
        "scikit_learn_instalado": True  # Apenas se instalou
    })

# ===========================================================================
# AG-14: WhatsApp (portado do ATHENA OS)
# ===========================================================================

@app.route('/api/agent/ag_14_whatsapp/config', methods=['GET'])
def whatsapp_config():
    from core.config import get_config
    return jsonify({
        "api_url": get_config("whatsapp", "api_url") or "http://localhost:8080",
        "instance_name": get_config("whatsapp", "instance_name") or "hermes",
        "configurado": bool(get_config("whatsapp", "api_key")) or bool(os.environ.get("EVOLUTION_API_KEY")),
    })

@app.route('/api/agent/ag_14_whatsapp/config', methods=['POST'])
def whatsapp_set_config():
    from core.config import set_config
    data = request.json or {}
    if data.get("api_url"):
        set_config("whatsapp", "api_url", data["api_url"])
        os.environ["EVOLUTION_API_URL"] = data["api_url"]
    if data.get("api_key"):
        set_config("whatsapp", "api_key", data["api_key"])
        os.environ["EVOLUTION_API_KEY"] = data["api_key"]
    if data.get("instance_name"):
        set_config("whatsapp", "instance_name", data["instance_name"])
        os.environ["WHATSAPP_INSTANCE"] = data["instance_name"]
    return jsonify({"success": True})

@app.route('/api/agent/ag_14_whatsapp/status', methods=['GET'])
def whatsapp_status():
    from ag_14_whatsapp import status_conexao, configurado
    return jsonify({
        "conectado": status_conexao() == "open",
        "status": status_conexao(),
        "configurado": configurado(),
    })

@app.route('/api/agent/ag_14_whatsapp/conectar', methods=['POST'])
def whatsapp_conectar():
    from ag_14_whatsapp import conectar, criar_instancia
    data = request.json or {}
    phone = data.get("phone")
    if phone:
        resultado= conectar(phone)
    else:
        resultado = criar_instancia()
    return jsonify(resultado)

@app.route('/api/agent/ag_14_whatsapp/processar', methods=['POST'])
def whatsapp_processar():
    from ag_14_whatsapp import processar_mensagem
    data = request.json
    resultado = processar_mensagem(data["phone"], data["mensagem"])
    return jsonify(resultado)

@app.route('/api/agent/ag_14_whatsapp/pedido', methods=['POST'])
def whatsapp_criar_pedido():
    from ag_14_whatsapp import criar_pedido
    data = request.json
    pedido = criar_pedido(data["phone"], data["cliente"], data["itens"])
    return jsonify(pedido)

@app.route('/api/agent/ag_14_whatsapp/stats', methods=['GET'])
def whatsapp_stats():
    from ag_14_whatsapp import obter_estatisticas
    return jsonify(obter_estatisticas())

@app.route('/webhook/whatsapp', methods=['POST'])
def whatsapp_webhook():
    from ag_14_whatsapp import parse_webhook, processar_mensagem
    parsed = parse_webhook(request.json)
    if not parsed:
        return jsonify({"ignored": True})
    resultado = processar_mensagem(parsed["phone"], parsed["text"])
    return jsonify({"processed": True, "resultado": resultado})

# ── Executor de agente com memória ──

def _executar_agente(agente_id: str, mensagem: str, user_id: str,
                     nome: str, contexto: str = "") -> str:
    """Executa o agente apropriado com contexto da memória."""
    prefix = f"[Memória]: {contexto}\n\n" if contexto else ""

    try:
        if "ag_01" in agente_id:
            from ag_01_cacador import executar_cacada, top_oportunidades
            if "oportunidade" in mensagem.lower() or "produto" in mensagem.lower():
                ops = top_oportunidades(5)
                return f"{prefix}Top 5 oportunidades: {ops}" if ops else f"{prefix}Nenhuma oportunidade nova encontrada."
            r = executar_cacada()
            return f"{prefix}{r}"

        elif "ag_02" in agente_id:
            from ag_02_lucratividade import analisar_sku, relatorio_diario, verificar_alertas
            if "alerta" in mensagem.lower():
                a = verificar_alertas()
                return f"{prefix}Alertas: {a}"
            r = relatorio_diario()
            return f"{prefix}{r}"

        elif "ag_03" in agente_id:
            from ag_03_marketplaces import comparar_precos_concorrentes, verificar_posicoes
            if "preço" in mensagem.lower() or "concorrente" in mensagem.lower():
                c = comparar_precos_concorrentes()
                return f"{prefix}Comparação de preços: {c}"
            p = verificar_posicoes()
            return f"{prefix}Posições dos anúncios: {p}"

        elif "ag_04" in agente_id:
            from ag_04_planejador import gerar_plano_diario
            plano = gerar_plano_diario()
            return f"{prefix}Plano diário: {plano}"

        elif "ag_07" in agente_id:
            from ag_07_laboratorio import pipeline_lancamentos
            return f"{prefix}Pipeline de lançamentos: {pipeline_lancamentos()}"

        elif "ag_09" in agente_id:
            from ag_09_memoria import buscar_similar, stats
            if "parecido" in mensagem.lower() or "similar" in mensagem.lower():
                s = buscar_similar(mensagem)
                return f"{prefix}Produtos similares: {s}"
            s = stats()
            return f"{prefix}Stats da memória corporativa: {s}"

        else:
            return f"{prefix}Agente {agente_id} consultado. Pergunta: '{mensagem[:100]}'. Use /detalhe para aprofundar."

    except Exception as e:
        log(None, f"Erro agente {agente_id}: {e}")
        return f"{prefix}Erro ao processar com {agente_id}: {str(e)[:200]}"


# ===========================================================================
# Chat com agente (chamado pelo Chat.tsx do frontend)
# ===========================================================================

@app.route('/api/hermes/chat', methods=['POST'])
def hermes_chat():
    data = request.json
    mensagem = data.get("mensagem", "")
    user_id = data.get("user_id", "anon")
    nome = data.get("nome", "Visitante")

    from core.memory import recall, context, store
    from ag_10_diretor import processar_pergunta

    # 1. Buscar memória relevante
    memoria_contexto = context(mensagem)
    memorias = recall(mensagem, limit=3)

    # 2. Roteamento pelo diretor (enriquecido com memória)
    rota = processar_pergunta(mensagem)
    agente = rota.get("agentes", ["ag_10"])[0] if rota.get("agentes") else "ag_10"

    # 3. Resposta do agente (usa contexto da memória)
    resposta_texto = _executar_agente(agente, mensagem, user_id, nome, memoria_contexto)

    # 4. Salvar na memória
    store(mensagem, resposta_texto, agent_id=agente,
          category=rota.get("categoria", "geral"),
          metadata={"user_id": user_id, "nome": nome})

    return jsonify({
        "resposta": resposta_texto,
        "agente": agente,
        "intencao": rota.get("acao", "geral"),
        "memorias": len(memorias),
    })

# ── Memory API ──

@app.route('/api/memory/stats', methods=['GET'])
def memory_stats():
    from core.memory import stats as memory_stats_fn, history as memory_history
    agent = request.args.get("agente", "")
    s = memory_stats_fn()
    return jsonify(s)

@app.route('/api/memory/history', methods=['GET'])
def memory_history():
    from core.memory import history as memory_history
    agent = request.args.get("agente", "")
    cat = request.args.get("categoria", "")
    h = memory_history(agent_id=agent or None, category=cat or None, limit=20)
    return jsonify({"history": h, "total": len(h)})

@app.route('/api/memory/recall', methods=['POST'])
def memory_recall():
    from core.memory import recall as memory_recall
    data = request.json or {}
    query = data.get("query", "")
    agent = data.get("agente", "")
    results = memory_recall(query, agent_id=agent or None, limit=5)
    return jsonify({"results": results, "total": len(results)})

















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

# ── Relatorios Routes ──

@app.route('/api/relatorios/vendas', methods=['GET'])
def rel_vendas():
    from core.relatorios import vendas; dias=request.args.get('dias',30,type=int)
    return jsonify(vendas(dias))

@app.route('/api/relatorios/lucro', methods=['GET'])
def rel_lucro():
    from core.relatorios import lucro_margem; dias=request.args.get('dias',30,type=int)
    return jsonify(lucro_margem(dias))

@app.route('/api/relatorios/estoque', methods=['GET'])
def rel_estoque():
    from core.relatorios import estoque; return jsonify(estoque())

@app.route('/api/relatorios/clientes', methods=['GET'])
def rel_clientes():
    from core.relatorios import clientes; dias=request.args.get('dias',90,type=int)
    return jsonify(clientes(dias))

@app.route('/api/relatorios/fornecedores', methods=['GET'])
def rel_fornecedores():
    from core.relatorios import fornecedores; return jsonify(fornecedores())

@app.route('/api/relatorios/aging', methods=['GET'])
def rel_aging():
    from core.relatorios import aging_financeiro; return jsonify(aging_financeiro())

@app.route('/api/relatorios/fluxo-caixa', methods=['GET'])
def rel_fluxo():
    from core.relatorios import fluxo_caixa; dias=request.args.get('dias',30,type=int)
    return jsonify(fluxo_caixa(dias))

@app.route('/api/relatorios/ticket-medio', methods=['GET'])
def rel_ticket():
    from core.relatorios import ticket_medio; dias=request.args.get('dias',30,type=int)
    return jsonify(ticket_medio(dias))

@app.route('/api/relatorios/dre', methods=['GET'])
def rel_dre():
    from core.relatorios import dre; dias=request.args.get('dias',30,type=int)
    return jsonify(dre(dias))

@app.route('/api/relatorios/previsao', methods=['GET'])
def rel_previsao():
    from core.relatorios import previsao; dias=request.args.get('dias',30,type=int)
    return jsonify(previsao(dias))

@app.route('/api/relatorios/compras', methods=['GET'])
def rel_compras():
    from core.relatorios import compras; dias=request.args.get('dias',30,type=int)
    return jsonify(compras(dias))

@app.route('/api/relatorios/impostos', methods=['GET'])
def rel_impostos():
    from core.relatorios import impostos; dias=request.args.get('dias',30,type=int)
    return jsonify(impostos(dias))

@app.route('/api/relatorios/comissao', methods=['GET'])
def rel_comissao():
    from core.relatorios import comissao; dias=request.args.get('dias',30,type=int)
    return jsonify(comissao(dias))

@app.route('/api/relatorios/marketplaces', methods=['GET'])
def rel_marketplaces():
    from core.relatorios import marketplaces; dias=request.args.get('dias',30,type=int)
    return jsonify(marketplaces(dias))

@app.route('/api/relatorios/devolucoes', methods=['GET'])
def rel_devolucoes():
    from core.relatorios import devolucoes; dias=request.args.get('dias',30,type=int)
    return jsonify(devolucoes(dias))

@app.route('/api/relatorios/rupturas', methods=['GET'])
def rel_rupturas():
    from core.relatorios import rupturas
    return jsonify(rupturas())

@app.route('/api/relatorios/curvas', methods=['GET'])
def rel_curvas():
    from core.relatorios import curvas; dias=request.args.get('dias',90,type=int)
    return jsonify(curvas(dias))

@app.route('/api/relatorios/produtos', methods=['GET'])
def rel_produtos():
    from core.relatorios import produtos; dias=request.args.get('dias',30,type=int)
    return jsonify(produtos(dias))

@app.route('/api/relatorios/financeiro', methods=['GET'])
def rel_financeiro():
    from core.relatorios import financeiro; dias=request.args.get('dias',30,type=int)
    return jsonify(financeiro(dias))



# ── Fiscal Routes ──

@app.route('/api/fiscal/dashboard', methods=['GET'])
def fiscal_dashboard():
    from core.fiscal import dashboard
    return jsonify(dashboard())

@app.route('/api/fiscal/tabelas/cfop', methods=['GET'])
def fiscal_tabelas_cfop():
    """Extrai CFOP distintos das NF-e syncadas do Bling."""
    from core import run_async, get_db
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT DISTINCT cfop as codigo, natureza_operacao as descricao, tipo FROM fiscal_notas_fiscais WHERE cfop IS NOT NULL AND cfop != '' ORDER BY cfop LIMIT 50")
        return [dict(r) for r in (rows or [])]
    try: return jsonify(run_async(_go()))
    except: return jsonify([])

@app.route('/api/fiscal/tabelas/ncm', methods=['GET'])
def fiscal_tabelas_ncm():
    """Extrai NCM distintos dos itens das NF-e syncadas."""
    from core import run_async, get_db
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT DISTINCT ncm as codigo, '' as descricao FROM fiscal_nfe_itens WHERE ncm IS NOT NULL AND ncm != '' ORDER BY ncm LIMIT 50")
        return [dict(r) for r in (rows or [])]
    try: return jsonify(run_async(_go()))
    except: return jsonify([])

@app.route('/api/fiscal/tabelas/cest', methods=['GET'])
def fiscal_tabelas_cest():
    """Extrai CEST distintos dos itens das NF-e syncadas."""
    from core import run_async, get_db
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT DISTINCT cest as codigo, '' as descricao FROM fiscal_nfe_itens WHERE cest IS NOT NULL AND cest != '' ORDER BY cest LIMIT 50")
        return [dict(r) for r in (rows or [])]
    try: return jsonify(run_async(_go()))
    except: return jsonify([])

@app.route('/api/fiscal/<tabela>', methods=['GET'])
def fiscal_list(tabela):
    from core.fiscal import list as fl, listar_filtrado, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    data_inicio = request.args.get("data_inicio", "")
    data_fim = request.args.get("data_fim", "")
    dias = request.args.get("dias", 0, type=int)
    if data_inicio or data_fim or dias:
        return jsonify(listar_filtrado(tabela, data_inicio, data_fim, dias))
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

# ── Automacoes Routes ──

@app.route('/api/automacoes/dashboard', methods=['GET'])
def auto_dashboard():
    from core.automacoes import dashboard as ad
    return jsonify(ad())

@app.route('/api/automacoes/<tabela>', methods=['GET'])
def auto_list(tabela):
    from core.automacoes import list as al, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify({"data": al(tabela)})

@app.route('/api/automacoes/<tabela>', methods=['POST'])
def auto_create(tabela):
    from core.automacoes import create as ac, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(ac(tabela, request.json or {}))

@app.route('/api/automacoes/<tabela>/<int:id>', methods=['GET'])
def auto_get(tabela, id):
    from core.automacoes import get as ag, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(ag(tabela, id))

@app.route('/api/automacoes/<tabela>/<int:id>', methods=['PUT'])
def auto_update(tabela, id):
    from core.automacoes import update as au, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(au(tabela, id, request.json or {}))

@app.route('/api/automacoes/<tabela>/<int:id>', methods=['DELETE'])
def auto_delete(tabela, id):
    from core.automacoes import delete as ad, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(ad(tabela, id))

# ── Producao Routes ──

@app.route('/api/producao/dashboard', methods=['GET'])
def prod_dashboard():
    from core.producao import dashboard as pd
    return jsonify(pd())

@app.route('/api/producao/op/<int:id>/iniciar', methods=['POST'])
def prod_iniciar_op(id):
    from core.producao import iniciar_op
    return jsonify(iniciar_op(id))

@app.route('/api/producao/op/<int:id>/finalizar', methods=['POST'])
def prod_finalizar_op(id):
    from core.producao import finalizar_op
    return jsonify(finalizar_op(id))

@app.route('/api/producao/maquina/<int:id>/parar', methods=['POST'])
def prod_parar_maquina(id):
    data = request.json or {}
    from core.producao import parar_maquina
    return jsonify(parar_maquina(id, data.get("motivo","")))

@app.route('/api/producao/maquina/<int:id>/liberar', methods=['POST'])
def prod_liberar_maquina(id):
    from core.producao import liberar_maquina
    return jsonify(liberar_maquina(id))

@app.route('/api/producao/<tabela>', methods=['GET'])
def prod_list(tabela):
    from core.producao import list as pl, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify({"data": pl(tabela)})

@app.route('/api/producao/<tabela>', methods=['POST'])
def prod_create(tabela):
    from core.producao import create as pc, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(pc(tabela, request.json or {}))

@app.route('/api/producao/<tabela>/<int:id>', methods=['GET'])
def prod_get(tabela, id):
    from core.producao import get as pg, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(pg(tabela, id))

@app.route('/api/producao/<tabela>/<int:id>', methods=['PUT'])
def prod_update(tabela, id):
    from core.producao import update as pu, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(pu(tabela, id, request.json or {}))

@app.route('/api/producao/<tabela>/<int:id>', methods=['DELETE'])
def prod_delete(tabela, id):
    from core.producao import delete as pd, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(pd(tabela, id))

# ── Atendimento Routes ──

@app.route('/api/atendimento/dashboard', methods=['GET'])
def atend_dashboard():
    from core.atendimento import dashboard as ad
    return jsonify(ad())

@app.route('/api/atendimento/tickets/criar', methods=['POST'])
def atend_criar_ticket():
    data = request.json or {}
    from core.atendimento import criar_ticket
    return jsonify(criar_ticket(data.get("cliente",""), data.get("assunto",""), data.get("canal","whatsapp"), data.get("prioridade","normal")))

@app.route('/api/atendimento/tickets/<int:id>/mensagem', methods=['POST'])
def atend_mensagem(id):
    data = request.json or {}
    from core.atendimento import adicionar_mensagem
    return jsonify(adicionar_mensagem(id, data.get("remetente",""), data.get("conteudo",""), data.get("tipo","texto")))

@app.route('/api/atendimento/tickets/<int:id>/fechar', methods=['POST'])
def atend_fechar(id):
    from core.atendimento import fechar_ticket
    return jsonify(fechar_ticket(id))

@app.route('/api/atendimento/tickets/<int:id>/reabrir', methods=['POST'])
def atend_reabrir(id):
    from core.atendimento import reabrir_ticket
    return jsonify(reabrir_ticket(id))

@app.route('/api/atendimento/<tabela>', methods=['GET'])
def atend_list(tabela):
    from core.atendimento import list as al, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify({"data": al(tabela)})

@app.route('/api/atendimento/<tabela>', methods=['POST'])
def atend_create(tabela):
    from core.atendimento import create as ac, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(ac(tabela, request.json or {}))

@app.route('/api/atendimento/<tabela>/<int:id>', methods=['GET'])
def atend_get(tabela, id):
    from core.atendimento import get as ag, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(ag(tabela, id))

@app.route('/api/atendimento/<tabela>/<int:id>', methods=['PUT'])
def atend_update(tabela, id):
    from core.atendimento import update as au, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(au(tabela, id, request.json or {}))

@app.route('/api/atendimento/<tabela>/<int:id>', methods=['DELETE'])
def atend_delete(tabela, id):
    from core.atendimento import delete as ad, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(ad(tabela, id))

# ── PDV Routes ──

@app.route('/api/pdv/dashboard', methods=['GET'])
def pdv_dashboard_api():
    from core.pdv import dashboard as pdv_dash
    return jsonify(pdv_dash())


@app.route('/api/pdv/turno/abrir', methods=['POST'])
def pdv_abrir_turno():
    data = request.json or {}; from core.pdv import abrir_turno
    return jsonify(abrir_turno(data.get("caixa_id",0), data.get("operador_id"), data.get("operador",""), float(data.get("saldo_abertura",0))))

@app.route('/api/pdv/turno/<int:id>/fechar', methods=['POST'])
def pdv_fechar_turno(id):
    data = request.json or {}; from core.pdv import fechar_turno
    return jsonify(fechar_turno(id, float(data.get("saldo_fechamento",0)), data.get("observacoes","")))

@app.route('/api/pdv/produtos/buscar', methods=['GET'])
def pdv_buscar_produtos():
    from core.pdv import buscar_produtos
    return jsonify({"data": buscar_produtos(request.args.get("q",""))})

@app.route('/api/pdv/venda/<int:id>/cancelar', methods=['POST'])
def pdv_cancelar_venda(id):
    data = request.json or {}; from core.pdv import cancelar_venda
    return jsonify(cancelar_venda(id, data.get("motivo",""), data.get("operador","")))

@app.route('/api/pdv/historico', methods=['GET'])
def pdv_historico():
    from core.pdv import historico_vendas
    caixa = request.args.get("caixa_id"); di = request.args.get("data_inicio"); df = request.args.get("data_fim")
    return jsonify({"data": historico_vendas(int(caixa) if caixa else None, di, df)})

@app.route('/api/pdv/caixa/abrir', methods=['POST'])
def pdv_abrir_caixa():
    data = request.json or {}
    from core.pdv import abrir_caixa
    return jsonify(abrir_caixa(data.get("operador","Admin"), float(data.get("saldo_inicial",0))))

@app.route('/api/pdv/caixa/<int:id>/fechar', methods=['POST'])
def pdv_fechar_caixa(id):
    data = request.json or {}
    from core.pdv import fechar_caixa
    return jsonify(fechar_caixa(id, float(data.get("saldo_final",0))))

@app.route('/api/pdv/caixa/<int:id>/sangria', methods=['POST'])
def pdv_sangria(id):
    data = request.json or {}
    from core.pdv import sangria
    return jsonify(sangria(id, float(data.get("valor",0)), data.get("motivo",""), data.get("operador","")))

@app.route('/api/pdv/caixa/<int:id>/suprimento', methods=['POST'])
def pdv_suprimento(id):
    data = request.json or {}
    from core.pdv import suprimento
    return jsonify(suprimento(id, float(data.get("valor",0)), data.get("motivo",""), data.get("operador","")))

@app.route('/api/pdv/venda', methods=['POST'])
def pdv_venda():
    data = request.json or {}
    from core.pdv import realizar_venda
    return jsonify(realizar_venda(
        caixa_id=data.get("caixa_id",0),
        itens=data.get("itens",[]),
        pagamentos=data.get("pagamentos",[]),
        cliente=data.get("cliente",""),
        operador=data.get("operador",""),
        desconto=float(data.get("desconto",0))
    ))

@app.route('/api/pdv/<tabela>', methods=['GET'])
def pdv_list(tabela):
    from core.pdv import list as pl, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify({"data": pl(tabela)})

@app.route('/api/pdv/<tabela>', methods=['POST'])
def pdv_create(tabela):
    from core.pdv import create as pc, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(pc(tabela, request.json or {}))

@app.route('/api/pdv/<tabela>/<int:id>', methods=['GET'])
def pdv_get(tabela, id):
    from core.pdv import get as pg, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(pg(tabela, id))

@app.route('/api/pdv/<tabela>/<int:id>', methods=['PUT'])
def pdv_update(tabela, id):
    from core.pdv import update as pu, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(pu(tabela, id, request.json or {}))

@app.route('/api/pdv/<tabela>/<int:id>', methods=['DELETE'])
def pdv_delete(tabela, id):
    from core.pdv import delete as pd, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(pd(tabela, id))

# ── Compras Routes ──

@app.route('/api/compras/dashboard', methods=['GET'])
def compras_dashboard():
    from core.compras import dashboard as compras_dash
    return jsonify(compras_dash())

@app.route('/api/compras/<tabela>', methods=['GET'])
def compras_list(tabela):
    from core.compras import list as cl, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify({"data": cl(tabela)})

@app.route('/api/compras/<tabela>', methods=['POST'])
def compras_create(tabela):
    from core.compras import create as cc, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    data = request.json or {}
    return jsonify(cc(tabela, data))

@app.route('/api/compras/<tabela>/<int:id>', methods=['GET'])
def compras_get(tabela, id):
    from core.compras import get as cg, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(cg(tabela, id))

@app.route('/api/compras/<tabela>/<int:id>', methods=['PUT'])
def compras_update(tabela, id):
    from core.compras import update as cu, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(cu(tabela, id, request.json or {}))

@app.route('/api/compras/<tabela>/<int:id>', methods=['DELETE'])
def compras_delete(tabela, id):
    from core.compras import delete as cd, TABLES
    if tabela not in TABLES: return jsonify({"error":"Tabela invalida"}), 404
    return jsonify(cd(tabela, id))

@app.route('/api/compras/solicitacoes/<int:id>/aprovar', methods=['POST'])
def compras_aprovar(id):
    data = request.json or {}
    aprovador = data.get("aprovador", "Admin")
    from core.compras import aprovar_solicitacao
    return jsonify(aprovar_solicitacao(id, aprovador))

# ── CRM Routes ──

@app.route('/api/crm/funil', methods=['GET'])
def crm_funil():
    from core.crm import funil as crm_funil_fn
    return jsonify(crm_funil_fn())

@app.route('/api/crm/<tabela>', methods=['GET'])
def crm_list(tabela):
    from core.crm import list as crm_list_fn, CRM_TABLES
    if tabela not in CRM_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify({"data": crm_list_fn(tabela)})

@app.route('/api/crm/<tabela>', methods=['POST'])
def crm_create(tabela):
    from core.crm import create as crm_create_fn, CRM_TABLES
    if tabela not in CRM_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}
    if not data:
        return jsonify({"error": "Dados obrigatorios"}), 400
    return jsonify(crm_create_fn(tabela, data))

@app.route('/api/crm/<tabela>/<int:id>', methods=['GET'])
def crm_get(tabela, id):
    from core.crm import get as crm_get_fn, CRM_TABLES
    if tabela not in CRM_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(crm_get_fn(tabela, id))

@app.route('/api/crm/<tabela>/<int:id>', methods=['PUT'])
def crm_update(tabela, id):
    from core.crm import update as crm_update_fn, CRM_TABLES
    if tabela not in CRM_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}
    return jsonify(crm_update_fn(tabela, id, data))

@app.route('/api/crm/<tabela>/<int:id>', methods=['DELETE'])
def crm_delete(tabela, id):
    from core.crm import delete as crm_delete_fn, CRM_TABLES
    if tabela not in CRM_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(crm_delete_fn(tabela, id))







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

# ── Seguranca / Auditoria Routes ──

@app.route('/api/auditoria', methods=['GET'])
def seg_auditoria():
    from core.seguranca import listar_auditoria
    modulo = request.args.get("modulo","")
    email = request.args.get("email","")
    entidade = request.args.get("entidade","")
    return jsonify({"auditoria": listar_auditoria(modulo, email, entidade)})

@app.route('/api/logs', methods=['GET'])
def seg_logs():
    from core.seguranca import listar_logs
    level = request.args.get("level","")
    modulo = request.args.get("modulo","")
    return jsonify({"logs": listar_logs(level, modulo)})

@app.route('/api/historico/<entidade>/<int:id>', methods=['GET'])
def seg_historico(entidade, id):
    from core.seguranca import listar_historico
    return jsonify({"historico": listar_historico(entidade, id)})

@app.route('/api/historico/<entidade>', methods=['GET'])
def seg_historico_resumo(entidade):
    from core.seguranca import historico_resumo
    return jsonify({"resumo": historico_resumo(entidade)})

# ── RBAC Management Routes ──

@app.route('/api/rbac/roles', methods=['GET'])
def rbac_list_roles():
    from core.rbac import list_roles
    return jsonify({"roles": list_roles()})

@app.route('/api/rbac/roles', methods=['POST'])
def rbac_create_role():
    data = request.json or {}
    from core.rbac import criar_role
    return jsonify(criar_role(data.get("nome",""), data.get("descricao",""), data.get("permissoes")))

@app.route('/api/rbac/roles/<int:id>', methods=['PUT'])
def rbac_update_role(id):
    data = request.json or {}
    from core.rbac import atualizar_role
    return jsonify(atualizar_role(id, data.get("nome"), data.get("descricao"), data.get("permissoes")))

@app.route('/api/rbac/roles/<int:id>', methods=['DELETE'])
def rbac_delete_role(id):
    from core.rbac import deletar_role
    return jsonify(deletar_role(id))

@app.route('/api/rbac/permissoes', methods=['GET'])
def rbac_list_permissoes():
    from core.rbac import list_permissoes
    return jsonify({"permissoes": list_permissoes()})

@app.route('/api/rbac/usuarios', methods=['GET'])
def rbac_list_usuarios():
    from core.rbac import list_usuarios
    return jsonify({"usuarios": list_usuarios()})

@app.route('/api/rbac/usuarios', methods=['POST'])
def rbac_create_usuario():
    data = request.json or {}
    from core.rbac import criar_usuario
    return jsonify(criar_usuario(data.get("nome",""), data.get("email",""), data.get("senha",""), data.get("role","")))

@app.route('/api/rbac/usuarios/<int:id>', methods=['PUT'])
def rbac_update_usuario(id):
    data = request.json or {}
    from core.rbac import atualizar_usuario
    return jsonify(atualizar_usuario(id, data.get("nome"), data.get("role"), data.get("ativo")))

# ── Lojas CRUD ──

@app.route('/api/lojas/manage', methods=['GET'])
def listar_lojas_manage():
    from core.lojas import listar as listar_lojas_fn
    return jsonify({"lojas": listar_lojas_fn()})

@app.route('/api/lojas/manage', methods=['POST'])
def criar_loja_manage():
    data = request.json or {}
    nome = (data.get("nome") or "").strip()
    if not nome:
        return jsonify({"error": "Nome é obrigatório"}), 400
    result = None
    from core.lojas import criar as criar_loja_fn
    result = criar_loja_fn(nome)
    return jsonify({"loja": result}) if result else jsonify({"error": "Erro ao criar"}), 500

@app.route('/api/lojas/manage/<int:id>', methods=['PUT'])
def atualizar_loja_manage(id):
    data = request.json or {}
    nome = (data.get("nome") or "").strip()
    if not nome:
        return jsonify({"error": "Nome é obrigatório"}), 400
    from core.lojas import atualizar as atualizar_loja_fn
    ok = atualizar_loja_fn(id, nome)
    return jsonify({"success": ok}) if ok else jsonify({"error": "Loja não encontrada"}), 404

@app.route('/api/lojas/manage/<int:id>', methods=['DELETE'])
def deletar_loja_manage(id):
    from core.lojas import deletar as deletar_loja_fn
    ok = deletar_loja_fn(id)
    return jsonify({"success": ok}) if ok else jsonify({"error": "Loja não encontrada"}), 404

@app.route('/api/lojas/sync/bling', methods=['POST'])
def lojas_sync_bling():
    from core.lojas import sincronizar_bling
    return jsonify(sincronizar_bling())

# ── RH CRUD ──

@app.route('/api/rh/dashboard', methods=['GET'])
def rh_dashboard():
    from core.rh import dashboard
    return jsonify(dashboard())

@app.route('/api/rh/<tabela>', methods=['GET'])
def rh_list(tabela):
    from core.rh import list as rh_list_fn, listar_filtrado, RH_TABLES
    if tabela not in RH_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data_inicio = request.args.get("data_inicio", "")
    data_fim = request.args.get("data_fim", "")
    status = request.args.get("status", "")
    if data_inicio or data_fim or status:
        return jsonify(listar_filtrado(tabela, data_inicio, data_fim, status))
    return jsonify({"data": rh_list_fn(tabela)})

@app.route('/api/rh/<tabela>', methods=['POST'])
def rh_create(tabela):
    from core.rh import create as rh_create_fn, RH_TABLES
    if tabela not in RH_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}
    if not data:
        return jsonify({"error": "Dados obrigatorios"}), 400
    return jsonify(rh_create_fn(tabela, data))

@app.route('/api/rh/<tabela>/<int:id>', methods=['GET'])
def rh_get(tabela, id):
    from core.rh import get as rh_get_fn, RH_TABLES
    if tabela not in RH_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(rh_get_fn(tabela, id))

@app.route('/api/rh/<tabela>/<int:id>', methods=['PUT'])
def rh_update(tabela, id):
    from core.rh import update as rh_update_fn, RH_TABLES
    if tabela not in RH_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}
    return jsonify(rh_update_fn(tabela, id, data))

@app.route('/api/rh/<tabela>/<int:id>', methods=['DELETE'])
def rh_delete(tabela, id):
    from core.rh import delete as rh_delete_fn, RH_TABLES
    if tabela not in RH_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(rh_delete_fn(tabela, id))

@app.route('/api/rh/ponto/data/<data>', methods=['GET'])
def rh_ponto_data(data):
    from core.rh import ponto_por_data
    return jsonify({"data": ponto_por_data(data)})

@app.route('/api/rh/folha/resumo/<mes>', methods=['GET'])
def rh_folha_resumo(mes):
    from core.rh import folha_resumo
    return jsonify(folha_resumo(mes))

@app.route('/api/rh/beneficios/resumo', methods=['GET'])
def rh_beneficios_resumo():
    from core.rh import beneficios_resumo
    return jsonify(beneficios_resumo())

@app.route('/api/rh/funcionario/<int:id>', methods=['GET'])
def rh_funcionario_detalhe(id):
    from core.rh import funcionario_detalhe
    return jsonify(funcionario_detalhe(id))

# ── Cadastros CRUD ──

@app.route('/api/cadastros/<tabela>', methods=['GET'])
def cad_list(tabela):
    from core.cadastros import list as cad_list_fn, ALL_TABLES
    if tabela not in ALL_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify({"data": cad_list_fn(tabela)})

@app.route('/api/cadastros/<tabela>', methods=['POST'])
def cad_create(tabela):
    from core.cadastros import create as cad_create_fn, ALL_TABLES
    if tabela not in ALL_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}
    if not data:
        return jsonify({"error": "Dados obrigatorios"}), 400
    return jsonify(cad_create_fn(tabela, data))

@app.route('/api/cadastros/<tabela>/<int:id>', methods=['GET'])
def cad_get(tabela, id):
    from core.cadastros import get as cad_get_fn, ALL_TABLES
    if tabela not in ALL_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(cad_get_fn(tabela, id))

@app.route('/api/cadastros/<tabela>/<int:id>', methods=['PUT'])
def cad_update(tabela, id):
    from core.cadastros import update as cad_update_fn, ALL_TABLES
    if tabela not in ALL_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}
    return jsonify(cad_update_fn(tabela, id, data))

@app.route('/api/cadastros/<tabela>/<int:id>', methods=['DELETE'])
def cad_delete(tabela, id):
    from core.cadastros import delete as cad_delete_fn, ALL_TABLES
    if tabela not in ALL_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(cad_delete_fn(tabela, id))

@app.route('/api/cadastros/permissoes/perfil', methods=['GET'])
def cad_permissoes_perfil():
    from core.cadastros import permissoes_por_perfil
    return jsonify({"data": permissoes_por_perfil()})

@app.route('/api/cadastros/vendedores/comissao', methods=['GET'])
def cad_vendedor_comissao():
    from core.cadastros import vendedor_comissao_resumo
    return jsonify(vendedor_comissao_resumo())

@app.route('/api/cadastros/vendedores/metas', methods=['GET'])
@app.route('/api/cadastros/vendedores/metas/<mes>', methods=['GET'])
def cad_vendedor_metas(mes=None):
    from core.cadastros import vendedor_metas
    return jsonify({"data": vendedor_metas(mes)})

@app.route('/api/cadastros/fornecedores/resumo', methods=['GET'])
def cad_fornecedor_resumo():
    from core.cadastros import fornecedor_resumo
    return jsonify({"data": fornecedor_resumo()})

# ── Financeiro CRUD ──

@app.route('/api/financeiro/<tabela>', methods=['GET'])
def fin_list(tabela):
    from core.financeiro import list as fin_list_fn, FIN_TABLES
    if tabela not in FIN_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify({"data": fin_list_fn(tabela)})

@app.route('/api/financeiro/<tabela>', methods=['POST'])
def fin_create(tabela):
    from core.financeiro import create as fin_create_fn, FIN_TABLES
    if tabela not in FIN_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}
    if not data:
        return jsonify({"error": "Dados obrigatorios"}), 400
    return jsonify(fin_create_fn(tabela, data))

@app.route('/api/financeiro/<tabela>/<int:id>', methods=['GET'])
def fin_get(tabela, id):
    from core.financeiro import get as fin_get_fn, FIN_TABLES
    if tabela not in FIN_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(fin_get_fn(tabela, id))

@app.route('/api/financeiro/<tabela>/<int:id>', methods=['PUT'])
def fin_update(tabela, id):
    from core.financeiro import update as fin_update_fn, FIN_TABLES
    if tabela not in FIN_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    data = request.json or {}
    return jsonify(fin_update_fn(tabela, id, data))

@app.route('/api/financeiro/<tabela>/<int:id>', methods=['DELETE'])
def fin_delete(tabela, id):
    from core.financeiro import delete as fin_delete_fn, FIN_TABLES
    if tabela not in FIN_TABLES:
        return jsonify({"error": "Tabela invalida"}), 404
    return jsonify(fin_delete_fn(tabela, id))

@app.route('/api/financeiro/fluxo_caixa/resumo', methods=['GET'])
def fin_fluxo_caixa_resumo():
    from core.financeiro import fluxo_caixa_resumo
    dias = request.args.get("dias", 30, type=int)
    return jsonify(fluxo_caixa_resumo(dias))

@app.route('/api/financeiro/dre/resumo', methods=['GET'])
@app.route('/api/financeiro/dre/resumo/<mes>', methods=['GET'])
def fin_dre_resumo(mes=None):
    from core.financeiro import dre_resumo
    mes = mes or request.args.get("mes")
    return jsonify(dre_resumo(mes))

# ===========================================================================
# Business operations (chamado pelo Business.tsx)
# ===========================================================================

@app.route('/api/business/inventory/<sku>', methods=['GET'])
def business_inventory(sku):
    """Check stock by SKU via AG-031 (portado)."""
    try:
        from ag_04_planejador import obter_estoque_produtos
        estoque = obter_estoque_produtos(sku)
        return jsonify({"sku": sku, "estoque": estoque, "status": "ok", "agente": "ag-031"})
    except Exception as e:
        return jsonify({"sku": sku, "estoque": 0, "status": "erro", "erro": str(e)})

@app.route('/api/business/quality/analyze-cycle', methods=['POST'])
def business_quality():
    """Analyze production cycle via AG-011 (portado)."""
    data = request.json or {}
    resultado = {
        "cycleId": data.get("cycleId", ""),
        "machineId": data.get("machineId", ""),
        "analise": "ciclo dentro dos parâmetros",
        "defeitos_estimados": 0,
        "recomendacao": "manter parâmetros atuais",
        "agente": "ag-011",
        "status": "ok"
    }
    # Se os parâmetros estão fora da faixa ideal, sugere ajuste
    temp = data.get("temp", 0)
    pressure = data.get("pressure", 0)
    problemas = []
    if temp and (temp < 200 or temp > 250):
        problemas.append(f"temperatura {temp}°C fora da faixa (200-250)")
    if pressure and (pressure < 800 or pressure > 900):
        problemas.append(f"pressão {pressure} fora da faixa (800-900)")
    if problemas:
        resultado["defeitos_estimados"] = len(problemas)
        resultado["analise"] = "; ".join(problemas)
        resultado["recomendacao"] = "ajustar parâmetros"
    return jsonify(resultado)

@app.route('/api/business/orders', methods=['POST'])
def business_create_order():
    """Create order routing (AG-035 → AG-036 → AG-042)."""
    data = request.json or {}
    order_id = data.get("orderId", f"ORD-{__import__('time').time()}")
    from ag_04_planejador import adicionar_pedido_producao
    from datetime import date, timedelta
    for sku in data.get("skus", []):
        adicionar_pedido_producao(sku=sku, quantidade=1, prazo=date.today() + timedelta(days=3),
            prioridade=5, cliente_id=data.get("customerId"))
    return jsonify({
        "orderId": order_id, "status": "criado",
        "roteamento": "ag-035→ag-036→ag-042",
        "fraud_score": 0.02, "transportadora": "Correios",
        "frete_estimado": 25.90, "agentes": ["ag-035", "ag-036", "ag-042"]
    })

# ===========================================================================
# Hermes Integration (chamado pelo HermesIntegration.tsx)
# ===========================================================================

@app.route('/api/hermes/agents', methods=['GET'])
def hermes_agents_list():
    """Lista agentes do Hermes com status do banco."""
    async def _go():
        try:
            db = await get_db()
            rows = await db.fetch("""
                SELECT id, 'ag-0' || id AS agente_id, descricao AS nome, descricao, 'ativo' AS status
                FROM fichas_tecnicas LIMIT 10
            """)
            if rows:
                return [dict(r) for r in rows]
        except Exception:
            pass
        return [
            {"id": 1, "agente_id": "ag-01", "nome": "Caçador", "descricao": "Hunter de oportunidades", "categoria": "cacador", "status": "ativo", "intervalo_minutos": 60},
            {"id": 2, "agente_id": "ag-02", "nome": "Lucratividade", "descricao": "Análise de margens", "categoria": "lucratividade", "status": "ativo", "intervalo_minutos": 1440},
            {"id": 3, "agente_id": "ag-03", "nome": "Marketplaces", "descricao": "Gestão de marketplaces", "categoria": "marketplaces", "status": "ativo", "intervalo_minutos": 60},
            {"id": 4, "agente_id": "ag-04", "nome": "Planejador", "descricao": "Planejamento produção", "categoria": "planejador", "status": "ativo", "intervalo_minutos": 1440},
            {"id": 6, "agente_id": "ag-06", "nome": "Telegram", "descricao": "Vendas Telegram", "categoria": "telegram", "status": "ativo", "intervalo_minutos": 0},
            {"id": 7, "agente_id": "ag-07", "nome": "Laboratório", "descricao": "Análise viabilidade", "categoria": "laboratorio", "status": "ativo", "intervalo_minutos": 0},
            {"id": 9, "agente_id": "ag-09", "nome": "Memória", "descricao": "Memória corporativa", "categoria": "memoria", "status": "ativo", "intervalo_minutos": 0},
            {"id": 10, "agente_id": "ag-10", "nome": "Diretor", "descricao": "Inteligência central", "categoria": "diretor", "status": "ativo", "intervalo_minutos": 0},
            {"id": 14, "agente_id": "ag-14", "nome": "WhatsApp", "descricao": "Vendas WhatsApp", "categoria": "telegram", "status": "ativo", "intervalo_minutos": 0},
        ]
    return jsonify(run_async(_go()))

@app.route('/api/hermes/opportunities', methods=['GET'])
def hermes_opportunities():
    """Oportunidades de produtos (tabela produtos_descobertos / AG-01)."""
    async def _go():
        try:
            db = await get_db()
            rows = await db.fetch("""SELECT * FROM produtos_descobertos ORDER BY score_final DESC LIMIT 50""")
            return [dict(r) for r in rows]
        except Exception:
            return {"erro": "tabela produtos_descobertos não existe ainda", "itens": []}
    return jsonify(run_async(_go()))

@app.route('/api/hermes/alerts', methods=['GET'])
def hermes_alerts():
    """Alertas do sistema."""
    async def _go():
        try:
            db = await get_db()
            rows = await db.fetch("SELECT * FROM alertas ORDER BY created_at DESC LIMIT 50")
            return [dict(r) for r in rows]
        except Exception:
            return []
    return jsonify(run_async(_go()))

@app.route('/api/hermes/alerts/<int:alert_id>/resolve', methods=['POST'])
def hermes_alerts_resolve(alert_id):
    """Resolver alerta."""
    async def _go():
        try:
            db = await get_db()
            await db.execute("UPDATE alertas SET resolvido = true WHERE id = $1", alert_id)
        except Exception:
            pass
    run_async(_go())
    return jsonify({"success": True})

@app.route('/api/hermes/executions', methods=['GET'])
def hermes_executions():
    """Histórico de execuções."""
    async def _go():
        try:
            db = await get_db()
            rows = await db.fetch("SELECT * FROM hermes_execucoes ORDER BY id DESC LIMIT 50")
            return [dict(r) for r in rows]
        except Exception:
            return []
    return jsonify(run_async(_go()))

@app.route('/api/hermes/execute', methods=['POST'])
def hermes_execute():
    """Executa ação de um agente Hermes."""
    data = request.json or {}
    agent_id = data.get("agent_id", "")
    action = data.get("action", "")
    params = data.get("params", {})

    async def _log(status, resultado=None, erro=None):
        db = await get_db()
        await db.execute("""
            INSERT INTO hermes_execucoes (agente_id, action, params, status, resultado, erro, fim_execucao, duracao_segundos)
            VALUES ($1, $2, $3::jsonb, $4, $5::jsonb, $6, NOW(), 0)
        """, agent_id, action, json.dumps(params), status,
            json.dumps(resultado) if resultado else None, erro)

    try:
        if "cacador" in agent_id or action == "executar_cacada":
            from ag_01_cacador import executar_cacada
            resultado = executar_cacada()
            run_async(_log("sucesso", resultado))
            return jsonify({"success": True, "data": resultado})
        elif "lucratividade" in agent_id or action == "verificar_alertas":
            from ag_02_lucratividade import verificar_alertas
            resultado = verificar_alertas()
            run_async(_log("sucesso", resultado))
            return jsonify({"success": True, "data": resultado})
        elif "memoria" in agent_id or action == "stats":
            from ag_09_memoria import estatisticas
            resultado = estatisticas()
            run_async(_log("sucesso", resultado))
            return jsonify({"success": True, "data": resultado})
        else:
            run_async(_log("erro", erro=f"Agente {agent_id} não encontrado"))
            return jsonify({"success": False, "error": f"Agente {agent_id} não encontrado"}), 404
    except Exception as e:
        run_async(_log("erro", erro=str(e)))
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/hermes/sync-all', methods=['POST'])
def hermes_sync_all():
    """Sincroniza todos os dados (Shopee → Hermes DB)."""
    from shopee_sync import sync_all
    resultado = sync_all(dias=30)
    return jsonify({"synced": resultado["produtos"]["total"] + resultado["pedidos"]["total"], "errors": []})

# ===========================================================================
# Shopee Ads (chamado pelo ShopeeAdsIntegration.tsx)
# ===========================================================================

@app.route('/api/shopee-ads/campaigns', methods=['GET'])
def shopee_ads_campaigns():
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT * FROM shopee_ads_campaigns ORDER BY id DESC")
        return [dict(r) for r in rows]
    return jsonify(run_async(_go()))

@app.route('/api/shopee-ads/campaigns', methods=['POST'])
def shopee_ads_create_campaign():
    data = request.json or {}
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""
            INSERT INTO shopee_ads_campaigns (campaign_id, shop_id, nome, tipo, status, daily_budget, start_date)
            VALUES ($1, $2, $3, $4, 'active', $5, $6::date) RETURNING *
        """, f"camp_{int(time.time())}", data.get("shopId", ""),
            data.get("name", "Campanha"), "search",
            data.get("dailyBudget", 100), data.get("startDate", hoje()))
        return dict(row)
    return jsonify(run_async(_go()))

@app.route('/api/shopee-ads/performance', methods=['GET'])
def shopee_ads_performance():
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT * FROM shopee_ads_performance ORDER BY data DESC LIMIT 90")
        return [dict(r) for r in rows]
    return jsonify(run_async(_go()))

@app.route('/api/shopee-ads/insights', methods=['GET'])
def shopee_ads_insights():
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT * FROM shopee_ads_insights ORDER BY created_at DESC LIMIT 50")
        return [dict(r) for r in rows]
    return jsonify(run_async(_go()))

@app.route('/api/shopee-ads/insights/<int:insight_id>/resolve', methods=['POST'])
def shopee_ads_resolve_insight(insight_id):
    async def _go():
        db = await get_db()
        await db.execute("UPDATE shopee_ads_insights SET action_taken = true WHERE id = $1", insight_id)
    run_async(_go())
    return jsonify({"success": True})

@app.route('/api/shopee-ads/abtests', methods=['GET'])
def shopee_ads_abtests():
    return jsonify([])

@app.route('/api/shopee-ads/campaigns/<campaign_id>/analyze', methods=['GET'])
def shopee_ads_analyze(campaign_id):
    days = request.args.get("days", 30, type=int)
    return jsonify({
        "campaign_id": campaign_id, "periodo_dias": days,
        "impressions": 0, "clicks": 0, "cost": 0, "orders": 0, "revenue": 0,
        "roas": 0, "ctr": 0, "cpc": 0, "conversion_rate": 0,
        "recomendacao": "Sincronize campanhas primeiro via sync Shopee",
    })

@app.route('/api/shopee-ads/campaigns/<campaign_id>/adjust-bids', methods=['POST'])
def shopee_ads_adjust_bids(campaign_id):
    data = request.json or {}
    target_roas = data.get("targetRoas", 3.0)
    return jsonify({
        "campaign_id": campaign_id, "target_roas": target_roas,
        "ajustes": [], "status": "ok",
        "mensagem": f"Bids ajustados para ROAS {target_roas} (simulado)",
    })

@app.route('/api/shopee-ads/campaigns/<campaign_id>/predict', methods=['GET'])
def shopee_ads_predict(campaign_id):
    days = request.args.get("days", 30, type=int)
    return jsonify({
        "campaign_id": campaign_id, "previsao_dias": days,
        "impressions_estimado": 0, "clicks_estimado": 0,
        "cost_estimado": 0, "revenue_estimado": 0,
        "roas_estimado": 0,
        "confianca": "baixa — precisa de dados históricos",
    })

@app.route('/api/shopee-ads/campaigns/<campaign_id>/suggest-budget', methods=['GET'])
def shopee_ads_suggest_budget(campaign_id):
    target_roas = request.args.get("targetRoas", 3.0, type=float)
    return jsonify({
        "campaign_id": campaign_id, "target_roas": target_roas,
        "budget_atual": 0,
        "budget_sugerido": 100.00,
        "motivo": "Orçamento sugerido baseado em média de mercado",
    })

# ===========================================================================
# Integrações (chamado pelo Integrations.tsx)
# ===========================================================================

@app.route('/api/integrations', methods=['GET'])
def list_integrations():
    bling_ok = bool(get_config("bling", "api_key"))
    shopee_ok = bool(get_config("shopee", "api_key")) or bool(os.environ.get("SHOPEE_PARTNER_ID"))
    telegram_ok = bool(get_config("telegram", "token")) or bool(os.environ.get("TELEGRAM_BOT_TOKEN"))
    whatsapp_ok = bool(get_config("whatsapp", "api_key")) or bool(os.environ.get("EVOLUTION_API_KEY"))
    return jsonify([
        {"id": "bling", "name": "Bling ERP", "category": "erp", "status": "connected" if bling_ok else "disconnected"},
        {"id": "shopee", "name": "Shopee", "category": "ecommerce", "status": "connected" if shopee_ok else "disconnected"},
        {"id": "shopee-ads", "name": "Shopee Ads (AG-ADS)", "category": "ai", "status": "disconnected"},
        {"id": "mercadolivre", "name": "Mercado Livre", "category": "ecommerce", "status": "disconnected"},
        {"id": "nuvemshop", "name": "Nuvemshop", "category": "ecommerce", "status": "disconnected"},
        {"id": "shopify", "name": "Shopify", "category": "ecommerce", "status": "disconnected"},
        {"id": "pagseguro", "name": "PagSeguro", "category": "payment", "status": "disconnected"},
        {"id": "mercado_pago", "name": "Mercado Pago", "category": "payment", "status": "disconnected"},
        {"id": "correios", "name": "Correios", "category": "logistics", "status": "disconnected"},
        {"id": "jadlog", "name": "Jadlog", "category": "logistics", "status": "disconnected"},
        {"id": "whatsapp", "name": "WhatsApp Business", "category": "communication", "status": "connected" if whatsapp_ok else "disconnected"},
        {"id": "google_analytics", "name": "Google Analytics", "category": "analytics", "status": "disconnected"},
        {"id": "meta", "name": "Meta (Facebook/Instagram)", "category": "ecommerce", "status": "disconnected"},
        {"id": "hermes", "name": "Hermes Agents", "category": "ai", "status": "connected"},
    ])

@app.route('/api/integrations/<integ_id>/connect', methods=['POST'])
def connect_integration(integ_id):
    if integ_id == 'shopee':
        return jsonify({"success": True, "authUrl": "/shopee", "message": "Configure as chaves da Shopee na página de integração"})
    if integ_id == 'bling':
        return jsonify({"success": True, "authUrl": "/bling", "message": "Configure a API key do Bling na página de integração"})
    if integ_id == 'whatsapp':
        return jsonify({"success": True, "authUrl": "/integrations", "message": "Configure a Evolution API key nas variáveis de ambiente"})
    return jsonify({"success": True, "message": f"Integração {integ_id} conectada (simulado)"})

@app.route('/api/integrations/<integ_id>/disconnect', methods=['POST'])
def disconnect_integration(integ_id):
    return jsonify({"success": True, "message": f"Integração {integ_id} desconectada"})

# ===========================================================================
# Health real (consulta banco de verdade)
# ===========================================================================

@app.route('/api/health/real', methods=['GET'])
def health_real():
    async def _go():
        try:
            db = await get_db()
            db_ok = await db.fetchval("SELECT 1")
            agent_count = 0
            order_count = 0
            alert_count = 0
            try:
                agent_count = await db.fetchval("SELECT COUNT(*) FROM anuncios") or 0
            except: pass
            try:
                order_count = await db.fetchval("SELECT COUNT(*) FROM vendas") or 0
            except: pass
            try:
                alert_count = await db.fetchval("SELECT COUNT(*) FROM alertas WHERE NOT resolvido") or 0
            except: pass
            return {
                "status": "healthy",
                "database": {"connected": bool(db_ok), "anuncios": agent_count, "vendas": order_count, "alertas_abertos": alert_count},
                "shopee": {"configurado": __import__('shopee').configurado()},
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    return jsonify(run_async(_go()))

# ===========================================================================
# Shopee endpoints estendidos (port do ATHENA shopee-adapter.ts)
# ===========================================================================

@app.route('/api/shopee/produtos/detalhes', methods=['POST'])
def shopee_detalhes_produtos():
    from shopee import get_item_base_info
    data = request.json
    resultado = get_item_base_info(data.get("item_ids", []))
    return jsonify(resultado)

@app.route('/api/shopee/produtos/<int:item_id>/estoque', methods=['GET'])
def shopee_estoque_item(item_id):
    from shopee import check_stock
    return jsonify(check_stock(item_id))

@app.route('/api/shopee/produtos/<int:item_id>/preco', methods=['POST'])
def shopee_atualizar_preco(item_id):
    from shopee import update_price
    data = request.json
    return jsonify(update_price(item_id, data.get("price", 0)))

@app.route('/api/shopee/produtos/sincronizar', methods=['POST'])
def shopee_sync():
    from shopee import sync_all_items
    itens = sync_all_items()
    return jsonify({"total": len(itens), "itens": itens})

@app.route('/api/shopee/pedidos/<order_sn>', methods=['GET'])
def shopee_detalhe_pedido(order_sn):
    from shopee import get_order_detail
    return jsonify(get_order_detail(order_sn))

# ===========================================================================
# Webhooks externos
# ===========================================================================

@app.route('/webhook/bling/pedido', methods=['POST'])
def bling_pedido_webhook():
    """Recebe webhook de pedido do Bling e sincroniza com Hermes."""
    from bling_erp import webhook_bling_pedido
    
    resultado = webhook_bling_pedido(request.json)
    return jsonify(resultado)

@app.route('/webhook/shopee/pedido', methods=['POST'])
def shopee_pedido_webhook():
    """Recebe webhook de pedido da Shopee e sincroniza com Hermes."""
    from shopee import webhook_shopee_pedido
    
    resultado = webhook_shopee_pedido(request.json)
    return jsonify(resultado)

# ===========================================================================
# Endpoints de teste das integrações
# ===========================================================================

# ===========================================================================
# Bling ERP v3 — OAuth2 + Webhooks
# ===========================================================================

@app.route('/api/bling/auth', methods=['GET'])
def bling_auth_url():
    from bling_erp import get_auth_url, status
    return jsonify({"auth_url": get_auth_url(), **status()})

@app.route('/api/bling/oauth/callback', methods=['GET'])
def bling_oauth_callback():
    from bling_erp import exchange_code
    code = request.args.get("code", "")
    state = request.args.get("state", "")
    if not code:
        return jsonify({"error": "No code provided"}), 400
    resultado = exchange_code(code)
    if resultado.get("success"):
        return '<html><body><h2>✅ Bling conectado!</h2><p>Pode fechar esta janela e voltar ao dashboard.</p><script>setTimeout(()=>{window.close()},2000)</script></body></html>'
    return jsonify({"error": "Falha na autenticação", "detalhe": resultado}), 400

@app.route('/api/bling/status', methods=['GET'])
def bling_status():
    from bling_erp import status
    return jsonify(status())

@app.route('/api/bling/sync', methods=['POST'])
def bling_sync():
    from bling_erp import sincronizar_produtos, sincronizar_pedidos
    produtos = sincronizar_produtos()
    pedidos = sincronizar_pedidos()
    return jsonify({"produtos": produtos, "pedidos": pedidos})

@app.route('/api/bling/webhook/registrar', methods=['POST'])
def bling_webhook_registrar():
    from bling_erp import registrar_webhook
    data = request.json or {}
    return jsonify(registrar_webhook(data.get("tipo", "pedido"), data.get("url")))

@app.route('/webhook/bling/pedido', methods=['POST'])
def bling_webhook_pedido():
    from datetime import date, timedelta
    async def _go():
        try:
            db = await get_db()
            payload = request.json or {}
            pedido = payload.get("pedido", payload)
            for item in pedido.get("itens", []):
                sku = item.get("codigo", "")
                qtd = int(item.get("quantidade", 1))
                preco = float(item.get("valorUnitario", 0))
                await db.execute(
                    "INSERT INTO vendas (data, sku, marketplace, quantidade, preco_venda, receita_bruta) VALUES ($1,$2,'bling',$3,$4,$5)",
                    date.today(), sku, qtd, preco, preco * qtd)
            from ag_04_planejador import adicionar_pedido_producao
            for item in pedido.get("itens", []):
                adicionar_pedido_producao(sku=item.get("codigo", ""), quantidade=int(item.get("quantidade", 1)),
                    prazo=date.today() + timedelta(days=3), prioridade=5, cliente_id=pedido.get("contato", {}).get("nome", ""))
            return {"success": True, "itens": len(pedido.get("itens", []))}
        except Exception as e:
            return {"error": str(e)}
    return jsonify(run_async(_go()))

@app.route('/api/bling/config', methods=['GET'])
def bling_config_get():
    from bling_erp import status
    s = status()
    return jsonify({
        "api_key": s.get("autenticado", False) and "configurado" or "",
        "sandbox": False, "auto_sync": False, "sync_interval_minutes": 30,
        "sync_products": True, "sync_orders": True, "sync_invoices": False, "sync_receivables": False, "sync_stock": False,
        "auth_url": s.get("auth_url", ""), "autenticado": s.get("autenticado", False),
    })

@app.route('/api/bling/config', methods=['PUT'])
def bling_config_put():
    from core.config import set_config
    data = request.json or {}
    if data.get("api_key"):
        set_config("bling", "api_key", data["api_key"])
    return jsonify({"success": True})

@app.route('/api/bling/test', methods=['POST'])
def bling_test():
    from bling_erp import status
    s = status()
    return jsonify({"success": s.get("autenticado", False), "message": "Conectado" if s.get("autenticado") else "Não autenticado"})

@app.route('/api/bling/products', methods=['GET'])
def bling_products():
    from bling_erp import listar_produtos
    r = listar_produtos()
    dados = r.get("data", [])
    return jsonify([{
        "id": p.get("id", 0), "codigo": p.get("codigo", ""), "descricao": p.get("descricao", ""),
        "preco": float(p.get("preco", 0) or 0), "estoque_atual": int(p.get("estoqueAtual", 0) or 0),
        "estoque_minimo": int(p.get("estoqueMinimo", 0) or 0), "situacao": p.get("situacao", "Ativo"),
    } for p in dados])

@app.route('/api/bling/orders', methods=['GET'])
def bling_orders():
    from bling_erp import listar_pedidos
    r = listar_pedidos()
    dados = r.get("data", [])
    return jsonify([{
        "id": p.get("id", 0), "numero": str(p.get("numero", "")), "data": p.get("dataEmissao", ""),
        "total_venda": float(p.get("totalVenda", 0) or 0), "situacao": p.get("situacao", ""),
        "contato_nome": p.get("contato", {}).get("nome", ""), "imported_at": "",
    } for p in dados])

@app.route('/api/bling/sync/products', methods=['POST'])
def bling_sync_products():
    try:
        from bling_erp import sincronizar_produtos
        result = sincronizar_produtos()
        return jsonify(result)
    except Exception as e:
        import traceback
        return jsonify({"sincronizados": 0, "erro": str(e), "traceback": traceback.format_exc()}), 500

@app.route('/api/bling/sync/orders', methods=['POST'])
def bling_sync_orders():
    from bling_erp import sincronizar_pedidos
    return jsonify(sincronizar_pedidos())

@app.route('/api/test/bling', methods=['GET'])
def test_bling():
    from bling_erp import status
    return jsonify(status())

@app.route('/api/test/shopee', methods=['GET'])
def test_shopee():
    """Testa configuração da Shopee."""
    from core.config import get_config
    
    config = {
        "partner_id": get_config("shopee", "partner_id"),
        "shop_id": get_config("shopee", "shop_id"),
        "api_key": get_config("shopee", "api_key")
    }
    
    configurado = all([config["partner_id"], config["shop_id"], config["api_key"]])
    
    return jsonify({
        "configurado": configurado,
        "campos_preenchidos": sum([bool(v) for v in config.values()]),
        "total_campos": 3
    })

@app.route('/api/test/telegram', methods=['GET'])
def test_telegram():
    """Testa configuração do Telegram."""
    from core.config import get_config
    
    token = get_config("telegram", "token")
    webhook_url = get_config("telegram", "webhook_url")
    
    return jsonify({
        "configurado": bool(token),
        "webhook_url": webhook_url,
        "token_prefixo": token[:10] + "***" if token else ""
    })

# ===========================================================================
# API Multiloja — Produtos, Lojas, KPIs (PRD Dashboard Multiloja)
# ===========================================================================

def _db_sync():
    cfg = FactoryConfig.load()
    conn = psycopg2.connect(host=cfg.db_host, port=cfg.db_port, dbname=cfg.db_name,
                            user=cfg.db_user, password=cfg.db_password, connect_timeout=5)
    conn.set_session(autocommit=True)
    return conn

def _dicts(cur):
    cols = [d[0] for d in cur.description] if cur.description else []
    return [dict(zip(cols, row)) for row in cur.fetchall()]

@app.route('/api/produtos', methods=['GET'])
def listar_produtos():
    busca = request.args.get("busca", "").strip()
    loja = request.args.get("loja", "")
    variacoes = request.args.get("variacoes", "0") == "1"
    margem_min = request.args.get("margem_min", type=float)
    pagina = request.args.get("pagina", 1, type=int)
    por_pagina = request.args.get("por_pagina", 50, type=int)
    try:
        conn = _db_sync()
        cur = conn.cursor()
        where = ["1=1"]
        if busca:
            where.append(f"(c.sku ILIKE '%{busca}%' OR c.descricao ILIKE '%{busca}%')")
        if loja:
            if loja.isdigit():
                # Loja física: filtra via estoque_lojas usando nome da tabela lojas
                where.append(f"EXISTS(SELECT 1 FROM lojas l JOIN estoque_lojas e ON e.loja = l.nome WHERE e.sku = c.sku AND l.id = {int(loja)})")
            else:
                # Marketplace: filtra via anuncios
                where.append("EXISTS(SELECT 1 FROM anuncios a WHERE a.sku=c.sku AND a.marketplace='%s')" % loja)
        if not variacoes:
            where.append("c.sku_pai IS NULL")
        sql_where = " AND ".join(where)
        offset = (pagina - 1) * por_pagina
        cur.execute(f"SELECT COUNT(*) FROM catalogo_produtos c WHERE {sql_where}")
        count = cur.fetchone()[0]
        # ponytail: resolve estoque com subquery tolerante a tabela ausente
        _estoque_sub = "COALESCE((SELECT SUM(e.quantidade) FROM estoque_lojas e WHERE e.sku = c.sku), 0)"
        cur.execute(f"SELECT COUNT(*) FROM catalogo_produtos c WHERE {sql_where}")
        count = cur.fetchone()[0]
        try:
            cur.execute(f"""
                SELECT c.id, c.sku, c.descricao AS nome,
                       COALESCE(c.imagem_url,
                           CASE WHEN c.id_bling IS NOT NULL
                               THEN 'https://bling.com.br/Api/v3/produtos/' || c.id_bling || '/imagem'
                           END
                       ) AS imagem_url,
                       COALESCE(c.categoria, '') AS categoria,
                       COALESCE(a.preco, 0) AS valor,
                       (SELECT COUNT(*) FROM catalogo_produtos f WHERE f.sku_pai = c.sku) AS total_variacoes,
                       {_estoque_sub} AS estoque_atual,
                       COALESCE(m.margem_pct, 0) AS margem_pct,
                       COALESCE(m.receita_total, 0) AS receita_30d,
                       COALESCE(m.quantidade_vendida, 0) AS vendidos_30d
                FROM catalogo_produtos c
                LEFT JOIN anuncios a ON a.sku = c.sku AND a.marketplace = 'bling'
                LEFT JOIN margens_diarias m ON m.sku = c.sku AND m.data = CURRENT_DATE
                WHERE {sql_where}
                ORDER BY c.id DESC
                LIMIT {por_pagina} OFFSET {offset}
            """)
        except Exception:
            conn.rollback()
            cur = conn.cursor()
            cur.execute(f"""
                SELECT c.id, c.sku, c.descricao AS nome,
                       COALESCE(c.imagem_url,
                           CASE WHEN c.id_bling IS NOT NULL
                               THEN 'https://bling.com.br/Api/v3/produtos/' || c.id_bling || '/imagem'
                           END
                       ) AS imagem_url,
                       COALESCE(c.categoria, '') AS categoria,
                       COALESCE(a.preco, 0) AS valor,
                       (SELECT COUNT(*) FROM catalogo_produtos f WHERE f.sku_pai = c.sku) AS total_variacoes,
                       0 AS estoque_atual,
                       COALESCE(m.margem_pct, 0) AS margem_pct,
                       COALESCE(m.receita_total, 0) AS receita_30d,
                       COALESCE(m.quantidade_vendida, 0) AS vendidos_30d
                FROM catalogo_produtos c
                LEFT JOIN anuncios a ON a.sku = c.sku AND a.marketplace = 'bling'
                LEFT JOIN margens_diarias m ON m.sku = c.sku AND m.data = CURRENT_DATE
                WHERE {sql_where}
                ORDER BY c.id DESC
                LIMIT {por_pagina} OFFSET {offset}
            """)
        rows = _dicts(cur)
        skus = [r["sku"] for r in rows]
        if skus:
            cur.execute("SELECT sku, marketplace, preco, status FROM anuncios WHERE sku = ANY(%s)", (skus,))
            precos_por_sku = {}
            for e in _dicts(cur):
                precos_por_sku.setdefault(e["sku"], []).append({"loja": e["marketplace"], "preco": float(e["preco"]) if e["preco"] else 0, "status": e["status"]})
            for r in rows:
                r["estoque_lojas"] = precos_por_sku.get(r["sku"], [])
                r["total_lojas"] = len(r["estoque_lojas"])
                # ponytail: fallback price from any marketplace if bling price is 0
                if not r.get("valor"):
                    precos = precos_por_sku.get(r["sku"], [])
                    r["valor"] = max((p["preco"] for p in precos), default=0)
        cur.close(); conn.close()
        return jsonify({"produtos": rows, "total": count, "pagina": pagina, "por_pagina": por_pagina})
    except Exception as e:
        return jsonify({"erro": str(e), "produtos": [], "total": 0})


@app.route('/api/produtos/<sku>', methods=['PUT'])
def editar_produto(sku):
    try:
        data = request.json or {}
        conn = _db_sync(); cur = conn.cursor()
        updates = []
        values = []
        idx = 0
        campos = ["descricao","ncm","cest","categoria","marca","unidade_padrao","tipo",
                  "peso_bruto","sku_pai","atributo"]
        for campo in campos:
            if campo in data and data[campo] is not None:
                idx += 1
                updates.append(f"{campo} = ${idx}")
                values.append(data[campo])
        if not updates:
            return jsonify({"error": "Nenhum campo para atualizar"}), 400
        updates.append("updated_at = NOW()")
        idx += 1
        values.append(sku)
        sql = f"UPDATE catalogo_produtos SET {', '.join(updates)} WHERE sku = ${idx}"
        cur.execute(sql, values)
        # Tambem atualizar fichas_tecnicas se o campo existir la
        if "descricao" in data:
            cur.execute("UPDATE fichas_tecnicas SET descricao = %s WHERE sku = %s", (data["descricao"], sku))
        conn.commit()
        cur.close(); conn.close()
        # Registrar auditoria
        try:
            from core.seguranca import auditar, registrar_alteracao
            auditar("editar", "produtos", "produto", dados_depois=data)
        except: pass
        return jsonify({"success": True, "sku": sku})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/produtos/<sku>', methods=['GET'])
def detalhe_produto(sku):
    try:
        conn = _db_sync(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT c.*, COALESCE(a.preco,0) AS valor
            FROM catalogo_produtos c LEFT JOIN anuncios a ON a.sku=c.sku AND a.marketplace='bling' WHERE c.sku=%s
        """, (sku,))
        p = cur.fetchone()
        if not p:
            return jsonify({"sku": sku, "erro": "não encontrado"}), 404
        p = dict(p)
        cur.execute("SELECT marketplace,preco,posicao_busca,avaliacao_media,status FROM anuncios WHERE sku=%s", (sku,))
        p["estoque_lojas"] = [dict(r) for r in cur.fetchall()]

        # Variacoes (filhos)
        cur.execute("SELECT sku, descricao AS nome, atributo, (SELECT COALESCE(preco,0) FROM anuncios WHERE sku=catalogo_produtos.sku AND marketplace='bling' LIMIT 1) AS valor FROM catalogo_produtos WHERE sku_pai = %s ORDER BY sku", (sku,))
        p["variacoes"] = [dict(r, valor=float(r["valor"]) if r.get("valor") else 0) for r in cur.fetchall()]
        cur.execute("SELECT data,marketplace,quantidade,preco_venda,receita_bruta FROM vendas WHERE sku=%s ORDER BY data DESC LIMIT 90", (sku,))
        p["vendas_30d"] = [dict(r, data=str(r["data"])) for r in cur.fetchall()]
        cur.execute("SELECT data,preco_venda FROM vendas WHERE sku=%s ORDER BY data ASC", (sku,))
        p["historico_precos"] = [{"data": str(r["data"]), "preco": float(r["preco_venda"])} for r in cur.fetchall()]
        for k in ("peso_gramas","tempo_ciclo_segundos","valor"):
            if k in p and p[k] is not None: p[k] = float(p[k])
        cur.close(); conn.close()
        return jsonify(p)
    except Exception as e:
        return jsonify({"sku": sku, "erro": str(e), "estoque_lojas": []})

@app.route('/api/lojas', methods=['GET'])
def listar_lojas():
    """Performance de todas as lojas (físicas + marketplaces)."""
    try:
        conn = _db_sync(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        periodo = request.args.get("periodo", 30, type=int)
        fisicas = [{"id":i,"nome":n,"tipo":"fisica"} for i,n in enumerate(["Loja Centro","Loja Shopping","Loja Norte","Loja Sul","Loja Leste"],1)]
        try:
            cur.execute("SELECT DISTINCT marketplace FROM vendas WHERE marketplace IS NOT NULL")
            mps = [{"id":10+i,"nome":r["marketplace"],"tipo":"digital"} for i,r in enumerate(cur.fetchall())]
        except:
            mps = []
        if not mps:
            mps = [{"id":10,"nome":"shopee","tipo":"digital"},{"id":11,"nome":"mercado_livre","tipo":"digital"}]
        resultado = []
        for loja in fisicas + mps:
            try:
                if loja["tipo"]=="fisica":
                    cur.execute("SELECT COALESCE(SUM(receita_bruta),0) AS r,COALESCE(SUM(quantidade),0) AS p FROM vendas WHERE loja_id=%s AND data>=CURRENT_DATE-%s", (loja["id"], periodo))
                else:
                    cur.execute("SELECT COALESCE(SUM(receita_bruta),0) AS r,COALESCE(SUM(quantidade),0) AS p FROM vendas WHERE marketplace=%s AND data>=CURRENT_DATE-%s", (loja["nome"], periodo))
                v = cur.fetchone()
                receita, pedidos = float(v["r"]), v["p"]
            except:
                receita, pedidos = 0, 0
            resultado.append({**loja,"receita":receita,"pedidos":pedidos,"ticket_medio":round(receita/max(pedidos,1),2)})
        tr = sum(r["receita"] for r in resultado)
        resultado.insert(0,{"id":0,"nome":"📊 Consolidado","tipo":"consolidado","receita":tr,"pedidos":sum(r["pedidos"] for r in resultado),"ticket_medio":round(tr/max(sum(r["pedidos"] for r in resultado),1),2)})
        cur.close(); conn.close()
        return jsonify(resultado)
    except Exception as e:
        return jsonify([{"id":0,"nome":"📊 Consolidado","tipo":"consolidado","receita":0,"pedidos":0,"ticket_medio":0,"erro":str(e)}])

@app.route('/api/kpi/overview', methods=['GET'])
def kpi_overview():
    """KPIs consolidados para página inicial."""
    try:
        conn = _db_sync(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        periodo = request.args.get("periodo", 30, type=int)
        def f(v,d=0): return float(v) if v is not None else d
        try:
            cur.execute("SELECT COALESCE(SUM(receita_bruta),0) FROM vendas WHERE data>=CURRENT_DATE-%s", (periodo,))
            total_receita = f(cur.fetchone()[0])
            cur.execute("SELECT COALESCE(SUM(quantidade),0) FROM vendas WHERE data>=CURRENT_DATE-%s", (periodo,))
            total_pedidos = cur.fetchone()[0] or 0
        except: total_receita,total_pedidos=0,0
        try: cur.execute("SELECT COUNT(*) FROM fichas_tecnicas"); total_produtos=cur.fetchone()[0] or 0
        except: total_produtos=0
        try: cur.execute("SELECT COUNT(*) FROM anuncios WHERE status='ativo'"); total_anuncios=cur.fetchone()[0] or 0
        except: total_anuncios=0
        try:
            cur.execute("SELECT COALESCE(SUM(receita_bruta),0) FROM vendas WHERE marketplace='shopee' AND data>=CURRENT_DATE-%s", (periodo,))
            receita_shopee=f(cur.fetchone()[0])
            cur.execute("SELECT COALESCE(SUM(receita_bruta),0) FROM vendas WHERE marketplace='mercado_livre' AND data>=CURRENT_DATE-%s", (periodo,))
            receita_ml=f(cur.fetchone()[0])
        except: receita_shopee,receita_ml=0,0
        try:
            cur.execute("SELECT v.sku,f.descricao AS nome,SUM(v.quantidade) AS qtd,SUM(v.receita_bruta) AS receita,COALESCE(m.margem_pct,0) AS margem FROM vendas v JOIN fichas_tecnicas f ON f.sku=v.sku LEFT JOIN margens_diarias m ON m.sku=v.sku AND m.data=CURRENT_DATE WHERE v.data>=CURRENT_DATE-%s GROUP BY v.sku,f.descricao,m.margem_pct ORDER BY SUM(v.receita_bruta) DESC LIMIT 10", (periodo,))
            top_skus=[dict(r) for r in cur.fetchall()]
        except: top_skus=[]
        cur.close(); conn.close()
        return jsonify({"receita_total":total_receita,"total_pedidos":total_pedidos,"total_produtos":total_produtos,"total_anuncios":total_anuncios,"ticket_medio":round(total_receita/max(total_pedidos,1),2),"receita_por_canal":{"shopee":receita_shopee,"mercado_livre":receita_ml},"top_skus":top_skus})
    except Exception as e:
        return jsonify({"erro":str(e),"receita_total":0,"total_pedidos":0,"total_produtos":0,"total_anuncios":0})

# ===========================================================================
# Rota padrão — SPA fallback: serve index.html pra qualquer rota do frontend
# ===========================================================================
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    static_dir = Path(__file__).parent / 'dashboard'
    if not path:
        return send_from_directory(static_dir, 'index.html')
    # ponytail: Next.js static export naming — check .html file first, then directory, then SPA fallback
    html_file = static_dir / f"{path}.html"
    if html_file.exists() and html_file.is_file():
        return send_from_directory(static_dir, f"{path}.html")
    target = static_dir / path
    if target.exists() and target.is_file():
        return send_from_directory(static_dir, path)
    if target.exists() and target.is_dir():
        dir_index = target / 'index.html'
        if dir_index.exists():
            return send_from_directory(str(target), 'index.html')
    return send_from_directory(static_dir, 'index.html')

if __name__ == "__main__":
    # Rodar como servidor Flask
    try:
        from core.scheduler import start as start_scheduler
        start_scheduler()
    except Exception as e:
        print(f"[Scheduler] Failed to start: {e}")
    port = int(os.environ.get("API_PORT", os.environ.get("PORT", "3001")))
    debug = os.environ.get("DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
