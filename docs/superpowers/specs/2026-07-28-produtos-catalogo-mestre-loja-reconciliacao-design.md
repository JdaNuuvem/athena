# Reconciliação — Catálogo Mestre + Produto da Loja vs PIM Core Fase 1

**Relacionado:** [2026-07-28-produtos-pim-core-fase1-design.md](2026-07-28-produtos-pim-core-fase1-design.md) (implementado, commit `665bfcd`), [2026-07-15-produtos-hierarquia-pai-filho-design.md](2026-07-15-produtos-hierarquia-pai-filho-design.md) (implementado).

## Por que este documento existe

A PIM Core Fase 1 decidiu explicitamente (decisão #1 daquele spec): **evoluir `catalogo_produtos` in-place, sem tabela paralela**, mantendo `preco_custo`, `preco_venda`, `fornecedor_id`, `estoque_minimo`, `estoque_maximo`, `estoque_localizacao`, `controlar_estoque`, `estoque_crossdocking` como colunas únicas (uma linha por SKU, valor global — não por loja). Essa decisão já está implementada e é lida por **17 arquivos** (`core/estoque.py`, `core/pdv.py`, `core/bi.py`, `core/relatorios.py`, `shopee/pricing.py`, `shopee/replication.py`, `athena_bridge.py`, `bling_erp.py`, entre outros).

A nova spec ("Catálogo Mestre + Produto da Loja") pede o oposto exatamente nesses campos: preço, custo, fornecedor, promoção, comissão, depósito, localização física, estoque mín/máx viram **por loja**, numa entidade separada, com o catálogo global ("mestre") sem nenhum dado operacional.

Não dá pra fazer as duas coisas ao mesmo tempo na mesma coluna. Este documento decide, campo a campo, o que fica onde, e como migrar os 17 consumidores sem quebrar produção no meio do caminho.

## Decisão: Opção B (camada nova, migração incremental)

`catalogo_produtos` não perde nenhuma coluna agora. As colunas operacionais que já existem lá (`preco_custo`, `preco_venda`, `fornecedor_id`, `estoque_minimo`, `estoque_maximo`, `estoque_localizacao`, `controlar_estoque`, `estoque_crossdocking`) ficam **congeladas** — continuam existindo, continuam sendo lidas pelos 17 arquivos que não migraram ainda, mas passam a ser tratadas como **valor da "loja padrão"** (a primeira/única loja de quem ainda não usa multiloja de verdade), não mais como fonte de verdade para quem já opera com múltiplas lojas.

`produtos_loja` (tabela nova) é a fonte de verdade daqui pra frente para essas informações, mas só passa a valer para os módulos que forem migrados explicitamente, um de cada vez. Motivo de não fazer corte único: os 17 arquivos leem essas colunas hoje assumindo 1 valor global por SKU — trocar de uma vez exige que cada um saiba "de qual loja" ler, o que é uma mudança de contrato, não só de fonte de dado. Migração forçada e simultânea desses 17 pontos é o tipo de corte que quebra produção se algum for esquecido.

## Modelo de dados — divisão campo a campo

### Fica em `catalogo_produtos` (Mestre) — sem mudança nenhuma nas colunas já existentes

`sku` (chave mestre), `nome`, `nome_reduzido`, `nome_impressao`, `descricao`, `descricao_curta`, `descricao_complementar` (descrição técnica), `categoria`/`categoria_id_norm`, `marca`/`marca_id`, `fabricante_id`, `linha`, `modelo`, `colecao`, `unidade_padrao`, `peso_bruto`/`peso_liquido`, `largura`/`altura`/`profundidade`/`unidade_medida_dimensao`, `codigo_barras`/`gtin_embalagem`, `ncm`, `cest`, `origem_fiscal` (tributação padrão), `imagens` (JSONB), `campos_customizados` (atributos), `classificacao`, `situacao` (status), `sku_pai`/`atributo`/`id_bling` (hierarquia de variação), `estrutura` (BOM), tags (`catalogo_tags`/`catalogo_produto_tags`). SEO ainda não existe como campo — fica registrado como gap (ver "Fora de escopo").

### Sai de `catalogo_produtos` como fonte de verdade, mas a coluna não é removida (congelada)

`preco_custo`, `preco_venda`, `fornecedor_id`, `estoque_minimo`, `estoque_maximo`, `estoque_localizacao`, `controlar_estoque`, `estoque_crossdocking`, `custo_transporte`.

### Tabela nova: `produtos_loja`

```sql
CREATE TABLE IF NOT EXISTS produtos_loja (
    id SERIAL PRIMARY KEY,
    empresa_id INT,
    loja VARCHAR(50) NOT NULL,
    produto_mestre_sku VARCHAR(50) REFERENCES catalogo_produtos(sku),
    sku VARCHAR(50) NOT NULL,
    codigo_interno VARCHAR(50),
    codigo_barras_override VARCHAR(50),
    nome_override VARCHAR(300),
    status VARCHAR(1) DEFAULT 'A',
    preco_custo DECIMAL(12,2),
    preco_venda DECIMAL(12,2),
    promocao_ativa BOOLEAN DEFAULT FALSE,
    promocao_preco DECIMAL(12,2),
    promocao_inicio DATE,
    promocao_fim DATE,
    comissao_pct DECIMAL(5,2),
    fornecedor_id INT,
    deposito VARCHAR(100),
    localizacao_fisica VARCHAR(100),
    estoque_minimo DECIMAL(12,3),
    estoque_maximo DECIMAL(12,3),
    observacoes_internas TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(loja, sku)
)
```

`produto_mestre_sku` é opcional (`NULL` = produto criado do zero direto na loja, sem vínculo — atende "podendo ser criado do zero ou derivado" do pedido original). `estoque` (quantidade real) **não é coluna aqui** — continua em `estoque_lojas(sku, loja, quantidade)`, já existente e já usado por 16 arquivos; `produtos_loja.sku` é a mesma chave usada em `estoque_lojas.sku`, então o join é direto por `(sku, loja)`, sem duplicar o dado de saldo. `estoque_minimo`/`estoque_maximo` aqui são o parâmetro de alerta (não o saldo), coerente com o que hoje existe em `catalogo_produtos` mas agora por loja.

Histórico/auditoria de `produtos_loja`: reaproveita `core/seguranca.py::auditar_alteracao()`/`auditar_exclusao()` (grava em `audit_log`, já genérica, mesmo padrão usado na PIM Core Fase 1) — sem tabela de auditoria nova.

## Migração incremental dos 17 consumidores

Não faz parte desta reconciliação decidir a ordem — isso é o plano de implementação (próximo passo). Mas o critério de migração de cada um fica registrado aqui: um arquivo migra quando passa a receber `loja` como parâmetro explícito em vez de assumir 1 valor global. Até migrar, continua lendo as colunas congeladas de `catalogo_produtos` (comportamento idêntico ao de hoje, sem regressão). Depois de migrado, lê `produtos_loja` filtrado por `(sku, loja)`.

Ordem sugerida (mais isolado → mais espalhado, para o primeiro corte validar o padrão com risco baixo): `core/estoque_contagem.py` → `routes/estoque.py` → `core/pdv.py` → `shopee/pricing.py` → `core/bi.py`/`core/relatorios.py` → `bling_erp.py`/`athena_bridge.py` (sync, mexe em todos os outros indiretamente, fica por último).

## Replicação e Sincronização (sem conflito com a PIM Core Fase 1 — funcionalidade nova)

Não há decisão anterior sobre isso — implementação direta conforme a spec original:

- **Replicar para outras lojas**: cria N linhas em `produtos_loja` (uma por loja destino) a partir de uma existente, copiando só campos do Mestre associado (nome/descrição/categoria/marca/imagens/atributos/tributação já vêm do `produto_mestre_sku` compartilhado — não precisam ser copiados, são lidos via join). Os campos operacionais (preço, custo, fornecedor, promoção, comissão, depósito, localização) **nunca** são copiados — cada linha nova nasce com esses campos vazios, cadastro manual na loja destino depois.
- **Sincronizar campos do Mestre**: já é automático por natureza do modelo (join, não cópia) para os campos que ficam no Mestre. "Sincronização seletiva e manual" da spec original só faz sentido para os campos que hoje são *override* em `produtos_loja` (`nome_override`, `codigo_barras_override`) — ação explícita "aceitar valor do mestre" que copia `catalogo_produtos.nome` para `produtos_loja.nome_override` (ou limpa o override, voltando a herdar do join) numa loja escolhida.

## Fora de escopo (registrado, não decidido aqui)

- SEO como campo do Mestre — não existe hoje em `catalogo_produtos`, pedido original menciona mas fica para quando essa fase for planejada.
- Ordem exata e cronograma de migração dos 17 consumidores — vira o plano de implementação.
- Dashboard/UI para comparar Mestre vs Loja lado a lado — mencionado implicitamente pela ideia de sync seletiva, mas não especificado a ponto de virar tarefa.
- Multi-empresa de verdade (`empresa_id` na tabela nova existe como coluna, mas não há hoje conceito de "empresa" separado de "loja" no restante do sistema — checar se `core/cadastros.py` ou equivalente já tem entidade Empresa antes de decidir se `empresa_id` é FK real ou fica solto).

## Próximo passo

Com este documento, a spec original de "Catálogo Mestre + Produto da Loja" e a PIM Core Fase 1 deixam de se contradizer — cada uma cobre um subconjunto de campos diferente, com transição incremental definida. O próximo passo natural é transformar isto num plano de implementação (`superpowers:writing-plans`), tarefa por tarefa, começando pela criação de `produtos_loja` e do endpoint de Replicação (a parte sem dependência dos 17 consumidores existentes).
