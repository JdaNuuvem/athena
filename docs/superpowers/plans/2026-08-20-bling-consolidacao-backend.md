# Bling — Consolidação Backend (Plano 1/N) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminar as três gerações duplicadas de rotas/sync Bling hoje coexistindo no
backend, consolidando em uma única implementação por funcionalidade, e corrigir o bug de
sync de pedidos de venda quebrado — sem tirar nenhuma funcionalidade hoje em uso do ar.

**Architecture:** `bling_bp` (`routes/integrations.py`, prefixo `/api/bling`) passa a ser o
único blueprint de rotas Bling. Rotas equivalentes definidas direto em `athena_bridge.py`
("Bling Portuguese Routes") e em `integrations_bp` (geração antiga, também em
`routes/integrations.py`) são removidas. Sync de pedidos de venda passa a usar
exclusivamente `core.vendas.sincronizar_pedidos_bling()` (SSOT completo). Webhook de pedido
consolida em `/webhook/bling` (validação HMAC + roteamento por evento).

**Tech Stack:** Flask (Python), pytest, Next.js/TypeScript (só o ajuste mínimo em
`produtos/page.tsx` necessário para não quebrar com a remoção de rota).

**Spec:** `docs/superpowers/specs/2026-08-20-modulo-bling-design.md`

## Global Constraints

- Nenhuma rota hoje efetivamente usada pelo frontend pode parar de funcionar antes do
  frontend ser atualizado para apontar para a rota sobrevivente (ver Task 1).
- TDD: escrever teste, confirmar falha, implementar, confirmar passa, para cada mudança de
  comportamento (não aplica a remoções puras de código morto, que só precisam da suíte
  completa passando ao final).
- Rodar a suíte completa (`pytest hermes_agents/tests -q`) ao final de cada task antes de
  commitar.

---

### Task 1: Repontar `produtos/page.tsx` para a rota Bling sobrevivente

O único uso vivo no frontend de uma rota que será removida é `api.blingSyncProducts()` em
`web/src/app/produtos/page.tsx:160`, que chama `POST /api/bling/sync/products` (geração
antiga, `routes/integrations.py:348-361`). A rota sobrevivente equivalente é
`POST /api/bling/produtos/sincronizar` (`bling_bp`, `routes/integrations.py:833-835`), que
devolve o formato bruto de `sincronizar_produtos()` (`{"sincronizados": int, "pais_resolvidos": int, "erros": list}`)
— não o formato transformado `{"count", "errors"}` que a rota antiga devolvia (que já não
batia com o que o componente lia, `r.erros`/`r.sincronizados`/`r.erro`; a troca corrige esse
descompasso como efeito colateral).

**Files:**
- Modify: `web/src/lib/api.ts:253` (função `blingSyncProducts`)
- Modify: `web/src/app/produtos/page.tsx:160` (nenhuma mudança de lógica necessária — a
  função já lê os campos certos, só o endpoint estava errado)

**Interfaces:**
- Produces: `api.blingSyncProducts(): Promise<{ sincronizados: number; pais_resolvidos: number; erros: string[] }>`

- [ ] **Step 1: Trocar o endpoint em `api.ts`**

Em `web/src/lib/api.ts`, substituir a linha 253:

```typescript
  blingSyncProducts: () => request<{ count: number; errors: string[] }>("/api/bling/sync/products", { method: "POST" }),
```

por:

```typescript
  blingSyncProducts: () => request<{ sincronizados: number; pais_resolvidos: number; erros: string[] }>("/api/bling/produtos/sincronizar", { method: "POST" }),
```

- [ ] **Step 2: Ajustar a leitura do resultado em `produtos/page.tsx`**

Em `web/src/app/produtos/page.tsx`, a função `syncBling` (linhas 156-170) já lê
`r.erros`/`r.sincronizados`/`r.erro`. Como o novo formato não tem `erro` (singular), remover
esse ramo morto. Substituir:

```tsx
      const r = await api.blingSyncProducts() as any;
      if (r.erros && r.erros.length > 0) setError(r.erros.join("; "));
      else if (r.sincronizados !== undefined) setError(`Sincronizados: ${r.sincronizados} produtos`);
      else if (r.erro) setError(r.erro);
      load(busca, 1);
```

por:

```tsx
      const r = await api.blingSyncProducts();
      if (r.erros && r.erros.length > 0) setError(r.erros.join("; "));
      else if (r.sincronizados !== undefined) setError(`Sincronizados: ${r.sincronizados} produtos`);
      load(busca, 1);
```

- [ ] **Step 3: Checar tipos e build**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros.

Run: `cd web && npm run build`
Expected: build completo sem erros.

- [ ] **Step 4: Commit**

```bash
git add web/src/lib/api.ts web/src/app/produtos/page.tsx
git commit -m "fix: aponta sync de produtos Bling na tela de produtos pra rota v2 (bling_bp)"
```

---

### Task 2: Consolidar sync de pedidos de venda na função SSOT

Hoje existem duas implementações: `bling_erp.sincronizar_pedidos()` (grava só em `vendas`,
tabela legada) e `core.vendas.sincronizar_pedidos_bling()` (SSOT completo, grava em
`vendas_pedidos`/`vendas_itens`/`vendas_pagamentos`, já usada corretamente em
`routes/vendas.py:139-144`). A rota `bling_bp` `/vendas/sincronizar`
(`routes/integrations.py:864-871`) e a função `migrar_tudo()`
(`routes/integrations.py:669-708`, linha 693) chamam `bling_erp.sincronizar_pedidos()` com
argumentos (`pagina`, `limite`) que sua assinatura (`sincronizar_pedidos(loja_id: int = None)`)
não aceita — isso gera `TypeError` sem tratamento, virando erro 500 sempre que essas rotas são
chamadas.

**Files:**
- Modify: `hermes_agents/routes/integrations.py:864-871` (rota `/vendas/sincronizar`)
- Modify: `hermes_agents/routes/integrations.py:669-708` (função `migrar_tudo`)
- Modify: `hermes_agents/routes/integrations.py:757-769` (bloco de import de `bling_erp` —
  remove `sincronizar_pedidos` da lista, que deixará de ser usado neste arquivo)
- Test: `hermes_agents/tests/test_bling_routes.py`

**Interfaces:**
- Consumes: `core.vendas.sincronizar_pedidos_bling(pagina: int = 1, limite: int = 100) -> dict`
  (já existe, `hermes_agents/core/vendas.py:329`, sem mudanças)

- [ ] **Step 1: Escrever o teste que expõe o bug atual**

Adicionar ao final de `hermes_agents/tests/test_bling_routes.py`:

```python
    def test_vendas_sincronizar_route_calls_ssot_function(self):
        with patch("routes.integrations.sincronizar_pedidos_bling", return_value={"sync": 3, "erros": []}) as mock_sync:
            rv = self.client.post("/api/bling/vendas/sincronizar", json={"pagina": 2, "limite": 50})
            self.assertEqual(rv.status_code, 200)
            data = json.loads(rv.data)
            self.assertEqual(data["sync"], 3)
            mock_sync.assert_called_once_with(pagina=2, limite=50)
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_bling_routes.py::TestBlingFlaskRoutes::test_vendas_sincronizar_route_calls_ssot_function -v`
Expected: FAIL — `AttributeError` ou `ImportError` (`routes.integrations` ainda não expõe
`sincronizar_pedidos_bling`), ou `TypeError` se a rota antiga for exercida como está.

- [ ] **Step 3: Trocar a função usada na rota `/vendas/sincronizar`**

Em `hermes_agents/routes/integrations.py`, no bloco de import de `bling_erp` (linhas
757-769), remover `sincronizar_pedidos` da lista de nomes importados e adicionar o import da
função SSOT logo abaixo do bloco:

```python
from bling_erp import (
    status as bling_status_fn, get_auth_url, exchange_code,
    listar_produtos, listar_produtos_agrupados, criar_produto, atualizar_produto, deletar_produto,
    atualizar_situacao_produtos,
    listar_depositos, obter_saldo_deposito, atualizar_estoque_deposito,
    listar_pedidos, listar_contas_receber, listar_notas_fiscais,
    get_nfe_detail, get_nfe_xml,
    listar_contatos, get_contato, listar_categorias, get_categoria,
    get_pedido_detalhe, listar_contas_pagar, listar_formas_pagamento,
    resumo_vendas, sincronizar_produtos,
    listar_webhooks, criar_webhook, deletar_webhook,
    listar_notificacoes, confirmar_leitura_notificacao,
)
from core.vendas import sincronizar_pedidos_bling
```

Substituir a rota (linhas 864-871):

```python
@bling_bp.route("/vendas/sincronizar", methods=["POST"])
def api_sincronizar_pedidos():
    dados = request.get_json(silent=True) or {}
    return jsonify(sincronizar_pedidos(
        loja_id=dados.get("loja_id"),
        pagina=dados.get("pagina", 1),
        limite=dados.get("limite", 100)
    ))
```

por:

```python
@bling_bp.route("/vendas/sincronizar", methods=["POST"])
def api_sincronizar_pedidos():
    dados = request.get_json(silent=True) or {}
    return jsonify(sincronizar_pedidos_bling(
        pagina=dados.get("pagina", 1),
        limite=dados.get("limite", 100),
    ))
```

- [ ] **Step 4: Rodar o teste e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_bling_routes.py::TestBlingFlaskRoutes::test_vendas_sincronizar_route_calls_ssot_function -v`
Expected: PASS

- [ ] **Step 5: Corrigir a mesma chamada quebrada em `migrar_tudo()`**

Em `hermes_agents/routes/integrations.py`, a função `migrar_tudo()` (linha 669) importa e
chama `sincronizar_pedidos` do mesmo jeito quebrado. Substituir a linha 672:

```python
    from bling_erp import sincronizar_produtos, sincronizar_pedidos
```

por:

```python
    from bling_erp import sincronizar_produtos
    from core.vendas import sincronizar_pedidos_bling
```

E a linha 693:

```python
    resultados["vendas"] = seguro(lambda: sincronizar_pedidos(pagina=1, limite=100), "vendas")
```

por:

```python
    resultados["vendas"] = seguro(lambda: sincronizar_pedidos_bling(pagina=1, limite=100), "vendas")
```

Note que `seguro()` já lê `r.get("sincronizados") or r.get("sync") or ...` — o retorno de
`sincronizar_pedidos_bling` usa a chave `"sync"` (ver `core/vendas.py:355`), já coberta.

- [ ] **Step 6: Rodar a suíte completa de testes Bling**

Run: `cd hermes_agents && python -m pytest tests/test_bling_routes.py tests/test_bling_erp.py tests/test_vendas.py -v`
Expected: todos PASS.

- [ ] **Step 7: Commit**

```bash
git add hermes_agents/routes/integrations.py hermes_agents/tests/test_bling_routes.py
git commit -m "fix: sync de pedidos de venda Bling usa funcao SSOT em vez da versao quebrada/legada"
```

---

### Task 3: Remover `bling_erp.sincronizar_pedidos` (código morto após Task 2)

Depois da Task 2, nenhum caller de produção usa mais `bling_erp.sincronizar_pedidos()`. Ela
só grava na tabela legada `vendas` e é a fonte do bug de assinatura já corrigido. Removê-la
evita que uma futura rota volte a apontar pra versão errada.

**Files:**
- Modify: `hermes_agents/bling_erp.py:461-486` (função `sincronizar_pedidos` e o que estiver
  logo antes/depois dela — confirmar limites exatos ao editar, usando a assinatura
  `def sincronizar_pedidos(loja_id: int = None) -> dict:` como âncora de início)

- [ ] **Step 1: Confirmar que não sobra nenhuma referência**

Run: `cd hermes_agents && grep -rn "sincronizar_pedidos\b" --include="*.py" .`
Expected: nenhuma ocorrência fora da própria definição em `bling_erp.py` (as chamadas em
`routes/integrations.py` já foram trocadas na Task 2; `core/vendas.py` define
`sincronizar_pedidos_bling`, nome diferente, não conflita).

- [ ] **Step 2: Remover a função**

Em `hermes_agents/bling_erp.py`, remover o bloco inteiro de `def sincronizar_pedidos(loja_id: int = None) -> dict:`
até a linha em branco antes da próxima função (`sincronizar_pedidos` termina onde a função
seguinte de `bling_erp.py` começa — confirmar lendo o arquivo antes de cortar, para não levar
nem deixar linhas da função vizinha).

- [ ] **Step 3: Rodar a suíte completa**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: todos PASS (nenhum teste hoje exercita `bling_erp.sincronizar_pedidos` diretamente
— confirmado por busca prévia, sem hits em `tests/`).

- [ ] **Step 4: Commit**

```bash
git add hermes_agents/bling_erp.py
git commit -m "refactor: remove bling_erp.sincronizar_pedidos (versao legada, substituida pela SSOT)"
```

---

### Task 4: Remover terceira geração de rotas Bling direto em `athena_bridge.py`

Existe um bloco "Bling Portuguese Routes" em `hermes_agents/athena_bridge.py:607-771`
definindo rotas `/api/bling/*` diretamente no `app` Flask — uma TERCEIRA implementação
paralela às de `bling_bp`, incluindo uma versão própria e divergente de
`/api/bling/produtos/agrupados` (linhas 642-665, agrupa produtos por substring do nome, sem
usar a hierarquia pai/filho de `bling_erp.listar_produtos_agrupados`, que é o que `bling_bp`
usa no endpoint de mesmo nome). Como as URLs colidem com as de `bling_bp` (já registrado
antes, em `athena_bridge.py:255`), o comportamento de qual delas responde depende da ordem de
resolução de rota do Werkzeug — risco real de comportamento não determinístico, mesmo padrão
de bug já documentado no comentário de `athena_bridge.py:711-719` sobre o DANFE.

**Files:**
- Modify: `hermes_agents/athena_bridge.py:607-771` (bloco inteiro "Bling Portuguese Routes")
- Test: `hermes_agents/tests/test_bling_routes.py`

- [ ] **Step 1: Escrever teste que confirma `bling_bp` responde por `/produtos/agrupados` usando a lógica correta**

Adicionar a `hermes_agents/tests/test_bling_routes.py`:

```python
    def test_produtos_agrupados_usa_hierarquia_bling_erp(self):
        with patch("routes.integrations.listar_produtos_agrupados", return_value={"grupos": [], "avulsos": []}) as mock_fn:
            rv = self.client.get("/api/bling/produtos/agrupados")
            self.assertEqual(rv.status_code, 200)
            mock_fn.assert_called_once()
```

- [ ] **Step 2: Rodar e confirmar que falha ou é ambíguo**

Run: `cd hermes_agents && python -m pytest tests/test_bling_routes.py::TestBlingFlaskRoutes::test_produtos_agrupados_usa_hierarquia_bling_erp -v`
Expected: neste teste isolado (só `bling_bp` registrado, sem `athena_bridge.py`) já deve
passar — o teste serve de trava de regressão para depois da Task 4, não de reprodução do bug
de colisão em si (que só existe com a app completa rodando).

- [ ] **Step 3: Remover o bloco de rotas duplicado**

Em `hermes_agents/athena_bridge.py`, remover integralmente as linhas 607 a 771 (do comentário
`# ── Bling Portuguese Routes (alias para rotas inglesas existentes) ──` até a linha em
branco antes de `# Workflows Cross-Agent`), incluindo o comentário "ponytail" nas linhas
711-719 (a decisão que ele documenta — manter a versão de `routes/integrations.py` para
DANFE — já era a direção certa e continua válida, só o texto do comentário fica órfão sem o
bloco ao redor).

- [ ] **Step 4: Rodar a suíte completa**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: todos PASS.

- [ ] **Step 5: Smoke test manual do app completo**

Run: `cd hermes_agents && python -c "import athena_bridge"`
Expected: importa sem erro (garante que a remoção não deixou referência solta, ex. função
usada em outro lugar do arquivo).

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/athena_bridge.py hermes_agents/tests/test_bling_routes.py
git commit -m "refactor: remove terceira geracao de rotas Bling duplicadas em athena_bridge.py"
```

---

### Task 5: Remover geração antiga de rotas Bling em `routes/integrations.py` (`integrations_bp`)

Restam as rotas Bling do blueprint `integrations_bp` (a geração "v1", linhas 247-489 de
`routes/integrations.py`), todas com equivalente funcional em `bling_bp`. Nenhuma delas é
usada pelo frontend hoje (confirmado: só `blingSyncProducts`, já repontada na Task 1; as
outras funções `blingSync`, `blingSyncOrders`, `blingSyncInvoices`, `blingSyncReceivables`,
`blingProducts`, `blingOrders`, `blingInvoices`, `blingStatus` em `web/src/lib/api.ts` não são
chamadas em nenhuma página).

**Files:**
- Modify: `hermes_agents/routes/integrations.py:247-489` (bloco de rotas `/api/bling/*` do
  `integrations_bp`)
- Modify: `web/src/lib/api.ts:252-267` (remove as funções mortas correspondentes)

**Interfaces:**
- Consumes: nenhuma — bloco isolado, sem outras funções do arquivo dependendo dele.

- [ ] **Step 1: Confirmar que o bloco realmente não é mais referenciado**

Run: `grep -rn "blingSync\(\)\|blingSyncOrders\|blingSyncInvoices\|blingSyncReceivables\|blingProducts\(\)\|blingOrders\(\)\|blingInvoices\(\)\|blingStatus\(\)" web/src/app`
Expected: nenhuma ocorrência (já confirmado antes de escrever este plano; reconfirmar aqui
porque o código pode ter mudado entre o levantamento e a execução).

- [ ] **Step 2: Remover o bloco de rotas em `routes/integrations.py`**

Remover as linhas 247 a 489 (de `@integrations_bp.route("/api/bling/auth", ...)` até o fim da
função `bling_categories()`, imediatamente antes do comentário
`# --- Entidades SSOT: Vincular Clientes / Migrar Fornecedores ---`).

- [ ] **Step 3: Remover as funções mortas de `api.ts`**

Em `web/src/lib/api.ts`, remover as linhas 252-260 (bloco `blingStatus` até `blingInvoices`)
e a linha 253 relacionada a `blingSync`, mantendo apenas o que ainda for referenciado em
código vivo (confirmar com o Step 1 antes de decidir o que sobra — a essa altura só
`blingSyncProducts`, já reapontada na Task 1, deve permanecer).

- [ ] **Step 4: Checar tipos do frontend**

Run: `cd web && npx tsc --noEmit`
Expected: sem erros (se algum tipo/import ficar órfão, o compilador aponta).

- [ ] **Step 5: Rodar a suíte completa do backend**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: todos PASS.

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/routes/integrations.py web/src/lib/api.ts
git commit -m "refactor: remove geracao antiga de rotas Bling (integrations_bp), so bling_bp sobrevive"
```

---

### Task 6: Consolidar webhook de pedido em `/webhook/bling`

Hoje três endpoints recebem webhook de pedido Bling: `/webhook/bling/pedido`
(`webhooks_bp`, chama `bling_erp.webhook_bling_pedido`), `/webhook/bling/pedido/v2`
(`webhooks_bp`, lógica inline duplicada) e `/webhook/bling` (`webhook_bp`, valida HMAC e
roteia por tipo de evento via `bling_erp.processar_evento_webhook`). Confirmado por leitura:
`processar_evento_webhook` já cobre o mesmo efeito de `webhook_bling_pedido` (grava venda +
enfileira produção via `adicionar_pedido_producao`, ver `bling_erp.py:793-795`) — é superset,
não perda de funcionalidade. `bling_erp.registrar_webhook()` (linha 532) hoje aponta o valor
padrão de URL para `/webhook/bling/pedido` (o endpoint legado, sem HMAC) — esse é o bug raiz
que faz o endpoint legado parecer "o que está registrado": ele só está registrado porque
ninguém nunca passou uma URL explícita ao chamar `registrar_webhook`.

**Files:**
- Modify: `hermes_agents/bling_erp.py:531-535` (`registrar_webhook`, corrige URL padrão)
- Modify: `hermes_agents/bling_erp.py:502-528` (remove `webhook_bling_pedido`, agora sem uso)
- Modify: `hermes_agents/routes/webhooks.py:18-54` (remove as rotas `/webhook/bling/pedido` e
  `/webhook/bling/pedido/v2`)
- Test: `hermes_agents/tests/test_bling_erp.py`

**Interfaces:**
- Consumes: `bling_erp.processar_evento_webhook(evento: str, payload: dict) -> dict` (já
  existe, sem mudanças, usada por `webhook_bp` em `routes/webhooks.py:74-99`)

- [ ] **Step 1: Escrever o teste do novo default de `registrar_webhook`**

Adicionar a `hermes_agents/tests/test_bling_erp.py`:

```python
    def test_registrar_webhook_default_aponta_para_endpoint_com_hmac(self):
        with patch("bling_erp._request", return_value={"data": {"id": 1}}) as mock_request:
            bling_erp.registrar_webhook(tipo="pedido")
            _, kwargs_ou_args = mock_request.call_args, None
            payload = mock_request.call_args[0][1]
            self.assertEqual(payload["webhook"]["url"], f"https://{bling_erp.BLING_DOMAIN}/webhook/bling")
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_bling_erp.py::TestBlingErp::test_registrar_webhook_default_aponta_para_endpoint_com_hmac -v`
Expected: FAIL — asserção não bate (`.../webhook/bling/pedido` != `.../webhook/bling`).

Se o nome da classe de teste em `test_bling_erp.py` for diferente de `TestBlingErp`, usar o
nome real encontrado no arquivo ao rodar este comando.

- [ ] **Step 3: Corrigir o default em `registrar_webhook`**

Em `hermes_agents/bling_erp.py`, substituir a linha 532:

```python
    webhook_url = url or f"https://{BLING_DOMAIN}/webhook/bling/pedido"
```

por:

```python
    webhook_url = url or f"https://{BLING_DOMAIN}/webhook/bling"
```

- [ ] **Step 4: Rodar o teste e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_bling_erp.py::TestBlingErp::test_registrar_webhook_default_aponta_para_endpoint_com_hmac -v`
Expected: PASS

- [ ] **Step 5: Remover `webhook_bling_pedido` de `bling_erp.py`**

Remover o bloco `def webhook_bling_pedido(payload: dict, loja_id: int = None) -> dict:`
completo (linhas 502-528, até a linha em branco antes de `def registrar_webhook`).

- [ ] **Step 6: Remover as rotas legadas de `routes/webhooks.py`**

Em `hermes_agents/routes/webhooks.py`, remover as linhas 18-21 (`bling_pedido_webhook`) e
30-54 (comentário + `bling_pedido_webhook_v2`), mantendo as demais rotas do arquivo
(`whatsapp_webhook`, `shopee_pedido_webhook`) intactas e na mesma ordem relativa.

- [ ] **Step 7: Rodar a suíte completa**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: todos PASS.

- [ ] **Step 8: Registrar novamente o webhook em produção (ação manual, fora do código)**

Este passo não é código — é uma ação operacional necessária após o deploy: como o endpoint
`/webhook/bling/pedido` deixa de existir, se ele estiver de fato cadastrado no painel do Bling
como callback ativo, os webhooks vão parar de chegar até que alguém chame
`POST /api/bling/webhook/registrar` (rota existente, `routes/integrations.py:279-283`) para
registrar `/webhook/bling` como novo callback. Deixar anotado no PR/commit para o usuário
confirmar isso após o deploy.

- [ ] **Step 9: Commit**

```bash
git add hermes_agents/bling_erp.py hermes_agents/routes/webhooks.py hermes_agents/tests/test_bling_erp.py
git commit -m "fix: consolida webhook de pedido Bling em /webhook/bling (HMAC), corrige default de registrar_webhook"
```

---

### Task 7: Regressão final

**Files:**
- Test: `hermes_agents/tests/test_bling_routes.py`

- [ ] **Step 1: Escrever teste confirmando que as rotas removidas não existem mais**

Adicionar a `hermes_agents/tests/test_bling_routes.py`, dentro da classe de teste que registra
só `bling_bp` — para essas rotas específicas o teste precisa ser feito contra uma app que
registra TODOS os blueprints Bling remanescentes, então criar um teste separado:

```python
class TestBlingRotasRemovidas(unittest.TestCase):
    """Confirma que as rotas duplicadas removidas nao respondem mais."""

    @classmethod
    def setUpClass(cls):
        from flask import Flask
        from routes.integrations import bling_bp
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(bling_bp)
        cls.client = app.test_client()

    def test_rota_antiga_sync_products_nao_existe(self):
        rv = self.client.post("/api/bling/sync/products")
        self.assertEqual(rv.status_code, 404)

    def test_rota_antiga_sync_orders_nao_existe(self):
        rv = self.client.post("/api/bling/sync/orders")
        self.assertEqual(rv.status_code, 404)

    def test_rota_nova_produtos_sincronizar_existe(self):
        with patch("routes.integrations.sincronizar_produtos", return_value={"sincronizados": 0, "erros": []}):
            rv = self.client.post("/api/bling/produtos/sincronizar")
            self.assertEqual(rv.status_code, 200)
```

- [ ] **Step 2: Rodar e confirmar que passa**

Run: `cd hermes_agents && python -m pytest tests/test_bling_routes.py -v`
Expected: todos PASS, incluindo a nova classe `TestBlingRotasRemovidas`.

- [ ] **Step 3: Rodar a suíte inteira do projeto**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: todos PASS, nenhuma regressão em outros módulos.

- [ ] **Step 4: Build do frontend**

Run: `cd web && npm run build`
Expected: build completo sem erros.

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/tests/test_bling_routes.py
git commit -m "test: trava de regressao confirmando remocao das rotas Bling duplicadas"
```
