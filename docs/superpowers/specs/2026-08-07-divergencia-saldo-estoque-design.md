# Estoque — Divergência de Saldo (i9Logic + Shopee)

**Data:** 2026-08-07
**Status:** Aprovado para planejamento

## Contexto

Pedido: lapidar `/estoque/discrepancias` pra comparar saldo real contra o sistema externo — loja física contra i9Logic (ou nosso estoque), loja online contra Shopee.

A tela atual `/estoque/discrepancias` (`web/src/app/estoque/discrepancias/page.tsx`) cobre outra coisa — audita comportamento humano (saídas grandes aprovadas, transferências com discrepância, faltas em contagem cíclica), agregado por loja e por operador, via `GET /api/estoque/relatorio-discrepancias`. Fica intocada. Esta spec adiciona uma seção nova, separada, na mesma página: **Divergência de Saldo**.

### O que já existe (i9Logic)

`hermes_agents/core/i9logic.py` tem um sistema de reconciliação maduro, mas resolve um problema adjacente ao pedido: a rota `GET /api/integrations/i9logic/divergencias` (nunca chamada pelo frontend hoje) mostra `qtd_contabil - qtd_fisico` — a divergência **entre os dois feeds do próprio i9Logic** (físico e contábil), não envolve o saldo do Athena. Quem de fato compara Athena contra i9Logic é `comparar_com_athena(sku, loja)`, mas só processa um SKU por chamada — não serve pra listar uma tela inteira.

Peças reaproveitáveis que já existem e que esta spec usa sem modificar:
- `snapshot_mais_recente(filial_id)` — lê o snapshot físico mais recente de uma filial (usado hoje pela tela de Estoque Físico, `EstoqueFisicoI9Logic.tsx`).
- `_disparar_coleta_se_necessario(filial_id, data_coleta)` — lazy-trigger-on-read: se o snapshot está ausente ou mais velho que `FRESCOR_MAXIMO_MINUTOS` (30) e nenhuma coleta já roda pra aquela filial, dispara uma `threading.Thread(daemon=True)` em background e retorna na hora; quem chamou faz polling até o status virar "pronto". Hoje é disparado por `estoque_fisico_por_loja()`, consumida pela tela de Estoque Físico do dia a dia — **não** pela tela de divergências.
- `classificar_divergencia(qtd_referencia, qtd_comparacao)` + `TOLERANCIA_ZERO`/`LIMIAR_ALERTA_ABSOLUTO`/`LIMIAR_ALERTA_PERCENTUAL` — regra de classificação, genérica (não tem nada específico de i9Logic no corpo).
- `core.estoque.ajustar_absoluto(sku, loja, quantidade_absoluta, motivo, usuario_id, usuario_nome, ip, dispositivo)` — aplica um saldo absoluto no Athena via ledger formal. Já é a mesma função usada por `aplicar_ajuste_divergencia` do i9Logic e por `atualizar_celula_estoque_rapido` do Estoque Rápido Shopee.
- `core.estoque_saldos.saldo(sku, loja, tipo="disponivel")` — lê o saldo atual do Athena (por nome de loja, texto).

### O que não existe (Shopee)

Nada — sem tabela de snapshot, sem comparação, sem coleta.

Peça reaproveitável do lado Shopee: `shopee.products.sync_all_items(loja_id) -> list[dict]` já devolve, por item anunciado, `{item_id, sku, name, status, stock, reserved, price}` — o `sku` já vem resolvido pela própria API Shopee (via `item_sku`, com fallback pro `item_id` como string), sem precisar de tabela de-para nem join com `anuncios`.

## Decisões (fechadas com o usuário durante o brainstorming)

- i9Logic e Shopee entram juntos nesta spec (não em fases separadas).
- **i9Logic**: nova função em lote que compara Athena contra o saldo físico i9Logic (não a divergência interna físico/contábil que a rota existente expõe) — reaproveitando `snapshot_mais_recente` + `saldo()` + `classificar_divergencia`, sem tocar nas tabelas/rotas existentes de i9Logic.
- Ação de resolução da divergência: **ajustar o Athena pra bater com o saldo externo** (i9Logic físico ou Shopee) — mesma direção nos dois lados.
- Coleta Shopee: **mesmo mecanismo lazy-trigger-on-read do i9Logic** (não sob demanda "bloqueia a tela esperando a API"). Como não existe hub de estoque Shopee equivalente ao físico pra disparar isso organicamente, o disparo fica na própria rota de divergências Shopee.
- A seção nova mostra a fonte certa automaticamente conforme o tipo da loja selecionada no seletor global do app (mesmo padrão já usado no hub `/estoque`, que decide entre `EstoqueFisicoI9Logic` e `EstoqueRapidoVirtual`): loja física → divergências Athena×i9Logic; loja virtual → divergências Athena×Shopee.

## Backend

### Módulo compartilhado: `hermes_agents/core/estoque_divergencia.py`

Extrai de `core/i9logic.py` (linhas 28-30, 354-365) as constantes e a função de classificação:

```python
LIMIAR_ALERTA_ABSOLUTO = 5
LIMIAR_ALERTA_PERCENTUAL = 0.10
TOLERANCIA_ZERO = 0.5

def classificar_divergencia(qtd_referencia: float, qtd_comparacao: float) -> str:
    ...  # corpo idêntico ao de core/i9logic.py hoje
```

`core/i9logic.py` passa a importar de lá (`from core.estoque_divergencia import classificar_divergencia, TOLERANCIA_ZERO, LIMIAR_ALERTA_ABSOLUTO, LIMIAR_ALERTA_PERCENTUAL`), sem mudar nenhum comportamento — é só mover o código pra um lugar neutro. Teste de regressão confirma que `core.i9logic.classificar_divergencia` (agora um re-export) continua se comportando igual.

### i9Logic — nova função em lote, nada existente é tocado

Nova função em `core/i9logic.py`, ao lado de `comparar_com_athena` (não substitui essa função — ela continua existindo pra consulta pontual de 1 sku):

```python
def listar_divergencias_athena(loja_athena: str) -> dict:
    """Modo monitoramento continuo EM LOTE — mesmo calculo de
    comparar_com_athena(), mas pra todos os skus de uma loja de uma vez,
    usando o snapshot fisico mais recente da filial em vez de uma query por
    sku. Dispara o mesmo lazy-trigger que a tela de Estoque Fisico usa —
    esta tela nao tem coleta propria, so' consome o que a tela de Estoque
    Fisico ja mantem atualizado."""
    from core.estoque_saldos import saldo
    id_i9logic = buscar_id_i9logic("filial", loja_athena)
    if id_i9logic is None:
        return {"erro": f"mapeamento de filial i9Logic nao encontrado para a loja '{loja_athena}'"}
    filial_id = int(id_i9logic)
    data_coleta, itens = snapshot_mais_recente(filial_id)
    processando = _disparar_coleta_se_necessario(filial_id, data_coleta)
    divergencias = []
    for item in itens:
        sku = item.get("sku_athena")
        if not sku:
            continue
        qtd_fisico = float(item.get("qtd") or 0)
        disponivel_athena = saldo(sku, loja_athena, "disponivel")
        divergencias.append({
            "sku": sku,
            "descricao": item.get("descricao"),
            "disponivel_athena": disponivel_athena,
            "qtd_fisico_i9logic": qtd_fisico,
            "divergencia": round(disponivel_athena - qtd_fisico, 3),
            "classificacao": classificar_divergencia(qtd_fisico, disponivel_athena),
        })
    return {
        "ok": True,
        "status": "processando" if processando else "pronto",
        "filial_i9logic": filial_id,
        "data_coleta": data_coleta.isoformat() if data_coleta else None,
        "data": divergencias,
    }
```

Ação de ajuste reaproveita `aplicar_ajuste_divergencia` já existente — mas essa função hoje só aceita `snapshot_id` (um registro específico do snapshot i9Logic-interno), não `(sku, loja)`. Como `listar_divergencias_athena` não tem `snapshot_id` (calcula em memória, não grava nada novo), a ação de ajuste pra esta seção chama `core.estoque.ajustar_absoluto(sku, loja_athena, qtd_fisico_i9logic, motivo="ajuste_inventario", ...)` diretamente — mais simples que reusar `aplicar_ajuste_divergencia` (que existe pra outro fluxo, o de revisão do snapshot i9Logic-interno). "Marcar revisado" nesta seção não tem uma tabela própria pra marcar (não há um snapshot dedicado a esta comparação) — não existe estado "revisado" pra Athena×i9Logic; a única ação disponível é "Ajustar". Isso é uma assimetria real com o lado Shopee (que tem tabela própria e portanto pode marcar revisado) — documentada, não escondida.

### Rota nova (`hermes_agents/routes/i9logic.py`, ao lado de `/comparar`)

```
GET /api/integrations/i9logic/divergencias-athena?loja=
```

Chama `listar_divergencias_athena(loja)`, permissão `estoque.ver`. Rota nova em vez de reaproveitar `/divergencias` — nomes diferentes porque são conceitos diferentes (divergência i9Logic-interna vs divergência Athena×i9Logic), reaproveitar o mesmo path esconderia a diferença.

Ação de ajuste: rota nova `POST /api/integrations/i9logic/divergencias-athena/ajustar`, corpo `{sku, loja}`, chama `ajustar_absoluto` (ver acima). Permissão `estoque.editar`.

### Shopee — novo módulo `hermes_agents/shopee/divergencia.py`

Nova tabela, guardando só o dado externo bruto — a comparação com Athena é sempre calculada ao vivo na leitura (mesmo princípio do i9Logic: o saldo Athena muda a cada venda, "congelar" ele no snapshot ficaria desatualizado rápido demais pra ser confiável):

```sql
CREATE TABLE IF NOT EXISTS shopee_estoque_snapshot (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(50) NOT NULL,
    loja_id INT NOT NULL REFERENCES lojas(id),
    item_id_shopee VARCHAR(100),
    qtd_shopee DECIMAL(12,3),
    data_coleta TIMESTAMP DEFAULT NOW(),
    revisado BOOLEAN DEFAULT FALSE,
    UNIQUE(sku, loja_id, data_coleta)
)
```

Funções (mesma forma dos pares de i9Logic, pra manter os dois módulos legíveis lado a lado):

```python
FRESCOR_MAXIMO_MINUTOS = 30  # mesmo valor do i9Logic

def executar_coleta_loja(loja_id: int) -> dict:
    """Chama shopee.products.sync_all_items(loja_id) (ja' existente) e grava
    um snapshot por sku com o saldo Shopee bruto (sem comparar com Athena
    aqui — comparacao e' sempre ao vivo na leitura, ver listar_divergencias).
    Item sem sku util (sku == str(item_id), sinal de que a Shopee nao
    devolveu item_sku de verdade) ainda e' gravado — o pareamento com Athena
    na leitura e' quem descarta se nao achar produto correspondente."""

def snapshot_mais_recente(loja_id: int):
    """Identico em forma a core.i9logic.snapshot_mais_recente — (data_coleta,
    itens) da corrida mais recente da loja, ou (None, []) se nunca coletada."""

def disparar_coleta_se_necessario(loja_id: int, data_coleta) -> bool:
    """Identico em forma a core.i9logic._disparar_coleta_se_necessario —
    mesmas constantes/lock/set/thread daemon, chave por loja_id em vez de
    filial_id."""

def listar_divergencias(loja_id: int) -> dict:
    """Le o snapshot mais recente da loja (disparando coleta se necessario),
    resolve o nome da loja, e pra cada sku compara qtd_shopee contra
    core.estoque_saldos.saldo(sku, nome_loja, "disponivel") — mesmo formato
    de retorno de core.i9logic.listar_divergencias_athena (data/status/
    data_coleta), pra o frontend tratar os dois lados de forma simetrica."""

def marcar_revisado(snapshot_id: int) -> dict:
    """Identico em forma a core.i9logic.marcar_revisado."""

def aplicar_ajuste_divergencia(snapshot_id: int, usuario_id=None, usuario_nome="") -> dict:
    """Le o snapshot (sku, qtd_shopee), resolve o nome da loja a partir de
    loja_id, chama core.estoque.ajustar_absoluto(sku, nome_loja, qtd_shopee,
    ...). Mesma guarda de frescor do i9Logic (so' aplica se for o snapshot
    mais recente pra aquele sku/loja)."""
```

### Rotas novas (`hermes_agents/routes/shopee.py`, ao lado das rotas de `/estoque-rapido`)

```
GET  /api/shopee/divergencias?loja_id=
POST /api/shopee/divergencias/<id>/resolver
POST /api/shopee/divergencias/<id>/ajustar
```

Permissão: `estoque.ver` pra GET, `estoque.editar` pra `resolver`/`ajustar` (mesmo par usado pelas rotas de i9Logic).

## Frontend

### Nova seção em `web/src/app/estoque/discrepancias/page.tsx`

Adicionada abaixo das duas seções existentes (Por loja / Por operador), cabeçalho próprio "Divergência de Saldo" com subtítulo explicando a comparação. Usa `useStore()` (`tipoLojaSelecionada`, `lojaId`, `lojas`) pra decidir a fonte, mesmo padrão do hub `/estoque`:

- **Física**: chama `GET /api/integrations/i9logic/divergencias-athena?loja=`. Tabela: SKU, descrição, saldo Athena, saldo físico i9Logic, divergência, classificação (badge sem_acao/registrado/alerta — cores neutra/âmbar/vermelho, padrão semântico do DESIGN.md), botão "Ajustar" (sem "Marcar revisado" — não existe estado de revisão nesta comparação, ver nota de assimetria no Backend). Resposta tem `status: "processando" | "pronto"` — a UI faz polling a cada 5s (mesmo `POLL_INTERVAL_MS` de `EstoqueFisicoI9Logic.tsx`) enquanto `processando`, mesmo padrão de banner informativo ("Coletando estoque atualizado... a lista atualiza sozinha").
- **Virtual**: mesma tabela, trocando "i9Logic" por "Shopee", consumindo `GET /api/shopee/divergencias?loja_id=` — também retorna `status`, mesmo padrão de polling. Aqui SIM existe "Marcar revisado" (tem tabela própria de snapshot), então os botões são "Ajustar" e "Marcar revisado", como o i9Logic-interno original.
- Nenhuma loja selecionada: mensagem "Selecione uma loja no topo da página" (mesmo texto do hub `/estoque`).

### `web/src/lib/api.ts`

Funções novas: `i9logicListarDivergenciasAthena(loja)`, `i9logicAjustarDivergenciaAthena(sku, loja)`, `shopeeListarDivergencias(lojaId)`, `shopeeResolverDivergencia(id)`, `shopeeAjustarDivergencia(id)`.

## Fora de escopo

- Ajustar a Shopee/i9Logic pra bater com o Athena (decidido: só a direção Athena←externo).
- Job cronado no scheduler pra coleta Shopee — decidido: lazy-trigger-on-read, disparado pela própria rota de divergências.
- Dar "Marcar revisado" pro lado i9Logic×Athena — não há tabela própria pra guardar esse estado nesta comparação; documentado como assimetria conhecida, não implementado.
- Unificar as tabelas/schemas de i9Logic e Shopee — propositalmente diferentes (de-para manual vs resolução direta via API).
- Mexer na seção comportamental existente (Por loja / Por operador) — fica como está.
- Mexer nas rotas/tabelas i9Logic já existentes (`/divergencias`, `/comparar`, `i9logic_estoque_snapshot`) — a comparação Athena×i9Logic é aditiva, não substitui nada.

## Testes

- Backend: `classificar_divergencia` movida — teste de regressão confirmando que `core.i9logic.classificar_divergencia` continua se comportando igual após virar re-export de `core.estoque_divergencia`.
- `core.i9logic.listar_divergencias_athena`: loja sem mapeamento de filial retorna erro claro; snapshot vazio retorna `data: []` sem quebrar; item sem `sku_athena` é ignorado (não aparece na lista); divergência e classificação calculadas corretamente comparando contra `saldo()` mockado; `status` reflete o retorno de `_disparar_coleta_se_necessario` (mock).
- `shopee.divergencia.executar_coleta_loja`: item presente grava snapshot; item com sku igual ao item_id (sem sku real) ainda é gravado (decisão: pareamento descarta na leitura, não na coleta); erro de API Shopee não quebra a coleta de outras lojas.
- `shopee.divergencia.listar_divergencias`: mesma cobertura de `listar_divergencias_athena` (dispara coleta se necessário, calcula divergência ao vivo, `status` correto).
- `aplicar_ajuste_divergencia` (Shopee): guarda de frescor (não aplica snapshot desatualizado), aplica corretamente via `ajustar_absoluto`.
- Testes de RBAC nas rotas novas (i9Logic e Shopee) seguindo o padrão já usado no projeto — usuário sem `estoque.ver`/`estoque.editar` recebe 403, função core não é chamada.
- Frontend: verificação manual (sem backend/DB local disponível nesta sessão, mesma limitação já registrada em specs anteriores) cobrindo: seção mostra i9Logic com loja física selecionada, Shopee com loja virtual, troca de fonte ao trocar o tipo de loja no seletor, polling funciona enquanto "processando", ajustar/marcar revisado atualizam a lista.
