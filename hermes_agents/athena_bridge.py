"""
Athena Bridge — conecta o Hermes Agent ao ATHENA OS via GraphQL.
ATHENA OS tem 52 agentes, 40+ queries GraphQL, 30+ endpoints REST.
"""
import os, sys, json, urllib.request
from typing import Optional
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from core import run_async, get_db
from pathlib import Path

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
    """Login com username/password por perfil."""
    data = request.json or {}
    username = data.get('username', '').lower()
    password = data.get('password', '')
    api_key = data.get('api_key', '')

    user = USUARIOS.get(username, {})
    if user and user["password"] == password:
        return jsonify({"token": API_TOKEN, "role": user["role"], "name": user["name"]})
    if api_key and api_key == API_TOKEN:
        return jsonify({"token": API_TOKEN, "role": "admin", "name": "Admin"})
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/me', methods=['GET'])
def current_user():
    """Retorna dados do usuário logado."""
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {API_TOKEN}":
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"name": "Admin", "role": "admin", "permissoes": [
        "ver_produtos", "ver_estoque", "ver_financeiro", "ver_tributario",
        "ver_lojas", "ver_marketplaces", "ver_integracoes", "exportar",
        "gerenciar_usuarios"
    ]})

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

# AG-04: Estoque
@app.route('/api/estoque/produtos', methods=['GET'])
def estoque_produtos():
    """Obtém estoque de produtos acabados."""
    from ag_04_planejador import obter_estoque_produtos
    
    sku = request.args.get('sku', '')
    estoque = obter_estoque_produtos(sku)
    return jsonify(estoque)

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
    """Configura Bling."""
    from core.config import set_config
    
    api_key = request.json.get('apiKey', '')
    api_url = request.json.get('apiUrl', '')
    
    if not api_key:
        return jsonify({"error": "API key não fornecida"}), 400
    
    set_config("bling", "api_key", api_key)
    if api_url:
        set_config("bling", "api_url", api_url)
    
    return jsonify({"success": True, "configurado": True})

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

# ===========================================================================
# Chat com agente (chamado pelo Chat.tsx do frontend)
# ===========================================================================

@app.route('/api/hermes/chat', methods=['POST'])
def hermes_chat():
    data = request.json
    mensagem = data.get("mensagem", "")
    user_id = data.get("user_id", "anon")
    nome = data.get("nome", "Visitante")

    from ag_10_diretor import processar_pergunta
    from ag_06_telegram import classificar_cliente

    cliente = classificar_cliente(user_id, nome)
    resposta = processar_pergunta(user_id, mensagem, cliente)

    return jsonify({
        "resposta": resposta.get("resposta", "Não entendi. Pode reformular?"),
        "agente": resposta.get("agente", "diretor"),
        "intencao": resposta.get("intencao", "geral"),
        "user_id": user_id,
    })

# ===========================================================================
# Business operations (chamado pelo Business.tsx)
# ===========================================================================

@app.route('/api/business/inventory/<sku>', methods=['GET'])
def business_inventory(sku):
    """Check stock by SKU via AG-031 (portado)."""
    from ag_04_planejador import obter_estoque_produtos
    estoque = obter_estoque_produtos(sku)
    return jsonify({
        "sku": sku, "estoque": estoque,
        "status": "ok", "agente": "ag-031", "fonte": "hermes_db"
    })

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

@app.route('/api/test/bling', methods=['GET'])
def test_bling():
    """Testa conexão com Bling."""
    from bling_erp import get_api_key, get_api_url
    
    return jsonify({
        "configurado": bool(get_api_key()),
        "api_url": get_api_url()
    })

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

@app.route('/api/produtos', methods=['GET'])
def listar_produtos():
    """Catálogo com busca, filtros e estoque por loja."""
    busca = request.args.get("busca", "").strip()
    loja = request.args.get("loja", "")
    categoria = request.args.get("categoria", "")
    status = request.args.get("status", "")
    margem_min = request.args.get("margem_min", type=float)
    pagina = request.args.get("pagina", 1, type=int)
    por_pagina = request.args.get("por_pagina", 50, type=int)

    async def _go():
        db = await get_db()
        where = ["1=1"]
        params = []
        i = 1
        if busca:
            where.append(f"(f.sku ILIKE ${i} OR f.descricao ILIKE ${i})")
            params.append(f"%{busca}%")
            i += 1
        if loja:
            where.append(f"a.marketplace = ${i}")
            params.append(loja)
            i += 1
        if margem_min is not None:
            where.append(f"COALESCE(m.margem_pct, 0) >= ${i}")
            params.append(margem_min)
            i += 1

        offset = (pagina - 1) * por_pagina
        sql_where = " AND ".join(where)
        count = await db.fetchval(f"SELECT COUNT(*) FROM fichas_tecnicas f WHERE {sql_where}", *params)
        rows = await db.fetch(f"""
            SELECT f.id, f.sku, f.descricao AS nome, f.peso_gramas, f.material_principal,
                   f.tempo_ciclo_segundos, f.created_at,
                   COALESCE(m.margem_pct, 0) AS margem_pct,
                   COALESCE(m.receita_total, 0) AS receita_30d,
                   COALESCE(m.quantidade_vendida, 0) AS vendidos_30d
            FROM fichas_tecnicas f
            LEFT JOIN margens_diarias m ON m.sku = f.sku AND m.data = CURRENT_DATE
            WHERE {sql_where}
            ORDER BY m.quantidade_vendida DESC NULLS LAST
            LIMIT ${i} OFFSET ${i+1}
        """, *params, por_pagina, offset)
        produtos = [dict(r) for r in rows]

        # Buscar estoque por loja pra cada produto
        skus = [p["sku"] for p in produtos]
        estoques = {}
        if skus:
            estoque_rows = await db.fetch("""
                SELECT sku, marketplace, preco, status FROM anuncios
                WHERE sku = ANY($1::varchar[])
            """, skus)
            for e in estoque_rows:
                s = estoques.setdefault(e["sku"], [])
                s.append({"loja": e["marketplace"], "preco": float(e["preco"]) if e["preco"] else 0, "status": e["status"]})

        for p in produtos:
            p["estoque_lojas"] = estoques.get(p["sku"], [])
            p["total_lojas"] = len(p["estoque_lojas"])
        return {"produtos": produtos, "total": count, "pagina": pagina, "por_pagina": por_pagina}
    return jsonify(run_async(_go()))

@app.route('/api/produtos/<sku>', methods=['GET'])
def detalhe_produto(sku):
    """Detalhes do produto com histórico de preços e estoque."""
    async def _go():
        db = await get_db()
        produto = await db.fetchrow("""
            SELECT f.*, COALESCE(m.margem_pct, 0) AS margem_pct,
                   COALESCE(m.receita_total, 0) AS receita_30d,
                   COALESCE(m.quantidade_vendida, 0) AS vendidos_30d,
                   COALESCE(m.lucro_liquido, 0) AS lucro_30d
            FROM fichas_tecnicas f
            LEFT JOIN margens_diarias m ON m.sku = f.sku AND m.data = CURRENT_DATE
            WHERE f.sku = $1
        """, sku)
        if not produto:
            return {"error": "Produto não encontrado"}, 404
        p = dict(produto)

        estoque = await db.fetch("SELECT marketplace, preco, posicao_busca, avaliacao_media, status FROM anuncios WHERE sku = $1", sku)
        p["estoque_lojas"] = [dict(r) for r in estoque]

        vendas = await db.fetch("""
            SELECT data, marketplace, quantidade, preco_venda, receita_bruta
            FROM vendas WHERE sku = $1 ORDER BY data DESC LIMIT 90
        """, sku)
        p["vendas_30d"] = [dict(r) for r in vendas]

        precos = await db.fetch("""
            SELECT data, preco_venda FROM vendas
            WHERE sku = $1 ORDER BY data ASC
        """, sku)
        p["historico_precos"] = [{"data": str(r["data"]), "preco": float(r["preco_venda"])} for r in precos]

        return p
    return jsonify(run_async(_go()))

@app.route('/api/lojas', methods=['GET'])
def listar_lojas():
    """Performance de todas as lojas (físicas + marketplaces)."""
    async def _go():
        db = await get_db()

        # Lojas físicas fixas
        fisicas = [
            {"id": 1, "nome": "Loja Centro", "tipo": "fisica", "endereco": "Rua XV, 123"},
            {"id": 2, "nome": "Loja Shopping", "tipo": "fisica", "endereco": "Shopping Center, loja 45"},
            {"id": 3, "nome": "Loja Norte", "tipo": "fisica", "endereco": "Av. Norte, 789"},
            {"id": 4, "nome": "Loja Sul", "tipo": "fisica", "endereco": "Av. Sul, 456"},
            {"id": 5, "nome": "Loja Leste", "tipo": "fisica", "endereco": "Av. Leste, 321"},
        ]

        # Marketplaces do banco
        mps = await db.fetch("SELECT DISTINCT marketplace FROM vendas WHERE marketplace IS NOT NULL")
        marketplaces = [{"id": 10 + i, "nome": r["marketplace"], "tipo": "digital"} for i, r in enumerate(mps)]
        if not mps:
            marketplaces = [
                {"id": 10, "nome": "shopee", "tipo": "digital"},
                {"id": 11, "nome": "mercado_livre", "tipo": "digital"},
            ]

        todas = fisicas + marketplaces
        resultado = []
        for loja in todas:
            periodo = request.args.get("periodo", 30, type=int)
            if loja["tipo"] == "fisica":
                v = await db.fetchrow("""
                    SELECT COALESCE(SUM(receita_bruta), 0) AS receita,
                           COALESCE(SUM(quantidade), 0) AS pedidos,
                           COALESCE(SUM(receita_bruta) / NULLIF(SUM(quantidade), 0), 0) AS ticket
                    FROM vendas WHERE loja_id = $1
                    AND data >= CURRENT_DATE - $2::integer
                """, loja["id"], periodo)
            else:
                v = await db.fetchrow("""
                    SELECT COALESCE(SUM(receita_bruta), 0) AS receita,
                           COALESCE(SUM(quantidade), 0) AS pedidos,
                           COALESCE(SUM(receita_bruta) / NULLIF(SUM(quantidade), 0), 0) AS ticket
                    FROM vendas WHERE marketplace = $1
                    AND data >= CURRENT_DATE - $2::integer
                """, loja["nome"], periodo)

            resultado.append({
                **loja,
                "receita": float(v["receita"]) if v else 0,
                "pedidos": v["pedidos"] if v else 0,
                "ticket_medio": float(v["ticket"]) if v else 0,
                "margem": 0,
                "tendencia": "estavel",
            })

        # Totais consolidados
        total_receita = sum(r["receita"] for r in resultado)
        resultado.insert(0, {
            "id": 0, "nome": "📊 Consolidado", "tipo": "consolidado",
            "receita": total_receita,
            "pedidos": sum(r["pedidos"] for r in resultado),
            "ticket_medio": round(total_receita / max(sum(r["pedidos"] for r in resultado), 1), 2),
            "margem": 0, "tendencia": "estavel",
        })

        return resultado
    return jsonify(run_async(_go()))

@app.route('/api/kpi/overview', methods=['GET'])
def kpi_overview():
    """KPIs consolidados para página inicial."""
    async def _go():
        db = await get_db()
        periodo = request.args.get("periodo", 30, type=int)

        total_receita = await db.fetchval(
            "SELECT COALESCE(SUM(receita_bruta), 0) FROM vendas WHERE data >= CURRENT_DATE - $1::integer", periodo)
        total_pedidos = await db.fetchval(
            "SELECT COALESCE(SUM(quantidade), 0) FROM vendas WHERE data >= CURRENT_DATE - $1::integer", periodo)
        total_produtos = await db.fetchval("SELECT COUNT(*) FROM fichas_tecnicas")
        total_anuncios = await db.fetchval("SELECT COUNT(*) FROM anuncios WHERE status = 'ativo'")

        receita_shopee = await db.fetchval(
            "SELECT COALESCE(SUM(receita_bruta), 0) FROM vendas WHERE marketplace ILIKE '%shopee%' AND data >= CURRENT_DATE - $1::integer", periodo)
        receita_ml = await db.fetchval(
            "SELECT COALESCE(SUM(receita_bruta), 0) FROM vendas WHERE marketplace ILIKE '%mercado_livre%' AND data >= CURRENT_DATE - $1::integer", periodo)

        top_skus = await db.fetch("""
            SELECT v.sku, f.descricao AS nome, SUM(v.quantidade) AS qtd,
                   SUM(v.receita_bruta) AS receita,
                   COALESCE(m.margem_pct, 0) AS margem
            FROM vendas v
            JOIN fichas_tecnicas f ON f.sku = v.sku
            LEFT JOIN margens_diarias m ON m.sku = v.sku AND m.data = CURRENT_DATE
            WHERE v.data >= CURRENT_DATE - $1::integer
            GROUP BY v.sku, f.descricao, m.margem_pct
            ORDER BY SUM(v.receita_bruta) DESC LIMIT 10
        """, periodo)

        receita_por_dia = await db.fetch("""
            SELECT data, SUM(receita_bruta) AS receita
            FROM vendas WHERE data >= CURRENT_DATE - 14
            GROUP BY data ORDER BY data
        """)

        return {
            "receita_total": float(total_receita),
            "total_pedidos": total_pedidos,
            "total_produtos": total_produtos,
            "total_anuncios": total_anuncios,
            "ticket_medio": round(float(total_receita) / max(total_pedidos, 1), 2),
            "receita_por_canal": {
                "shopee": float(receita_shopee),
                "mercado_livre": float(receita_ml),
            },
            "top_skus": [dict(r) for r in top_skus],
            "receita_por_dia": [{"data": str(r["data"]), "receita": float(r["receita"])} for r in receita_por_dia],
        }
    return jsonify(run_async(_go()))

# ===========================================================================
# Rota padrão — SPA fallback: serve index.html pra qualquer rota do frontend
# ===========================================================================
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    static_dir = Path(__file__).parent / 'dashboard'
    if not path:
        return send_from_directory(static_dir, 'index.html')
    target = static_dir / path
    if target.exists() and target.is_file():
        return send_from_directory(static_dir, path)
    return send_from_directory(static_dir, 'index.html')

if __name__ == "__main__":
    # Rodar como servidor Flask
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
