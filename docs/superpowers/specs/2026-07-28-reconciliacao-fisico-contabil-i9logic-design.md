# Reconciliação Físico x Contábil — Ponte i9Logic → Athena

Complementar à [Fase 1 — Saldos Segregados + Ledger Formal](2026-07-28-fase1-saldos-segregados-design.md). Não é uma fase da decomposição de arquitetura interna do Athena — é a ponte de migração/coexistência com o sistema legado (i9Logic), enquanto ele ainda for a fonte de dados de produção.

## Contexto (validado com dado real da API i9Logic)

A API i9Logic (`GET /v1/produtos_estoques`) expõe dois saldos por `(idproduto, filial)`, via parâmetro `tipoestoque`:

- `tipoestoque=1` — físico (o que realmente existe, presumível de contagem/movimentação física)
- `tipoestoque=2` — contábil (saldo "livro": inclui lançamentos que nem sempre correspondem a movimento físico confirmado)

Teste real (produto `idproduto=29098`, filial `63`):

| tipo | qtd |
|---|---|
| físico | 165 |
| contábil | 348 |

Divergência de 183 unidades no mesmo produto/filial, no sistema em produção. Não é caso isolado: o mesmo produto tinha `saldonavenda` negativo em `pedidos_produtos` (venda concluída com saldo já negativo no momento da venda), e uma varredura em lote da filial 63 (9.342 SKUs com físico > 0 registrado) já mostra SKUs com físico negativo (`qtd:-2`, `qtd:-1`) mesmo sem filtrar por nenhum caso especial.

Conclusão: o i9Logic opera anos sem reconciliar físico x contábil. Isso não é uma feature a replicar no Athena — é exatamente o problema que a [Fase 1](2026-07-28-fase1-saldos-segregados-design.md) já resolve por construção (saldo único, movimentado atomicamente via `mover_saldo()`, nunca diverge de si mesmo). O papel desta reconciliação é diferente: **usar os dois números do i9Logic como insumo confiável na migração**, não replicar a dualidade dentro do Athena.

## Decisão de fonte de verdade

- **Físico (`tipoestoque=1`) é o valor usado para semear `estoque_saldos` (Fase 1) no Athena.** É o que representa "existe na prateleira/depósito agora", que é a definição do bucket `disponivel`.
- **Contábil (`tipoestoque=2`) nunca vira bucket no Athena.** Não existe `tipo` correspondente em `TIPOS_SALDO` (Fase 1) e não deve ser criado — ele não representa um estado físico real de estoque (reservado, em trânsito etc.), é um artefato de lançamento contábil do sistema legado sem rastreabilidade de causa.
- O contábil só é usado como **sinal de auditoria**: a divergência `contábil - físico` indica SKU/loja com histórico de inconsistência que merece contagem física prioritária antes ou logo depois da migração daquele item.

## Modelo de dados novo

Tabela de staging, separada de `estoque_saldos` (Fase 1) — este é dado do sistema legado, não o ledger do Athena:

```sql
CREATE TABLE i9logic_estoque_snapshot (
    id SERIAL PRIMARY KEY,
    idproduto_i9logic INT NOT NULL,
    codproduto_i9logic VARCHAR(50),
    sku_athena VARCHAR(50),
    filial_i9logic INT NOT NULL,
    loja_athena VARCHAR(50),
    qtd_fisico DECIMAL(12,3),
    qtd_contabil DECIMAL(12,3),
    divergencia DECIMAL(12,3) GENERATED ALWAYS AS (qtd_contabil - qtd_fisico) STORED,
    data_coleta TIMESTAMP DEFAULT NOW(),
    revisado BOOLEAN DEFAULT FALSE,
    UNIQUE(idproduto_i9logic, filial_i9logic, data_coleta)
)
```

`sku_athena`/`loja_athena` ficam nulos até existir o de-para (ver seção De-para abaixo) — a tabela grava o snapshot bruto do i9Logic mesmo sem mapeamento resolvido, pra não perder dado de coleta esperando resolução manual.

## De-para de identidade (pré-requisito, bloqueia o resto)

i9Logic identifica produto por `id` interno (`idproduto`) e por `codproduto` (código comercial, ex: `"041725"`). Filial por `id` interno (ex: `63`). Athena usa `sku`/`loja` como string livre (ver `core/estoque.py`, `estoque_saldos`). **Não existe ainda uma tabela de correlação `codproduto_i9logic ↔ sku_athena` nem `filial_i9logic ↔ loja_athena` no Hermes** (confirmado — grep no core não encontrou nada). Isso é a Fase 0 real desta ponte: sem de-para, qualquer reconciliação compara números sem saber se são do mesmo item.

Escopo mínimo pra desbloquear: tabela `de_para_i9logic` (`tipo` = `'produto'|'filial'`, `id_i9logic`, `codigo_athena`), populada manualmente ou por um script de matching único (`codproduto` i9Logic → `sku` Athena por igualdade textual, com relatório de não-casados pra revisão humana — não automatizar match fuzzy).

## Job de coleta (bulk, respeitando rate limit)

Confirmado por teste real: `GET /v1/produtos_estoques?filial={id}&tipoestoque={1|2}&page=N&per_page=200` retorna o catálogo inteiro da filial, sem precisar informar `idproduto` — **não precisa de 1 chamada por SKU**. Filial 63 sozinha: 9.342 registros de físico, ~47 páginas a 200/página.

Rate limit da API: 30 req/min por credencial (fixo, documentado). Rotina de coleta:

1. Para cada filial mapeada (via de-para): pagina `tipoestoque=1` até `page * per_page >= total`, depois `tipoestoque=2` igual.
2. ~94 requisições por filial (47 páginas × 2 tipos) → a 30 req/min, ~3,2 min por filial. Job assíncrono, sem pressa (varredura noturna), com sleep entre chamadas pra nunca estourar 30/min (ex: 1 req a cada 2,5s = 24/min, margem de segurança).
3. Grava cada página em `i9logic_estoque_snapshot` (upsert por `idproduto_i9logic + filial_i9logic + data_coleta`, uma linha por corrida completa — não sobrescreve corridas anteriores, permite ver evolução da divergência ao longo do tempo).
4. Resolve `sku_athena`/`loja_athena` via `de_para_i9logic` no momento da gravação (join simples); se não achar, grava com os campos Athena nulos e loga contagem de não resolvidos ao final da corrida.

## Regra de decisão sobre divergência

Nenhum ajuste automático de saldo — dado do legado não é confiável o suficiente pra corrigir Athena sozinho (histórico já mostra saldo negativo aceito em venda concluída, ou seja, o próprio "físico" pode estar errado, não só o contábil).

- `divergencia == 0` (ou abaixo de uma tolerância pequena, ex `0.5` pra evitar ruído de arredondamento): sem ação.
- `abs(divergencia) > 0` e abaixo do limiar de alerta: fica só registrado no snapshot, sem alerta ativo.
- Limiar de alerta (ajustável, sugestão inicial): `abs(divergencia) >= 5` **ou** `abs(divergencia) / max(qtd_fisico, 1) >= 0.10` (10%) — o que disparar primeiro. Gera item de revisão (`revisado = FALSE`) numa fila/relatório pra time de estoque decidir: contar fisicamente, ajustar manualmente via `core/estoque.ajustar_absoluto()` (Fase 1) com motivo `ajuste_inventario`, ou aceitar a divergência como conhecida (ex: produto com movimentação legítima em trânsito que a contábil já reconhece e o físico ainda não).
- Toda decisão manual sobre um item do snapshot vira uma chamada real a `ajustar_absoluto()` — ou seja, ainda passa pelo ledger formal do Athena (Fase 1), gerando linha em `estoque_movimentacoes` com `motivo` citando o snapshot de origem (rastreável).

## Dois modos de uso do mesmo job

1. **Seed inicial** (migração de um SKU/loja pra Athena pela primeira vez): usa o físico coletado como entrada única via `core.estoque.entrada(sku, loja, qtd_fisico, motivo="producao_interna")` ou diretamente `mover_saldo(tipo_origem=None, tipo_destino='disponivel', ...)` com motivo `import_i9logic` (precisa virar um motivo válido novo em `MOTIVOS_ENTRADA`, não reaproveitar `outro`). Contábil não participa do seed, só fica no snapshot como referência.
2. **Monitoramento contínuo** (enquanto i9Logic e Athena operam em paralelo, período de transição/strangler): corridas periódicas (diária) comparando o snapshot novo com Athena's saldo atual (`core.estoque_saldos.saldo(sku, loja, 'disponivel')`), não só físico-vs-contábil do i9Logic isolado. Três números em jogo por SKU/loja nesse modo: físico i9Logic, contábil i9Logic, disponível Athena — divergência relevante aqui é `disponivel_athena - qtd_fisico_i9logic` (detecta drift entre os dois sistemas rodando em paralelo, sinal de que algum evento não foi propagado de um lado pro outro).

## Fora de escopo desta spec

- Reconciliação de `pedidos`/`nfe`/`tef_transacoes` contra o financeiro do Athena — outra frente, não é saldo de estoque.
- Criar bucket "contábil" em `estoque_saldos` — decisão explícita de não fazer (ver seção "Decisão de fonte de verdade").
- Ajuste automático sem revisão humana, mesmo abaixo do limiar de alerta.
- Import histórico de movimentações (`estoque_movimentacoes` do passado) — esta spec cobre só saldo corrente, não histórico de como ele foi formado no i9Logic.
- Matching fuzzy de produto/filial no de-para — só igualdade exata + fila de não-casados pra humano resolver.

## Testes

- Unitário: cálculo de `divergencia` e classificação (sem ação / registrado / alerta) para os casos de fronteira do limiar (exatamente 5, exatamente 10%, os dois ao mesmo tempo).
- Unitário: resolução de de-para (achou / não achou, grava snapshot mesmo sem achar).
- Integração (mock da API i9Logic): paginação completa de uma filial simulada com >200 registros, confirma que todas as páginas são coletadas e nenhuma duplicada.
- Integração: seed inicial gera exatamente uma linha em `estoque_movimentacoes` com motivo `import_i9logic` e saldo final em `estoque_saldos` bate com o físico coletado.
- Regressão de rate limit: mock de contagem de chamadas/tempo, confirma que a rotina nunca ultrapassa 30 req/min mesmo em filial com muitas páginas.
