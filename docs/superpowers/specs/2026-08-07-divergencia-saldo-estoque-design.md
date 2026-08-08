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

Mais simples que a de i9Logic — `shopee.products.sync_all_items()` já devolve `sku` resolvido por item (via `item_sku` da própria API Shopee, com fallback pro `item_id` como string), sem precisar de tabela de-para manual nem join com `anuncios`.

Funções (mesmo formato do módulo i9Logic, pra manter os dois times legíveis lado a lado):

```python
def executar_coleta_loja(loja_id: int) -> dict:
    """Resolve o nome da loja (SELECT nome FROM lojas WHERE id=$1), chama
    shopee.products.sync_all_items(loja_id) (ja existente — devolve lista de
    {item_id, sku, name, status, stock, reserved, price} por item), le o
    saldo Athena atual de cada sku via core.estoque_saldos.saldo(sku, nome_loja,
    "disponivel") e grava um snapshot por sku com a divergencia calculada."""

def listar_itens_para_revisao(loja_id: int, revisado: bool = False) -> list:
    """Mesma forma de core.i9logic.listar_itens_para_revisao, filtrado por loja_id
    (Shopee e' inerentemente multi-loja, i9Logic filtra por filial dentro
    da loja_athena — a assinatura difere nisso, o resto e' identico)."""

def marcar_revisado(snapshot_id: int) -> dict:
    """Identico em forma a core.i9logic.marcar_revisado."""

def aplicar_ajuste_divergencia(snapshot_id: int, usuario_id=None, usuario_nome="") -> dict:
    """Le o snapshot, resolve o nome da loja a partir de loja_id, chama
    core.estoque.ajustar_absoluto(sku, nome_loja, qtd_shopee, ...) — mesma
    funcao que core.i9logic.aplicar_ajuste_divergencia e
    shopee.estoque_rapido.atualizar_celula_estoque_rapido ja usam. Mesma guarda
    de frescor (so' aplica se for o snapshot mais recente pra aquele sku/loja)
    que a versao i9Logic ja implementa — copiar a logica, adaptando pra loja_id
    em vez de loja_athena (texto)."""

def snapshot_mais_recente(loja_id: int):
    """Identico em forma a core.i9logic.snapshot_mais_recente — (data_coleta,
    itens) da corrida mais recente da loja, ou (None, []) se nunca coletada."""

def disparar_coleta_se_necessario(loja_id: int, data_coleta) -> bool:
    """Identico em forma a core.i9logic._disparar_coleta_se_necessario —
    mesmas constantes/lock/set/thread daemon, chave por loja_id."""
```

Diferente do i9Logic (que zera silenciosamente sem alertar quando o produto não aparece no feed contábil), aqui: se `sync_all_items` não retornar o item pra aquele SKU (ex.: produto pausado/deletado na Shopee), o snapshot não é gravado para esse SKU — não existe "gravar zero com alerta", porque a ausência já é informação suficiente (produto não está mais anunciado).

### Rotas novas (`hermes_agents/routes/shopee.py`, ao lado das rotas de `/estoque-rapido`)

```
GET  /api/shopee/divergencias?loja_id=&revisado=false
POST /api/shopee/divergencias/<id>/resolver
POST /api/shopee/divergencias/<id>/ajustar
```

Permissão: `estoque.ver` pra GET, `estoque.editar` pra `resolver`/`ajustar` (mesmo par usado pelas rotas equivalentes de i9Logic).

### Coleta em background — mesmo mecanismo do i9Logic, não é job cronado

Investigação corrigiu a premissa inicial em dois pontos:

1. O i9Logic não tem job periódico no `scheduler.py` pra coleta de estoque físico (só tem job cronado pra sync de *pedidos*, `i9logic-pedidos`, 10 min — outra coisa). O que existe é **lazy-trigger-on-read**: `core/i9logic.py:223-287` — ao ler o snapshot, se ele estiver ausente ou mais velho que `FRESCOR_MAXIMO_MINUTOS` (30) e nenhuma coleta já estiver rodando pra aquela filial (`_coleta_em_andamento`, `_coleta_lock`), dispara uma `threading.Thread(daemon=True)` que roda a coleta completa em background e libera o lock ao final (mesmo em erro). O chamador nunca espera a thread — lê o snapshot que já tinha (ou vazio) e a tela faz polling até o status virar "pronto".
2. Quem dispara esse mecanismo pro i9Logic hoje é `estoque_fisico_por_loja()` (usada pelo hub `/estoque`, componente `EstoqueFisicoI9Logic` — a tela de estoque físico do dia a dia), **não** a rota de divergências. A tela de divergências só lê snapshots que já existem porque o operador abriu a tela de estoque físico antes. Não existe um "hub de estoque Shopee" equivalente que dispararia isso organicamente pro lado Shopee — a rota `GET /api/shopee/divergencias` precisa disparar o próprio lazy-trigger (via `disparar_coleta_se_necessario`) dentro dela mesma, retornando também `status: "processando" | "pronto"` no payload (mesmo formato que `estoque_fisico_por_loja` já retorna), pra a UI saber quando fazer polling.

Isso cumpre a decisão do usuário ("periódica em background, mesmo padrão do i9Logic — não sob demanda bloqueando a tela"): mesmo padrão de mecanismo, só que o ponto de disparo é a própria tela de divergências (não há alternativa orgânica pro lado Shopee).

## Frontend

### Nova seção em `web/src/app/estoque/discrepancias/page.tsx`

Adicionada abaixo das duas seções existentes (Por loja / Por operador), com um cabeçalho próprio "Divergência de Saldo" e subtítulo explicando a comparação. Usa o tipo de loja selecionada no seletor global do app (mesmo hook/contexto que `web/src/app/estoque/page.tsx` já usa — `useStore()`, `tipoLojaSelecionada`) pra decidir a fonte:

- **Física**: chama as rotas i9Logic existentes (`GET /api/integrations/i9logic/divergencias`). Tabela: SKU, saldo Athena (disponível), saldo físico i9Logic, divergência, classificação (badge sem_acao/registrado/alerta — cores neutra/âmbar/vermelho, mesmo padrão semântico do DESIGN.md), data da coleta, botões "Ajustar" e "Marcar revisado". Como a coleta i9Logic é dispara pela tela de estoque físico (não por esta seção), se não houver snapshot ainda a seção mostra "Nenhuma coleta ainda — abra a tela de Estoque Físico desta loja primeiro" em vez de lista vazia.
- **Virtual**: mesma tabela, mesmas colunas, trocando "i9Logic" por "Shopee" nos rótulos, consumindo `GET /api/shopee/divergencias?loja_id=`. Essa chamada já dispara a coleta em background quando necessário (ver seção de backend) — a UI usa o `status` retornado (`"processando" | "pronto"`) pra fazer polling a cada alguns segundos até ficar pronto, mesmo padrão de UX que `EstoqueFisicoI9Logic.tsx` já usa pro lado físico.
- Nenhuma loja selecionada: mensagem "Selecione uma loja no topo da página" (mesmo texto/padrão já usado no hub `/estoque`).

### `web/src/lib/api.ts`

Funções novas: `i9logicListarDivergencias`, `i9logicResolverDivergencia`, `i9logicAjustarDivergencia` (consumindo rotas já existentes, nunca chamadas do frontend hoje) e `shopeeListarDivergencias`, `shopeeResolverDivergencia`, `shopeeAjustarDivergencia` (rotas novas).

## Fora de escopo

- Ajustar a Shopee pra bater com o Athena (decidido: só a direção Athena←Shopee).
- Job cronado no scheduler pra coleta Shopee — decidido: mesmo mecanismo lazy-trigger-on-read do i9Logic, disparado pela própria rota de divergências (não há hub de estoque Shopee equivalente ao físico pra disparar organicamente).
- Unificar a tabela de snapshot i9Logic e Shopee num schema só — schemas diferentes o suficiente (mapeamento de-para manual vs resolução direta via API) pra não valer a pena forçar unificação agora.
- Mexer na seção comportamental existente (Por loja / Por operador) — fica como está.

## Testes

- Backend: `classificar_divergencia` movida — teste de regressão confirmando que o comportamento não mudou (mesmos casos de teste que já existem para `core.i9logic.classificar_divergencia`, agora importados de `core.estoque_divergencia`). `shopee.divergencia.executar_coleta_loja`: item presente com divergência (grava snapshot classificado corretamente), item sem divergência (classificação `sem_acao`), item ausente do retorno da Shopee (não grava, não quebra), erro de API Shopee (não quebra a coleta da loja seguinte). `aplicar_ajuste_divergencia`: guarda de frescor (não aplica snapshot desatualizado), aplica corretamente via `ajustar_absoluto`. `disparar_coleta_se_necessario`: não dispara segunda thread se já há coleta em andamento pra mesma loja; dispara quando snapshot ausente ou mais velho que o limite. Testes de RBAC nas rotas novas seguindo o padrão já usado no projeto (`crm.ver`/`crm.criar` equivalente pra `estoque.ver`/`estoque.editar`).
- Frontend: verificação manual (sem backend/DB local disponível nesta sessão, mesma limitação já registrada em specs anteriores) cobrindo: seção mostra i9Logic com loja física selecionada, Shopee com loja virtual, troca de fonte ao trocar o tipo de loja no seletor, ajustar/marcar revisado atualizam a lista, botão "Verificar agora" dispara coleta.
