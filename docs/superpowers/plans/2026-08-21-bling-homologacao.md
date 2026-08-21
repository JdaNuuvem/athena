# Bling — Homologação / Ambiente (Plano 5/N) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir operar o módulo Bling em ambiente de homologação sem contaminar os dados de
produção — toggle `bling.ambiente` persistido, base URL de homologação vinda de configuração
(nunca hardcoded), tokens OAuth segregados por ambiente, e coluna `ambiente` nas três tabelas
que recebem dado sincronizado do Bling (`fiscal_notas_fiscais`, `compras_pedidos`,
`vendas_pedidos`), com as rotas de leitura local filtrando `ambiente = 'producao'` por padrão.

**Architecture:** `bling_erp.py` ganha um bloco de ambiente (`get_ambiente`, `set_ambiente`,
`_base_url`, `_chave_token`) e passa a resolver a URL base em tempo de chamada em vez de usar a
constante `BASE_URL` diretamente — a constante continua existindo como o valor de produção e
como fallback de homologação, então nada muda de comportamento enquanto o ambiente for
`'producao'` (o default). Os tokens OAuth passam a ser gravados/lidos numa chave de config
sufixada por ambiente, pra que autenticar em homologação não sobrescreva o token de produção.
As funções de sync já existentes passam o ambiente corrente até as queries de INSERT/UPDATE via
parâmetro nomeado de posição trailing — mesmo padrão seguro usado por `tipo_documento` na fase 4b.

**Decisão de design (confirmada com o usuário):** a API Bling v3 **não** tem host de sandbox
público documentado — diferente da Shopee, que tem (`shopee/auth.py::BASE_URL_SANDBOX`).
Portanto o host de homologação vem de config (`bling.base_url_homologacao` ou env
`BLING_BASE_URL_HOMOLOGACAO`) e, **quando não configurado, cai de volta na URL de produção**.
Ativar homologação sem configurar host isola os DADOS (coluna `ambiente`) mas continua falando
com a API real — comportamento deliberado, visível na resposta de `GET /api/bling/ambiente`, não
um bug. Se o host de sandbox aparecer depois, é uma linha de config, não um deploy.

**Tech Stack:** Flask (Python), pytest, requests, asyncpg (Postgres).

**Spec:** `docs/superpowers/specs/2026-08-20-modulo-bling-design.md` (seção "Homologação (novo)")

## Global Constraints

- **`'producao'` é o default em absolutamente todo lugar.** Colunas novas usam
  `ADD COLUMN IF NOT EXISTS ambiente VARCHAR(15) DEFAULT 'producao'`; parâmetros novos de função
  usam `ambiente: str = "producao"`; `get_ambiente()` devolve `'producao'` pra qualquer valor
  ausente ou inválido. Nenhum registro já existente pode mudar de classificação, e nenhuma
  chamada existente pode mudar de comportamento.
- **Parâmetro novo vai por ÚLTIMO, nunca no meio da lista posicional.** Vale principalmente pra
  `core/fiscal.py::_upsert_nota_fiscal`, que terminou a fase 4b com INSERT de 36 placeholders /
  36 argumentos e UPDATE de 34 / 34 — e cujo `WHERE bling_id=$N` **tem que continuar sendo o
  último placeholder do UPDATE**. Existe um teste-guarda dessa contagem
  (`tests/test_fiscal.py::TestUpsertNotaFiscalTipoDocumento::test_contagem_de_placeholders_bate_com_argumentos`)
  que precisa continuar passando ao final de cada task que toque essa função.
- **Nunca hardcode um host de sandbox do Bling.** Sem `base_url_homologacao` configurado,
  `_base_url()` devolve `BASE_URL` (produção). Um host inventado quebraria silenciosamente o
  módulo inteiro assim que alguém ligasse o toggle.
- **O toggle é escopado só ao Bling.** Não encoste em Shopee, i9Logic ou outra integração — cada
  uma tem o próprio conceito de sandbox e não compartilha config.
- **`_TOKEN` mantém o formato atual** `{"access": ..., "refresh": ...}`. Vários testes existentes
  escrevem direto nele (`bling._TOKEN["access"] = "mock"`); mudar pro formato dict-por-ambiente
  quebraria esses testes. A segregação acontece nas CHAVES DE CONFIG; o cache em memória é do
  ambiente corrente e é limpo ao trocar de ambiente.
- Rodar a suíte completa (`cd hermes_agents && python -m pytest tests/ -q`) ao final de cada
  task. Baseline conhecido: **8 falhas pré-existentes** alheias a Bling (RH endpoints, compras
  segurança, RBAC lojas) — nenhuma NOVA falha é aceitável.

## File Structure

| Arquivo | Responsabilidade nesta fase |
|---|---|
| `hermes_agents/bling_erp.py` | Fonte da verdade do ambiente: `get_ambiente`/`set_ambiente`/`_base_url`/`_chave_token`, `status()` expondo ambiente |
| `hermes_agents/core/fiscal.py` | Coluna `ambiente` em `fiscal_notas_fiscais`, parâmetro no upsert, syncs de NF-e/NFC-e/NFS-e gravando o ambiente corrente |
| `hermes_agents/core/compras.py` | Coluna `ambiente` em `compras_pedidos` + sync de pedidos de compra gravando |
| `hermes_agents/core/vendas.py` | Coluna `ambiente` em `vendas_pedidos` + sync de pedidos de venda Bling gravando |
| `hermes_agents/routes/integrations.py` | Rotas `GET`/`POST /api/bling/ambiente` + filtro por `ambiente` nas leituras locais |
| `hermes_agents/tests/test_bling_erp.py` | Ambiente, base URL, tokens segregados |
| `hermes_agents/tests/test_fiscal.py` | `ambiente` no upsert de nota e nos syncs fiscais |
| `hermes_agents/tests/test_compras_bling.py` | `ambiente` no sync de pedidos de compra |
| `hermes_agents/tests/test_vendas.py` | `ambiente` no sync de pedidos de venda Bling |
| `hermes_agents/tests/test_bling_routes.py` | Rotas de toggle e filtro por ambiente |

---

### Task 1: Ambiente em `bling_erp` — config, base URL em runtime, tokens segregados

**Files:**
- Modify: `hermes_agents/bling_erp.py` (topo do arquivo — bloco novo depois de `_TOKEN`; as 4
  funções que usam `BASE_URL` direto: `get_auth_url`, `exchange_code`, `refresh_access_token`,
  `_request`; os 4 acessos a chave de token em `get_access_token`/`set_access_token`/
  `get_refresh_token`/`set_refresh_token`; e `status()`)
- Test: `hermes_agents/tests/test_bling_erp.py`

**Interfaces:**
- Consumes: `core.config.get_config` / `core.config.set_config` — já importados no topo de
  `bling_erp.py`, então o alvo de `patch` nos testes é `bling_erp.get_config`, **não**
  `core.config.get_config`.
- Produces:
  - `bling_erp.AMBIENTES: tuple[str, str]` = `("producao", "homologacao")`
  - `bling_erp.get_ambiente() -> str`
  - `bling_erp.set_ambiente(ambiente: str) -> dict` — `{"ambiente": "..."}` ou `{"error": "..."}`
  - `bling_erp._base_url() -> str`
  - `bling_erp._chave_token(nome: str) -> str`
  - `bling_erp.status() -> dict` ganha as chaves `"ambiente"` e `"base_url"`

- [ ] **Step 1: Escrever os testes (RED)**

Adicionar a `hermes_agents/tests/test_bling_erp.py`, antes da linha
`if __name__=="__main__": unittest.main(verbosity=2)`. O arquivo já importa `os`, `unittest`,
`patch` e o módulo como `bling`:

```python
class TestAmbienteBling(unittest.TestCase):
    """Toggle producao/homologacao: default seguro, base URL nunca hardcoded,
    tokens segregados por ambiente."""

    def setUp(self):
        os.environ.pop("BLING_AMBIENTE", None)
        os.environ.pop("BLING_BASE_URL_HOMOLOGACAO", None)

    def test_ambiente_default_e_producao(self):
        with patch("bling_erp.get_config", return_value=""):
            self.assertEqual(bling.get_ambiente(), "producao")

    def test_ambiente_invalido_cai_para_producao(self):
        with patch("bling_erp.get_config", return_value="qualquer-coisa"):
            self.assertEqual(bling.get_ambiente(), "producao")

    def test_ambiente_le_da_config(self):
        with patch("bling_erp.get_config", return_value="homologacao"):
            self.assertEqual(bling.get_ambiente(), "homologacao")

    def test_ambiente_le_do_env_com_prioridade(self):
        os.environ["BLING_AMBIENTE"] = "homologacao"
        try:
            with patch("bling_erp.get_config", return_value="producao"):
                self.assertEqual(bling.get_ambiente(), "homologacao")
        finally:
            os.environ.pop("BLING_AMBIENTE", None)

    def test_set_ambiente_persiste_e_limpa_cache_de_token(self):
        bling._TOKEN["access"] = "token-de-producao"
        bling._TOKEN["refresh"] = "refresh-de-producao"
        with patch("bling_erp.set_config") as mock_set:
            r = bling.set_ambiente("homologacao")
        self.assertEqual(r["ambiente"], "homologacao")
        mock_set.assert_called_once_with("bling", "ambiente", "homologacao")
        # cache do ambiente anterior nao pode vazar pro novo ambiente
        self.assertEqual(bling._TOKEN["access"], "")
        self.assertEqual(bling._TOKEN["refresh"], "")

    def test_set_ambiente_invalido_nao_persiste(self):
        with patch("bling_erp.set_config") as mock_set:
            r = bling.set_ambiente("xpto")
        self.assertIn("error", r)
        mock_set.assert_not_called()

    def test_base_url_em_producao_e_a_constante(self):
        with patch("bling_erp.get_ambiente", return_value="producao"):
            self.assertEqual(bling._base_url(), bling.BASE_URL)

    def test_base_url_em_homologacao_sem_host_configurado_cai_em_producao(self):
        """Bling v3 nao publica host de sandbox. Sem config, homologacao isola
        os DADOS mas continua falando com a API real — nunca aponta pra host
        inventado."""
        with patch("bling_erp.get_ambiente", return_value="homologacao"), \
             patch("bling_erp.get_config", return_value=""):
            self.assertEqual(bling._base_url(), bling.BASE_URL)

    def test_base_url_em_homologacao_usa_host_configurado_sem_barra_final(self):
        with patch("bling_erp.get_ambiente", return_value="homologacao"), \
             patch("bling_erp.get_config", return_value="https://sandbox.bling.test/Api/v3/"):
            self.assertEqual(bling._base_url(), "https://sandbox.bling.test/Api/v3")

    def test_chave_de_token_e_sufixada_em_homologacao(self):
        """Autenticar em homologacao nao pode sobrescrever o token de producao."""
        with patch("bling_erp.get_ambiente", return_value="homologacao"), \
             patch("bling_erp.set_config") as mock_set:
            bling.set_access_token("tok-homologacao")
        mock_set.assert_called_once_with("bling", "access_token_homologacao", "tok-homologacao")

    def test_chave_de_token_em_producao_continua_sem_sufixo(self):
        with patch("bling_erp.get_ambiente", return_value="producao"), \
             patch("bling_erp.set_config") as mock_set:
            bling.set_refresh_token("refresh-producao")
        mock_set.assert_called_once_with("bling", "refresh_token", "refresh-producao")

    def test_status_expoe_ambiente_e_base_url(self):
        with patch("bling_erp.get_ambiente", return_value="homologacao"):
            s = bling.status()
        self.assertEqual(s["ambiente"], "homologacao")
        self.assertIn("base_url", s)
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_bling_erp.py -k "Ambiente" -v`
Expected: FAIL — `AttributeError: module 'bling_erp' has no attribute 'get_ambiente'`.

- [ ] **Step 3: Implementar o bloco de ambiente**

Em `hermes_agents/bling_erp.py`, **depois** da linha `_TOKEN = {"access": "", "refresh": ""}`
(o bloco referencia `_TOKEN`; colocar antes quebra no import), adicionar:

```python
# ── Ambiente (producao / homologacao) ──
# ponytail: a API Bling v3 nao publica host de sandbox (a Shopee publica — ver
# shopee/auth.py::BASE_URL_SANDBOX). Por isso o host de homologacao vem de
# config e, sem config, cai de volta em producao: ligar o toggle isola os DADOS
# (coluna `ambiente` nas tabelas sincronizadas) mesmo quando ainda nao existe
# host separado pra apontar. Apontar pra host inventado quebraria o modulo
# inteiro em silencio.
AMBIENTES = ("producao", "homologacao")

def get_ambiente() -> str:
    amb = (os.environ.get("BLING_AMBIENTE") or "").strip().lower()
    if amb not in AMBIENTES:
        try: amb = (get_config("bling", "ambiente") or "").strip().lower()
        except Exception: amb = ""
    return amb if amb in AMBIENTES else "producao"

def set_ambiente(ambiente: str) -> dict:
    amb = (ambiente or "").strip().lower()
    if amb not in AMBIENTES:
        return {"error": f"ambiente invalido: {ambiente!r} (use 'producao' ou 'homologacao')"}
    set_config("bling", "ambiente", amb)
    # o cache em memoria e' do ambiente anterior — deixar vazar daria 401 em
    # loop (token de um ambiente contra a base do outro).
    _TOKEN["access"] = ""
    _TOKEN["refresh"] = ""
    return {"ambiente": amb}

def _base_url() -> str:
    if get_ambiente() == "homologacao":
        url = os.environ.get("BLING_BASE_URL_HOMOLOGACAO") or ""
        if not url:
            try: url = get_config("bling", "base_url_homologacao") or ""
            except Exception: url = ""
        url = url.strip().rstrip("/")
        if url: return url
    return BASE_URL

def _chave_token(nome: str) -> str:
    """Chaves de config de token sao sufixadas fora de producao, pra que
    autenticar em homologacao nao sobrescreva o token de producao."""
    return nome if get_ambiente() == "producao" else f"{nome}_homologacao"
```

- [ ] **Step 4: Trocar os usos de `BASE_URL` e as chaves de token**

Quatro trocas de URL em `bling_erp.py` (`grep -n BASE_URL bling_erp.py` mostra 5 ocorrências: a
declaração da constante, que **fica**, e 4 usos, que mudam):

1. `get_auth_url`: `return f"{BASE_URL}/oauth/authorize?{params}"` → `return f"{_base_url()}/oauth/authorize?{params}"`
2. `exchange_code`: `requests.post(f"{BASE_URL}/oauth/token", ...)` → `requests.post(f"{_base_url()}/oauth/token", ...)`
3. `refresh_access_token`: `requests.post(f"{BASE_URL}/oauth/token", ...)` → `requests.post(f"{_base_url()}/oauth/token", ...)`
4. `_request`: `url = f"{BASE_URL}/{endpoint}"` → `url = f"{_base_url()}/{endpoint}"`

Quatro trocas de chave de token (só a string da chave muda):

- `get_access_token`: `get_config("bling", "access_token")` → `get_config("bling", _chave_token("access_token"))`
- `set_access_token`: `set_config("bling", "access_token", token)` → `set_config("bling", _chave_token("access_token"), token)`
- `get_refresh_token`: `get_config("bling", "refresh_token")` → `get_config("bling", _chave_token("refresh_token"))`
- `set_refresh_token`: `set_config("bling", "refresh_token", token)` → `set_config("bling", _chave_token("refresh_token"), token)`

E `status()` ganha duas chaves:

```python
def status() -> dict:
    token = get_access_token()
    return {
        "client_id_setado": bool(_client_id()),
        "autenticado": bool(token),
        "auth_url": get_auth_url() if not token else "",
        "ambiente": get_ambiente(),
        "base_url": _base_url(),
    }
```

- [ ] **Step 5: Rodar e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_bling_erp.py -k "Ambiente" -v`
Expected: PASS

- [ ] **Step 6: Regressão de OAuth/URL no arquivo inteiro**

Run: `cd hermes_agents && python -m pytest tests/test_bling_erp.py tests/test_bling_routes.py -q`
Expected: todos PASS. Em especial `test_auth_url`, que afirma `"bling.com.br" in get_auth_url()`:
com o default `'producao'`, `_base_url()` devolve a constante e o teste continua passando. Se ele
falhar, `get_ambiente()` está devolvendo homologação por engano — conserte antes de seguir.

- [ ] **Step 7: Suíte completa**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: mesmas 8 falhas pré-existentes, nenhuma nova.

- [ ] **Step 8: Commit**

```bash
git add hermes_agents/bling_erp.py hermes_agents/tests/test_bling_erp.py
git commit -m "feat: ambiente producao/homologacao no Bling (base URL configuravel, tokens segregados)"
```

---

### Task 2: Coluna `ambiente` em `fiscal_notas_fiscais` + parâmetro no upsert

**Files:**
- Modify: `hermes_agents/core/fiscal.py` (`_ensure_tables`, `_upsert_nota_fiscal`,
  `sincronizar_notas_fiscais_bling`, `sincronizar_uma_nota_fiscal`,
  `_sincronizar_notas_bling_por_tipo`, `sincronizar_nfce_bling`, `sincronizar_nfse_bling`)
- Test: `hermes_agents/tests/test_fiscal.py`

**Interfaces:**
- Consumes: `bling_erp.get_ambiente()` (Task 1)
- Produces:
  - `core.fiscal._upsert_nota_fiscal(db, bling_id: int, detalhe: dict, tipo_documento: str = "nfe", ambiente: str = "producao") -> int`
  - `core.fiscal._sincronizar_notas_bling_por_tipo(listar_fn, detalhe_fn, tipo_documento: str, pagina: int = 1, limite: int = 100, pular: int = 0, ambiente: str = "producao") -> dict`

- [ ] **Step 1: Reler a função antes de editar**

Leia `hermes_agents/core/fiscal.py` de `async def _upsert_nota_fiscal` até `return nota_id`.
Estado esperado ao começar (deixado pela fase 4b): UPDATE com `$1..$34` (`$33` =
`tipo_documento`, `$34` = `bling_id` no `WHERE`) e INSERT com `$1..$36` (`$35` = `bling_id`,
`$36` = `tipo_documento`). Confirme esses números; se divergirem, ajuste os números dos steps
seguintes em vez de aplicar cegamente.

- [ ] **Step 2: Escrever os testes (RED)**

Adicionar dentro da classe `TestUpsertNotaFiscalTipoDocumento` em
`hermes_agents/tests/test_fiscal.py` (ela já tem os helpers `_insert_call` / `_update_call` e o
teste-guarda de contagem):

```python
    def test_upsert_grava_ambiente_quando_informado(self):
        db = _FakeDBNotas(existing_id=None)
        self.run_async(self.fiscal._upsert_nota_fiscal(
            db, 997, _NFE_DETALHE_MOCK, tipo_documento="nfce", ambiente="homologacao"))
        self.assertIn("homologacao", self._insert_call(db)[1])

    def test_upsert_default_de_ambiente_e_producao(self):
        db = _FakeDBNotas(existing_id=None)
        self.run_async(self.fiscal._upsert_nota_fiscal(db, 996, _NFE_DETALHE_MOCK))
        self.assertIn("producao", self._insert_call(db)[1])

    def test_update_com_ambiente_mantem_bling_id_no_where(self):
        db = _FakeDBNotas(existing_id=55)
        self.run_async(self.fiscal._upsert_nota_fiscal(
            db, 777, _NFE_DETALHE_MOCK, tipo_documento="nfse", ambiente="homologacao"))
        q, args = self._update_call(db)
        self.assertEqual(args[-1], 777)            # WHERE bling_id continua ULTIMO
        self.assertEqual(args[-2], "homologacao")  # ambiente entra imediatamente antes
        self.assertEqual(args[-3], "nfse")
```

E, como classe nova no mesmo arquivo (logo após `TestSincronizarNfceNfseBling`):

```python
class TestSyncNotasPropagaAmbiente(unittest.TestCase):
    """O ambiente corrente do Bling tem que chegar ate' a coluna, senao dado de
    homologacao entra classificado como producao."""
    def setUp(self):
        import core.fiscal as fiscal
        self.fiscal = fiscal

    def _ambiente_gravado(self, db):
        q, args = next(c for c in db.fetchvals if "INSERT INTO fiscal_notas_fiscais" in c[0])
        return args[-1]

    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.get_ambiente", return_value="homologacao")
    @patch("bling_erp.listar_nfce", return_value={"data": [{"id": 111}]})
    @patch("bling_erp.get_nfce_detalhe", return_value={"data": _NFE_DETALHE_MOCK})
    def test_sync_nfce_grava_ambiente_corrente(self, mdet, ml, mamb, mt):
        db = _FakeDBNotas(existing_id=None)
        async def fake_get_db(): return db
        with patch.object(self.fiscal, "get_db", fake_get_db):
            r = self.fiscal.sincronizar_nfce_bling()
        self.assertEqual(r["sync"], 1)
        self.assertEqual(self._ambiente_gravado(db), "homologacao")

    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.get_ambiente", return_value="homologacao")
    @patch("bling_erp.listar_nfse", return_value={"data": [{"id": 222}]})
    @patch("bling_erp.get_nfse_detalhe", return_value={"data": _NFE_DETALHE_MOCK})
    def test_sync_nfse_grava_ambiente_corrente(self, mdet, ml, mamb, mt):
        db = _FakeDBNotas(existing_id=None)
        async def fake_get_db(): return db
        with patch.object(self.fiscal, "get_db", fake_get_db):
            r = self.fiscal.sincronizar_nfse_bling()
        self.assertEqual(r["sync"], 1)
        self.assertEqual(self._ambiente_gravado(db), "homologacao")

    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.get_ambiente", return_value="producao")
    @patch("bling_erp.listar_notas_fiscais", return_value={"data": [{"id": 777}]})
    @patch("bling_erp.get_nfe_completa", return_value={"data": _NFE_DETALHE_MOCK})
    def test_sync_nfe_em_producao_grava_producao(self, mdet, ml, mamb, mt):
        db = _FakeDBNotas(existing_id=None)
        async def fake_get_db(): return db
        with patch.object(self.fiscal, "get_db", fake_get_db):
            r = self.fiscal.sincronizar_notas_fiscais_bling()
        self.assertEqual(r["sync"], 1)
        self.assertEqual(self._ambiente_gravado(db), "producao")

    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.get_ambiente", return_value="homologacao")
    @patch("bling_erp.get_nfe_completa", return_value={"data": _NFE_DETALHE_MOCK})
    def test_sync_de_uma_nota_webhook_grava_ambiente_corrente(self, mdet, mamb, mt):
        db = _FakeDBNotas(existing_id=None)
        async def fake_get_db(): return db
        with patch.object(self.fiscal, "get_db", fake_get_db):
            r = self.fiscal.sincronizar_uma_nota_fiscal(777)
        self.assertEqual(r["nota_id"], 99)
        self.assertEqual(self._ambiente_gravado(db), "homologacao")
```

- [ ] **Step 3: Rodar e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_fiscal.py -k "ambiente or Ambiente" -v`
Expected: FAIL — `TypeError: _upsert_nota_fiscal() got an unexpected keyword argument 'ambiente'`
nos primeiros, `AssertionError`/`StopIteration` nos de sync.

- [ ] **Step 4: Adicionar a coluna em `_ensure_tables`**

Em `hermes_agents/core/fiscal.py`, logo após o `ALTER TABLE ... ADD COLUMN IF NOT EXISTS
tipo_documento ...` da fase 4b:

```python
        # ambiente separa dado sincronizado em homologacao do dado real de
        # producao dentro da mesma tabela. DEFAULT 'producao' classifica
        # retroativamente tudo que ja existe, sem UPDATE manual.
        try: await db.execute("ALTER TABLE fiscal_notas_fiscais ADD COLUMN IF NOT EXISTS ambiente VARCHAR(15) DEFAULT 'producao'")
        except Exception as e: pass
```

- [ ] **Step 5: Estender `_upsert_nota_fiscal`**

1. Assinatura — de:
   `async def _upsert_nota_fiscal(db, bling_id: int, detalhe: dict, tipo_documento: str = "nfe") -> int:`
   para:
   `async def _upsert_nota_fiscal(db, bling_id: int, detalhe: dict, tipo_documento: str = "nfe", ambiente: str = "producao") -> int:`

2. UPDATE — a cláusula hoje termina assim:

```
            xml_url=$30, danfe_url=$31, dados_brutos_bling=$32::jsonb, tipo_documento=$33,
            sincronizado_em=NOW()
            WHERE bling_id=$34""",
```

   vira:

```
            xml_url=$30, danfe_url=$31, dados_brutos_bling=$32::jsonb, tipo_documento=$33,
            ambiente=$34, sincronizado_em=NOW()
            WHERE bling_id=$35""",
```

   e a última linha de argumentos, hoje:

```
            campos["xml_url"], campos["danfe_url"], raw, tipo_documento, bling_id)
```

   vira:

```
            campos["xml_url"], campos["danfe_url"], raw, tipo_documento, ambiente, bling_id)
```

3. INSERT — a lista de colunas hoje termina com
   `... dados_brutos_bling, bling_id, tipo_documento, sincronizado_em)` e vira
   `... dados_brutos_bling, bling_id, tipo_documento, ambiente, sincronizado_em)`.
   O `VALUES` hoje termina com `...,$34::jsonb,$35,$36,NOW())` e vira `...,$34::jsonb,$35,$36,$37,NOW())`.
   A última linha de argumentos, hoje:

```
            campos["xml_url"], campos["danfe_url"], raw, bling_id, tipo_documento)
```

   vira:

```
            campos["xml_url"], campos["danfe_url"], raw, bling_id, tipo_documento, ambiente)
```

- [ ] **Step 6: Propagar o ambiente nos syncs**

Quatro pontos em `hermes_agents/core/fiscal.py`. Em cada um, `get_ambiente` entra no
`from bling_erp import ...` local que já existe, e o valor é resolvido UMA vez antes do loop
(trocar de ambiente no meio de um sync não deve partir o lote em dois):

1. `sincronizar_notas_fiscais_bling` — import vira
   `from bling_erp import listar_notas_fiscais as bling_nfe, get_nfe_completa, get_access_token, get_auth_url, get_ambiente`;
   adicione `ambiente = get_ambiente()` antes de `async def _go():`; a chamada
   `await _upsert_nota_fiscal(db, bling_id, detalhe)` vira
   `await _upsert_nota_fiscal(db, bling_id, detalhe, ambiente=ambiente)`.

2. `sincronizar_uma_nota_fiscal` (webhook) — import vira
   `from bling_erp import get_nfe_completa, get_access_token, get_ambiente`; adicione
   `ambiente = get_ambiente()` logo após o import; a chamada
   `nota_id = await _upsert_nota_fiscal(db, bling_id, detalhe)` vira
   `nota_id = await _upsert_nota_fiscal(db, bling_id, detalhe, ambiente=ambiente)`.

3. `_sincronizar_notas_bling_por_tipo` — essa função **não** importa de `bling_erp` (recebe os
   wrappers por parâmetro). Adicione `ambiente: str = "producao"` **por último** na assinatura e
   repasse:
   `await _upsert_nota_fiscal(db, bling_id, detalhe, tipo_documento=tipo_documento, ambiente=ambiente)`.

4. `sincronizar_nfce_bling` e `sincronizar_nfse_bling` — passam o ambiente corrente pro motor:

```python
def sincronizar_nfce_bling(pagina: int = 1, limite: int = 100, pular: int = 0) -> dict:
    """Sync de NFC-e (nota de consumidor, venda presencial) → fiscal_notas_fiscais
    com tipo_documento='nfce'."""
    from bling_erp import listar_nfce, get_nfce_detalhe, get_access_token, get_auth_url, get_ambiente
    token = get_access_token()
    if not token: return {"error": "Bling nao autenticado", "auth_url": get_auth_url()}
    return _sincronizar_notas_bling_por_tipo(listar_nfce, get_nfce_detalhe, "nfce",
                                             pagina, limite, pular, get_ambiente())
```

   Idem para `sincronizar_nfse_bling`, trocando `listar_nfse` / `get_nfse_detalhe` / `"nfse"`.

- [ ] **Step 7: Rodar os testes novos**

Run: `cd hermes_agents && python -m pytest tests/test_fiscal.py -k "ambiente or Ambiente" -v`
Expected: PASS

- [ ] **Step 8: Rodar TODA a suíte fiscal — passo mais importante desta task**

Run: `cd hermes_agents && python -m pytest tests/test_fiscal.py tests/test_fiscal_seguranca.py tests/test_fiscal_apuracao_fechamento.py tests/test_fiscal_obrigacoes_ocorrencias.py -v`
Expected: todos PASS, incluindo `test_contagem_de_placeholders_bate_com_argumentos`, que agora
valida INSERT 37/37 e UPDATE 35/35. Se ele falhar, a contagem de `$N` ficou errada e algum campo
fiscal está indo pra coluna errada: PARE e conserte antes de qualquer outra coisa.

- [ ] **Step 9: Suíte completa**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: mesmas 8 falhas pré-existentes, nenhuma nova.

- [ ] **Step 10: Commit**

```bash
git add hermes_agents/core/fiscal.py hermes_agents/tests/test_fiscal.py
git commit -m "feat: coluna ambiente em fiscal_notas_fiscais + propagacao nos syncs de nota"
```

---

### Task 3: Coluna `ambiente` em `compras_pedidos` e `vendas_pedidos`

**Files:**
- Modify: `hermes_agents/core/compras.py` (`_ensure_tables` e o UPDATE/INSERT do sync Bling em
  `sincronizar_pedidos_compra_bling`, hoje por volta das linhas 375-388)
- Modify: `hermes_agents/core/vendas.py` (`_ensure_tables` e o UPDATE/INSERT do sync Bling em
  `sincronizar_pedidos_bling`, hoje por volta das linhas 382-400 — o bloco com
  `marketplace='bling'`; **não** o bloco de Shopee logo abaixo, por volta da linha 480)
- Test: `hermes_agents/tests/test_compras_bling.py`, `hermes_agents/tests/test_vendas.py`

**Interfaces:**
- Consumes: `bling_erp.get_ambiente()` (Task 1)
- Produces: nenhuma assinatura pública nova — as colunas passam a ser gravadas pelos syncs já
  existentes (`core.compras.sincronizar_pedidos_compra_bling`,
  `core.vendas.sincronizar_pedidos_bling`).

- [ ] **Step 1: Escrever os testes (RED)**

Em `hermes_agents/tests/test_compras_bling.py`, adicionar antes do
`if __name__ == "__main__":` (o arquivo usa `fake_db = AsyncMock()` e patch de
`core.compras.get_db` — mesmo padrão dos testes de situação que já existem lá):

```python
class TestSyncComprasAmbiente(unittest.TestCase):
    """Pedido de compra sincronizado em homologacao nao pode entrar
    classificado como producao."""

    def test_sync_pedido_compra_grava_ambiente_corrente(self):
        fake_db = AsyncMock()
        fake_db.fetchval.side_effect = [None, None, None, 42]
        fake_db.fetchrow.return_value = None
        with patch("bling_erp.get_access_token", return_value="tok"), \
             patch("bling_erp.get_ambiente", return_value="homologacao"), \
             patch("core.compras.get_db", new=AsyncMock(return_value=fake_db)), \
             patch("bling_erp.get_pedido_compra_detalhe", return_value={"data": {
                 "id": 555, "numero": "PC-001", "total": 1000.0,
                 "data": "2026-08-21", "dataPrevista": "2026-08-28",
                 "situacao": {"valor": 6, "nome": "Em andamento"},
                 "fornecedor": {"nome": "Fornecedor XYZ", "numeroDocumento": "12.345.678/0001-99"},
                 "itens": [],
             }}), \
             patch("bling_erp.listar_pedidos_compra", return_value={"data": [{"id": 555}]}):
            resultado = core_compras.sincronizar_pedidos_compra_bling()
        self.assertEqual(resultado["sync"], 1)
        insert = next(c for c in fake_db.execute.call_args_list
                      if "INSERT INTO compras_pedidos" in c.args[0])
        self.assertIn("homologacao", insert.args)

    def test_sync_pedido_compra_em_producao_grava_producao(self):
        fake_db = AsyncMock()
        fake_db.fetchval.side_effect = [None, None, None, 43]
        fake_db.fetchrow.return_value = None
        with patch("bling_erp.get_access_token", return_value="tok"), \
             patch("bling_erp.get_ambiente", return_value="producao"), \
             patch("core.compras.get_db", new=AsyncMock(return_value=fake_db)), \
             patch("bling_erp.get_pedido_compra_detalhe", return_value={"data": {
                 "id": 556, "numero": "PC-002", "total": 500.0,
                 "data": "2026-08-21", "dataPrevista": "2026-08-28",
                 "situacao": {"valor": 6, "nome": "Em andamento"},
                 "fornecedor": {"nome": "Fornecedor ABC", "numeroDocumento": ""},
                 "itens": [],
             }}), \
             patch("bling_erp.listar_pedidos_compra", return_value={"data": [{"id": 556}]}):
            resultado = core_compras.sincronizar_pedidos_compra_bling()
        self.assertEqual(resultado["sync"], 1)
        insert = next(c for c in fake_db.execute.call_args_list
                      if "INSERT INTO compras_pedidos" in c.args[0])
        self.assertIn("producao", insert.args)
```

Em `hermes_agents/tests/test_vendas.py`, adicionar à classe `TestSincronizarPedidosBling` (que
já usa `_FakeDBPedidos` e `patch.object(vendas, "get_db", fake_get_db)`):

```python
    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.get_ambiente", return_value="homologacao")
    @patch("bling_erp.listar_pedidos", return_value={"data": [{"id": 555}]})
    @patch("bling_erp.get_pedido_detalhe", return_value={"data": _PEDIDO_DETALHE_MOCK})
    def test_cria_pedido_grava_ambiente_corrente(self, mdet, ml, mamb, mt):
        db = _FakeDBPedidos(existing_id=None)
        async def fake_get_db(): return db
        with patch.object(vendas, "get_db", fake_get_db):
            r = vendas.sincronizar_pedidos_bling()
        self.assertEqual(r["sync"], 1)
        insert = next(e for e in db.executed if "INSERT INTO vendas_pedidos" in e[0])
        self.assertIn("homologacao", insert[1])

    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.get_ambiente", return_value="homologacao")
    @patch("bling_erp.listar_pedidos", return_value={"data": [{"id": 555}]})
    @patch("bling_erp.get_pedido_detalhe", return_value={"data": _PEDIDO_DETALHE_MOCK})
    def test_atualiza_pedido_grava_ambiente_e_mantem_bling_id_no_where(self, mdet, ml, mamb, mt):
        db = _FakeDBPedidos(existing_id=33)
        async def fake_get_db(): return db
        with patch.object(vendas, "get_db", fake_get_db):
            r = vendas.sincronizar_pedidos_bling()
        self.assertEqual(r["sync"], 1)
        q, args = next(e for e in db.executed if "UPDATE vendas_pedidos" in e[0])
        self.assertEqual(args[-1], 555)             # WHERE bling_id continua ULTIMO
        self.assertEqual(args[-2], "homologacao")   # ambiente imediatamente antes
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_compras_bling.py tests/test_vendas.py -k "ambiente" -v`
Expected: FAIL — `AssertionError` (a query ainda não grava a coluna).

- [ ] **Step 3: Adicionar as colunas**

Em `hermes_agents/core/compras.py`, dentro de `_ensure_tables`, logo após o
`CREATE TABLE IF NOT EXISTS compras_pedidos (...)`:

```python
        try: await db.execute("ALTER TABLE compras_pedidos ADD COLUMN IF NOT EXISTS ambiente VARCHAR(15) DEFAULT 'producao'")
        except Exception as e: pass
```

Em `hermes_agents/core/vendas.py`, dentro de `_ensure_tables`, logo após o
`CREATE TABLE IF NOT EXISTS vendas_pedidos (...)`:

```python
        try: await db.execute("ALTER TABLE vendas_pedidos ADD COLUMN IF NOT EXISTS ambiente VARCHAR(15) DEFAULT 'producao'")
        except Exception as e: pass
```

- [ ] **Step 4: Gravar o ambiente no sync de pedidos de compra**

Em `hermes_agents/core/compras.py::sincronizar_pedidos_compra_bling`: o import local vira
`from bling_erp import listar_pedidos_compra, get_pedido_compra_detalhe, get_access_token, get_auth_url, get_ambiente`,
e `ambiente = get_ambiente()` é resolvido uma vez, antes do loop. As duas queries — hoje:

```python
                    await db.execute("""UPDATE compras_pedidos SET
                        numero=$1, fornecedor_id=$2, valor_total=$3, status=$4,
                        data_emissao=$5::date, data_entrega_prevista=$6::date, updated_at=NOW()
                        WHERE bling_id=$7""",
                        numero, fornecedor_id, valor_total, situacao,
                        data_emissao, data_prevista, bling_id)
```

viram:

```python
                    await db.execute("""UPDATE compras_pedidos SET
                        numero=$1, fornecedor_id=$2, valor_total=$3, status=$4,
                        data_emissao=$5::date, data_entrega_prevista=$6::date,
                        ambiente=$7, updated_at=NOW()
                        WHERE bling_id=$8""",
                        numero, fornecedor_id, valor_total, situacao,
                        data_emissao, data_prevista, ambiente, bling_id)
```

e o INSERT — hoje:

```python
                    await db.execute("""INSERT INTO compras_pedidos
                        (numero, fornecedor_id, valor_total, status, data_emissao,
                         data_entrega_prevista, bling_id)
                        VALUES ($1,$2,$3,$4,$5::date,$6::date,$7)""",
                        numero, fornecedor_id, valor_total, situacao,
                        data_emissao, data_prevista, bling_id)
```

vira:

```python
                    await db.execute("""INSERT INTO compras_pedidos
                        (numero, fornecedor_id, valor_total, status, data_emissao,
                         data_entrega_prevista, bling_id, ambiente)
                        VALUES ($1,$2,$3,$4,$5::date,$6::date,$7,$8)""",
                        numero, fornecedor_id, valor_total, situacao,
                        data_emissao, data_prevista, bling_id, ambiente)
```

- [ ] **Step 5: Gravar o ambiente no sync de pedidos de venda Bling**

Em `hermes_agents/core/vendas.py::sincronizar_pedidos_bling`: `get_ambiente` entra no import
local (`from bling_erp import listar_pedidos as bling_pedidos, get_pedido_detalhe, get_access_token, get_auth_url, get_ambiente`),
`ambiente = get_ambiente()` resolvido uma vez antes do loop.

UPDATE — hoje termina em `observacoes=$13, updated_at=NOW() WHERE bling_id=$14` com os
argumentos terminando em `campos["observacoes"], bling_id)`. Vira
`observacoes=$13, ambiente=$14, updated_at=NOW() WHERE bling_id=$15`, com os argumentos
terminando em `campos["observacoes"], ambiente, bling_id)` — `ambiente` como penúltimo,
**imediatamente antes de `bling_id`**, porque o `WHERE` tem que continuar sendo o último
placeholder.

INSERT — a lista de colunas hoje termina em
`..., bling_id, bling_numero, loja_id, observacoes)` com
`VALUES ($1,...,'bling','bling',$12,$13,$14,$15)`. Vira
`..., bling_id, bling_numero, loja_id, observacoes, ambiente)` com
`VALUES ($1,...,'bling','bling',$12,$13,$14,$15,$16)` e `ambiente` acrescentado ao FIM da lista
de argumentos posicionais.

Antes de commitar, conte nas quatro queries tocadas nesta task: número de `$N` = número de
argumentos posicionais.

- [ ] **Step 6: Rodar os testes novos, depois os arquivos inteiros**

Run: `cd hermes_agents && python -m pytest tests/test_compras_bling.py tests/test_vendas.py -v`
Expected: todos PASS. (`test_compras_seguranca.py` e `test_rbac_lojas_rotas.py` são outros
arquivos e contêm falhas do baseline — não confunda.)

- [ ] **Step 7: Suíte completa**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: mesmas 8 falhas pré-existentes, nenhuma nova.

- [ ] **Step 8: Commit**

```bash
git add hermes_agents/core/compras.py hermes_agents/core/vendas.py hermes_agents/tests/test_compras_bling.py hermes_agents/tests/test_vendas.py
git commit -m "feat: coluna ambiente em compras_pedidos e vendas_pedidos nos syncs Bling"
```

---

### Task 4: Rotas do toggle + filtro por ambiente nas leituras locais

**Files:**
- Modify: `hermes_agents/routes/integrations.py` (bloco `bling_bp`: rotas novas de ambiente e as
  rotas de leitura local `/notas` e `/pedidos-compra`)
- Test: `hermes_agents/tests/test_bling_routes.py`

**Interfaces:**
- Consumes: `bling_erp.get_ambiente`, `bling_erp.set_ambiente`, `bling_erp.AMBIENTES`,
  `bling_erp._base_url` (Task 1)
- Produces:
  - `GET /api/bling/ambiente` → `{"ambiente": "...", "base_url": "...", "ambientes": [...]}`
  - `POST /api/bling/ambiente` body `{"ambiente": "homologacao"}` → `{"ambiente": "..."}` ou 400
  - `GET /api/bling/notas?tipo=...&ambiente=...` — `ambiente` default `'producao'`,
    `ambiente=todos` desliga o filtro
  - `GET /api/bling/pedidos-compra?ambiente=...` — mesma convenção

- [ ] **Step 1: Escrever os testes (RED)**

Adicionar à classe `TestBlingFlaskRoutes` em `hermes_agents/tests/test_bling_routes.py`:

```python
    def test_ambiente_get_route(self):
        with patch("routes.integrations.get_ambiente", return_value="producao"):
            rv = self.client.get("/api/bling/ambiente")
        self.assertEqual(rv.status_code, 200)
        data = json.loads(rv.data)
        self.assertEqual(data["ambiente"], "producao")
        self.assertIn("homologacao", data["ambientes"])

    def test_ambiente_post_route_exige_permissao(self):
        rv = self.client.post("/api/bling/ambiente", json={"ambiente": "homologacao"})
        self.assertEqual(rv.status_code, 403)

    def test_ambiente_post_route_troca(self):
        with patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN}), \
             patch("routes.integrations.set_ambiente", return_value={"ambiente": "homologacao"}) as mock_set:
            rv = self.client.post("/api/bling/ambiente", json={"ambiente": "homologacao"},
                                  headers={"Authorization": f"Bearer {_TEST_TOKEN}"})
        self.assertEqual(rv.status_code, 200)
        mock_set.assert_called_once_with("homologacao")

    def test_ambiente_post_route_invalido_devolve_400(self):
        with patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN}), \
             patch("routes.integrations.set_ambiente", return_value={"error": "ambiente invalido"}):
            rv = self.client.post("/api/bling/ambiente", json={"ambiente": "xpto"},
                                  headers={"Authorization": f"Bearer {_TEST_TOKEN}"})
        self.assertEqual(rv.status_code, 400)

    def test_notas_filtra_producao_por_padrao(self):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        with patch("routes.integrations.get_db", new=AsyncMock(return_value=fake_db)):
            rv = self.client.get("/api/bling/notas")
        self.assertEqual(rv.status_code, 200)
        q, args = fake_db.fetch.call_args.args[0], fake_db.fetch.call_args.args[1:]
        self.assertIn("ambiente = $1", q)
        self.assertEqual(args, ("producao",))

    def test_notas_ambiente_todos_desliga_o_filtro(self):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        with patch("routes.integrations.get_db", new=AsyncMock(return_value=fake_db)):
            rv = self.client.get("/api/bling/notas?ambiente=todos")
        self.assertEqual(rv.status_code, 200)
        self.assertNotIn("ambiente = ", fake_db.fetch.call_args.args[0])

    def test_notas_tipo_e_ambiente_juntos(self):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        with patch("routes.integrations.get_db", new=AsyncMock(return_value=fake_db)):
            rv = self.client.get("/api/bling/notas?tipo=nfce&ambiente=homologacao")
        self.assertEqual(rv.status_code, 200)
        q, args = fake_db.fetch.call_args.args[0], fake_db.fetch.call_args.args[1:]
        self.assertIn("tipo_documento = $1", q)
        self.assertIn("ambiente = $2", q)
        self.assertEqual(args, ("nfce", "homologacao"))

    def test_pedidos_compra_filtra_producao_por_padrao(self):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        with patch("routes.integrations.get_db", new=AsyncMock(return_value=fake_db)):
            rv = self.client.get("/api/bling/pedidos-compra")
        self.assertEqual(rv.status_code, 200)
        q, args = fake_db.fetch.call_args.args[0], fake_db.fetch.call_args.args[1:]
        self.assertIn("ambiente = $1", q)
        self.assertEqual(args, ("producao",))
```

Atenção: o teste `test_notas_listar_route_com_filtro_tipo` da fase 4b afirma
`self.assertEqual(args, ("nfce",))` sem passar `ambiente`. Com o filtro novo, essa chamada passa
a receber `("nfce", "producao")`. **Atualize esse teste existente** pra
`self.assertEqual(args, ("nfce", "producao"))` — é mudança de comportamento esperada e desejada
(o default passa a filtrar produção), não regressão.

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_bling_routes.py -k "ambiente" -v`
Expected: FAIL — 404 nas rotas novas, `AssertionError` nos filtros.

- [ ] **Step 3: Importar as funções de ambiente no módulo de rotas**

Em `hermes_agents/routes/integrations.py`, no import que já traz funções de `bling_erp` pro
namespace do módulo (procure `from bling_erp import`), adicione `get_ambiente` e `set_ambiente`.
Esses dois são leves (leem config em memória) — diferente dos syncs, que continuam com import
local dentro do handler.

- [ ] **Step 4: Adicionar as rotas de ambiente**

Logo antes de `@bling_bp.route("/notas")`:

```python
@bling_bp.route("/ambiente")
def api_bling_ambiente():
    from bling_erp import AMBIENTES, _base_url
    return jsonify({"ambiente": get_ambiente(), "base_url": _base_url(),
                    "ambientes": list(AMBIENTES)})


@bling_bp.route("/ambiente", methods=["POST"])
@requer_permissao("bling.sincronizar")
def api_bling_set_ambiente():
    dados = request.get_json(silent=True) or {}
    r = set_ambiente(dados.get("ambiente", ""))
    if r.get("error"):
        return jsonify(r), 400
    return jsonify(r)
```

Nota sobre RBAC: `bling.sincronizar` é a permissão de escrita já cadastrada e escopada ao Bling
(seed em `core/rbac.py`, por volta da linha 175). Não invente um código de permissão novo aqui —
permissão não semeada não é concedida a nenhum papel, e a rota ficaria inacessível pra todo mundo
exceto o token master.

- [ ] **Step 5: Filtrar por ambiente nas leituras locais**

`api_notas_locais` (rota `/notas`) passa a montar o `WHERE` com duas condições opcionais:

```python
@bling_bp.route("/notas")
def api_notas_locais():
    """Le notas ja sincronizadas do banco local, filtrando por tipo_documento
    (nfe/nfce/nfse) e por ambiente (default: so' producao; 'todos' desliga o
    filtro). Distinta de /financeiro/notas-fiscais, que proxya direto pra API
    Bling ao vivo (so' NF-e, sem tocar o banco local)."""
    tipo = request.args.get("tipo", "")
    ambiente = request.args.get("ambiente", "producao")
    async def _go():
        db = await get_db()
        sql = """SELECT id, numero, chave_acesso, tipo_documento, ambiente, status,
            data_emissao, valor_nf, contato_nome, bling_id
            FROM fiscal_notas_fiscais"""
        condicoes, valores = [], []
        if tipo:
            valores.append(tipo)
            condicoes.append(f"tipo_documento = ${len(valores)}")
        if ambiente != "todos":
            valores.append(ambiente)
            condicoes.append(f"ambiente = ${len(valores)}")
        if condicoes:
            sql += " WHERE " + " AND ".join(condicoes)
        sql += " ORDER BY data_emissao DESC LIMIT 200"
        rows = await db.fetch(sql, *valores)
        return [dict(r) for r in rows]
    try:
        return jsonify(run_async(_go()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

`api_pedidos_compra` (rota `/pedidos-compra`) segue a mesma ideia, mantendo o
`bling_id IS NOT NULL` que já existe:

```python
@bling_bp.route("/pedidos-compra")
def api_pedidos_compra():
    ambiente = request.args.get("ambiente", "producao")
    async def _go():
        db = await get_db()
        sql = """SELECT id, numero, fornecedor_id, valor_total, status,
            data_emissao, data_entrega_prevista, bling_id, ambiente
            FROM compras_pedidos WHERE bling_id IS NOT NULL"""
        valores = []
        if ambiente != "todos":
            valores.append(ambiente)
            sql += f" AND ambiente = ${len(valores)}"
        sql += " ORDER BY data_emissao DESC"
        rows = await db.fetch(sql, *valores)
        return [dict(r) for r in rows]
    try:
        return jsonify(run_async(_go()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

- [ ] **Step 6: Rodar e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_bling_routes.py -v`
Expected: todos PASS, inclusive o teste de `/notas` da fase 4b atualizado no Step 1.

- [ ] **Step 7: Suíte completa**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: mesmas 8 falhas pré-existentes, nenhuma nova.

- [ ] **Step 8: Commit**

```bash
git add hermes_agents/routes/integrations.py hermes_agents/tests/test_bling_routes.py
git commit -m "feat: rotas GET/POST /api/bling/ambiente e filtro por ambiente nas leituras locais"
```

---

### Task 5: Regressão final

**Files:**
- Test: todos os `hermes_agents/tests/test_fiscal*.py`, `test_bling_routes.py`,
  `test_bling_erp.py`, `test_compras_bling.py`, `test_vendas.py`

- [ ] **Step 1: Suíte fiscal completa**

Run: `ls hermes_agents/tests/test_fiscal*.py`, depois:

Run: `cd hermes_agents && python -m pytest tests/test_fiscal.py tests/test_fiscal_seguranca.py tests/test_fiscal_apuracao_fechamento.py tests/test_fiscal_obrigacoes_ocorrencias.py -v`
Expected: 100% PASS, com o teste-guarda de contagem de placeholders passando.

- [ ] **Step 2: Suíte Bling + compras + vendas**

Run: `cd hermes_agents && python -m pytest tests/test_bling_routes.py tests/test_bling_erp.py tests/test_compras_bling.py tests/test_vendas.py -v`
Expected: todos PASS.

- [ ] **Step 3: Suíte inteira**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: mesmas 8 falhas pré-existentes, nenhuma nova.

- [ ] **Step 4: Smoke test de import**

Run: `cd hermes_agents && python -c "import athena_bridge; print('import OK')"`
Expected: imprime `import OK` (as linhas de `getaddrinfo failed` são esperadas fora do servidor —
não há Postgres alcançável no ambiente local).

- [ ] **Step 5: Confirmar que o default de produção sobreviveu**

Run: `cd hermes_agents && python -c "import bling_erp as b; print(b.get_ambiente(), b._base_url() == b.BASE_URL)"`
Expected: `producao True`. Se imprimir `homologacao`, alguma config local está ligando o toggle —
investigue antes de considerar a fase concluída.

- [ ] **Step 6: Conferir a contagem de parâmetros das queries tocadas**

Releia e conte, uma última vez: `_upsert_nota_fiscal` (INSERT e UPDATE), o UPDATE/INSERT de
`compras_pedidos` e o UPDATE/INSERT de `vendas_pedidos`. Para cada query, número de colunas =
número de placeholders `$N` = número de argumentos posicionais, descontando literais sem
placeholder (`NOW()`, `'bling'`). Documente os seis números no relatório final.

- [ ] **Step 7: Commit**

```bash
git status --porcelain
```

Confirme que nada de `hermes_agents/storage/` ou `hermes_agents/uploads/` está staged. Se não
houver mudança de código real:

```bash
git commit -m "test: regressao final ambiente de homologacao Bling" --allow-empty
```
