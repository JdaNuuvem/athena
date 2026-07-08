-- Fase 3: Cadeia de Manufatura
-- Extensões para tracking completo de moldes, produção, qualidade e manutenção

-- ===========================================================================
-- Extensões na tabela moldes (já existente na Fase 1)
-- ===========================================================================

ALTER TABLE moldes ADD COLUMN IF NOT EXISTS status_atual VARCHAR(20) DEFAULT 'projeto' CHECK (status_atual IN ('projeto', 'designed', 'em_fabricacao', 'fabricado', 'instalado', 'manutencao', 'descartado'));
ALTER TABLE moldes ADD COLUMN IF NOT EXISTS data_design DATE;
ALTER TABLE moldes ADD COLUMN IF NOT EXISTS data_fabricacao_inicio DATE;
ALTER TABLE moldes ADD COLUMN IF NOT EXISTS data_fabricacao_fim DATE;
ALTER TABLE moldes ADD COLUMN IF NOT EXISTS data_instalacao DATE;
ALTER TABLE moldes ADD COLUMN IF NOT EXISTS data_remocao DATE;
ALTER TABLE moldes ADD COLUMN IF NOT EXISTS maquina_id VARCHAR(50);
ALTER TABLE moldes ADD COLUMN IF NOT EXISTS ciclos_acumulados INTEGER DEFAULT 0;
ALTER TABLE moldes ADD COLUMN IF NOT EXISTS ultima_manutencao DATE;
ALTER TABLE moldes ADD COLUMN IF NOT EXISTS proxima_manutencao INTEGER; -- ciclos

-- ===========================================================================
-- Eventos de lifecycle de moldes
-- ===========================================================================

CREATE TABLE IF NOT EXISTS moldes_eventos (
  id SERIAL PRIMARY KEY,
  molde_id INTEGER REFERENCES moldes(id) ON DELETE CASCADE,
  tipo VARCHAR(30) NOT NULL CHECK (tipo IN ('designed', 'fabrication_started', 'fabrication_completed', 'installed', 'removed', 'maintenance', 'inspection', 'repaired', 'retired')),
  descricao TEXT,
  dados JSONB,
  usuario VARCHAR(100),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_moldes_eventos_molde_id ON moldes_eventos(molde_id);
CREATE INDEX IF NOT EXISTS idx_moldes_eventos_tipo ON moldes_eventos(tipo);
CREATE INDEX IF NOT EXISTS idx_moldes_eventos_created_at ON moldes_eventos(created_at DESC);

-- ===========================================================================
-- Jobs de usinagem CNC
-- ===========================================================================

CREATE TABLE IF NOT EXISTS cnc_jobs (
  id SERIAL PRIMARY KEY,
  job_id VARCHAR(50) UNIQUE NOT NULL,
  molde_id INTEGER REFERENCES moldes(id),
  maquina_id VARCHAR(50) NOT NULL,
  operador VARCHAR(100),
  status VARCHAR(20) DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'running', 'completed', 'failed', 'cancelled')),
  data_inicio DATE,
  data_fim DATE,
  horas_planejadas DECIMAL(5,2),
  horas_reais DECIMAL(5,2),
  material_usado_kg DECIMAL(10,2),
  material_tipo VARCHAR(50),
  observacoes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cnc_jobs_molde_id ON cnc_jobs(molde_id);
CREATE INDEX IF NOT EXISTS idx_cnc_jobs_maquina_id ON cnc_jobs(maquina_id);
CREATE INDEX IF NOT EXISTS idx_cnc_jobs_status ON cnc_jobs(status);

-- ===========================================================================
-- Lotes de produção
-- ===========================================================================

CREATE TABLE IF NOT EXISTS producao_lotes (
  id SERIAL PRIMARY KEY,
  lote_id VARCHAR(50) UNIQUE NOT NULL,
  pedido_producao_id INTEGER REFERENCES pedidos_producao(id),
  molde_id INTEGER REFERENCES moldes(id),
  maquina_id VARCHAR(50) NOT NULL,
  operador VARCHAR(100),
  sku VARCHAR(50) NOT NULL,
  status VARCHAR(20) DEFAULT 'programado' CHECK (status IN ('programado', 'em_producao', 'pausado', 'concluido', 'cancelado', 'em_qualidade')),
  data_inicio DATE,
  data_fim DATE,
  quantidade_planejada INTEGER,
  quantidade_produzida INTEGER DEFAULT 0,
  quantidade_defeituosa INTEGER DEFAULT 0,
  tempo_ciclo_segundos INTEGER,
  ciclos_realizados INTEGER DEFAULT 0,
  oee_calculado DECIMAL(5,2),
  material_usado_kg DECIMAL(10,2),
  observacoes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_producao_lotes_sku ON producao_lotes(sku);
CREATE INDEX IF NOT EXISTS idx_producao_lotes_molde_id ON producao_lotes(molde_id);
CREATE INDEX IF NOT EXISTS idx_producao_lotes_maquina_id ON producao_lotes(maquina_id);
CREATE INDEX IF NOT EXISTS idx_producao_lotes_status ON producao_lotes(status);
CREATE INDEX IF NOT EXISTS idx_producao_lotes_data_inicio ON producao_lotes(data_inicio);

-- ===========================================================================
-- Inspeção de qualidade
-- ===========================================================================

CREATE TABLE IF NOT EXISTS inspecao_qualidade (
  id SERIAL PRIMARY KEY,
  inspecao_id VARCHAR(50) UNIQUE NOT NULL,
  lote_id INTEGER REFERENCES producao_lotes(id),
  data_inspecao DATE DEFAULT CURRENT_DATE,
  inspetor VARCHAR(100),
  tipo_inspecao VARCHAR(30) NOT NULL CHECK (tipo_inspecao IN ('inicial', 'intermediaria', 'final', 'aleatoria')),
  quantidade_amostrada INTEGER,
  quantidade_aprovada INTEGER,
  quantidade_reprovada INTEGER,
  status_inspecao VARCHAR(20) CHECK (status_inspecao IN ('em_andamento', 'aprovado', 'reprovado', 'condicional')),
  resultado TEXT,
  acoes_tomadas TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_inspecao_qualidade_lote_id ON inspecao_qualidade(lote_id);
CREATE INDEX IF NOT EXISTS idx_inspecao_qualidade_data_inspecao ON inspecao_qualidade(data_inspecao DESC);
CREATE INDEX IF NOT EXISTS idx_inspecao_qualidade_status ON inspecao_qualidade(status_inspecao);

-- ===========================================================================
-- Catálogo de defeitos
-- ===========================================================================

CREATE TABLE IF NOT EXISTS defeitos (
  id SERIAL PRIMARY KEY,
  codigo VARCHAR(20) UNIQUE NOT NULL,
  nome VARCHAR(100) NOT NULL,
  categoria VARCHAR(50) CHECK (categoria IN ('dimensional', 'estetico', 'funcional', 'material', 'embalagem', 'outro')),
  gravidade VARCHAR(20) CHECK (gravidade IN ('baixa', 'media', 'alta', 'critica')),
  descricao TEXT,
  causa_raiz_sugerida TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_defeitos_categoria ON defeitos(categoria);
CREATE INDEX IF NOT EXISTS idx_defeitos_gravidade ON defeitos(gravidade);

-- ===========================================================================
-- Defeitos encontrados nas inspeções
-- ===========================================================================

CREATE TABLE IF NOT EXISTS inspecao_defeitos (
  id SERIAL PRIMARY KEY,
  inspecao_id INTEGER REFERENCES inspecao_qualidade(id),
  defeito_id INTEGER REFERENCES defeitos(id),
  quantidade INTEGER DEFAULT 1,
  gravidade VARCHAR(20),
  posicao_peca VARCHAR(100), -- Ex: "base", "tampa", "conjunto"
  observacoes TEXT,
  foto_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_inspecao_defeitos_inspecao_id ON inspecao_defeitos(inspecao_id);
CREATE INDEX IF NOT EXISTS idx_inspecao_defeitos_defeito_id ON inspecao_defeitos(defeito_id);

-- ===========================================================================
-- CAPA (Corrective and Preventive Actions)
-- ===========================================================================

CREATE TABLE IF NOT EXISTS capa_registros (
  id SERIAL PRIMARY KEY,
  numero VARCHAR(30) UNIQUE NOT NULL,
  tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('corretiva', 'preventiva', 'melhoria')),
  origem VARCHAR(50), -- defeito, cliente, auditoria, processo, interna
  origem_id INTEGER,
  descricao_problema TEXT NOT NULL,
  causa_raiz TEXT,
  acao_corretiva TEXT,
  acao_preventiva TEXT,
  responsavel VARCHAR(100),
  data_abertura DATE DEFAULT CURRENT_DATE,
  data_prevista_conclusao DATE,
  data_conclusao DATE,
  status VARCHAR(20) DEFAULT 'aberta' CHECK (status IN ('aberta', 'em_andamento', 'concluida', 'cancelada')),
  eficacia_verificada BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_capa_registros_status ON capa_registros(status);
CREATE INDEX IF NOT EXISTS idx_capa_registros_tipo ON capa_registros(tipo);
CREATE INDEX IF NOT EXISTS idx_capa_registros_origem ON capa_registros(origem);

-- ===========================================================================
-- Manutenções (máquinas e moldes)
-- ===========================================================================

CREATE TABLE IF NOT EXISTS manutencoes (
  id SERIAL PRIMARY KEY,
  numero VARCHAR(30) UNIQUE NOT NULL,
  equipamento_tipo VARCHAR(30) NOT NULL CHECK (equipamento_tipo IN ('maquina', 'molde')),
  equipamento_id VARCHAR(50) NOT NULL,
  tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('preventiva', 'corretiva', 'preditiva')),
  prioridade INTEGER DEFAULT 3 CHECK (prioridade BETWEEN 1 AND 5), -- 1=alta, 5=baixa
  descricao TEXT,
  data_agendada DATE NOT NULL,
  data_inicio DATE,
  data_fim DATE,
  duracao_horas DECIMAL(5,2),
  tecnico VARCHAR(100),
  pecas_substituidas JSONB,
  custo_pecas DECIMAL(10,2),
  custo_mao_obra DECIMAL(10,2),
  custo_total DECIMAL(10,2),
  observacoes TEXT,
  status VARCHAR(20) DEFAULT 'agendada' CHECK (status IN ('agendada', 'em_andamento', 'concluida', 'cancelada', 'adiada')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_manutencoes_equipamento ON manutencoes(equipamento_tipo, equipamento_id);
CREATE INDEX IF NOT EXISTS idx_manutencoes_status ON manutencoes(status);
CREATE INDEX IF NOT EXISTS idx_manutencoes_data_agendada ON manutencoes(data_agendada);
CREATE INDEX IF NOT EXISTS idx_manutencoes_prioridade ON manutencoes(prioridade);

-- ===========================================================================
-- Histórico de manutenções
-- ===========================================================================

CREATE TABLE IF NOT EXISTS manutencoes_historico (
  id SERIAL PRIMARY KEY,
  manutencao_id INTEGER REFERENCES manutencoes(id) ON DELETE CASCADE,
  data_registro TIMESTAMPTZ DEFAULT NOW(),
  descricao TEXT,
  usuario VARCHAR(100),
  acao VARCHAR(30) CHECK (acao IN ('criada', 'iniciada', 'pausada', 'retomada', 'concluida', 'cancelada'))
);

CREATE INDEX IF NOT EXISTS idx_manutencoes_historico_manutencao_id ON manutencoes_historico(manutencao_id);

-- ===========================================================================
-- Estoque de produtos acabados
-- ===========================================================================

CREATE TABLE IF NOT EXISTS estoque_produtos (
  id SERIAL PRIMARY KEY,
  sku VARCHAR(50) NOT NULL,
  lote_id INTEGER REFERENCES producao_lotes(id),
  quantidade INTEGER NOT NULL CHECK (quantidade >= 0),
  data_entrada DATE DEFAULT CURRENT_DATE,
  data_saida DATE,
  origem VARCHAR(30) CHECK (origem IN ('producao', 'compra', 'transferencia', 'ajuste')),
  loja_id INTEGER,
  observacoes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_estoque_produtos_sku ON estoque_produtos(sku);
CREATE INDEX IF NOT EXISTS idx_estoque_produtos_lote_id ON estoque_produtos(lote_id);
CREATE INDEX IF NOT EXISTS idx_estoque_produtos_loja_id ON estoque_produtos(loja_id);
CREATE INDEX IF NOT EXISTS idx_estoque_produtos_origem ON estoque_produtos(origem);

-- ===========================================================================
-- Transferências de estoque
-- ===========================================================================

CREATE TABLE IF NOT EXISTS transferencias_estoque (
  id SERIAL PRIMARY KEY,
  transferencia_id VARCHAR(50) UNIQUE NOT NULL,
  sku VARCHAR(50) NOT NULL,
  quantidade INTEGER NOT NULL,
  origem_loja_id INTEGER,
  destino_loja_id INTEGER,
  data_solicitacao DATE DEFAULT CURRENT_DATE,
  data_envio DATE,
  data_recebimento DATE,
  status VARCHAR(20) DEFAULT 'solicitada' CHECK (status IN ('solicitada', 'enviada', 'recebida', 'cancelada')),
  solicitante VARCHAR(100),
  transportadora VARCHAR(100),
  custo_frete DECIMAL(10,2),
  observacoes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transferencias_estoque_sku ON transferencias_estoque(sku);
CREATE INDEX IF NOT EXISTS idx_transferencias_estoque_status ON transferencias_estoque(status);
CREATE INDEX IF NOT EXISTS idx_transferencias_estoque_origem ON transferencias_estoque(origem_loja_id);
CREATE INDEX IF NOT EXISTS idx_transferencias_estoque_destino ON transferencias_estoque(destino_loja_id);

-- ===========================================================================
-- Dados de exemplo (opcional)
-- ===========================================================================

-- Defeitos comuns
INSERT INTO defeitos (codigo, nome, categoria, gravidade, descricao) VALUES
('DEF-001', 'Rebarba excessiva', 'estetico', 'media', 'Sobras de material nas bordas da peça'),
('DEF-002', 'Bolhas de ar', 'estetico', 'alta', 'Formação de bolhas na superfície da peça'),
('DEF-003', 'Dimensão fora de tolerância', 'dimensional', 'critica', 'Medidas fora da especificação'),
('DEF-004', 'Descoloração', 'estetico', 'baixa', 'Variação de cor não planejada'),
('DEF-005', 'Trinca', 'funcional', 'critica', 'Falha estrutural da peça'),
('DEF-006', 'Empenamento', 'dimensional', 'alta', 'Deformação da peça'),
('DEF-007', 'Acabamento ruim', 'estetico', 'media', 'Superfície irregular ou porosa'),
('DEF-008', 'Falha de fechamento', 'funcional', 'critica', 'Componentes não encaixam corretamente')
ON CONFLICT (codigo) DO NOTHING;

-- Manutenções de exemplo
INSERT INTO manutencoes (numero, equipamento_tipo, equipamento_id, tipo, prioridade, descricao, data_agendada) VALUES
('MAN-001', 'molde', 'M-001', 'preventiva', 2, 'Manutenção preventiva programada - verificar pinos ejetores', CURRENT_DATE + INTERVAL '7 days'),
('MAN-002', 'maquina', 'injetora_1', 'preventiva', 3, 'Troca de óleo hidráulico', CURRENT_DATE + INTERVAL '14 days')
ON CONFLICT (numero) DO NOTHING;