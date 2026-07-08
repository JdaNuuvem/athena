# Plano de Implementação — Fase 3: Cadeia de Manufatura

**Data:** 2026-07-07
**Objetivo:** Implementar rastreamento completo da cadeia de manufatura: moldes → CNC → injeção → qualidade → estoque
**Status:** ⏳ Planejamento

---

## Visão Geral

| Agente | Nome | Prioridade | Status Atual | Faltante |
|---|---|---|---|---|
| AG-05 | Gerente Industrial | 1 | ✅ Básico | Tracking completo de moldes, lifecycle events |
| AG-04 | Planejador de Produção | 2 | ✅ Básico | Integração com eventos de manufatura |
| AG-09 | Memória Corporativa | 3 | ✅ Básico | Histórico de manutenção, ciclos de molde |
| AG-02 | Analista de Lucratividade | 4 | ✅ Existente | Custo por ciclo, custo real vs. estimado |
| NOVO | Controlador de Qualidade | 5 | ❌ Não existe | Inspeção, defeitos, CAPA |
| NOVO | Gestor de Manutenção | 6 | ❌ Não existe | Preventiva/corretiva, agendamento |

---

## Arquitetura de Cadeia de Manufatura

```
┌─────────────────────────────────────────────────────────────────────┐
│                    FASE 3: MANUFACTURING CHAIN                     │
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │   Design     │ →  │    CNC       │ →  │  Injeção     │          │
│  │   (AG-07)    │    │   (AG-05)    │    │  (AG-05)    │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│         ↓                  ↓                  ↓                    │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │  Molde Novo  │    │  Usinagem    │    │  Produção    │          │
│  │   (AG-09)    │    │  Completa    │    │   em Lotes   │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │                  Controle de Qualidade (NOVO)            │      │
│  │  Inspeção → Defeitos → CAPA → Retrabalho → Aprovação      │      │
│  └──────────────────────────────────────────────────────────┘      │
│                          ↓                                        │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │                   Estoque (AG-04/AG-09)                  │      │
│  │  Entrada → FIFO → LIFO → Expedição → Loja/Marketplace    │      │
│  └──────────────────────────────────────────────────────────┘      │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │                  Gestão de Manutenção (NOVO)             │      │
│  │  Preventiva → Corretiva → Histórico → Previsão          │      │
│  └──────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Tarefa 1: Aprofundar AG-05 — Ciclo de Vida de Moldes

### 1.1 Criar tabelas para tracking de moldes
```sql
-- Extensão da tabela moldes existente
ALTER TABLE moldes ADD COLUMN IF NOT EXISTS status_atual VARCHAR(20) DEFAULT 'projeto';
ALTER TABLE moldes ADD COLUMN IF NOT EXISTS data_design DATE;
ALTER TABLE moldes ADD COLUMN IF NOT EXISTS data_fabricacao_inicio DATE;
ALTER TABLE moldes ADD COLUMN IF NOT EXISTS data_fabricacao_fim DATE;
ALTER TABLE moldes ADD COLUMN IF NOT EXISTS data_instalacao DATE;
ALTER TABLE moldes ADD COLUMN IF NOT EXISTS maquina_id VARCHAR(50);
ALTER TABLE moldes ADD COLUMN IF NOT EXISTS ciclos_acumulados INTEGER DEFAULT 0;
ALTER TABLE moldes ADD COLUMN IF NOT EXISTS ultima_manutencao DATE;
ALTER TABLE moldes ADD COLUMN IF NOT EXISTS proxima_manutencao INTEGER; -- ciclos

-- Tabela de eventos de molde
CREATE TABLE IF NOT EXISTS moldes_eventos (
  id SERIAL PRIMARY KEY,
  molde_id INTEGER REFERENCES moldes(id),
  tipo VARCHAR(30) NOT NULL, -- designed, fabrication_started, fabrication_completed, installed, removed, maintenance
  descricao TEXT,
  dados JSONB,
  usuario VARCHAR(100),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabela de usinagem CNC
CREATE TABLE IF NOT EXISTS cnc_jobs (
  id SERIAL PRIMARY KEY,
  job_id VARCHAR(50) UNIQUE NOT NULL,
  molde_id INTEGER REFERENCES moldes(id),
  maquina_id VARCHAR(50) NOT NULL,
  operador VARCHAR(100),
  status VARCHAR(20) DEFAULT 'scheduled', -- scheduled, running, completed, failed
  data_inicio DATE,
  data_fim DATE,
  horas_planejadas DECIMAL(5,2),
  horas_reais DECIMAL(5,2),
  material_usado_kg DECIMAL(10,2),
  observacoes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabela de lotes de produção
CREATE TABLE IF NOT EXISTS producao_lotes (
  id SERIAL PRIMARY KEY,
  lote_id VARCHAR(50) UNIQUE NOT NULL,
  pedido_producao_id INTEGER REFERENCES pedidos_producao(id),
  molde_id INTEGER REFERENCES moldes(id),
  maquina_id VARCHAR(50) NOT NULL,
  operador VARCHAR(100),
  sku VARCHAR(50) NOT NULL,
  status VARCHAR(20) DEFAULT 'programado', -- programado, em_producao, pausado, concluido, cancelado
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
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS inspecao_qualidade (
  id SERIAL PRIMARY KEY,
  lote_id INTEGER REFERENCES producao_lotes(id),
  data_inspecao DATE DEFAULT CURRENT_DATE,
  inspetor VARCHAR(100),
  tipo_inspecao VARCHAR(30) NOT NULL, -- inicial, intermediaria, final
  quantidade_amostrada INTEGER,
  quantidade_aprovada INTEGER,
  quantidade_reprovada INTEGER,
  defeitos_encontrados JSONB,
  status_inspecao VARCHAR(20), -- aprovado, reprovado, condicional
  acoes_tomadas TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 1.2 Implementar tracking de lifecycle de moldes
```python
# ag_05_industrial/mold_lifecycle.py

def registrar_evento_molde(molde_id: int, tipo: str, descricao: str = "", dados: dict = None) -> int:
    """Registra evento no lifecycle do molde."""
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""
            INSERT INTO moldes_eventos (molde_id, tipo, descricao, dados)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """, molde_id, tipo, descricao, json.dumps(dados or {}))
        return row['id']
    return run_async(_go())

def avancar_status_molde(molde_id: int, novo_status: str, dados: dict = None) -> bool:
    """Avança o status do molde e registra evento."""
    # TODO: Implementar
    pass

def obter_historico_molde(molde_id: int) -> list:
    """Obtém histórico completo de eventos do molde."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT me.*, m.codigo, m.produto
            FROM moldes_eventos me
            JOIN moldes m ON m.id = me.molde_id
            WHERE me.molde_id = $1
            ORDER BY me.created_at
        """, molde_id)
        return [dict(r) for r in rows]
    return run_async(_go())
```

---

## Tarefa 2: Implementar Controle de Qualidade (AG-11)

### 2.1 Criar AG-11: Controlador de Qualidade
```python
# ag_11_qualidade/__init__.py

"""
AG-11: Controlador de Qualidade
Gerencia inspeções, defeitos, CAPA (Corrective and Preventive Actions),
estatísticas de qualidade, tendências de defeitos.
"""

AGENT = "AG-11 | Controlador de Qualidade"

def registrar_inspecao(lote_id: int, dados_inspecao: dict) -> dict:
    """Registra inspeção de qualidade de um lote."""
    # TODO: Implementar
    pass

def analisar_defeitos(lote_id: int) -> dict:
    """Analisa defeitos encontrados e classifica por tipo."""
    # TODO: Implementar
    pass

def gerar_capa(defeito_id: int, acao: str, responsavel: str) -> int:
    """Gera CAPA (Corrective and Preventive Action)."""
    # TODO: Implementar
    pass

def calcular_taxa_defeitos periodo_dias: int = 30) -> dict:
    """Calcula taxa de defeitos por SKU, molde, máquina."""
    # TODO: Implementar
    pass

def pareto_defeitos(periodo_dias: int = 30) -> list:
    """Gera análise Pareto de defeitos (80/20)."""
    # TODO: Implementar
    pass
```

### 2.2 Tabelas para qualidade
```sql
CREATE TABLE IF NOT EXISTS defeitos (
  id SERIAL PRIMARY KEY,
  codigo VARCHAR(20) UNIQUE NOT NULL,
  nome VARCHAR(100) NOT NULL,
  categoria VARCHAR(50), -- dimensional, estetico, funcional, material
  gravidade VARCHAR(20), -- baixa, media, alta, critica
  descricao TEXT,
  causa_raiz_sugerida TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS capa_registros (
  id SERIAL PRIMARY KEY,
  numero VARCHAR(30) UNIQUE NOT NULL,
  tipo VARCHAR(20) NOT NULL, -- corretiva, preventiva
  origem VARCHAR(50), -- defeito, cliente, auditoria, processo
  descricao_problema TEXT NOT NULL,
  causa_raiz TEXT,
  acao_corretiva TEXT,
  acao_preventiva TEXT,
  responsavel VARCHAR(100),
  data_abertura DATE DEFAULT CURRENT_DATE,
  data_prevista_conclusao DATE,
  data_conclusao DATE,
  status VARCHAR(20) DEFAULT 'aberta', -- aberta, em_andamento, concluida, cancelada
  eficacia_verificada BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS inspecao_defeitos (
  id SERIAL PRIMARY KEY,
  inspecao_id INTEGER REFERENCES inspecao_qualidade(id),
  defeito_id INTEGER REFERENCES defeitos(id),
  quantidade INTEGER DEFAULT 1,
  gravidade VARCHAR(20),
  observacoes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Tarefa 3: Implementar Gestão de Manutenção (AG-12)

### 3.1 Criar AG-12: Gestor de Manutenção
```python
# ag_12_manutencao/__init__.py

"""
AG-12: Gestor de Manutenção
Gerencia manutenção preventiva e corretiva de máquinas e moldes.
Agendamento, histórico, previsão, alertas.
"""

AGENT = "AG-12 | Gestor de Manutenção"

def agendar_manutencao(equipamento_id: str, tipo: str, data: date, descricao: str) -> int:
    """Agenda manutenção de equipamento."""
    # TODO: Implementar
    pass

def registrar_manutencao_realizada(manutencacao_id: int, dados: dict) -> dict:
    """Registra manutenção realizada."""
    # TODO: Implementar
    pass

def obter_manutencoes_pendentes() -> list:
    """Lista manutenções pendentes ordenadas por prioridade."""
    # TODO: Implementar
    pass

def prever_proxima_manutencao(equipamento_id: str) -> dict:
    """Preve próxima manutenção baseado em histórico."""
    # TODO: Implementar
    pass

def calcular_mtbtf(equipamento_id: str) -> float:
    """Calcula MTBF (Mean Time Between Failures)."""
    # TODO: Implementar
    pass
```

### 3.2 Tabelas para manutenção
```sql
CREATE TABLE IF NOT EXISTS manutencoes (
  id SERIAL PRIMARY KEY,
  numero VARCHAR(30) UNIQUE NOT NULL,
  equipamento_tipo VARCHAR(30) NOT NULL, -- maquina, molde
  equipamento_id VARCHAR(50) NOT NULL,
  tipo VARCHAR(20) NOT NULL, -- preventiva, corretiva, preditiva
  prioridade INTEGER DEFAULT 3, -- 1=alta, 2=media, 3=baixa
  descricao TEXT,
  data_agendada DATE NOT NULL,
  data_inicio DATE,
  data_fim DATE,
  duracao_horas DECIMAL(5,2),
  tecnico VARCHAR(100),
  pecas_substituidas JSONB,
  custo_pecas DECIMAL(10,2),
  custo_mao_obra DECIMAL(10,2),
  observacoes TEXT,
  status VARCHAR(20) DEFAULT 'agendada', -- agendada, em_andamento, concluida, cancelada
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS manutencoes_historico (
  id SERIAL PRIMARY KEY,
  manutencacao_id INTEGER REFERENCES manutencoes(id),
  data_registro TIMESTAMPTZ DEFAULT NOW(),
  descricao TEXT,
  usuario VARCHAR(100)
);
```

---

## Tarefa 4: Integrar Produção com Estoque Real

### 4.1 Atualizar AG-04 para tracking de entrada no estoque
```python
# ag_04_planejador/__init__.py

def registrar_producao_concluida(lote_id: int) -> dict:
    """Registra conclusão de lote e entra no estoque."""
    async def _go():
        db = await get_db()
        
        # Obter dados do lote
        lote = await db.fetchrow("SELECT * FROM producao_lotes WHERE id = $1", lote_id)
        if not lote:
            return {"error": "Lote não encontrado"}
        
        # Atualizar status do lote
        await db.execute("""
            UPDATE producao_lotes
            SET status = 'concluido', data_fim = CURRENT_DATE
            WHERE id = $1
        """, lote_id)
        
        # Entrar no estoque
        await db.execute("""
            INSERT INTO estoque_produtos (sku, lote_id, quantidade, data_entrada, origem)
            VALUES ($1, $2, $3, CURRENT_DATE, 'producao')
            ON CONFLICT (sku, lote_id) DO UPDATE
            SET quantidade = estoque_produtos.quantidade + $3
        """, lote['sku'], lote_id, lote['quantidade_produzida'])
        
        # Atualizar ciclos do molde
        await db.execute("""
            UPDATE moldes
            SET ciclos_acumulados = ciclos_acumulados + $1
            WHERE id = $2
        """, lote['ciclos_realizados'], lote['molde_id'])
        
        return {"success": True, "lote_id": lote_id, "sku": lote['sku'], "quantidade": lote['quantidade_produzida']}
    return run_async(_go())
```

### 4.2 Criar tabela de estoque de produtos
```sql
CREATE TABLE IF NOT EXISTS estoque_produtos (
  id SERIAL PRIMARY KEY,
  sku VARCHAR(50) NOT NULL,
  lote_id INTEGER REFERENCES producao_lotes(id),
  quantidade INTEGER NOT NULL,
  data_entrada DATE DEFAULT CURRENT_DATE,
  origem VARCHAR(30), -- producao, compra, transferencia
  loja_id INTEGER,
  data_saida DATE,
  observacoes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_estoque_sku ON estoque_produtos(sku);
CREATE INDEX IF NOT EXISTS idx_estoque_lote ON estoque_produtos(lote_id);
```

---

## Tarefa 5: Workflows Cross-Agent (Fase 3)

### 5.1 Workflow: Lote Completo → Qualidade → Estoque
```python
# workflows_fase3.py

def workflow_lote_para_estoque(lote_id: int) -> dict:
    """Lote produzido → inspeção → entrada estoque."""
    from ag_11_qualidade import registrar_inspecao, analisar_defeitos
    from ag_04_planejador import registrar_producao_concluida
    
    log("WORKFLOW", f"Iniciando Lote→Estoque: lote_id={lote_id}")
    
    # Registrar inspeção automática
    inspecao = registrar_inspecao(lote_id, {
        "tipo_inspecao": "final",
        "quantidade_amostrada": 10,  # Amostra de 10%
    })
    
    # Analisar defeitos
    defeitos = analisar_defeitos(lote_id)
    
    # Se aprovado, entrar no estoque
    if inspecao['status_inspecao'] == 'aprovado':
        estoque = registrar_producao_concluida(lote_id)
        return {"success": True, "lote_id": lote_id, "estoque": estoque}
    else:
        return {"success": False, "lote_id": lote_id, "motivo": "Reprovado na qualidade"}
```

### 5.2 Workflow: Manutenção Molde → Revisar Produção
```python
def workflow_manutencao_molde(molde_id: int) -> dict:
    """Manutenção realizada → revisar capacidade de produção."""
    from ag_12_manutencao import prever_proxima_manutencao
    from ag_04_planejador import recalcular_capacidade
    
    log("WORKFLOW", f"Iniciando Manutenção→Produção: molde_id={molde_id}")
    
    # Prever próxima manutenção
    proxima = prever_proxima_manutencao(molde_id)
    
    # Recalcular capacidade
    capacidade = recalcular_capacidade()
    
    return {"molde_id": molde_id, "proxima_manutencao": proxima, "capacidade": capacidade}
```

---

## Tarefa 6: Dashboard de Manufatura

### 6.1 Métricas principais
- OEE por máquina
- Taxa de defeitos por SKU/molde
- MTBF de equipamentos
- Tempo de ciclo real vs. planejado
- Custo real vs. estimado por lote
- Throughput por linha

### 6.2 Endpoints REST
```python
# athena_bridge.py (extensão)

# AG-11: Qualidade
@app.route('/api/agent/ag_11_qualidade/taxa_defeitos', methods=['GET'])
def taxa_defeitos():
    from ag_11_qualidade import calcular_taxa_defeitos
    periodo = request.args.get('periodo', 30, type=int)
    return jsonify(calcular_taxa_defeitos(periodo))

@app.route('/api/agent/ag_11_qualidade/pareto', methods=['GET'])
def pareto_defeitos():
    from ag_11_qualidade import pareto_defeitos
    periodo = request.args.get('periodo', 30, type=int)
    return jsonify(pareto_defeitos(periodo))

# AG-12: Manutenção
@app.route('/api/agent/ag_12_manutencao/pendentes', methods=['GET'])
def manutencoes_pendentes():
    from ag_12_manutencao import obter_manutencoes_pendentes
    return jsonify(obter_manutencoes_pendentes())

@app.route('/api/agent/ag_12_manutencao/agendar', methods=['POST'])
def agendar_manutencao():
    from ag_12_manutencao import agendar_manutencao
    data = request.json
    return jsonify({"id": agendar_manutencao(**data)})

# Tracking de moldes
@app.route('/api/moldes/<int:molde_id>/historico', methods=['GET'])
def historico_molde(molde_id):
    from ag_05_industrial.mold_lifecycle import obter_historico_molde
    return jsonify(obter_historico_molde(molde_id))
```

---

## Checklist de Validação

### ✅ Pré-requisitos
- [ ] Schema Fase 3 aplicado
- [ ] Moldes existentes migrados para novo schema
- [ ] AG-11 e AG-12 criados
- [ ] Workflows Fase 3 implementados

### ✅ Tracking de Moldes Validado
- [ ] Eventos de lifecycle registrados
- [ ] Histórico completo de molde acessível
- [ ] Status atualizado automaticamente
- [ ] Ciclos acumulados corretos

### ✅ Controle de Qualidade Validado
- [ ] Inspeções registradas por lote
- [ ] Defeitos classificados e categorizados
- [ ] CAPA geradas automaticamente
- [ ] Taxa de defeitos calculada corretamente
- [ ] Pareto de defeitos funciona

### ✅ Gestão de Manutenção Validado
- [ ] Manutenções agendadas e rastreadas
- [ ] Histórico completo disponível
- [ ] Previsão de próxima manutenção funciona
- [ ] MTBF calculado corretamente
- [ ] Alertas de manutenção funcionam

### ✅ Integração Estoque Validado
- [ ] Lotes concluídos entram no estoque
- [ ] Ciclos de molde atualizados
- [ ] FIFO/LIFO implementado
- [ ] Transferências entre lojas rastreadas

---

## Comandos de Validação

```bash
# 1. Aplicar schema Fase 3
cd hermes_agents
python migrate_fase3.py

# 2. Testar tracking de moldes
curl http://localhost:5000/api/moldes/1/historico

# 3. Testar qualidade
curl http://localhost:5000/api/agent/ag_11_qualidade/taxa_defeitos?periodo=30

# 4. Testar manutenção
curl http://localhost:5000/api/agent/ag_12_manutencao/pendentes

# 5. Rodar testes
python test_fase3.py
```

---

## Ordem de Implementação Recomendada

1. **Schema Fase 3** (0.5 dia)
2. **AG-05 — Tracking de Moldes** (1 dia)
3. **AG-11 — Controle de Qualidade** (1.5 dias)
4. **AG-12 — Gestão de Manutenção** (1.5 dias)
5. **AG-04 — Integração com Estoque** (0.5 dia)
6. **Workflows Fase 3** (0.5 dia)
7. **Endpoints REST** (0.5 dia)
8. **Testes e Validação** (0.5 dia)

**Total estimado: ~6.5 dias**