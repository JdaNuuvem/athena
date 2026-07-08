-- AG-04: Planejador de Produção
CREATE TABLE IF NOT EXISTS pedidos_producao (
  id SERIAL PRIMARY KEY,
  sku VARCHAR(50) NOT NULL,
  quantidade INTEGER NOT NULL,
  prazo DATE NOT NULL,
  prioridade INTEGER DEFAULT 0,
  status VARCHAR(20) DEFAULT 'pendente' CHECK (status IN ('pendente', 'em_andamento', 'concluido', 'cancelado')),
  cliente_id INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS materias_primas (
  id SERIAL PRIMARY KEY,
  nome VARCHAR(100) NOT NULL,
  estoque_atual_kg DECIMAL(10,2) NOT NULL,
  estoque_minimo_kg DECIMAL(10,2) NOT NULL,
  fornecedor_id INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS plano_producao_diario (
  id SERIAL PRIMARY KEY,
  data DATE NOT NULL,
  pedidos_sequenciados JSONB NOT NULL,
  maquina_id INTEGER,
  capacidade_utilizada_pct DECIMAL(5,2),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- AG-05: Gerente Industrial
CREATE TABLE IF NOT EXISTS status_maquinas (
  id SERIAL PRIMARY KEY,
  nome VARCHAR(100) NOT NULL,
  tipo VARCHAR(50) NOT NULL,
  status VARCHAR(20) NOT NULL CHECK (status IN ('running', 'stopped', 'maintenance', 'error')),
  tempo_ciclo_padrao INTEGER,
  tempo_ciclo_atual INTEGER,
  horas_ociosas INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS moldes (
  id SERIAL PRIMARY KEY,
  codigo VARCHAR(50) UNIQUE NOT NULL,
  produto VARCHAR(100) NOT NULL,
  ciclos_previstos INTEGER NOT NULL,
  ciclos_atuais INTEGER DEFAULT 0,
  status VARCHAR(20) DEFAULT 'ativo' CHECK (status IN ('ativo', 'manutencao', 'inativo', 'descartado')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ferramentas_cnc (
  id SERIAL PRIMARY KEY,
  nome VARCHAR(100) NOT NULL,
  consumo_medio DECIMAL(5,2),
  consumo_atual DECIMAL(5,2),
  horas_uso INTEGER DEFAULT 0,
  horas_vida INTEGER,
  status VARCHAR(20) DEFAULT 'normal' CHECK (status IN ('normal', 'anomalo', 'troca_proxima', 'critico')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- AG-06: Vendedor do Telegram
CREATE TABLE IF NOT EXISTS clientes_telegram (
  id SERIAL PRIMARY KEY,
  user_id VARCHAR(100) UNIQUE NOT NULL,
  nome VARCHAR(100),
  tipo VARCHAR(20) DEFAULT 'varejo' CHECK (tipo IN ('varejo', 'atacado')),
  total_pedidos INTEGER DEFAULT 0,
  total_gasto DECIMAL(10,2) DEFAULT 0,
  ticket_medio DECIMAL(10,2),
  ultimo_pedido TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sessoes_telegram (
  id SERIAL PRIMARY KEY,
  user_id VARCHAR(100) NOT NULL,
  estado VARCHAR(50) DEFAULT 'inicial',
  contexto JSONB,
  ultima_mensagem TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pedidos_telegram (
  id SERIAL PRIMARY KEY,
  pedido_id VARCHAR(50) UNIQUE NOT NULL,
  user_id VARCHAR(100) NOT NULL,
  itens JSONB NOT NULL,
  desconto_pct INTEGER DEFAULT 0,
  valor_total DECIMAL(10,2),
  status VARCHAR(20) DEFAULT 'aguardando_pagamento' CHECK (status IN ('aguardando_pagamento', 'pago', 'confirmado', 'cancelado')),
  pagamento VARCHAR(20),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- AG-07: Laboratório de Produtos
CREATE TABLE IF NOT EXISTS pipeline_lancamentos (
  id SERIAL PRIMARY KEY,
  nome_produto VARCHAR(200) NOT NULL,
  descricao TEXT,
  complexidade_molde INTEGER,
  custo_molde_estimado DECIMAL(12,2),
  tempo_desenvolvimento_dias INTEGER,
  custo_producao_unitario DECIMAL(10,2),
  preco_venda_sugerido DECIMAL(10,2),
  margem_estimada DECIMAL(5,1),
  volume_vendas_projetado_mes INTEGER,
  payback_meses DECIMAL(5,1),
  risco INTEGER,
  score_final DECIMAL(5,1),
  status VARCHAR(20) DEFAULT 'em_analise' CHECK (status IN ('em_analise', 'aprovado', 'prototipagem', 'pre_lancamento', 'lancamento', 'cancelado')),
  data_analise DATE DEFAULT CURRENT_DATE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS componentes_bom (
  id SERIAL PRIMARY KEY,
  pipeline_id INTEGER REFERENCES pipeline_lancamentos(id) ON DELETE CASCADE,
  componente_nome VARCHAR(100),
  quantidade DECIMAL(10,2),
  custo_unitario DECIMAL(10,2),
  custo_total DECIMAL(10,2),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS historico_custos_simulados (
  id SERIAL PRIMARY KEY,
  pipeline_id INTEGER REFERENCES pipeline_lancamentos(id) ON DELETE CASCADE,
  fonte VARCHAR(50),
  custo_producao DECIMAL(10,2),
  margem_pct DECIMAL(5,1),
  data_simulacao DATE DEFAULT CURRENT_DATE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_pedidos_producao_status ON pedidos_producao(status);
CREATE INDEX IF NOT EXISTS idx_pedidos_producao_prazo ON pedidos_producao(prazo);
CREATE INDEX IF NOT EXISTS idx_moldes_status ON moldes(status);
CREATE INDEX IF NOT EXISTS idx_ferramentas_cnc_status ON ferramentas_cnc(status);
CREATE INDEX IF NOT EXISTS idx_clientes_telegram_user_id ON clientes_telegram(user_id);
CREATE INDEX IF NOT EXISTS idx_pedidos_telegram_user_id ON pedidos_telegram(user_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_status ON pipeline_lancamentos(status);
CREATE INDEX IF NOT EXISTS idx_componentes_bom_pipeline_id ON componentes_bom(pipeline_id);