#!/usr/bin/env python3
"""
Deploy script — writes all Hermes Agent Swarm files to /workspace/hermes_agents/.
Run: python deploy_to_hermes.py
"""
import os

TARGET = "/workspace/hermes_agents"

FILES = {}

# ===========================================================================
# __init__.py (root)
# ===========================================================================
FILES["__init__.py"] = '''"""
Hermes Agent Swarm — Fábrica Inteligente
Sistema multi-agente para indústria de manufatura com vendas em marketplaces.

Fase 1:
  AG-09 — Memória Corporativa
  AG-01 — Caçador de Produtos
  AG-02 — Analista de Lucratividade
  AG-03 — Gerente de Marketplaces

Uso:
  python -m hermes_agents.setup    # Inicializa banco de dados
  python -m hermes_agents.scheduler  # Inicia scheduler diário
"""

from hermes_agents import ag_01_cacador, ag_02_lucratividade, ag_03_marketplaces, ag_09_memoria

def executar_ciclo_diario():
    """Executa o pipeline completo da Fase 1."""
    print("=" * 60)
    print("HERMES AGENT SWARM — FASE 1 — CICLO DIÁRIO")
    print("=" * 60)

    # 1. Caçada de produtos (06:00)
    print("\\n[1/3] AG-01 Caçador de Produtos — pesquisando marketplaces...")
    oportunidades = ag_01_cacador.executar_cacada()
    print(f"  → {len(oportunidades)} produtos analisados")

    # 2. Análise de lucratividade (07:00)
    print("\\n[2/3] AG-02 Analista de Lucratividade — calculando margens...")
    relatorio = ag_02_lucratividade.relatorio_diario()
    print(f"  → Receita do dia: R${relatorio['receita_total']:.2f} | {relatorio['skus_vendidos']} SKUs vendidos")
    alertas = ag_02_lucratividade.verificar_alertas()
    if alertas:
        print(f"  → {len(alertas)} SKUs com margem abaixo do mínimo!")

    # 3. Monitoramento de marketplaces
    print("\\n[3/3] AG-03 Gerente de Marketplaces — monitorando posições...")
    status = ag_03_marketplaces.relatorio_consolidado()
    print(f"  → {status['total_anuncios_ativos']} anúncios ativos | {status['anuncios_top10']} no top 10 | {status['alertas_abertos']} alertas")
    monitoramento = ag_03_marketplaces.executar_monitoramento()
    if monitoramento:
        print(f"  → {len(monitoramento)} ocorrências detectadas")

    print("\\n" + "=" * 60)
    print("CICLO CONCLUÍDO")
    print("=" * 60)

# Auto-teste
if __name__ == "__main__":
    print("AG-09 Stats:", ag_09_memoria.stats())

    # Teste de cálculo de lucro
    resultado = ag_02_lucratividade.calcular_lucro_real(49.90, 8.50, 18.0, 5.00)
    print(f"Lucro real: R${resultado['lucro_liquido']:.2f} ({resultado['margem_pct']}%)")

    print("\\nOk — módulos carregados com sucesso.")
'''

# ===========================================================================
# setup.py
# ===========================================================================
FILES["setup.py"] = '''"""
Deploy script — copia os agentes para dentro do container Hermes.
Rode este script localmente ou via Hermes execute_code.
"""
import os, sys, shutil
from pathlib import Path

SRC = Path(__file__).resolve().parent  # hermes_agents/
DST = Path("/workspace/hermes_agents")

def deploy():
    """Copia todo o pacote hermes_agents para /workspace."""
    print(f"Deploy: {SRC} → {DST}")

    # Remove destino anterior se existir
    if DST.exists():
        print(f"  Removendo {DST}...")
        shutil.rmtree(DST)

    # Copia diretórios
    shutil.copytree(SRC, DST, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))

    # Verifica
    for sub in ["core", "ag_09_memoria", "ag_01_cacador", "ag_02_lucratividade", "ag_03_marketplaces", "profiles"]:
        assert (DST / sub).exists(), f"Faltando {sub}!"

    print(f"Deploy concluído: {DST}")
    print("\\nPara testar, no execute_code do Hermes:")
    print("  import sys; sys.path.insert(0, '/workspace')")
    print("  from hermes_agents.ag_01_cacador import executar_cacada")
    print("  executar_cacada()")

def init_db():
    """Inicializa o schema do banco de dados."""
    schema_path = SRC / "sql" / "schema.sql"
    if not schema_path.exists():
        print(f"Schema não encontrado: {schema_path}")
        return

    sql = schema_path.read_text(encoding="utf-8")
    print(f"Schema: {len(sql)} bytes")
    print("Cole este SQL no terminal do PostgreSQL ou execute via Python:")
    print(f"  cat {schema_path} | psql -h <host> -U <user> -d hermes_factory")

if __name__ == "__main__":
    if "--init-db" in sys.argv:
        init_db()
    else:
        deploy()
'''

# ===========================================================================
# core/__init__.py
# ===========================================================================
FILES["core/__init__.py"] = '''"""
Core infrastructure for Hermes Agent Swarm.
Database connection, config loading, shared utilities.
"""
import os
import json
import asyncio
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, asdict, field

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")) / "factory_config.json"

@dataclass
class FactoryConfig:
    db_host: str = "postgresql-database-h3bdeft4hgsbg9rcxklxidwt"
    db_port: int = 5432
    db_name: str = "hermes_factory"
    db_user: str = os.environ.get("DB_USER", "postgres")
    db_password: str = os.environ.get("DB_PASSWORD", "")

    # Marketplaces
    mercado_livre_authorization: str = ""
    shopee_partner_id: str = ""
    shopee_partner_key: str = ""
    amazon_access_key: str = ""
    amazon_secret_key: str = ""

    # Telegram
    telegram_bot_token: str = ""

    # Lojas físicas
    lojas: list = field(default_factory=lambda: [
        {"id": 1, "nome": "Loja Centro"},
        {"id": 2, "nome": "Loja Shopping"},
        {"id": 3, "nome": "Loja Norte"},
        {"id": 4, "nome": "Loja Sul"},
        {"id": 5, "nome": "Loja Leste"},
    ])

    # Alerta
    margem_minima_pct: float = 15.0
    ruptura_estoque_dias: int = 7

    @classmethod
    def load(cls) -> "FactoryConfig":
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return cls(**data)
        return cls()

    def save(self):
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

_db_pool: Optional[Any] = None

async def get_db():
    """Retorna ou cria pool de conexões asyncpg."""
    global _db_pool
    if not HAS_ASYNCPG:
        raise RuntimeError("asyncpg não instalado")
    if _db_pool is None:
        cfg = FactoryConfig.load()
        _db_pool = await asyncpg.create_pool(
            host=cfg.db_host,
            port=cfg.db_port,
            database=cfg.db_name,
            user=cfg.db_user,
            password=cfg.db_password,
            min_size=2,
            max_size=10,
        )
    return _db_pool

def run_async(coro):
    """Helper para rodar async em contexto síncrono."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as ex:
            return ex.submit(lambda: asyncio.run(coro)).result()
    return asyncio.run(coro)

# ---------------------------------------------------------------------------
# Logging & utils
# ---------------------------------------------------------------------------

def log(agent: str, msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{agent}] {msg}")

def hoje() -> str:
    return date.today().isoformat()

def pct(v1: float, v2: float) -> float:
    """Retorna percentual v1 / v2 * 100."""
    return round((v1 / v2 * 100) if v2 else 0, 1)
'''

# ===========================================================================
# sql/schema.sql
# ===========================================================================
FILES["sql/schema.sql"] = r'''-- ===========================================================================
-- Hermes Agent Swarm — Database Schema
-- Fase 1: Memória Corporativa + Produtos + Lucratividade + Marketplaces
-- ===========================================================================

-- ===========================================================================
-- AG-09: Memória Corporativa
-- ===========================================================================

CREATE TABLE IF NOT EXISTS moldes (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE NOT NULL,
    produto VARCHAR(200) NOT NULL,
    material VARCHAR(100),
    ciclos_previstos INTEGER,
    ciclos_atuais INTEGER DEFAULT 0,
    custo_molde DECIMAL(12,2),
    data_aquisicao DATE,
    fabricante VARCHAR(200),
    desenho_path TEXT,
    status VARCHAR(20) DEFAULT 'ativo' CHECK (status IN ('ativo','manutencao','inativo','sucateado')),
    observacoes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fichas_tecnicas (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(50) UNIQUE NOT NULL,
    molde_id INTEGER REFERENCES moldes(id),
    descricao TEXT NOT NULL,
    peso_gramas DECIMAL(10,2),
    dimensoes_mm VARCHAR(50),
    cor_padrao VARCHAR(50),
    material_principal VARCHAR(100),
    tempo_ciclo_segundos INTEGER,
    cavidades INTEGER DEFAULT 1,
    peso_embalagem_gramas DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fornecedores (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(200) NOT NULL,
    categoria VARCHAR(50) CHECK (categoria IN ('materia_prima','ferramentas','embalagem','servicos','outros')),
    contato_nome VARCHAR(200),
    contato_telefone VARCHAR(50),
    contato_email VARCHAR(200),
    cnpj VARCHAR(20),
    prazo_medio_entrega_dias INTEGER,
    avaliacao INTEGER CHECK (avaliacao BETWEEN 1 AND 5),
    status VARCHAR(20) DEFAULT 'ativo',
    observacoes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS materias_primas (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(200) NOT NULL,
    tipo VARCHAR(100),
    fornecedor_id INTEGER REFERENCES fornecedores(id),
    unidade VARCHAR(20) DEFAULT 'kg',
    preco_unitario DECIMAL(12,4),
    data_cotacao DATE,
    estoque_minimo_kg DECIMAL(12,3),
    estoque_atual_kg DECIMAL(12,3),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS historico_custos (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(50) REFERENCES fichas_tecnicas(sku),
    data DATE NOT NULL,
    custo_materia_prima DECIMAL(12,4),
    custo_mao_obra DECIMAL(12,4),
    custo_embalagem DECIMAL(12,4),
    custo_total DECIMAL(12,4),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS problemas_resolvidos (
    id SERIAL PRIMARY KEY,
    titulo VARCHAR(200) NOT NULL,
    descricao TEXT,
    solucao TEXT,
    categoria VARCHAR(50),
    sku_relacionado VARCHAR(50),
    data_ocorrencia DATE,
    data_resolucao DATE,
    tags TEXT[],
    created_at TIMESTAMP DEFAULT NOW()
);

-- ===========================================================================
-- AG-01: Caçador de Produtos
-- ===========================================================================

CREATE TABLE IF NOT EXISTS produtos_descobertos (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(300) NOT NULL,
    marketplace_origem VARCHAR(50) CHECK (marketplace_origem IN ('shopee','mercado_livre','amazon','temu','tiktok_shop','google_trends','pinterest')),
    url TEXT,
    data_descoberta DATE DEFAULT CURRENT_DATE,
    preco_medio DECIMAL(12,2),
    volume_vendas_estimado INTEGER,
    concorrentes_diretos INTEGER,
    nivel_concorrencia VARCHAR(10) CHECK (nivel_concorrencia IN ('baixa','media','alta')),
    fabricavel BOOLEAN DEFAULT false,
    complexidade_molde INTEGER CHECK (complexidade_molde BETWEEN 1 AND 10),
    custo_molde_estimado DECIMAL(12,2),
    custo_producao_unitario DECIMAL(12,4),
    margem_estimada_pct DECIMAL(5,1),
    tempo_lancamento_dias INTEGER,
    tendencia VARCHAR(20) CHECK (tendencia IN ('subindo','estavel','caindo','explosiva')),
    score_final INTEGER CHECK (score_final BETWEEN 0 AND 100),
    status VARCHAR(20) DEFAULT 'analisar' CHECK (status IN ('analisar','aprovado','rejeitado','em_desenvolvimento','lancado')),
    tags TEXT[],
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tendencias (
    id SERIAL PRIMARY KEY,
    termo VARCHAR(300) NOT NULL,
    plataforma VARCHAR(50),
    volume_buscas INTEGER,
    crescimento_pct DECIMAL(7,2),
    data_coleta DATE DEFAULT CURRENT_DATE,
    categoria VARCHAR(100),
    relevancia INTEGER CHECK (relevancia BETWEEN 0 AND 100)
);

-- ===========================================================================
-- AG-02: Analista de Lucratividade
-- ===========================================================================

CREATE TABLE IF NOT EXISTS vendas (
    id SERIAL PRIMARY KEY,
    data DATE NOT NULL,
    sku VARCHAR(50) REFERENCES fichas_tecnicas(sku),
    marketplace VARCHAR(50),
    loja_id INTEGER,
    quantidade INTEGER NOT NULL,
    preco_venda DECIMAL(12,2),
    receita_bruta DECIMAL(12,2),
    taxa_marketplace_pct DECIMAL(5,1),
    taxa_marketplace_valor DECIMAL(12,2),
    frete DECIMAL(12,2),
    impostos DECIMAL(12,2),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS margens_diarias (
    id SERIAL PRIMARY KEY,
    data DATE NOT NULL,
    sku VARCHAR(50) REFERENCES fichas_tecnicas(sku),
    receita_total DECIMAL(12,2),
    custo_total DECIMAL(12,2),
    margem_bruta DECIMAL(12,2),
    margem_pct DECIMAL(5,1),
    quantidade_vendida INTEGER,
    lucro_liquido DECIMAL(12,2),
    status_margem VARCHAR(10) CHECK (status_margem IN ('saudavel','alerta','deficit')),
    created_at TIMESTAMP DEFAULT NOW()
);

-- ===========================================================================
-- AG-03: Gerente de Marketplaces
-- ===========================================================================

CREATE TABLE IF NOT EXISTS anuncios (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(50) REFERENCES fichas_tecnicas(sku),
    marketplace VARCHAR(50) NOT NULL,
    anuncio_id VARCHAR(100),
    titulo VARCHAR(300),
    preco DECIMAL(12,2),
    posicao_busca INTEGER,
    avaliacao_media DECIMAL(3,1),
    total_avaliacoes INTEGER,
    palavras_chave TEXT[],
    clicks_dia INTEGER DEFAULT 0,
    impressoes_dia INTEGER DEFAULT 0,
    taxa_conversao_pct DECIMAL(5,1),
    status VARCHAR(20) DEFAULT 'ativo',
    ultima_atualizacao TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS concorrentes (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(200),
    marketplace VARCHAR(50),
    produto_similar VARCHAR(300),
    sku_concorrente VARCHAR(100),
    preco DECIMAL(12,2),
    avaliacao DECIMAL(3,1),
    total_vendas_estimado INTEGER,
    data_coleta DATE DEFAULT CURRENT_DATE
);

CREATE TABLE IF NOT EXISTS sugestoes_otimizacao (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(50) REFERENCES fichas_tecnicas(sku),
    marketplace VARCHAR(50),
    tipo VARCHAR(50) CHECK (tipo IN ('titulo','descricao','preco','palavras_chave','kit','promocao')),
    sugestao TEXT NOT NULL,
    impacto_estimado VARCHAR(20) CHECK (impacto_estimado IN ('alto','medio','baixo')),
    status VARCHAR(20) DEFAULT 'pendente' CHECK (status IN ('pendente','aplicada','ignorada','testando')),
    resultado TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alertas (
    id SERIAL PRIMARY KEY,
    tipo VARCHAR(50) CHECK (tipo IN ('preco_concorrente','posicao','avaliacao','estoque','ruptura','tendencia','margem')),
    sku VARCHAR(50),
    marketplace VARCHAR(50),
    mensagem TEXT NOT NULL,
    gravidade VARCHAR(10) CHECK (gravidade IN ('info','alerta','critico')),
    resolvido BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ===========================================================================
-- Índices
-- ===========================================================================

CREATE INDEX IF NOT EXISTS idx_moldes_codigo ON moldes(codigo);
CREATE INDEX IF NOT EXISTS idx_fichas_sku ON fichas_tecnicas(sku);
CREATE INDEX IF NOT EXISTS idx_fornecedores_categoria ON fornecedores(categoria);
CREATE INDEX IF NOT EXISTS idx_produtos_status ON produtos_descobertos(status);
CREATE INDEX IF NOT EXISTS idx_produtos_score ON produtos_descobertos(score_final DESC);
CREATE INDEX IF NOT EXISTS idx_vendas_data ON vendas(data);
CREATE INDEX IF NOT EXISTS idx_vendas_sku ON vendas(sku);
CREATE INDEX IF NOT EXISTS idx_margens_sku_data ON margens_diarias(sku, data);
CREATE INDEX IF NOT EXISTS idx_anuncios_marketplace ON anuncios(marketplace, sku);
CREATE INDEX IF NOT EXISTS idx_alertas_resolvido ON alertas(resolvido, gravidade);
CREATE INDEX IF NOT EXISTS idx_historico_sku ON historico_custos(sku, data);

-- ===========================================================================
-- Dados de exemplo
-- ===========================================================================

INSERT INTO fornecedores (nome, categoria, contato_email, avaliacao) VALUES
('Plásticos Sul Ltda', 'materia_prima', 'vendas@plasticossul.com.br', 4),
('Ferramentas Pro Master', 'ferramentas', 'contato@ferramentaspro.com.br', 5),
('Embalagens EcoPack', 'embalagem', 'sac@ecopack.com.br', 4)
ON CONFLICT DO NOTHING;

INSERT INTO materias_primas (nome, tipo, preco_unitario, estoque_minimo_kg, estoque_atual_kg) VALUES
('PP Copolímero', 'Polipropileno', 12.50, 500, 1200),
('ABS Natural', 'ABS', 22.00, 300, 450),
('PEAD Branco', 'Polietileno', 10.80, 800, 2000),
('Masterbatch Preto', 'Corante', 35.00, 50, 80)
ON CONFLICT DO NOTHING;
'''

# ===========================================================================
# profiles/profiles.yaml
# ===========================================================================
FILES["profiles/profiles.yaml"] = r'''# Hermes Agent Swarm — Agent Profiles
# Fase 1: AG-01, AG-02, AG-03, AG-09

profiles:

  # =========================================================================
  # AG-09: Memória Corporativa
  # =========================================================================
  ag_09_memoria_corporativa:
    name: "AG-09 Memória Corporativa"
    description: >
      Bibliotecário técnico da fábrica. Conhece todos os moldes, fichas técnicas,
      fornecedores, matérias-primas, custos históricos e problemas já resolvidos.
      Responde perguntas como "Já fabricamos algo parecido?", "Qual molde usamos?",
      "Quem é o fornecedor mais barato de PP?"
    model: claude-sonnet-4-20250514
    provider: anthropic
    workspace: /workspace/factory
    skills:
      - factory-corporate-memory
    system_prompt: |
      Você é o AG-09 — Memória Corporativa da fábrica Jorge Charme e Leon.

      Seu papel: ser a memória técnica da empresa. Você conhece:
      - Todos os moldes (código, material, ciclos, custo)
      - Fichas técnicas de cada SKU
      - Fornecedores e preços de matéria-prima
      - Histórico de custos de produção
      - Problemas já resolvidos e suas soluções

      Regras:
      1. Responda sempre com dados concretos do banco, NUNCA invente
      2. Se não encontrou a informação, diga claramente "Não encontrei esse dado na base"
      3. Para buscas de similaridade, use a função buscar_similar()
      4. Formate valores monetários como R$ X.XXX,XX
      5. Seja conciso — o dono da fábrica quer respostas rápidas

    schedule: []

  # =========================================================================
  # AG-01: Caçador de Produtos
  # =========================================================================
  ag_01_cacador_produtos:
    name: "AG-01 Caçador de Produtos"
    description: >
      Descobre diariamente produtos em alta nos marketplaces que a fábrica
      pode produzir. Analisa viabilidade: margem estimada, complexidade do molde,
      concorrência, tempo de lançamento.
    model: claude-sonnet-4-20250514
    provider: anthropic
    workspace: /workspace/factory
    skills:
      - factory-product-hunter
      - factory-corporate-memory
    system_prompt: |
      Você é o AG-01 — Caçador de Produtos da fábrica Jorge Charme e Leon.

      Sua missão: encontrar produtos que a fábrica pode produzir ANTES da concorrência.

      Todos os dias você:
      1. Coleta produtos em alta de Shopee, Mercado Livre, Amazon, Temu, TikTok Shop
      2. Verifica tendências no Google Trends e Pinterest
      3. Analisa viabilidade de fabricação (material, molde, margem)
      4. Entrega um ranking priorizado

      Critérios de prioridade:
      - Fabricável com nossos materiais (PP, ABS, PEAD, silicone) → +40 pontos
      - Baixa concorrência (< 30 vendedores) → +30 pontos
      - Margem estimada > 40% → +30 pontos

      Regras:
      1. SEMPRE priorize produtos fabricáveis com injeção plástica
      2. Ignore eletrônicos (não temos linha de montagem)
      3. Destaque tendências explosivas (crescimento > 50% em 30 dias)
      4. Formate a resposta como tabela de oportunidades

    schedule:
      - cron: "0 6 * * *"
        task: "executar_cacada()"
        description: "Caçada diária de produtos"

  # =========================================================================
  # AG-02: Analista de Lucratividade
  # =========================================================================
  ag_02_analista_lucratividade:
    name: "AG-02 Analista de Lucratividade"
    description: >
      Calcula o lucro real de cada SKU descontando todos os custos.
      Identifica produtos que vendem muito mas geram pouco lucro.
    model: claude-sonnet-4-20250514
    provider: anthropic
    workspace: /workspace/factory
    skills:
      - factory-profitability-analyst
      - factory-corporate-memory
    system_prompt: |
      Você é o AG-02 — Analista de Lucratividade da fábrica Jorge Charme e Leon.

      Sua missão: mostrar quais produtos REALMENTE dão lucro.

      O lucro real é calculado como:
      lucro = receita_bruta - custo_materia_prima - custo_mao_obra - taxa_marketplace - frete - impostos

      Você responde perguntas como:
      - "Qual produto dá mais lucro?"
      - "Qual SKU vende muito mas não gera margem?"
      - "Vale a pena continuar fabricando o produto X?"

      Regras:
      1. Margem abaixo de 15% = 🚨 DEFICIT — sugira descontinuar ou aumentar preço
      2. Margem entre 15% e 25% = ⚠️ ALERTA — monitore de perto
      3. Margem acima de 25% = ✅ SAUDÁVEL
      4. Sempre mostre o cálculo detalhado quando perguntado

    schedule:
      - cron: "0 7 * * *"
        task: "relatorio_diario() + verificar_alertas()"
        description: "Relatório diário de lucratividade"

  # =========================================================================
  # AG-03: Gerente de Marketplaces
  # =========================================================================
  ag_03_gerente_marketplaces:
    name: "AG-03 Gerente de Marketplaces"
    description: >
      Monitora anúncios, preços dos concorrentes, avaliações.
      Sugere otimizações de título, SEO, preço e criação de kits.
    model: claude-sonnet-4-20250514
    provider: anthropic
    workspace: /workspace/factory
    skills:
      - factory-marketplace-manager
      - factory-corporate-memory
    system_prompt: |
      Você é o AG-03 — Gerente de Marketplaces da fábrica Jorge Charme e Leon.

      Sua missão: aumentar vendas nos marketplaces sem criar novos produtos.

      Você monitora continuamente:
      - Posição dos anúncios (Shopee, Mercado Livre, Amazon)
      - Preços dos concorrentes
      - Avaliações e reputação
      - Palavras-chave e SEO

      Ações que você pode sugerir:
      - Novo título otimizado para SEO
      - Ajuste de preço baseado na concorrência
      - Criação de kits (produto A + produto B com desconto)
      - Promoções relâmpago para queimar estoque parado

      Regras:
      1. Alerte IMEDIATAMENTE se um concorrente baixou o preço em mais de 10%
      2. Sugira kits apenas para produtos complementares reais
      3. Priorize anúncios que caíram do top 10
      4. Seja acionável — toda sugestão deve ter um "faça isso agora"

    schedule:
      - cron: "0 */4 * * *"
        task: "executar_monitoramento()"
        description: "Monitoramento de marketplaces a cada 4 horas"
'''

# ===========================================================================
# ag_01_cacador/__init__.py
# ===========================================================================
FILES["ag_01_cacador/__init__.py"] = '''"""
AG-01: Caçador de Produtos
Pesquisa diariamente marketplaces em busca de produtos em alta,
com baixa concorrência, que a fábrica consegue produzir.
"""
import sys, json, os
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Optional
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import get_db, run_async, log, hoje, pct

AGENT = "AG-01 | Caçador de Produtos"

# ---------------------------------------------------------------------------
# Config de fontes
# ---------------------------------------------------------------------------

MARKETPLACES = ["shopee", "mercado_livre", "amazon", "temu", "tiktok_shop"]
FONTES_TENDENCIAS = ["google_trends", "pinterest"]

# ---------------------------------------------------------------------------
# Simulador de coleta — em produção usar APIs reais / raspagem
# ---------------------------------------------------------------------------

def pesquisar_marketplace(marketplace: str, categoria: str = "casa_e_decoracao") -> list:
    """
    Coleta produtos do marketplace.
    Em produção: substituir por chamada real à API ou Playwright.
    """
    log(AGENT, f"Pesquisando {marketplace} > {categoria}...")

    # ponytail: simulador placeholder, trocar por API real quando tokens configurados
    produtos_simulados = {
        "shopee": [
            {"nome": "Organizador de Gaveta Modular Plástico", "preco": 29.90, "vendas_mes": 8500, "concorrentes": 120},
            {"nome": "Porta Tempero Giratório 3 Andares", "preco": 49.90, "vendas_mes": 6200, "concorrentes": 45},
            {"nome": "Cabo USB-C Trançado 2m 100W", "preco": 35.00, "vendas_mes": 15000, "concorrentes": 300},
            {"nome": "Suporte de Parede para Celular Cozinha", "preco": 22.90, "vendas_mes": 4100, "concorrentes": 25},
            {"nome": "Kit Potes Herméticos 10 Peças", "preco": 89.90, "vendas_mes": 9800, "concorrentes": 80},
            {"nome": "Escorredor de Louça Dobrável Silicone", "preco": 39.90, "vendas_mes": 7200, "concorrentes": 35},
        ],
        "mercado_livre": [
            {"nome": "Suporte Ajustável para Notebook Alumínio", "preco": 79.90, "vendas_mes": 5500, "concorrentes": 90},
            {"nome": "Luminária LED Recarregável Toque", "preco": 45.00, "vendas_mes": 11000, "concorrentes": 150},
            {"nome": "Ventilador USB Clip Mesa Silencioso", "preco": 55.00, "vendas_mes": 4300, "concorrentes": 40},
        ],
        "amazon": [
            {"nome": "Capa Impermeável para Sofá 3 Lugares", "preco": 119.90, "vendas_mes": 3200, "concorrentes": 55},
            {"nome": "Filtro de Água Torneira Purificador", "preco": 69.90, "vendas_mes": 7800, "concorrentes": 65},
        ],
        "temu": [
            {"nome": "Mini Ventilador Portátil USB Recarregável", "preco": 15.90, "vendas_mes": 25000, "concorrentes": 500},
            {"nome": "Cabo Organizador Clip Fio Mesa", "preco": 8.90, "vendas_mes": 18000, "concorrentes": 200},
        ],
        "tiktok_shop": [
            {"nome": "Espelho Adesivo Decorativo Formato Geométrico", "preco": 25.00, "vendas_mes": 35000, "concorrentes": 80},
            {"nome": "Caneca Térmica com Tampa Bomba 500ml", "preco": 59.90, "vendas_mes": 12000, "concorrentes": 50},
        ],
    }
    return produtos_simulados.get(marketplace, [])

# ---------------------------------------------------------------------------
# Coleta de tendências
# ---------------------------------------------------------------------------

def coletar_tendencias() -> list:
    """Coleta tendências do Google Trends e Pinterest."""
    log(AGENT, "Coletando tendências...")

    # ponytail: placeholder, trocar por pytrends / pinterest API
    tendencias = [
        {"termo": "organizador de cozinha", "volume": 22000, "crescimento": 45.0, "categoria": "casa"},
        {"termo": "acessórios home office", "volume": 18000, "crescimento": 30.0, "categoria": "escritorio"},
        {"termo": "produtos sustentaveis", "volume": 15000, "crescimento": 60.0, "categoria": "geral"},
        {"termo": "gadgets cozinha", "volume": 12000, "crescimento": 25.0, "categoria": "casa"},
        {"termo": "pet acessorios", "volume": 25000, "crescimento": 20.0, "categoria": "pets"},
        {"termo": "decoracao minimalista", "volume": 10000, "crescimento": 55.0, "categoria": "decoracao"},
    ]
    async def _save():
        db = await get_db()
        for t in tendencias:
            await db.execute("""
                INSERT INTO tendencias (termo, plataforma, volume_buscas, crescimento_pct, data_coleta, categoria, relevancia)
                VALUES ($1, 'google_trends', $2, $3, CURRENT_DATE, $4, $5)
                ON CONFLICT DO NOTHING
            """, t["termo"], t["volume"], t["crescimento"], t["categoria"], min(int(t["crescimento"]), 100))
    run_async(_save())
    return tendencias

# ---------------------------------------------------------------------------
# Análise de viabilidade
# ---------------------------------------------------------------------------

def analisar_viabilidade(produto: dict) -> dict:
    """Analisa se um produto é viável para fabricação própria."""
    # Critérios de fabricabilidade
    materiais_compativeis = ["plastico", "silicone", "pp", "abs", "pead", "pvc", "acrilico"]
    nome_lower = produto["nome"].lower()

    # Verifica se usa material que temos
    fabricavel = any(m in nome_lower for m in materiais_compativeis)

    # Estima complexidade do molde
    palavras_complexas = ["dobravel", "articulado", "mola", "encaixe", "rosca", "eletronico"]
    complexidade = sum(1 for p in palavras_complexas if p in nome_lower)
    complexidade = min(complexidade + 3, 10)

    # Estima margem
    preco = produto["preco"]
    custo_molde_estimado = complexidade * 5000  # R$5000 por ponto de complexidade
    custo_producao_unitario = preco * 0.18  # ~18% do preço de venda

    # Taxas marketplace (~18% em média)
    taxa = preco * 0.18
    lucro = preco - custo_producao_unitario - taxa
    margem = round((lucro / preco) * 100, 1) if preco else 0

    # Score final
    concorrencia = produto.get("concorrentes", 100)
    score = 0
    if fabricavel: score += 40
    if concorrencia < 30: score += 30
    elif concorrencia < 80: score += 15
    if margem > 40: score += 30
    elif margem > 25: score += 15

    nivel_concorrencia = "baixa" if concorrencia < 30 else ("media" if concorrencia < 100 else "alta")

    return {
        "nome": produto["nome"],
        "marketplace_origem": produto.get("marketplace", "desconhecido"),
        "url": produto.get("url", ""),
        "preco_medio": preco,
        "volume_vendas_estimado": produto.get("vendas_mes", 0),
        "concorrentes_diretos": concorrencia,
        "nivel_concorrencia": nivel_concorrencia,
        "fabricavel": fabricavel,
        "complexidade_molde": complexidade,
        "custo_molde_estimado": custo_molde_estimado,
        "custo_producao_unitario": round(custo_producao_unitario, 2),
        "margem_estimada": margem,
        "tempo_lancamento_dias": complexidade * 7 + 15,
        "tendencia": "estavel",
        "score_final": min(score, 100),
        "status": "analisar",
    }

# ---------------------------------------------------------------------------
# Pipeline principal: coleta + análise + salva
# ---------------------------------------------------------------------------

def executar_cacada(categoria: str = "casa_e_decoracao") -> list:
    """
    Executa a caçada completa:
    1. Coleta de todos os marketplaces
    2. Análise de viabilidade
    3. Ranking por score
    4. Salva no banco
    """
    log(AGENT, f"Iniciando caçada diária em {len(MARKETPLACES)} marketplaces...")
    todos_produtos = []

    for mp in MARKETPLACES:
        produtos = pesquisar_marketplace(mp, categoria)
        for p in produtos:
            p["marketplace"] = mp
            analise = analisar_viabilidade(p)
            todos_produtos.append(analise)

    # Ordena por score
    todos_produtos.sort(key=lambda x: x["score_final"], reverse=True)

    # Salva no banco
    async def _save():
        db = await get_db()
        for p in todos_produtos:
            await db.execute("""
                INSERT INTO produtos_descobertos
                    (nome, marketplace_origem, url, data_descoberta, preco_medio,
                     volume_vendas_estimado, concorrentes_diretos, nivel_concorrencia,
                     fabricavel, complexidade_molde, custo_molde_estimado,
                     custo_producao_unitario, margem_estimada_pct,
                     tempo_lancamento_dias, tendencia, score_final, status)
                VALUES ($1,$2,$3,CURRENT_DATE,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,'analisar')
                ON CONFLICT DO NOTHING
            """, p["nome"], p["marketplace_origem"], p["url"], p["preco_medio"],
                p["volume_vendas_estimado"], p["concorrentes_diretos"], p["nivel_concorrencia"],
                p["fabricavel"], p["complexidade_molde"], p["custo_molde_estimado"],
                p["custo_producao_unitario"], p["margem_estimada"],
                p["tempo_lancamento_dias"], p["tendencia"], p["score_final"])
    run_async(_save())

    log(AGENT, f"Caçada concluída: {len(todos_produtos)} produtos encontrados")
    return todos_produtos

def top_oportunidades(n: int = 10) -> list:
    """Retorna as top N oportunidades do dia."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT * FROM produtos_descobertos
            WHERE data_descoberta = CURRENT_DATE AND status = 'analisar'
            ORDER BY score_final DESC
            LIMIT $1
        """, n)
        return [dict(r) for r in rows]
    return run_async(_go())

# ---------------------------------------------------------------------------
# Auto-teste
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log(AGENT, "=== Auto-teste ===")
    resultados = executar_cacada()
    print(f"\\nTop 5 oportunidades:")
    for i, p in enumerate(resultados[:5], 1):
        print(f"  {i}. [{p['score_final']}/100] {p['nome']}")
        print(f"     R${p['preco_medio']:.2f} | Margem: {p['margem_estimada']}% | Concorrência: {p['nivel_concorrencia']} | Fabricável: {p['fabricavel']}")
'''

# ===========================================================================
# ag_01_cacador/SKILL.md
# ===========================================================================
FILES["ag_01_cacador/SKILL.md"] = r'''---
name: factory-product-hunter
description: >
  AG-01: Caçador de Produtos. Pesquisa marketplaces diariamente em busca de
  produtos em alta, baixa concorrência e viáveis para fabricação própria.
  Use para "O que devemos fabricar?", "Tendências da semana", "Novos produtos".
category: factory
bundled: true
---

# AG-01 — Caçador de Produtos

Descobre novas oportunidades de receita antes da concorrência.

## Fontes monitoradas

Shopee · Mercado Livre · Amazon · Temu · TikTok Shop · Google Trends · Pinterest

## Ferramentas

| Função | Descrição |
|---|---|
| `executar_cacada(categoria)` | Coleta + analisa + salva produtos de todos os marketplaces |
| `top_oportunidades(n)` | Top N produtos com maior score do dia |
| `coletar_tendencias()` | Tendências do Google Trends e Pinterest |
| `pesquisar_marketplace(mp, cat)` | Pesquisa um marketplace específico |
| `analisar_viabilidade(produto)` | Score de viabilidade de fabricação |

## Como usar

```python
sys.path.insert(0, "/workspace")
from hermes_agents.ag_01_cacador import *

# Caçada completa
resultados = executar_cacada()
for p in resultados[:10]:
    print(f"[{p['score_final']}/100] {p['nome']} — R${p['preco_medio']} — Margem: {p['margem_estimada']}%")

# Tendências
tendencias = coletar_tendencias()
for t in tendencias:
    print(f"  {t['termo']}: +{t['crescimento']}% — {t['volume']} buscas")
```
'''

# ===========================================================================
# ag_02_lucratividade/__init__.py
# ===========================================================================
FILES["ag_02_lucratividade/__init__.py"] = '''"""
AG-02: Analista de Lucratividade
Calcula o lucro REAL de cada SKU descontando:
custo de matéria-prima, mão de obra, taxa do marketplace, frete, impostos.
Identifica produtos que vendem muito mas dão pouco lucro.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import get_db, run_async, log, hoje, pct, FactoryConfig

AGENT = "AG-02 | Analista de Lucratividade"

# ===========================================================================
# Cálculo de lucro real
# ===========================================================================

def calcular_lucro_real(preco_venda: float, custo_unitario: float,
                        taxa_marketplace_pct: float, frete: float,
                        imposto_pct: float = 8.0) -> dict:
    """
    Calcula lucro líquido real de uma venda.
    """
    taxa_valor = preco_venda * (taxa_marketplace_pct / 100)
    imposto_valor = preco_venda * (imposto_pct / 100)
    receita_liquida = preco_venda - taxa_valor - frete - imposto_valor
    lucro_liquido = receita_liquida - custo_unitario
    margem_pct = round((lucro_liquido / preco_venda) * 100, 1) if preco_venda else 0

    return {
        "preco_venda": round(preco_venda, 2),
        "custo_unitario": round(custo_unitario, 2),
        "taxa_marketplace": round(taxa_valor, 2),
        "frete": round(frete, 2),
        "impostos": round(imposto_valor, 2),
        "receita_liquida": round(receita_liquida, 2),
        "lucro_liquido": round(lucro_liquido, 2),
        "margem_pct": margem_pct,
    }

# ===========================================================================
# Análise por SKU
# ===========================================================================

def analisar_sku(sku: str, dias: int = 30) -> dict:
    """Analisa lucratividade de um SKU específico nos últimos N dias."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT
                COUNT(*) AS total_vendas,
                SUM(quantidade) AS qtd_total,
                SUM(receita_bruta) AS receita_total,
                AVG(taxa_marketplace_pct) AS taxa_media,
                SUM(taxa_marketplace_valor) AS taxas_total,
                SUM(frete) AS frete_total,
                SUM(impostos) AS impostos_total
            FROM vendas
            WHERE sku = $1 AND data >= CURRENT_DATE - make_interval(days => $2)
        """, sku, dias)

        if not rows or not rows[0]["total_vendas"]:
            return {"sku": sku, "erro": "Sem dados de venda no período"}

        r = rows[0]
        # Busca custo mais recente
        custo = await db.fetchrow("""
            SELECT custo_total FROM historico_custos
            WHERE sku = $1 ORDER BY data DESC LIMIT 1
        """, sku)
        custo_unitario = float(custo["custo_total"]) if custo else 0

        receita = float(r["receita_total"])
        taxas = float(r["taxas_total"] or 0)
        frete = float(r["frete_total"] or 0)
        impostos = float(r["impostos_total"] or 0)
        qtd = int(r["qtd_total"])

        custo_total = custo_unitario * qtd
        lucro = receita - taxas - frete - impostos - custo_total
        margem = pct(lucro, receita)

        cfg = FactoryConfig.load()
        status = "saudavel"
        if margem < cfg.margem_minima_pct:
            status = "deficit"
        elif margem < cfg.margem_minima_pct * 1.5:
            status = "alerta"

        return {
            "sku": sku,
            "periodo_dias": dias,
            "total_vendas": int(r["total_vendas"]),
            "qtd_vendida": qtd,
            "receita_total": round(receita, 2),
            "taxas_total": round(taxas, 2),
            "frete_total": round(frete, 2),
            "impostos_total": round(impostos, 2),
            "custo_total": round(custo_total, 2),
            "lucro_liquido": round(lucro, 2),
            "margem_pct": round(margem, 1),
            "custo_unitario": round(custo_unitario, 4),
            "status": status,
        }
    return run_async(_go())

# ===========================================================================
# Rankings
# ===========================================================================

def top_lucrativos(n: int = 10) -> list:
    """Top N SKUs mais lucrativos."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT sku, SUM(receita_bruta) AS receita,
                   SUM(receita_bruta - taxa_marketplace_valor - frete - impostos) AS receita_liquida
            FROM vendas
            WHERE data >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY sku
            ORDER BY receita_liquida DESC
            LIMIT $1
        """, n)
        return [dict(r) for r in rows]
    return run_async(_go())

def bottom_deficitarios(n: int = 10) -> list:
    """SKUs com pior margem ou deficitários."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT sku,
                   SUM(receita_bruta) AS receita_total,
                   SUM(taxa_marketplace_valor) + SUM(frete) + SUM(impostos) AS custos_variaveis,
                   COUNT(*) AS total_vendas
            FROM vendas
            WHERE data >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY sku
            HAVING SUM(receita_bruta) < SUM(taxa_marketplace_valor) + SUM(frete) + SUM(impostos)
            ORDER BY receita_total DESC
            LIMIT $1
        """, n)
        return [dict(r) for r in rows]
    return run_async(_go())

# ===========================================================================
# Relatório diário
# ===========================================================================

def relatorio_diario() -> dict:
    """Gera relatório de lucratividade do dia."""
    log(AGENT, "Gerando relatório diário...")
    async def _go():
        db = await get_db()
        today = await db.fetchrow("""
            SELECT
                COUNT(DISTINCT sku) AS skus_vendidos,
                SUM(quantidade) AS qtd_total,
                SUM(receita_bruta) AS receita_total,
                SUM(taxa_marketplace_valor) AS taxas,
                SUM(frete) AS fretes,
                SUM(impostos) AS impostos
            FROM vendas
            WHERE data = CURRENT_DATE
        """)
        return {
            "data": hoje(),
            "skus_vendidos": int(today["skus_vendidos"] or 0),
            "qtd_total": int(today["qtd_total"] or 0),
            "receita_total": round(float(today["receita_total"] or 0), 2),
            "taxas_total": round(float(today["taxas"] or 0), 2),
            "frete_total": round(float(today["fretes"] or 0), 2),
            "impostos_total": round(float(today["impostos"] or 0), 2),
        }
    return run_async(_go())

# ===========================================================================
# Alertas
# ===========================================================================

def verificar_alertas() -> list:
    """Verifica SKUs com margem abaixo do mínimo e gera alertas."""
    cfg = FactoryConfig.load()
    log(AGENT, f"Verificando alertas (margem mínima: {cfg.margem_minima_pct}%)...")

    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT sku, margem_pct, lucro_liquido
            FROM margens_diarias
            WHERE data = CURRENT_DATE AND margem_pct < $1
            ORDER BY margem_pct ASC
        """, cfg.margem_minima_pct)

        alertas = []
        for r in rows:
            msg = f"SKU {r['sku']} com margem de {r['margem_pct']}% — abaixo do mínimo de {cfg.margem_minima_pct}%"
            alertas.append({"sku": r["sku"], "margem": r["margem_pct"], "lucro": float(r["lucro_liquido"]), "mensagem": msg})

            await db.execute("""
                INSERT INTO alertas (tipo, sku, mensagem, gravidade)
                VALUES ('margem', $1, $2, 'alerta')
            """, r["sku"], msg)

        return alertas
    return run_async(_go())

# ===========================================================================
# Auto-teste
# ===========================================================================

if __name__ == "__main__":
    log(AGENT, "=== Auto-teste ===")

    # Teste de cálculo isolado
    resultado = calcular_lucro_real(
        preco_venda=49.90,
        custo_unitario=8.50,
        taxa_marketplace_pct=18.0,
        frete=5.00,
    )
    print("Cálculo isolado:", resultado)

    print("\\nRelatório:", relatorio_diario())
'''

# ===========================================================================
# ag_02_lucratividade/SKILL.md
# ===========================================================================
FILES["ag_02_lucratividade/SKILL.md"] = r'''---
name: factory-profitability-analyst
description: >
  AG-02: Analista de Lucratividade. Calcula lucro REAL por SKU descontando
  matéria-prima, mão de obra, taxas, frete e impostos. Identifica produtos
  que vendem muito mas geram pouco lucro.
category: factory
bundled: true
---

# AG-02 — Analista de Lucratividade

Responde: "Qual produto REALMENTE dá lucro?"

## Ferramentas

| Função | Descrição |
|---|---|
| `calcular_lucro_real(preco, custo, taxa, frete)` | Cálculo isolado de lucro líquido |
| `analisar_sku(sku, dias)` | Análise completa de lucratividade de um SKU |
| `top_lucrativos(n)` | Ranking dos SKUs mais lucrativos |
| `bottom_deficitarios(n)` | SKUs com margem negativa |
| `relatorio_diario()` | Resumo de vendas e receita do dia |
| `verificar_alertas()` | SKUs abaixo da margem mínima |

## Como usar

```python
sys.path.insert(0, "/workspace")
from hermes_agents.ag_02_lucratividade import *

# Análise de um SKU
analise = analisar_sku("ORG001")
print(f"SKU: {analise['sku']} | Margem: {analise['margem_pct']}% | Status: {analise['status']}")

# Top 5 lucrativos
for p in top_lucrativos(5):
    print(f"  {p['sku']}: R${p['receita_liquida']:.2f}")

# Deficitários
for p in bottom_deficitarios(5):
    print(f"  ⚠️ {p['sku']}: R${p['receita_total']:.2f} — eliminando custo variável já fica no vermelho")
```
'''

# ===========================================================================
# ag_03_marketplaces/__init__.py
# ===========================================================================
FILES["ag_03_marketplaces/__init__.py"] = '''"""
AG-03: Gerente de Marketplaces
Monitora posição de anúncios, preços dos concorrentes, avaliações,
e gera sugestões de otimização (títulos, SEO, preços, kits).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import get_db, run_async, log, hoje

AGENT = "AG-03 | Gerente de Marketplaces"

# ===========================================================================
# Monitoramento de posição
# ===========================================================================

def verificar_posicoes() -> list:
    """Verifica posição de todos os anúncios ativos nos marketplaces."""
    log(AGENT, "Verificando posições dos anúncios...")
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT sku, marketplace, titulo, posicao_busca, avaliacao_media, total_avaliacoes
            FROM anuncios
            WHERE status = 'ativo'
            ORDER BY marketplace, posicao_busca
        """)
        return [dict(r) for r in rows]
    return run_async(_go())

def anuncios_caindo() -> list:
    """Anúncios que caíram de posição (fora do top 10)."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT * FROM anuncios
            WHERE status = 'ativo' AND posicao_busca > 10
            ORDER BY posicao_busca ASC
        """)
        return [dict(r) for r in rows]
    return run_async(_go())

# ===========================================================================
# Preços dos concorrentes
# ===========================================================================

def comparar_precos_concorrentes(sku: str = "") -> list:
    """Compara preço nosso vs concorrência para um SKU ou todos."""
    log(AGENT, f"Comparando preços {'para ' + sku if sku else 'todos SKUs'}...")
    async def _go():
        db = await get_db()
        query = """
            SELECT a.sku, a.marketplace, a.preco AS nosso_preco,
                   c.nome AS concorrente, c.preco AS preco_concorrente,
                   ROUND((a.preco - c.preco) / c.preco * 100, 1) AS diff_pct
            FROM anuncios a
            JOIN concorrentes c ON c.marketplace = a.marketplace
                AND c.produto_similar ILIKE '%' || a.sku || '%'
            WHERE a.status = 'ativo' AND c.data_coleta = CURRENT_DATE
        """
        if sku:
            query += " AND a.sku = $1"
            rows = await db.fetch(query, sku)
        else:
            rows = await db.fetch(query)
        return [dict(r) for r in rows]
    return run_async(_go())

# ===========================================================================
# Sugestões de otimização
# ===========================================================================

def gerar_sugestao_titulo(sku: str, palavras_chave: list, marketplace: str) -> dict:
    """Gera sugestão de título otimizado para SEO."""
    kws = " ".join(palavras_chave[:5])
    titulo_atual = f"Produto {sku}"

    async def _go():
        db = await get_db()
        a = await db.fetchrow("SELECT titulo FROM anuncios WHERE sku = $1 AND marketplace = $2", sku, marketplace)
        if a:
            titulo_atual = a["titulo"]

    run_async(_go())

    # Heurística simples de otimização
    novo_titulo = f"{sku} | {kws} — Entrega Rápida | Frete Grátis"
    return {
        "sku": sku,
        "marketplace": marketplace,
        "tipo": "titulo",
        "titulo_atual": titulo_atual,
        "sugestao": novo_titulo,
        "palavras_chave": palavras_chave,
        "impacto_estimado": "medio",
    }

def sugerir_kit(sku_a: str, sku_b: str, marketplace: str) -> dict:
    """Sugere criação de kit combinando dois produtos complementares."""
    async def _go():
        db = await get_db()
        a = await db.fetchrow("SELECT titulo, preco FROM anuncios WHERE sku = $1 AND marketplace = $2", sku_a, marketplace)
        b = await db.fetchrow("SELECT titulo, preco FROM anuncios WHERE sku = $1 AND marketplace = $2", sku_b, marketplace)
        if not a or not b:
            return {"erro": "SKU não encontrado"}
        preco_kit = round((float(a["preco"]) + float(b["preco"])) * 0.85, 2)
        return {
            "tipo": "kit",
            "sku_a": sku_a,
            "sku_b": sku_b,
            "nome_kit": f"Combo {a['titulo']} + {b['titulo']}",
            "preco_individual": round(float(a["preco"]) + float(b["preco"]), 2),
            "preco_kit": preco_kit,
            "desconto_pct": 15,
            "impacto_estimado": "alto",
        }
    return run_async(_go())

def sugerir_ajuste_preco(sku: str, marketplace: str) -> dict:
    """Sugere ajuste de preço baseado na concorrência."""
    precos = comparar_precos_concorrentes(sku)
    if not precos:
        return {"sku": sku, "mensagem": "Sem dados de concorrência"}

    nosso = precos[0]["nosso_preco"]
    concorrencia = [p["preco_concorrente"] for p in precos]
    media_concorrencia = sum(concorrencia) / len(concorrencia)
    diff_pct = round((nosso - media_concorrencia) / media_concorrencia * 100, 1)

    acao = "manter"
    novo_preco = nosso
    if diff_pct > 15:
        acao = "reduzir"
        novo_preco = round(media_concorrencia * 0.95, 2)
    elif diff_pct < -10:
        acao = "aumentar"
        novo_preco = round(media_concorrencia * 1.05, 2)

    return {
        "sku": sku,
        "marketplace": marketplace,
        "tipo": "preco",
        "nosso_preco": nosso,
        "media_concorrencia": round(media_concorrencia, 2),
        "diff_pct": diff_pct,
        "acao": acao,
        "novo_preco_sugerido": novo_preco,
        "impacto_estimado": "alto" if acao != "manter" else "baixo",
    }

# ===========================================================================
# Geração de relatório consolidado
# ===========================================================================

def relatorio_consolidado() -> dict:
    """Relatório completo do estado dos marketplaces."""
    log(AGENT, "Gerando relatório consolidado de marketplaces...")
    async def _go():
        db = await get_db()
        total_anuncios = await db.fetchval("SELECT COUNT(*) FROM anuncios WHERE status = 'ativo'")
        top10 = await db.fetchval("SELECT COUNT(*) FROM anuncios WHERE status = 'ativo' AND posicao_busca <= 10")
        sugestoes_pendentes = await db.fetchval("SELECT COUNT(*) FROM sugestoes_otimizacao WHERE status = 'pendente'")
        alertas_abertos = await db.fetchval("SELECT COUNT(*) FROM alertas WHERE resolvido = false")

        return {
            "data": hoje(),
            "total_anuncios_ativos": total_anuncios,
            "anuncios_top10": top10,
            "pct_top10": round(top10 / total_anuncios * 100, 1) if total_anuncios else 0,
            "sugestoes_pendentes": sugestoes_pendentes,
            "alertas_abertos": alertas_abertos,
        }
    return run_async(_go())

# ===========================================================================
# Execução programada (a cada 4h)
# ===========================================================================

def executar_monitoramento() -> list:
    """Roda todas as verificações e gera sugestões e alertas."""
    log(AGENT, "Executando ciclo de monitoramento...")
    resultados = []

    # 1. Anúncios caindo
    caidos = anuncios_caindo()
    for a in caidos:
        resultados.append(f"⚠️ {a['sku']} caiu para posição {a['posicao_busca']} no {a['marketplace']}")

    # 2. Comparação de preços
    for a in verificar_posicoes()[:5]:
        sugestao = sugerir_ajuste_preco(a["sku"], a["marketplace"])
        if sugestao.get("acao") != "manter":
            resultados.append(f"💰 {a['sku']}: {sugestao['acao']} preço para R${sugestao['novo_preco_sugerido']}")

    # 3. Salva alertas
    async def _salvar():
        db = await get_db()
        for r in resultados:
            await db.execute("INSERT INTO alertas (tipo, sku, mensagem, gravidade) VALUES ('posicao', 'geral', $1, 'info')", r)
    run_async(_salvar())

    log(AGENT, f"Monitoramento concluído: {len(resultados)} ocorrências")
    return resultados

# ===========================================================================
# Auto-teste
# ===========================================================================

if __name__ == "__main__":
    log(AGENT, "=== Auto-teste ===")
    print("Relatório:", relatorio_consolidado())
    print("\\nSugestão de preço:", sugerir_ajuste_preco("ORG001", "shopee"))
    print("\\nMonitoramento:", executar_monitoramento())
'''

# ===========================================================================
# ag_03_marketplaces/SKILL.md
# ===========================================================================
FILES["ag_03_marketplaces/SKILL.md"] = r'''---
name: factory-marketplace-manager
description: >
  AG-03: Gerente de Marketplaces. Monitora posição de anúncios, preços dos
  concorrentes, avaliações e gera sugestões de SEO, preço, kits e promoções.
category: factory
bundled: true
---

# AG-03 — Gerente de Marketplaces

Aumenta vendas nos marketplaces sem criar novos produtos.

## Ferramentas

| Função | Descrição |
|---|---|
| `verificar_posicoes()` | Posição de todos os anúncios ativos |
| `anuncios_caindo()` | Anúncios fora do top 10 |
| `comparar_precos_concorrentes(sku)` | Preço nosso vs concorrência |
| `gerar_sugestao_titulo(sku, kw, mp)` | Sugestão de título otimizado |
| `sugerir_kit(sku_a, sku_b, mp)` | Combo de produtos complementares |
| `sugerir_ajuste_preco(sku, mp)` | Ajuste baseado na concorrência |
| `relatorio_consolidado()` | Estado geral dos marketplaces |
| `executar_monitoramento()` | Ciclo completo com alertas |

## Como usar

```python
sys.path.insert(0, "/workspace")
from hermes_agents.ag_03_marketplaces import *

# Status geral
print(relatorio_consolidado())

# Preço vs concorrência
for p in comparar_precos_concorrentes("ORG001"):
    print(f"  Nosso: R${p['nosso_preco']} | {p['concorrente']}: R${p['preco_concorrente']} | Diff: {p['diff_pct']}%")

# Ciclo de monitoramento
alertas = executar_monitoramento()
for a in alertas:
    print(f"  {a}")
```
'''

# ===========================================================================
# ag_09_memoria/__init__.py
# ===========================================================================
FILES["ag_09_memoria/__init__.py"] = '''"""
AG-09: Memória Corporativa
Organiza e consulta todo o conhecimento da fábrica:
moldes, fichas técnicas, fornecedores, matérias-primas, histórico de custos,
problemas resolvidos, documentação técnica.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import get_db, run_async, log

AGENT = "AG-09 | Memória Corporativa"

# ===========================================================================
# Moldes
# ===========================================================================

def listar_moldes(status: str = "todos") -> list:
    """Lista todos os moldes cadastrados."""
    async def _go():
        db = await get_db()
        if status == "todos":
            rows = await db.fetch("SELECT * FROM moldes ORDER BY codigo")
        else:
            rows = await db.fetch("SELECT * FROM moldes WHERE status = $1 ORDER BY codigo", status)
        return [dict(r) for r in rows]
    return run_async(_go())

def buscar_molde(codigo: str) -> dict:
    """Busca um molde específico pelo código."""
    async def _go():
        db = await get_db()
        r = await db.fetchrow("SELECT * FROM moldes WHERE codigo = $1", codigo)
        return dict(r) if r else {}
    return run_async(_go())

def produtos_do_molde(codigo_molde: str) -> list:
    """Lista SKUs que usam determinado molde."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT ft.* FROM fichas_tecnicas ft
            JOIN moldes m ON m.id = ft.molde_id
            WHERE m.codigo = $1
        """, codigo_molde)
        return [dict(r) for r in rows]
    return run_async(_go())

# ===========================================================================
# Fichas Técnicas
# ===========================================================================

def buscar_ficha(sku: str) -> dict:
    """Busca ficha técnica completa de um SKU."""
    async def _go():
        db = await get_db()
        r = await db.fetchrow("""
            SELECT ft.*, m.codigo AS molde_codigo, m.material AS molde_material
            FROM fichas_tecnicas ft
            LEFT JOIN moldes m ON m.id = ft.molde_id
            WHERE ft.sku = $1
        """, sku)
        return dict(r) if r else {}
    return run_async(_go())

def listar_fichas(material: str = "") -> list:
    """Lista todas as fichas técnicas, opcionalmente por material."""
    async def _go():
        db = await get_db()
        if material:
            rows = await db.fetch("SELECT * FROM fichas_tecnicas WHERE material_principal ILIKE $1", f"%{material}%")
        else:
            rows = await db.fetch("SELECT * FROM fichas_tecnicas ORDER BY sku")
        return [dict(r) for r in rows]
    return run_async(_go())

# ===========================================================================
# Fornecedores
# ===========================================================================

def buscar_fornecedor(categoria: str = "") -> list:
    """Busca fornecedores, opcionalmente por categoria."""
    async def _go():
        db = await get_db()
        if categoria:
            rows = await db.fetch("SELECT * FROM fornecedores WHERE categoria = $1 AND status = 'ativo'", categoria)
        else:
            rows = await db.fetch("SELECT * FROM fornecedores WHERE status = 'ativo' ORDER BY nome")
        return [dict(r) for r in rows]
    return run_async(_go())

def fornecedor_mais_barato(materia_prima: str) -> dict:
    """Encontra o fornecedor mais barato para uma matéria-prima."""
    async def _go():
        db = await get_db()
        r = await db.fetchrow("""
            SELECT mp.nome, mp.preco_unitario, f.nome AS fornecedor, f.contato_email
            FROM materias_primas mp
            JOIN fornecedores f ON f.id = mp.fornecedor_id
            WHERE mp.nome ILIKE $1 AND f.status = 'ativo'
            ORDER BY mp.preco_unitario ASC
            LIMIT 1
        """, f"%{materia_prima}%")
        return dict(r) if r else {}
    return run_async(_go())

# ===========================================================================
# Matérias-primas
# ===========================================================================

def listar_materias_primas() -> list:
    """Lista matérias-primas com estoque e fornecedor."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT mp.*, f.nome AS fornecedor_nome
            FROM materias_primas mp
            LEFT JOIN fornecedores f ON f.id = mp.fornecedor_id
            ORDER BY mp.nome
        """)
        return [dict(r) for r in rows]
    return run_async(_go())

def alertas_estoque_baixo() -> list:
    """Retorna matérias-primas com estoque abaixo do mínimo."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT nome, estoque_atual_kg, estoque_minimo_kg,
                   (estoque_minimo_kg - estoque_atual_kg) AS deficit
            FROM materias_primas
            WHERE estoque_atual_kg <= estoque_minimo_kg
        """)
        return [dict(r) for r in rows]
    return run_async(_go())

# ===========================================================================
# Histórico de Custos
# ===========================================================================

def historico_custo_sku(sku: str, meses: int = 12) -> list:
    """Histórico de custo de produção de um SKU nos últimos meses."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT * FROM historico_custos
            WHERE sku = $1 AND data >= CURRENT_DATE - make_interval(months => $2)
            ORDER BY data
        """, sku, meses)
        return [dict(r) for r in rows]
    return run_async(_go())

# ===========================================================================
# Problemas Resolvidos (FAQ)
# ===========================================================================

def buscar_solucoes(palavra_chave: str) -> list:
    """Busca problemas já resolvidos por palavra-chave ou tag."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT * FROM problemas_resolvidos
            WHERE titulo ILIKE $1 OR descricao ILIKE $1
               OR EXISTS (SELECT 1 FROM unnest(tags) t WHERE t ILIKE $1)
            ORDER BY data_resolucao DESC
            LIMIT 20
        """, f"%{palavra_chave}%")
        return [dict(r) for r in rows]
    return run_async(_go())

# ===========================================================================
# Consulta inteligente — "Já fabricamos algo parecido?"
# ===========================================================================

def buscar_similar(descricao: str) -> list:
    """Busca produtos similares por descrição."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT ft.sku, ft.descricao, m.codigo AS molde,
                   hc.custo_total AS ultimo_custo
            FROM fichas_tecnicas ft
            LEFT JOIN moldes m ON m.id = ft.molde_id
            LEFT JOIN LATERAL (
                SELECT custo_total FROM historico_custos
                WHERE sku = ft.sku ORDER BY data DESC LIMIT 1
            ) hc ON true
            WHERE ft.descricao ILIKE $1 OR ft.material_principal ILIKE $1
        """, f"%{descricao}%")
        return [dict(r) for r in rows]
    return run_async(_go())

# ===========================================================================
# Stats
# ===========================================================================

def stats() -> dict:
    """Estatísticas da base de conhecimento."""
    async def _go():
        db = await get_db()
        total_moldes = await db.fetchval("SELECT COUNT(*) FROM moldes")
        total_fichas = await db.fetchval("SELECT COUNT(*) FROM fichas_tecnicas")
        total_fornecedores = await db.fetchval("SELECT COUNT(*) FROM fornecedores WHERE status = 'ativo'")
        total_faq = await db.fetchval("SELECT COUNT(*) FROM problemas_resolvidos")
        return {
            "moldes_ativos": total_moldes,
            "fichas_tecnicas": total_fichas,
            "fornecedores_ativos": total_fornecedores,
            "problemas_resolvidos": total_faq,
        }
    return run_async(_go())

if __name__ == "__main__":
    log(AGENT, "Auto-teste iniciado")
    for molde in listar_moldes("ativo"):
        print(f"  Molde: {molde['codigo']} → {molde['produto']} (status: {molde['status']})")
    log(AGENT, f"Stats: {stats()}")
'''

# ===========================================================================
# ag_09_memoria/SKILL.md
# ===========================================================================
FILES["ag_09_memoria/SKILL.md"] = r'''---
name: factory-corporate-memory
description: >
  AG-09: Memória Corporativa da fábrica. Consulta moldes, fichas técnicas,
  fornecedores, matérias-primas, histórico de custos e problemas resolvidos.
  Use para perguntas como "Já fabricamos algo parecido?",
  "Qual molde usamos para o produto X?", "Quem é o fornecedor mais barato?"
category: factory
bundled: true
---

# AG-09 — Memória Corporativa

Organiza e consulta todo o conhecimento técnico da fábrica.

## Ferramentas disponíveis

| Função | Descrição |
|---|---|
| `listar_moldes(status)` | Lista moldes (ativo/inativo/todos) |
| `buscar_molde(codigo)` | Busca molde por código |
| `produtos_do_molde(codigo)` | SKUs que usam um molde |
| `buscar_ficha(sku)` | Ficha técnica completa do SKU |
| `listar_fichas(material)` | Todas as fichas, filtro por material |
| `buscar_fornecedor(categoria)` | Fornecedores por categoria |
| `fornecedor_mais_barato(materia_prima)` | Melhor preço de matéria-prima |
| `listar_materias_primas()` | Estoque de matérias-primas |
| `alertas_estoque_baixo()` | Matérias-primas abaixo do mínimo |
| `historico_custo_sku(sku, meses)` | Evolução do custo de produção |
| `buscar_solucoes(palavra_chave)` | FAQ de problemas resolvidos |
| `buscar_similar(descricao)` | Produtos similares por descrição |
| `stats()` | Estatísticas da base |

## Como usar

```python
# No Hermes execute_code:
import sys
sys.path.insert(0, "/workspace")
from hermes_agents.ag_09_memoria import *

# Buscar molde
molde = buscar_molde("M-001")
print(molde)

# Buscar similar — "Já fabricamos algo parecido com organizador de mesa?"
similares = buscar_similar("organizador mesa")
for s in similares:
    print(f"  {s['sku']}: {s['descricao']} (custo: R${s.get('ultimo_custo', 'N/A')})")

# Fornecedor mais barato
barato = fornecedor_mais_barato("polipropileno")
print(f"Fornecedor: {barato['fornecedor']} — R${barato['preco_unitario']}/kg")
```
'''

# ===========================================================================
# Main deploy logic
# ===========================================================================

def deploy():
    print(f"Deploying Hermes Agent Swarm to {TARGET}...")
    print(f"Target exists: {os.path.exists(TARGET)}")

    for relpath, content in sorted(FILES.items()):
        full = os.path.join(TARGET, relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  wrote {relpath}")

    print(f"\nDeploy complete: {len(FILES)} files written to {TARGET}")

if __name__ == "__main__":
    deploy()
