# Financeiro — Caixa, Cofre e Relatórios por Loja

**Data**: 2026-08-02
**Status**: Aprovado (brainstorming), aguardando plano de implementação

## Contexto

A feature `/financeiro` já existe (contas a pagar/receber, boletos, PIX, conciliação,
bancos, DRE) mas tem bugs de segurança/robustez sendo corrigidos numa frente
separada (SQL injection via whitelist de colunas, RBAC ausente em GETs, status
HTTP sempre 200, schema drift de `bling_id`/`origem`, botões sem `onClick`) —
ver seção "Fora de escopo" abaixo.

Separado disso, o usuário forneceu 5 planilhas Excel que hoje formalizam
manualmente um processo de negócio que a feature Financeiro **não cobre**:

- `CONTAGEM DINHEIRO.xlsx` — contagem física de cédulas/moedas por loja/dia.
- `Fechamento.xlsx` — conferência sistema × contado, por maquineta (FIX/Stone/TEF)
  × forma de pagamento (PIX/débito/crédito).
- `SAIDA CAIXA.xlsx` — cofre por loja: saldo inicial, entradas, saídas, saldo final.
- `VENDAS MES LOJAS.xlsx` — vendas diárias por loja, grade mês inteiro.
- `MOV LOJA LEON.xlsx` — receita (por forma de pagamento) − despesa (por categoria)
  por loja/dia, com total líquido.

Investigação confirmou que **nenhuma dessas 5 coisas existe hoje**, nem em
Financeiro nem em PDV. PDV já tem abertura/fechamento de caixa (saldo
inicial/final, sangria, suprimento, conferência só de dinheiro) — as
planilhas cobrem exatamente os passos que faltam nesse fluxo mais os
relatórios de consolidação por loja.

## Decisão de arquitetura

Não duplicar o conceito de "caixa" (que já existe em `pdv_caixas`). PDV
continua dono da verdade transacional. Financeiro ganha a camada de
categorização (Cofre) e relatório (grades/P&L) — mesmo papel que já tem hoje
com contas a pagar/receber e DRE.

## Fase 1 — PDV: fechamento de caixa mais rico

### Contagem por denominação

Nova tabela:
```sql
CREATE TABLE pdv_caixa_contagem (
    id SERIAL PRIMARY KEY,
    caixa_id INT NOT NULL REFERENCES pdv_caixas(id),
    denominacao VARCHAR(10) NOT NULL,  -- "200","100","50","20","10","5","2","1","0.50","0.25","0.10","0.05"
    quantidade INT NOT NULL DEFAULT 0,
    subtotal DECIMAL(10,2) GENERATED ALWAYS AS (quantidade * denominacao::numeric) STORED,
    created_at TIMESTAMP DEFAULT NOW()
)
```
No modal de fechamento (`FechaModal.tsx`), antes do campo "saldo conferido",
uma grade cédula/moeda × quantidade. O saldo conferido em dinheiro passa a
ser a SOMA dos subtotais dessa grade (campo livre de "saldo conferido"
desaparece, substituído pelo total calculado).

### Conferência por maquineta

Adicionar coluna `maquineta VARCHAR(50)` em `pdv_pagamentos` (nullable —
default vazio para pagamentos antigos e para operadores que não
preencherem). Campo opcional (select ou texto livre, sem enum fixo no
schema) na tela de venda (`VendaTab.tsx`), ao lado de forma de pagamento,
para pagamentos que não são dinheiro.

Nova tabela para a conferência do fechamento:
```sql
CREATE TABLE pdv_caixa_conferencia (
    id SERIAL PRIMARY KEY,
    caixa_id INT NOT NULL REFERENCES pdv_caixas(id),
    maquineta VARCHAR(50) NOT NULL,
    forma_pagamento VARCHAR(30) NOT NULL,
    valor_sistema DECIMAL(12,2) NOT NULL DEFAULT 0,
    valor_conferido DECIMAL(12,2),
    diferenca DECIMAL(12,2) GENERATED ALWAYS AS (COALESCE(valor_conferido,0) - valor_sistema) STORED,
    created_at TIMESTAMP DEFAULT NOW()
)
```
No fechamento: `valor_sistema` pré-calculado agrupando `pdv_pagamentos` do
caixa por `(maquineta, forma)` (mesma query de `resumo_fechamento`, com
`GROUP BY` adicional). Operador digita `valor_conferido` por linha
(maquineta × forma) que apareceu no sistema. Pagamentos sem maquineta
preenchida caem num grupo "não informado".

`diferenca` total do fechamento (`pdv_caixas.diferenca`) passa a somar
dinheiro (contagem por denominação) + todas as linhas de conferência por
maquineta — hoje só considera dinheiro.

### Edge cases

- Caixa sem nenhum pagamento não-dinheiro → tabela de conferência vem vazia,
  sem quebrar o fechamento.
- Denominação com quantidade 0 não precisa ser inserida (grade só grava
  linhas preenchidas).
- Fechamentos já existentes (sem essas tabelas) continuam funcionando —
  `diferenca` cai de volta pro cálculo antigo (só dinheiro) se não houver
  linhas de conferência/contagem associadas.

## Fase 2 — Financeiro: Cofre

### Schema

```sql
CREATE TABLE fin_cofre (
    id SERIAL PRIMARY KEY,
    loja_id INT NOT NULL UNIQUE REFERENCES lojas(id),
    saldo_atual DECIMAL(12,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
)

CREATE TABLE fin_cofre_movimentos (
    id SERIAL PRIMARY KEY,
    cofre_id INT NOT NULL REFERENCES fin_cofre(id),
    tipo VARCHAR(20) NOT NULL,  -- entrada_sangria | saida_troco | saida_despesa | ajuste
    categoria VARCHAR(30),      -- só p/ saida_despesa: mat_limpeza|padaria|papelaria|passagem|outros
    valor DECIMAL(12,2) NOT NULL,
    descricao VARCHAR(200),
    caixa_id INT REFERENCES pdv_caixas(id),  -- preenchido p/ entrada_sangria e saida_troco
    data DATE NOT NULL DEFAULT CURRENT_DATE,
    criado_por VARCHAR(100),
    criado_por_id INT,
    created_at TIMESTAMP DEFAULT NOW()
)
```
`fin_cofre` é criado sob demanda (lazy) na primeira movimentação de uma loja
que ainda não tem cofre — não precisa de seed manual por loja.

### Automático: sangria → cofre

Ao fechar um caixa do PDV com `sangrias > 0` (soma de `pdv_sangrias` do
turno) E `loja_id` preenchido, gera automaticamente 1 `entrada_sangria` no
cofre da loja, valor = soma das sangrias do turno, `caixa_id` = o caixa que
fechou. Roda dentro do mesmo hook de fechamento (`fechar_caixa`), não
bloqueia o fechamento se falhar (loga erro, mesmo padrão de tolerância a
falha já usado em `ao_faturar_pedido`/`ao_receber_compra`).

Caixas sem `loja_id` (permitido hoje) não geram entrada no cofre — sem loja
não há cofre pra creditar. Reportado como aviso na UI de fechamento (não
bloqueia).

### Manual: saída de despesa / troco / ajuste

Nova aba "Cofre" em Financeiro. Por loja (seletor, respeitando
`lojas_permitidas`): saldo atual + extrato de movimentos (mais recentes
primeiro). Botões:
- **Nova saída**: tipo `saida_despesa` (categoria obrigatória, das 5 fixas +
  "outros" com descrição livre) ou `saida_troco` (opcional linkar a um
  `caixa_id` — não altera o caixa em si, é só rastreio de pra onde foi o
  troco).
- **Ajuste**: `tipo=ajuste`, valor pode ser positivo ou negativo, exige
  aprovação (`financeiro.aprovar` ou PIN/crachá de gerente — mesmo padrão de
  `_resolver_aprovador` já usado em contas a pagar) independente do valor
  (diferente do limite de R$5000 dos pagamentos — ajuste de cofre é sempre
  sensível).

`saldo_atual` é mantido via `UPDATE fin_cofre SET saldo_atual = saldo_atual +/- valor`
na mesma transação de cada movimento (não recalculado por SUM a cada
leitura — mais simples e já é o padrão usado em outras contas do sistema,
ex. `fin_bancos.saldo`).

### RBAC

`requer_acesso_loja` em todas as rotas de cofre (mesmo padrão corrigido em
Lojas nesta sessão) — usuário só vê/mexe no cofre das lojas que tem acesso
via `usuario_lojas`. Permissões: `financeiro.ver` (ler extrato),
`financeiro.criar` (nova saída), `financeiro.aprovar` (ajuste).

## Fase 3 — Financeiro: Relatórios (somente leitura)

### Vendas por Loja

`GET /api/financeiro/relatorios/vendas-por-loja?de=YYYY-MM-DD&ate=YYYY-MM-DD`
— agrega `pdv_vendas` (status finalizada) + `vendas_pedidos` faturados
(mesma união de `core/relatorios.py::vendas()`) por `loja_id` × dia, dentro
do intervalo. Retorna matriz {lojas: [...], dias: [{data, valores_por_loja,
total_dia}], totais_por_loja: {...}}. Só lojas em `lojas_permitidas`.

Tela nova em Financeiro: seletor de período (padrão = mês corrente, ajustável
livremente — cobre tanto visão "mês inteiro" quanto "um dia só" ao setar
`de == ate`), grade dias × lojas com totais.

### Movimento Diário por Loja

`GET /api/financeiro/relatorios/movimento-diario?de=...&ate=...&loja_id=...`
— por loja/dia no intervalo:
- Receita: soma de `pdv_pagamentos` (join `pdv_vendas`/`pdv_caixas`),
  quebrada por forma de pagamento (PIX/Dinheiro/Cartão — sem categoria de
  produto, decisão consciente de escopo, ver "Fora de escopo").
- Despesa: soma de `fin_cofre_movimentos` tipo `saida_despesa` do cofre
  daquela loja no dia, quebrada por categoria.
- Total líquido = receita total − despesa total.

Tela nova em Financeiro: mesmo seletor de período de "Vendas por Loja" +
seletor de loja, tabela por dia com colunas de receita (por forma) e despesa
(por categoria) e total líquido.

### Edge cases

- Loja sem cofre ainda (nenhum movimento) → despesas = 0, sem erro.
- Período sem vendas → linha do dia some ou aparece zerada (decisão de UI na
  hora de implementar, não afeta o contrato da API).

## Fora de escopo (decisões conscientes)

- **Receita categorizada por produto** (ex. "Venda Perf" da planilha) — exigiria
  juntar `pdv_itens` → `produtos.categoria`, uma feature de analytics bem
  maior. Movimento Diário mostra receita só por forma de pagamento.
- **Reabrir caixa fechado para creditar troco automaticamente** — troco
  enviado do cofre pro caixa fica só registrado no cofre; o próximo caixa
  aberto reflete isso manualmente no `saldo_inicial` informado na abertura.
- **Maquineta como enum fixo** — fica texto livre por loja, evita hardcodar
  nomes de adquirente específicos deste negócio no schema.
- **Correções de bugs já mapeadas do Financeiro existente** (SQL injection em
  `core/financeiro.py`, RBAC ausente em GETs, status HTTP sempre 200, schema
  drift `bling_id`/`origem`, botões sem `onClick` em 5 abas) — não fazem
  parte deste spec; são trabalho mecânico já em andamento numa frente
  separada, sem necessidade de design.

## Testes

Cada fase precisa de testes cobrindo: schema (colunas/tabelas novas criadas
corretamente), RBAC (`requer_acesso_loja` em todas as rotas de cofre),
cálculo de `diferenca`/`saldo_atual` (casos com e sem contagem/conferência),
edge case de caixa sem loja, e as duas queries de relatório com dados
mockados cobrindo múltiplas lojas/dias.
