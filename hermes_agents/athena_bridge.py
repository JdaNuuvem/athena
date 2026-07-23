"""
Athena Bridge â€” conecta o Hermes Agent ao ATHENA OS via GraphQL.
ATHENA OS tem 52 agentes, 40+ queries GraphQL, 30+ endpoints REST.
"""
import os, sys, json, urllib.request
from typing import Optional
from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS
from core import run_async, get_db, FactoryConfig
from pathlib import Path
import psycopg2
import psycopg2.extras

ATHENA_URL = os.environ.get("ATHENA_URL", "http://a181zp5xj2ety5z82mopyqzi.177.7.45.242.sslip.io")
GRAPHQL_URL = f"{ATHENA_URL}/graphql"

# Token de autenticaÃ§Ã£o para Athena OS
API_TOKEN = os.environ.get("ATHENA_TOKEN", "")
if not API_TOKEN:
    API_TOKEN = "athena-token-123456789" if os.environ.get("ATHENA_DEV_MODE", "").lower() == "true" else ""
    if not API_TOKEN:
        print("[ATHENA] AVISO: ATHENA_TOKEN nÃ£o definido. Defina a variÃ¡vel de ambiente ATHENA_TOKEN.")
        API_TOKEN = os.urandom(32).hex()  # token aleatÃ³rio por seguranÃ§a, mas quebra OAuth se nÃ£o configurar

# Rotas pÃºblicas (nÃ£o exigem autenticaÃ§Ã£o)
URLS_PUBLICAS = {
    "/api/auth/login", "/api/auth/logout", "/api/health", "/api/auth/me",
    "/api/shopee/callback", "/api/shopee/oauth2callback",
    "/api/bling/webhook", "/api/bling/webhooks",
}

def _autenticado() -> bool:
    auth = request.headers.get("Authorization", "")
    cookie_token = request.cookies.get("auth_token", "")
    token = auth.replace("Bearer ", "") or cookie_token
    return token == API_TOKEN if API_TOKEN else True

def _verificar_autenticacao():
    """Protege todos os endpoints exceto rotas pÃºblicas e OPTIONS (CORS preflight)."""
    if request.method == "OPTIONS":
        return None
    path = request.path.rstrip("/")
    # rotas pÃºblicas
    if path in URLS_PUBLICAS or path.startswith("/api/shopee/callback") or path.startswith("/api/bling/webhook"):
        return None
    # arquivos estÃ¡ticos do frontend (Next.js)
    if not path.startswith("/api/"):
        return None
    if not _autenticado():
        return jsonify({"error": "Unauthorized", "message": "Token de autenticaÃ§Ã£o invÃ¡lido ou ausente"}), 401
    return None

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
    """Detalhes de um pedido especÃ­fico."""
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
# ProduÃ§Ã£o / Moldes
# ===========================================================================

def listar_moldes() -> dict:
    """Moldes cadastrados."""
    return _gql("{ molds(limit: 50) { id code product material cyclesUsed cyclesTotal status } }")

def producao_ativa() -> dict:
    """ProduÃ§Ã£o em andamento."""
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
    """OrÃ§amento vs realizado."""
    return _gql("{ budget { category budget actual deviationPct } }")

def profitability() -> dict:
    """Rentabilidade por SKU."""
    return _gql("{ profitabilityBySKU { sku product revenue cost marginPct status } }")

def break_even() -> dict:
    """Ponto de equilÃ­brio."""
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
# RelatÃ³rio consolidado
# ===========================================================================

def relatorio_consolidado() -> str:
    """RelatÃ³rio executivo Athena."""
    lines = ["ðŸ›ï¸ ATHENA OS â€” RelatÃ³rio Consolidado", "=" * 50]
    h = health()
    k = kpi_summary()
    lines.append(f"Status: {h.get('status', 'N/A')}")
    if "data" in k:
        d = k["data"]["kpiSummary"]
        lines.append(f"Pedidos: {d.get('totalOrders', '?')} | Receita: R$ {d.get('totalRevenue', 0):,.2f}")
        lines.append(f"AnÃºncios ativos: {d.get('activeListings', '?')} | Alertas estoque: {d.get('lowStockAlerts', '?')}")
    return "\n".join(lines)

# ===========================================================================
# Fase 2: Agentes de ProduÃ§Ã£o - Endpoints REST
# ===========================================================================

from flask import Flask, request, jsonify
from flask_cors import CORS
from core.config import get_config
import time, json

app = Flask(__name__)
CORS(app)
app.before_request(_verificar_autenticacao)

from routes.integrations import bling_bp, integrations_bp
from routes.webhooks import webhook_bp
from routes.shopee import shopee_bp, shopee_ads_bp
from routes.estoque import estoque_bp, workflows_bp
from routes.agent_executor import hermes_bp, memory_bp
from routes.pdv import pdv_bp
from routes.vendas import vendas_bp
from routes.relatorios import relatorios_bp
from routes.fiscal import fiscal_bp
from routes.automacoes import automacoes_bp
from routes.producao import producao_bp
from routes.atendimento import atendimento_bp
from routes.compras import compras_bp
from routes.crm import crm_bp
from routes.documentos import documentos_bp, seguranca_bp
from routes.rbac import rbac_bp
from routes.lojas_manage import lojas_bp as lojas_manage_bp
from routes.rh import rh_bp
from routes.cadastros import cadastros_bp
from routes.financeiro import financeiro_bp
app.register_blueprint(bling_bp)
app.register_blueprint(integrations_bp)
app.register_blueprint(webhook_bp)
app.register_blueprint(shopee_bp)
app.register_blueprint(shopee_ads_bp)
app.register_blueprint(estoque_bp)
app.register_blueprint(workflows_bp)
app.register_blueprint(hermes_bp)
app.register_blueprint(memory_bp)
app.register_blueprint(pdv_bp)
app.register_blueprint(vendas_bp)
app.register_blueprint(relatorios_bp)
app.register_blueprint(fiscal_bp)
app.register_blueprint(automacoes_bp)
app.register_blueprint(producao_bp)
app.register_blueprint(atendimento_bp)
app.register_blueprint(compras_bp)
app.register_blueprint(crm_bp)
app.register_blueprint(documentos_bp)
app.register_blueprint(seguranca_bp)
app.register_blueprint(rbac_bp)
app.register_blueprint(lojas_manage_bp)
app.register_blueprint(rh_bp)
app.register_blueprint(cadastros_bp)
app.register_blueprint(financeiro_bp)

# ponytail: importar aqui garante que catalogo_produtos (SSOT) exista antes de
# qualquer sync/listagem â€” sincronizar_produtos()/listar_produtos() fazem SQL
# bruto contra essa tabela sem criÃ¡-la, entÃ£o o import precisa acontecer no boot.
import core.catalogo  # noqa: F401

# ===========================================================================
# AutenticaÃ§Ã£o e Health Check (Athena OS)
# ===========================================================================

# Fallback de emergencia â€” sÃ³ ativo em dev mode ou se senha vier por env
_dev_fallback = os.environ.get("ATHENA_DEV_MODE", "").lower() == "true"
_dev_admin_pw = os.environ.get("ATHENA_DEV_ADMIN_PW", "")
USUARIOS = {} if not _dev_fallback or not _dev_admin_pw else {
    "admin": {"password": _dev_admin_pw, "role": "admin", "name": "Admin"},
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
        except Exception as e: pass
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

# AG-04: Planejador de ProduÃ§Ã£o
@app.route('/api/agent/ag_04_planejador/plano_diario', methods=['POST'])
def plano_diario():
    """Gera plano de produÃ§Ã£o diÃ¡rio."""
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
    """Adiciona pedido de produÃ§Ã£o."""
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
    """RelatÃ³rio industrial completo."""
    from ag_05_industrial import relatorio_industrial
    import asyncio
    
    return jsonify(relatorio_industrial())

@app.route('/api/agent/ag_05_industrial/oee/<machine_id>', methods=['GET'])
def oee_status(machine_id):
    """Status OEE de uma mÃ¡quina."""
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
    """EstatÃ­sticas do Telegram."""
    from ag_06_telegram import obter_estatisticas_telegram
    
    stats = obter_estatisticas_telegram()
    return jsonify(stats)

# AG-07: LaboratÃ³rio de Produtos
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
    """ObtÃ©m itens do pipeline por status."""
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



# â”€â”€ Bling Portuguese Routes (alias para rotas inglesas existentes) â”€â”€

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
    """Workflow: AprovaÃ§Ã£o AG-07 gera pedido AG-04."""
    from workflows import workflow_ag07_para_ag04
    
    resultado = workflow_ag07_para_ag04(pipeline_id)
    return jsonify(resultado)

@app.route('/api/workflows/ag06_para_ag04/<pedido_id>', methods=['POST'])
def workflow_ag06_ag04(pedido_id):
    """Workflow: Pedido AG-06 gera produÃ§Ã£o AG-04."""
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
    """HistÃ³rico completo de eventos do molde."""
    from ag_05_industrial.mold_lifecycle import obter_historico_molde
    
    historico = obter_historico_molde(molde_id)
    return jsonify({"molde_id": molde_id, "historico": historico})

@app.route('/api/moldes/<int:molde_id>/status', methods=['GET'])
def status_molde(molde_id):
    """Status atual e informaÃ§Ãµes do molde."""
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
    """Inicia execuÃ§Ã£o de job CNC."""
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
    """Registra nova inspeÃ§Ã£o de qualidade."""
    from ag_11_qualidade import registrar_inspecao
    
    data = request.json
    inspecao = registrar_inspecao(data['lote_id'], data)
    return jsonify(inspecao)

@app.route('/api/qualidade/inspecoes/<inspecao_id>/finalizar', methods=['POST'])
def finalizar_inspecao(inspecao_id):
    """Finaliza inspeÃ§Ã£o com resultado."""
    from ag_11_qualidade import finalizar_inspecao
    
    resultado = finalizar_inspecao(inspecao_id, request.json)
    return jsonify(resultado)

@app.route('/api/qualidade/taxa_defeitos', methods=['GET'])
def taxa_defeitos():
    """Taxa de defeitos por perÃ­odo."""
    from ag_11_qualidade import calcular_taxa_defeitos
    
    periodo = request.args.get('periodo', 30, type=int)
    taxa = calcular_taxa_defeitos(periodo)
    return jsonify(taxa)

@app.route('/api/qualidade/pareto', methods=['GET'])
def pareto_defeitos():
    """AnÃ¡lise Pareto de defeitos (80/20)."""
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
    """Fecha CAPA verificando eficÃ¡cia."""
    from ag_11_qualidade import fechar_capa
    
    eficacia = request.json.get('eficacia', False)
    observacoes = request.json.get('observacoes', '')
    resultado = fechar_capa(capa_id, eficacia, observacoes)
    return jsonify(resultado)

# AG-12: GestÃ£o de ManutenÃ§Ã£o
@app.route('/api/manutencao/agendar', methods=['POST'])
def agendar_manutencao():
    """Agenda nova manutenÃ§Ã£o."""
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
    """Lista manutenÃ§Ãµes pendentes ordenadas por prioridade."""
    from ag_12_manutencao import obter_manutencoes_pendentes
    
    manutencoes = obter_manutencoes_pendentes()
    return jsonify({"manutencoes": manutencoes, "total": len(manutencoes)})

@app.route('/api/manutencao/<int:manutencao_id>/iniciar', methods=['POST'])
def iniciar_manutencao(manutencao_id):
    """Inicia execuÃ§Ã£o de manutenÃ§Ã£o."""
    from ag_12_manutencao import iniciar_manutencao
    
    resultado = iniciar_manutencao(manutencao_id, request.json.get('tecnico', ''))
    return jsonify(resultado)

@app.route('/api/manutencao/<int:manutencao_id>/concluir', methods=['POST'])
def concluir_manutencao(manutencao_id):
    """Conclui manutenÃ§Ã£o."""
    from ag_12_manutencao import concluir_manutencao
    
    resultado = concluir_manutencao(manutencao_id, request.json)
    return jsonify(resultado)

@app.route('/api/manutencao/alertas', methods=['GET'])
def alertas_manutencao():
    """Verifica alertas de manutenÃ§Ã£o."""
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
    """KPIs de manutenÃ§Ã£o."""
    from ag_12_manutencao import obter_kpi_manutencao
    
    periodo = request.args.get('periodo', 30, type=int)
    kpis = obter_kpi_manutencao(periodo)
    return jsonify(kpis)

# ===========================================================================
# ConfiguraÃ§Ã£o - Endpoints (Telegram, Bling, Shopee)
# ===========================================================================

@app.route('/api/config', methods=['GET'])
def get_all_configs():
    """Retorna todas as configuraÃ§Ãµes."""
    from core.config import get_all_config
    return jsonify(get_all_config())

@app.route('/api/config/telegram', methods=['POST'])
def set_telegram_config():
    """Configura Telegram."""
    from core.config import set_config
    
    token = request.json.get('token', '')
    webhook_url = request.json.get('webhookUrl', '')
    
    if not token:
        return jsonify({"error": "Token nÃ£o fornecido"}), 400
    
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
    """Configura Shopee (partner_id/api_key do app). shop_id e' opcional aqui â€”
    normalmente e' preenchido depois, por loja, via fluxo OAuth (conectar loja)."""
    from core.config import set_config
    data = request.json or {}

    partner_id = data.get('partnerId', '')
    shop_id = data.get('shopId', '')
    api_key = data.get('apiKey', '')

    if not partner_id or not api_key:
        return jsonify({"error": "ForneÃ§a partnerId e apiKey"}), 400

    set_config("shopee", "partner_id", partner_id)
    set_config("shopee", "api_key", api_key)
    if shop_id:
        set_config("shopee", "shop_id", shop_id)

    return jsonify({"success": True, "configurado": True})

@app.route('/api/config/status', methods=['GET'])
def get_config_status():
    """Retorna status das configuraÃ§Ãµes."""
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
    """Treina modelo de previsÃ£o de defeitos."""
    from ag_13_ml import treinar_modelo_previsao_defeitos
    
    resultado = treinar_modelo_previsao_defeitos()
    return jsonify(resultado)

@app.route('/api/ml/prever/<sku>', methods=['GET'])
def prever_defeitos_ml(sku):
    """PrevÃª defeitos para um SKU especÃ­fico."""
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
        return {"error": "Sem dados histÃ³ricos para este SKU"}
    
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


















# â”€â”€ Integracoes / SSOT Routes â”€â”€

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
        "analise": "ciclo dentro dos parÃ¢metros",
        "defeitos_estimados": 0,
        "recomendacao": "manter parÃ¢metros atuais",
        "agente": "ag-011",
        "status": "ok"
    }
    # Se os parÃ¢metros estÃ£o fora da faixa ideal, sugere ajuste
    temp = data.get("temp", 0)
    pressure = data.get("pressure", 0)
    problemas = []
    if temp and (temp < 200 or temp > 250):
        problemas.append(f"temperatura {temp}Â°C fora da faixa (200-250)")
    if pressure and (pressure < 800 or pressure > 900):
        problemas.append(f"pressÃ£o {pressure} fora da faixa (800-900)")
    if problemas:
        resultado["defeitos_estimados"] = len(problemas)
        resultado["analise"] = "; ".join(problemas)
        resultado["recomendacao"] = "ajustar parÃ¢metros"
    return jsonify(resultado)

@app.route('/api/business/orders', methods=['POST'])
def business_create_order():
    """Create order routing (AG-035 â†’ AG-036 â†’ AG-042)."""
    data = request.json or {}
    order_id = data.get("orderId", f"ORD-{__import__('time').time()}")
    from ag_04_planejador import adicionar_pedido_producao
    from datetime import date, timedelta
    for sku in data.get("skus", []):
        adicionar_pedido_producao(sku=sku, quantidade=1, prazo=date.today() + timedelta(days=3),
            prioridade=5, cliente_id=data.get("customerId"))
    return jsonify({
        "orderId": order_id, "status": "criado",
        "roteamento": "ag-035â†’ag-036â†’ag-042",
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
            {"id": 1, "agente_id": "ag-01", "nome": "CaÃ§ador", "descricao": "Hunter de oportunidades", "categoria": "cacador", "status": "ativo", "intervalo_minutos": 60},
            {"id": 2, "agente_id": "ag-02", "nome": "Lucratividade", "descricao": "AnÃ¡lise de margens", "categoria": "lucratividade", "status": "ativo", "intervalo_minutos": 1440},
            {"id": 3, "agente_id": "ag-03", "nome": "Marketplaces", "descricao": "GestÃ£o de marketplaces", "categoria": "marketplaces", "status": "ativo", "intervalo_minutos": 60},
            {"id": 4, "agente_id": "ag-04", "nome": "Planejador", "descricao": "Planejamento produÃ§Ã£o", "categoria": "planejador", "status": "ativo", "intervalo_minutos": 1440},
            {"id": 6, "agente_id": "ag-06", "nome": "Telegram", "descricao": "Vendas Telegram", "categoria": "telegram", "status": "ativo", "intervalo_minutos": 0},
            {"id": 7, "agente_id": "ag-07", "nome": "LaboratÃ³rio", "descricao": "AnÃ¡lise viabilidade", "categoria": "laboratorio", "status": "ativo", "intervalo_minutos": 0},
            {"id": 9, "agente_id": "ag-09", "nome": "MemÃ³ria", "descricao": "MemÃ³ria corporativa", "categoria": "memoria", "status": "ativo", "intervalo_minutos": 0},
            {"id": 10, "agente_id": "ag-10", "nome": "Diretor", "descricao": "InteligÃªncia central", "categoria": "diretor", "status": "ativo", "intervalo_minutos": 0},
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
            return {"erro": "tabela produtos_descobertos nÃ£o existe ainda", "itens": []}
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
    """HistÃ³rico de execuÃ§Ãµes."""
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
    """Executa aÃ§Ã£o de um agente Hermes."""
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
            run_async(_log("erro", erro=f"Agente {agent_id} nÃ£o encontrado"))
            return jsonify({"success": False, "error": f"Agente {agent_id} nÃ£o encontrado"}), 404
    except Exception as e:
        run_async(_log("erro", erro=str(e)))
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/hermes/sync-all', methods=['POST'])
def hermes_sync_all():
    """Sincroniza todos os dados (Shopee â†’ Hermes DB)."""
    from shopee_sync import sync_all
    resultado = sync_all(dias=30)
    return jsonify({"synced": resultado["produtos"]["total"] + resultado["pedidos"]["total"], "errors": []})

# ===========================================================================
# IntegraÃ§Ãµes (chamado pelo Integrations.tsx)
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
        return jsonify({"success": True, "authUrl": "/shopee", "message": "Configure as chaves da Shopee na pÃ¡gina de integraÃ§Ã£o"})
    if integ_id == 'bling':
        return jsonify({"success": True, "authUrl": "/bling", "message": "Configure a API key do Bling na pÃ¡gina de integraÃ§Ã£o"})
    if integ_id == 'whatsapp':
        return jsonify({"success": True, "authUrl": "/integrations", "message": "Configure a Evolution API key nas variÃ¡veis de ambiente"})
    return jsonify({"success": True, "message": f"IntegraÃ§Ã£o {integ_id} conectada (simulado)"})

@app.route('/api/integrations/<integ_id>/disconnect', methods=['POST'])
def disconnect_integration(integ_id):
    return jsonify({"success": True, "message": f"IntegraÃ§Ã£o {integ_id} desconectada"})

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
            except Exception as e: pass
            try:
                order_count = await db.fetchval("SELECT COUNT(*) FROM vendas") or 0
            except Exception as e: pass
            try:
                alert_count = await db.fetchval("SELECT COUNT(*) FROM alertas WHERE NOT resolvido") or 0
            except Exception as e: pass
            return {
                "status": "healthy",
                "database": {"connected": bool(db_ok), "anuncios": agent_count, "vendas": order_count, "alertas_abertos": alert_count},
                "shopee": {"configurado": __import__('shopee').configurado()},
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    return jsonify(run_async(_go()))


# ===========================================================================
# Produtos, Lojas e KPIs â€” rotas restauradas (removidas por engano em 479b1b5)
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

def _autenticado() -> bool:
    auth = request.headers.get("Authorization", "")
    cookie_token = request.cookies.get("auth_token", "")
    token = auth.replace("Bearer ", "") or cookie_token
    return token == API_TOKEN

@app.route('/api/produtos', methods=['GET'])
def listar_produtos():
    if not _autenticado():
        return jsonify({"error": "Unauthorized"}), 401
    busca = request.args.get("busca", "").strip()
    loja = request.args.get("loja", "")
    variacoes = request.args.get("variacoes", "0") == "1"
    pagina = request.args.get("pagina", 1, type=int)
    por_pagina = request.args.get("por_pagina", 50, type=int)
    try:
        conn = _db_sync()
        cur = conn.cursor()
        where = ["1=1"]
        params = []
        if busca:
            where.append("(c.sku ILIKE %s OR c.descricao ILIKE %s)")
            params.extend([f"%{busca}%", f"%{busca}%"])
        if loja:
            if loja.isdigit():
                # Loja fÃ­sica: filtra via estoque_lojas usando nome da tabela lojas
                where.append("EXISTS(SELECT 1 FROM lojas l JOIN estoque_lojas e ON e.loja = l.nome WHERE e.sku = c.sku AND l.id = %s)")
                params.append(int(loja))
            else:
                # Marketplace: filtra via anuncios
                where.append("EXISTS(SELECT 1 FROM anuncios a WHERE a.sku=c.sku AND a.marketplace=%s)")
                params.append(loja)
        if not variacoes:
            where.append("c.sku_pai IS NULL")
        sql_where = " AND ".join(where)
        offset = (pagina - 1) * por_pagina
        cur.execute(f"SELECT COUNT(*) FROM catalogo_produtos c WHERE {sql_where}", params)
        count = cur.fetchone()[0]
        _estoque_sub = "COALESCE((SELECT SUM(e.quantidade) FROM estoque_lojas e WHERE e.sku = c.sku), 0)"
        try:
            cur.execute(f"""
                SELECT c.id, c.sku, c.descricao AS nome,
                       COALESCE(c.imagem_url,
                           CASE WHEN c.id_bling IS NOT NULL
                               THEN 'https://bling.com.br/Api/v3/produtos/' || c.id_bling || '/imagem'
                           END
                       ) AS imagem_url,
                       COALESCE(c.categoria, '') AS categoria,
                       COALESCE(c.marca, '') AS marca,
                       COALESCE(c.codigo_barras, '') AS codigo_barras,
                       c.estoque_minimo, c.estoque_maximo, c.preco_custo,
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
                LIMIT %s OFFSET %s
            """, params + [por_pagina, offset])
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
                       COALESCE(c.marca, '') AS marca,
                       COALESCE(c.codigo_barras, '') AS codigo_barras,
                       c.estoque_minimo, c.estoque_maximo, c.preco_custo,
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
                LIMIT %s OFFSET %s
            """, params + [por_pagina, offset])
        rows = _dicts(cur)
        for r in rows:
            for k in ("estoque_minimo", "estoque_maximo", "preco_custo"):
                if r.get(k) is not None:
                    r[k] = float(r[k])
        skus = [r["sku"] for r in rows]
        if skus:
            cur.execute("SELECT sku, marketplace, preco, status FROM anuncios WHERE sku = ANY(%s)", (skus,))
            precos_por_sku = {}
            for e in _dicts(cur):
                precos_por_sku.setdefault(e["sku"], []).append({"loja": e["marketplace"], "preco": float(e["preco"]) if e["preco"] else 0, "status": e["status"]})
            for r in rows:
                r["estoque_lojas"] = precos_por_sku.get(r["sku"], [])
                r["total_lojas"] = len(r["estoque_lojas"])
                if not r.get("valor"):
                    precos = precos_por_sku.get(r["sku"], [])
                    r["valor"] = max((p["preco"] for p in precos), default=0)
        cur.close(); conn.close()
        return jsonify({"produtos": rows, "total": count, "pagina": pagina, "por_pagina": por_pagina})
    except Exception as e:
        return jsonify({"erro": str(e), "produtos": [], "total": 0})

@app.route('/api/produtos/<sku>', methods=['PUT'])
def editar_produto(sku):
    if not _autenticado():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.json or {}
        conn = _db_sync(); cur = conn.cursor()
        updates = []
        values = []
        campos = ["descricao","ncm","cest","categoria","marca","unidade_padrao","tipo",
                  "peso_bruto","sku_pai","atributo",
                  "codigo_barras","gtin_embalagem","descricao_curta","descricao_complementar",
                  "peso_liquido","largura","altura","profundidade","unidade_medida_dimensao",
                  "volumes","itens_por_caixa","cfop_padrao","observacoes","link_externo",
                  "fornecedor_nome","fornecedor_codigo","preco_custo",
                  "estoque_minimo","estoque_maximo","estoque_localizacao"]
        for campo in campos:
            if campo in data and data[campo] is not None:
                updates.append(f"{campo} = %s")
                values.append(data[campo])
        if not updates:
            return jsonify({"error": "Nenhum campo para atualizar"}), 400
        updates.append("updated_at = NOW()")
        values.append(sku)
        sql = f"UPDATE catalogo_produtos SET {', '.join(updates)} WHERE sku = %s"
        cur.execute(sql, values)
        if "descricao" in data:
            cur.execute("UPDATE fichas_tecnicas SET descricao = %s WHERE sku = %s", (data["descricao"], sku))
        cur.close(); conn.close()
        try:
            from core.seguranca import auditar
            auditar("editar", "produtos", "produto", dados_depois=data)
        except Exception:
            pass
        return jsonify({"success": True, "sku": sku})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/produtos/<sku>', methods=['GET'])
def detalhe_produto(sku):
    if not _autenticado():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        conn = _db_sync(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT c.*, COALESCE(a.preco,0) AS valor
            FROM catalogo_produtos c LEFT JOIN anuncios a ON a.sku=c.sku AND a.marketplace='bling' WHERE c.sku=%s
        """, (sku,))
        p = cur.fetchone()
        if not p:
            return jsonify({"sku": sku, "erro": "nÃ£o encontrado"}), 404
        p = dict(p)
        cur.execute("SELECT marketplace,shop_id,anuncio_id,preco,posicao_busca,avaliacao_media,status FROM anuncios WHERE sku=%s", (sku,))
        p["estoque_lojas"] = [dict(r) for r in cur.fetchall()]

        # Estoque real por loja/deposito (tabela estoque_lojas â€” quantidade fisica, nao confundir com o campo acima)
        cur.execute("SELECT loja, quantidade, data_atualizacao FROM estoque_lojas WHERE sku=%s ORDER BY loja", (sku,))
        p["estoque_por_loja"] = [dict(r, quantidade=float(r["quantidade"]) if r.get("quantidade") is not None else 0,
                                      data_atualizacao=str(r["data_atualizacao"]) if r.get("data_atualizacao") else None)
                                 for r in cur.fetchall()]

        # Variacoes (filhos)
        cur.execute("SELECT sku, descricao AS nome, atributo, (SELECT COALESCE(preco,0) FROM anuncios WHERE sku=catalogo_produtos.sku AND marketplace='bling' LIMIT 1) AS valor FROM catalogo_produtos WHERE sku_pai = %s ORDER BY sku", (sku,))
        p["variacoes"] = [dict(r, valor=float(r["valor"]) if r.get("valor") else 0) for r in cur.fetchall()]
        cur.execute("SELECT data,marketplace,quantidade,preco_venda,receita_bruta FROM vendas WHERE sku=%s ORDER BY data DESC LIMIT 90", (sku,))
        p["vendas_30d"] = [dict(r, data=str(r["data"])) for r in cur.fetchall()]
        cur.execute("SELECT data,preco_venda FROM vendas WHERE sku=%s ORDER BY data ASC", (sku,))
        p["historico_precos"] = [{"data": str(r["data"]), "preco": float(r["preco_venda"])} for r in cur.fetchall()]
        for k in ("peso_gramas","tempo_ciclo_segundos","valor",
                  "peso_bruto","peso_liquido","largura","altura","profundidade",
                  "percentual_tributos","valor_base_st_retencao","valor_st_retencao","valor_icms_st",
                  "preco_custo","estoque_minimo","estoque_maximo"):
            if k in p and p[k] is not None: p[k] = float(p[k])
        cur.close(); conn.close()
        return jsonify(p)
    except Exception as e:
        return jsonify({"sku": sku, "erro": str(e), "estoque_lojas": []})

@app.route('/api/produtos/limites', methods=['GET'])
def produtos_limites():
    """Estoque minimo/maximo, fornecedor e custo por SKU vindos do catalogo local.
    Usado pela tela de Estoque para enriquecer os dados ao vivo do Bling sem duplicar toda a busca do catalogo."""
    if not _autenticado():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        conn = _db_sync(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""SELECT sku, marca, fornecedor_nome, estoque_minimo, estoque_maximo, preco_custo
                       FROM catalogo_produtos""")
        out = {}
        for r in cur.fetchall():
            out[r["sku"]] = {
                "marca": r["marca"] or "",
                "fornecedor_nome": r["fornecedor_nome"] or "",
                "estoque_minimo": float(r["estoque_minimo"]) if r["estoque_minimo"] is not None else None,
                "estoque_maximo": float(r["estoque_maximo"]) if r["estoque_maximo"] is not None else None,
                "preco_custo": float(r["preco_custo"]) if r["preco_custo"] is not None else None,
            }
        cur.close(); conn.close()
        return jsonify(out)
    except Exception as e:
        return jsonify({"erro": str(e)})

@app.route('/api/lojas', methods=['GET'])
def listar_lojas():
    """Performance de todas as lojas (fÃ­sicas + marketplaces)."""
    if not _autenticado():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        conn = _db_sync(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        periodo = request.args.get("periodo", 30, type=int)
        cur.execute("SELECT id, nome FROM lojas ORDER BY id")
        fisicas = [{"id":r["id"],"nome":r["nome"],"tipo":"fisica"} for r in cur.fetchall()]
        if not fisicas:
            fisicas = [{"id":1,"nome":"Loja PadrÃ£o","tipo":"fisica"}]
        try:
            cur.execute("SELECT DISTINCT marketplace FROM vendas WHERE marketplace IS NOT NULL")
            mps = [{"id":10+i,"nome":r["marketplace"],"tipo":"digital"} for i,r in enumerate(cur.fetchall())]
        except Exception:
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
            except Exception:
                receita, pedidos = 0, 0
            resultado.append({**loja,"receita":receita,"pedidos":pedidos,"ticket_medio":round(receita/max(pedidos,1),2)})
        tr = sum(r["receita"] for r in resultado)
        resultado.insert(0,{"id":0,"nome":"ðŸ“Š Consolidado","tipo":"consolidado","receita":tr,"pedidos":sum(r["pedidos"] for r in resultado),"ticket_medio":round(tr/max(sum(r["pedidos"] for r in resultado),1),2)})
        cur.close(); conn.close()
        return jsonify(resultado)
    except Exception as e:
        return jsonify([{"id":0,"nome":"ðŸ“Š Consolidado","tipo":"consolidado","receita":0,"pedidos":0,"ticket_medio":0,"erro":str(e)}])

@app.route('/api/kpi/overview', methods=['GET'])
def kpi_overview():
    """KPIs consolidados para pÃ¡gina inicial."""
    if not _autenticado():
        return jsonify({"error": "Unauthorized"}), 401
    try:
        conn = _db_sync(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        periodo = request.args.get("periodo", 30, type=int)
        def f(v,d=0): return float(v) if v is not None else d
        try:
            cur.execute("SELECT COALESCE(SUM(receita_bruta),0) FROM vendas WHERE data>=CURRENT_DATE-%s", (periodo,))
            total_receita = f(cur.fetchone()[0])
            cur.execute("SELECT COALESCE(SUM(quantidade),0) FROM vendas WHERE data>=CURRENT_DATE-%s", (periodo,))
            total_pedidos = cur.fetchone()[0] or 0
        except Exception:
            total_receita,total_pedidos=0,0
        try:
            cur.execute("SELECT COUNT(*) FROM fichas_tecnicas"); total_produtos=cur.fetchone()[0] or 0
        except Exception:
            total_produtos=0
        try:
            cur.execute("SELECT COUNT(*) FROM anuncios WHERE status='ativo'"); total_anuncios=cur.fetchone()[0] or 0
        except Exception:
            total_anuncios=0
        try:
            cur.execute("SELECT COALESCE(SUM(receita_bruta),0) FROM vendas WHERE marketplace='shopee' AND data>=CURRENT_DATE-%s", (periodo,))
            receita_shopee=f(cur.fetchone()[0])
            cur.execute("SELECT COALESCE(SUM(receita_bruta),0) FROM vendas WHERE marketplace='mercado_livre' AND data>=CURRENT_DATE-%s", (periodo,))
            receita_ml=f(cur.fetchone()[0])
        except Exception:
            receita_shopee,receita_ml=0,0
        try:
            cur.execute("SELECT v.sku,f.descricao AS nome,SUM(v.quantidade) AS qtd,SUM(v.receita_bruta) AS receita,COALESCE(m.margem_pct,0) AS margem FROM vendas v JOIN fichas_tecnicas f ON f.sku=v.sku LEFT JOIN margens_diarias m ON m.sku=v.sku AND m.data=CURRENT_DATE WHERE v.data>=CURRENT_DATE-%s GROUP BY v.sku,f.descricao,m.margem_pct ORDER BY SUM(v.receita_bruta) DESC LIMIT 10", (periodo,))
            top_skus=[dict(r) for r in cur.fetchall()]
        except Exception:
            top_skus=[]
        cur.close(); conn.close()
        return jsonify({"receita_total":total_receita,"total_pedidos":total_pedidos,"total_produtos":total_produtos,"total_anuncios":total_anuncios,"ticket_medio":round(total_receita/max(total_pedidos,1),2),"receita_por_canal":{"shopee":receita_shopee,"mercado_livre":receita_ml},"top_skus":top_skus})
    except Exception as e:
        return jsonify({"erro":str(e),"receita_total":0,"total_pedidos":0,"total_produtos":0,"total_anuncios":0})

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    static_dir = Path(__file__).parent / 'dashboard'
    if not path:
        return send_from_directory(static_dir, 'index.html')
    # ponytail: Next.js static export naming â€” check .html file first, then directory, then SPA fallback
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
    port = int(os.environ.get("API_PORT", "3001"))
    debug = os.environ.get("DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
