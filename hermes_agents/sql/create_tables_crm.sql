-- ===========================================================================
-- Hermes Agent Swarm — Database Schema
-- CRM: Leads, Contatos, Empresas, Negociacoes, Atividades, Propostas, Contratos
--
-- ponytail: formaliza aqui o schema que core/crm.py::_ensure_tables() ja cria
-- em runtime via CREATE TABLE IF NOT EXISTS (idempotente, mantido como rede
-- de seguranca) — antes so' existia no codigo Python, fora do padrao de
-- migration versionada usado pelas fases 2/3 deste diretorio.
-- ===========================================================================

CREATE TABLE IF NOT EXISTS crm_empresas (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(200) NOT NULL,
    cnpj VARCHAR(20),
    segmento VARCHAR(100),
    porte VARCHAR(20),
    telefone VARCHAR(30),
    email VARCHAR(100),
    website VARCHAR(200),
    endereco TEXT,
    observacoes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS crm_leads (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(200) NOT NULL,
    email VARCHAR(100),
    telefone VARCHAR(30),
    empresa_id INT REFERENCES crm_empresas(id),
    origem VARCHAR(50) DEFAULT 'site',
    status VARCHAR(30) DEFAULT 'novo',
    funil_etapa VARCHAR(50) DEFAULT 'captacao',
    valor_potencial DECIMAL(12,2) DEFAULT 0,
    observacoes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS crm_contatos (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(200) NOT NULL,
    email VARCHAR(100),
    telefone VARCHAR(30),
    cargo VARCHAR(100),
    empresa_id INT REFERENCES crm_empresas(id),
    lead_id INT REFERENCES crm_leads(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS crm_negociacoes (
    id SERIAL PRIMARY KEY,
    titulo VARCHAR(200) NOT NULL,
    lead_id INT REFERENCES crm_leads(id),
    contato_id INT REFERENCES crm_contatos(id),
    empresa_id INT REFERENCES crm_empresas(id),
    valor DECIMAL(12,2) DEFAULT 0,
    etapa_funil VARCHAR(50) DEFAULT 'prospeccao',
    probabilidade INT DEFAULT 10,
    data_fechamento DATE,
    status VARCHAR(30) DEFAULT 'aberta',
    observacoes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS crm_atividades (
    id SERIAL PRIMARY KEY,
    tipo VARCHAR(30) NOT NULL,
    descricao TEXT,
    data_agendada TIMESTAMP,
    data_realizada TIMESTAMP,
    lead_id INT REFERENCES crm_leads(id),
    negociacao_id INT REFERENCES crm_negociacoes(id),
    contato_id INT REFERENCES crm_contatos(id),
    status VARCHAR(20) DEFAULT 'pendente',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS crm_propostas (
    id SERIAL PRIMARY KEY,
    negociacao_id INT REFERENCES crm_negociacoes(id),
    numero VARCHAR(30),
    valor DECIMAL(12,2) DEFAULT 0,
    status VARCHAR(30) DEFAULT 'rascunho',
    data_envio DATE,
    data_validade DATE,
    conteudo TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS crm_contratos (
    id SERIAL PRIMARY KEY,
    negociacao_id INT REFERENCES crm_negociacoes(id),
    proposta_id INT REFERENCES crm_propostas(id),
    numero VARCHAR(30),
    valor DECIMAL(12,2) DEFAULT 0,
    status VARCHAR(30) DEFAULT 'pendente',
    data_assinatura DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_crm_leads_empresa_id ON crm_leads(empresa_id);
CREATE INDEX IF NOT EXISTS idx_crm_leads_status ON crm_leads(status);
CREATE INDEX IF NOT EXISTS idx_crm_leads_email ON crm_leads(email);
CREATE INDEX IF NOT EXISTS idx_crm_contatos_empresa_id ON crm_contatos(empresa_id);
CREATE INDEX IF NOT EXISTS idx_crm_contatos_lead_id ON crm_contatos(lead_id);
CREATE INDEX IF NOT EXISTS idx_crm_contatos_email ON crm_contatos(email);
CREATE INDEX IF NOT EXISTS idx_crm_negociacoes_lead_id ON crm_negociacoes(lead_id);
CREATE INDEX IF NOT EXISTS idx_crm_negociacoes_empresa_id ON crm_negociacoes(empresa_id);
CREATE INDEX IF NOT EXISTS idx_crm_negociacoes_etapa_funil ON crm_negociacoes(etapa_funil);
CREATE INDEX IF NOT EXISTS idx_crm_negociacoes_status ON crm_negociacoes(status);
CREATE INDEX IF NOT EXISTS idx_crm_atividades_lead_id ON crm_atividades(lead_id);
CREATE INDEX IF NOT EXISTS idx_crm_atividades_negociacao_id ON crm_atividades(negociacao_id);
CREATE INDEX IF NOT EXISTS idx_crm_propostas_negociacao_id ON crm_propostas(negociacao_id);
CREATE INDEX IF NOT EXISTS idx_crm_contratos_negociacao_id ON crm_contratos(negociacao_id);
