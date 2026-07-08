-- ===========================================================================
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
