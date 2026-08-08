# Estoque — Divergência de Saldo (i9Logic + Shopee)

**Data:** 2026-08-07
**Status:** Aprovado para planejamento

## Contexto

Pedido: lapidar `/estoque/discrepancias` pra comparar saldo real contra o sistema externo — loja física contra i9Logic (ou nosso estoque), loja online contra Shopee.

Investigação encontrou dois cenários muito diferentes:

- **i9Logic (loja física): infraestrutura completa já existe**, sem nenhuma tela consumindo. `hermes_agents/core/i9logic.py` já tem coleta (`snapshot_mais_recente`, `_disparar_coleta_se_necessario`), classificação de divergência (`classificar_divergencia`), listagem pra revisão (`listar_itens_para_revisao`), comparação contínua (`comparar_com_athena`) e as duas ações de resolução (`marcar_revisado`, `aplicar_ajuste_divergencia`, que aplica o saldo físico via `core.estoque.ajustar_absoluto`). Rotas REST já prontas em `hermes_agents/routes/i9logic.py`: `GET /api/integrations/i9logic/divergencias`, `POST /divergencias/<id>/resolver`, `POST /divergencias/<id>/ajustar`, `GET /comparar`. Nenhuma tela do frontend chama essas rotas hoje.
- **Shopee (loja online): nada existe.** Sem tabela de snapshot, sem comparação, sem job de coleta.

A tela atual `/estoque/discrepancias` (`web/src/app/estoque/discrepancias/page.tsx`) cobre outra coisa — audita comportamento humano (saídas grandes aprovadas, transferências com discrepância, faltas em contagem cíclica), agregado por loja e por operador, via `GET /api/estoque/relatorio-discrepancias`. Fica intocada. Esta spec adiciona uma seção nova, separada, na mesma página: **Divergência de Saldo**.

## Decisões (fechadas com o usuário durante o brainstorming)

- i9Logic e Shopee entram juntos nesta spec (não em fases separadas).
- Ação de resolução da divergência Shopee: **ajustar o Athena pra bater com o saldo real da Shopee** (mesmo padrão do i9Logic — a Shopee é a fonte física do que foi de fato vendido/reservado no marketplace).
- Coleta Shopee: **periódica em background** (mesmo padrão do i9Logic — snapshot + job), não sob demanda.
- A seção nova mostra a fonte certa automaticamente conforme o tipo da loja selecionada no seletor global do app (mesmo padrão já usado no hub `/estoque`, que decide entre `EstoqueFisicoI9Logic` e `EstoqueRapidoVirtual`): loja física → divergências i9Logic; loja virtual → divergências Shopee.

## Backend

### Módulo compartilhado: `hermes_agents/core/estoque_divergencia.py`

Extrai de `core/i9logic.py` (linhas 28-30, 354-365) as constantes e a função de classificação, hoje só usadas por i9Logic mas conceitualmente genéricas (comparam "saldo físico/externo" contra "saldo de comparação", sem nada específico de i9Logic no corpo):

```python
LIMIAR_ALERTA_ABSOLUTO = 5
LIMIAR_ALERTA_PERCENTUAL = 0.10
TOLERANCIA_ZERO = 0.5

def classificar_divergencia(qtd_referencia: float, qtd_comparacao: float) -> str:
    ...  # corpo idêntico ao de core/i9logic.py hoje
```

`core/i9logic.py` passa a importar de lá (`from core.estoque_divergencia import classificar_divergencia, TOLERANCIA_ZERO`), sem mudar nenhum comportamento — é só mover o código pra um lugar neutro, com teste de regressão confirmando que o comportamento não mudou.

### i9Logic — só um ajuste pequeno de rota, resto já existe

A UI (ver Frontend) consome as rotas já existentes:
- `POST /api/integrations/i9logic/divergencias/<id>/ajustar` (`hermes_agents/routes/i9logic.py:70-85`)
- `POST /api/integrations/i9logic/divergencias/<id>/resolver` (`:61-67`)

`GET /api/integrations/i9logic/divergencias` (`:53-58`) já existe mas hoje ignora querystring — sempre chama `listar_itens_para_revisao()` sem argumento (equivalente a `revisado=False`, o default da função). Único ajuste de backend desta seção: ler `request.args.get("revisado", "false")` e repassar como bool pra `listar_itens_para_revisao(revisado)` — a função já aceita o parâmetro, só a rota não lê. Permissão das três rotas já é `estoque.ver` (GET) / `estoque.editar` (POST) — usar o mesmo par nas rotas novas de Shopee, por consistência.

### Shopee — novo módulo `hermes_agents/shopee/divergencia.py`

Nova tabela (criada em `_ensure_tables` do módulo, mesmo padrão de `i9logic_estoque_snapshot`):

```sql
CREATE TABLE IF NOT EXISTS shopee_estoque_snapshot (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(50) NOT NULL,
    loja_id INT NOT NULL REFERENCES lojas(id),
    item_id_shopee VARCHAR(100),
    qtd_shopee DECIMAL(12,3),
    qtd_athena DECIMAL(12,3),
    divergencia DECIMAL(12,3) GENERATED ALWAYS AS (qtd_athena - qtd_shopee) STORED,
    data_coleta TIMESTAMP DEFAULT NOW(),
    revisado BOOLEAN DEFAULT FALSE,
    UNIQUE(sku, loja_id, data_coleta)
)
```

Mais simples que a de i9Logic — Shopee já resolve `sku`↔`loja_id`↔`item_id` direto via `anuncios` (colunas `sku`, `shop_id`, `anuncio_id`, `marketplace='shopee'` — `anuncios.shop_id` casa com `lojas.shopee_shop_id`), sem precisar de tabela de-para manual.

Funções (mesmo formato do módulo i9Logic, pra manter os dois times legíveis lado a lado):

```python
def executar_coleta_loja(loja_id: int) -> dict:
    """Chama shopee.products.sync_all_items(loja_id) (ja existente — traz
    stock_info_v2.summary_info de todos os itens da loja), casa cada item
    com o sku via anuncios, le o saldo Athena atual (core.estoque_saldos.saldo)
    e grava um snapshot por sku com a divergencia calculada."""

def listar_itens_para_revisao(loja_id: int, revisado: bool = False) -> list:
    """Mesma forma de core.i9logic.listar_itens_para_revisao, filtrado por loja_id
    (Shopee e' inerentemente multi-loja, i9Logic filtra por filial dentro
    da loja_athena — a assinatura difere nisso, o resto e' identico)."""

def marcar_revisado(snapshot_id: int) -> dict:
    """Identico em forma a core.i9logic.marcar_revisado."""

def aplicar_ajuste_divergencia(snapshot_id: int, usuario_id=None, usuario_nome="") -> dict:
    """Le o snapshot, chama core.estoque.ajustar_absoluto(sku, loja_nome, qtd_shopee, ...)
    — mesma funcao que core.i9logic.aplicar_ajuste_divergencia e
    shopee.estoque_rapido.atualizar_celula_estoque_rapido ja usam. Mesma guarda
    de frescor (so' aplica se for o snapshot mais recente pra aquele sku/loja)
    que a versao i9Logic ja implementa — copiar a logica, adaptando pra loja_id
    em vez de loja_athena (texto)."""
```

Diferente do i9Logic (que zera silenciosamente sem alertar quando o produto não aparece no feed contábil), aqui: se `sync_all_items` não retornar o item pra aquele SKU (ex.: produto pausado/deletado na Shopee), o snapshot não é gravado para esse SKU — não existe "gravar zero com alerta", porque a ausência já é informação suficiente (produto não está mais anunciado).

### Rotas novas (`hermes_agents/routes/shopee.py`, ao lado das rotas de `/estoque-rapido`)

```
GET  /api/shopee/divergencias?loja_id=&revisado=false
POST /api/shopee/divergencias/<id>/resolver
POST /api/shopee/divergencias/<id>/ajustar
POST /api/shopee/divergencias/coletar   (dispara executar_coleta_loja pra todas as lojas Shopee ativas — usado pelo botão manual e pelo job)
```

Permissão: `estoque.ver` pra GET, `estoque.editar` pra `resolver`/`ajustar` (mesmo par usado pelas rotas equivalentes de i9Logic).

### Job de coleta (`hermes_agents/core/scheduler.py`)

Nova entrada ao lado do job de coleta i9Logic já existente, chamando `shopee.divergencia.executar_coleta_loja` pra cada loja retornada por `core.lojas.listar_lojas_shopee()`. Frequência: mesma do job i9Logic (confirmar valor lendo o scheduler existente ao implementar — não decidido aqui, segue o precedente já em produção).

## Frontend

### Nova seção em `web/src/app/estoque/discrepancias/page.tsx`

Adicionada abaixo das duas seções existentes (Por loja / Por operador), com um cabeçalho próprio "Divergência de Saldo" e subtítulo explicando a comparação. Usa o tipo de loja selecionada no seletor global do app (mesmo hook/contexto que `web/src/app/estoque/page.tsx` já usa — `useStore()`, `tipoLojaSelecionada`) pra decidir a fonte:

- **Física**: chama as rotas i9Logic existentes. Tabela: SKU, saldo Athena (disponível), saldo físico i9Logic, divergência, classificação (badge sem_acao/registrado/alerta — cores neutra/âmbar/vermelho, mesmo padrão semântico do DESIGN.md), data da coleta, botões "Ajustar" e "Marcar revisado".
- **Virtual**: mesma tabela, mesmas colunas, trocando "i9Logic" por "Shopee" nos rótulos, consumindo as rotas novas de `/api/shopee/divergencias`.
- Nenhuma loja selecionada: mensagem "Selecione uma loja no topo da página" (mesmo texto/padrão já usado no hub `/estoque`).
- Botão "Verificar agora" na seção, chamando a rota de coleta manual (i9Logic já tem esse padrão via `_disparar_coleta_se_necessario`; Shopee usa a rota `/coletar` nova) — não substitui o job periódico, só permite forçar uma atualização fora do ciclo.

### `web/src/lib/api.ts`

Funções novas: `i9logicListarDivergencias`, `i9logicResolverDivergencia`, `i9logicAjustarDivergencia` (consumindo rotas já existentes, nunca chamadas do frontend hoje) e `shopeeListarDivergencias`, `shopeeResolverDivergencia`, `shopeeAjustarDivergencia`, `shopeeColetarDivergencias` (rotas novas).

## Fora de escopo

- Ajustar a Shopee pra bater com o Athena (decidido: só a direção Athena←Shopee).
- Coleta sob demanda como único modo (decidido: periódica, com botão manual complementar).
- Unificar a tabela de snapshot i9Logic e Shopee num schema só — schemas diferentes o suficiente (de-para manual vs mapeamento direto) pra não valer a pena forçar unificação agora.
- Mexer na seção comportamental existente (Por loja / Por operador) — fica como está.
- Frequência exata do job de coleta Shopee — segue o precedente do job i9Logic já em produção, sem decisão nova aqui.

## Testes

- Backend: `classificar_divergencia` movida — teste de regressão confirmando que o comportamento não mudou (mesmos casos de teste que já existem para `core.i9logic.classificar_divergencia`, agora importados de `core.estoque_divergencia`). `shopee.divergencia.executar_coleta_loja`: item presente com divergência (grava snapshot classificado corretamente), item sem divergência (classificação `sem_acao`), item ausente do retorno da Shopee (não grava, não quebra), erro de API Shopee (não quebra o job, loja seguinte continua). `aplicar_ajuste_divergencia`: guarda de frescor (não aplica snapshot desatualizado), aplica corretamente via `ajustar_absoluto`. Testes de RBAC nas rotas novas seguindo o padrão já usado no projeto (`crm.ver`/`crm.criar` equivalente pra `estoque.ver`/`estoque.aprovar`).
- Frontend: verificação manual (sem backend/DB local disponível nesta sessão, mesma limitação já registrada em specs anteriores) cobrindo: seção mostra i9Logic com loja física selecionada, Shopee com loja virtual, troca de fonte ao trocar o tipo de loja no seletor, ajustar/marcar revisado atualizam a lista, botão "Verificar agora" dispara coleta.
