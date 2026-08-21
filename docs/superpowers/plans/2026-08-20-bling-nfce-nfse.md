# Bling — NFC-e e NFS-e (Plano 4b/N) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sincronizar NFC-e (nota de consumidor, venda presencial) e NFS-e (nota de serviço)
do Bling, reaproveitando `fiscal_notas_fiscais` (tabela já usada por NF-e) via coluna nova
`tipo_documento`, em vez de criar tabelas paralelas.

**Architecture:** Estende `_upsert_nota_fiscal` (`core/fiscal.py`) — a função central de upsert
já usada por `sincronizar_notas_fiscais_bling` e `sincronizar_uma_nota_fiscal` (webhook) — pra
aceitar um parâmetro `tipo_documento` com default `'nfe'`, preservando 100% do comportamento
atual pra quem já chama a função sem passar esse argumento. Duas funções de sync novas
(`sincronizar_nfce_bling`, `sincronizar_nfse_bling`) reaproveitam essa função estendida, só
trocando o wrapper de API Bling e o valor de `tipo_documento`. Isso é a task de maior risco do
módulo Bling até agora: `_upsert_nota_fiscal` tem 33 parâmetros posicionais em duas queries SQL
(INSERT e UPDATE) e já tem um bug documentado no próprio código-fonte (comentário sobre
impostos zerados quando a nota chegava via webhook) — qualquer erro de contagem/ordem de
parâmetro nesta função silenciosamente grava dado fiscal errado.

**Tech Stack:** Flask (Python), pytest, requests.

**Spec:** `docs/superpowers/specs/2026-08-20-modulo-bling-design.md` (seção "NFC-e / NFS-e
(novo)")

## Global Constraints

- **Nenhuma chamada existente a `_upsert_nota_fiscal` pode mudar de comportamento.** O
  parâmetro novo (`tipo_documento`) tem que ter default `'nfe'` e ir por ÚLTIMO na assinatura,
  nunca inserido no meio da lista de parâmetros posicionais existente — inserir no meio
  desalinha todos os `$N` das duas queries SQL sem gerar erro de sintaxe, só dado errado
  silencioso. Antes de editar, releia a função inteira em `core/fiscal.py` (procure `async def
  _upsert_nota_fiscal`) pra confirmar a lista exata de parâmetros posicionais nas duas queries
  (INSERT tem 35 placeholders `$1`...`$35`, UPDATE tem 33) e conte de novo depois de editar.
- A coluna nova (`tipo_documento VARCHAR(10) DEFAULT 'nfe'`) usa `ADD COLUMN IF NOT EXISTS`
  com default, preservando as notas NF-e já sincronizadas (ficam automaticamente
  `tipo_documento = 'nfe'`, sem precisar de UPDATE manual — o `DEFAULT` do `ALTER TABLE` já
  cobre isso em Postgres).
- TDD rigoroso nesta fase, mais do que nas anteriores: todo teste de `_upsert_nota_fiscal`
  precisa confirmar que os testes JÁ EXISTENTES de sync de NF-e continuam passando exatamente
  como antes (nenhum campo fiscal mudando de valor) — rode
  `tests/test_fiscal_seguranca.py` e qualquer outro arquivo de teste que cubra
  `_upsert_nota_fiscal`/`sincronizar_notas_fiscais_bling` a cada task, não só no final.
- O endpoint exato da API Bling v3 pra NFC-e/NFS-e (`nfce`, `nfse`) segue a mesma convenção
  REST já usada pra NF-e (`nfe`) em `bling_erp.py`, mas não foi confirmado contra uma conta
  Bling real ao vivo — mesmo caveat já registrado no plano de Situações
  (`docs/superpowers/plans/2026-08-20-bling-situacoes-crud.md`) sobre endpoints não
  confirmados. Se divergir na prática, o ponto de ajuste é só a string do endpoint nos
  wrappers da Task 1.
- Rodar a suíte completa (`cd hermes_agents && python -m pytest tests/ -q`) ao final de cada
  task. Baseline conhecido: 8 falhas pré-existentes alheias a Bling (RH endpoints, compras
  segurança, RBAC lojas) — nenhuma NOVA falha é aceitável, e principalmente nenhuma falha em
  testes de fiscal/NF-e que hoje passam.

---

### Task 1: Wrappers de API Bling para NFC-e e NFS-e

**Files:**
- Modify: `hermes_agents/bling_erp.py` (adicionar 4 funções novas, logo após
  `get_nfe_detail`/`get_nfe_xml` — procure a seção de notas fiscais)
- Test: `hermes_agents/tests/test_bling_erp.py`

**Interfaces:**
- Produces:
  - `bling_erp.listar_nfce(pagina: int = 1, limite: int = 100) -> dict`
  - `bling_erp.get_nfce_detalhe(id_nota: int) -> dict`
  - `bling_erp.listar_nfse(pagina: int = 1, limite: int = 100) -> dict`
  - `bling_erp.get_nfse_detalhe(id_nota: int) -> dict`

- [ ] **Step 1: Escrever os testes**

Adicionar a `hermes_agents/tests/test_bling_erp.py`:

```python
    def test_listar_nfce_chama_endpoint_correto(self):
        with patch("bling_erp._request", return_value={"data": []}) as mock_request:
            bling_erp.listar_nfce(pagina=1, limite=100)
            mock_request.assert_called_once_with("nfce", {"pagina": 1, "limite": 100})

    def test_get_nfce_detalhe_chama_endpoint_correto(self):
        with patch("bling_erp._request", return_value={"data": {}}) as mock_request:
            bling_erp.get_nfce_detalhe(321)
            mock_request.assert_called_once_with("nfce/321")

    def test_listar_nfse_chama_endpoint_correto(self):
        with patch("bling_erp._request", return_value={"data": []}) as mock_request:
            bling_erp.listar_nfse(pagina=1, limite=100)
            mock_request.assert_called_once_with("nfse", {"pagina": 1, "limite": 100})

    def test_get_nfse_detalhe_chama_endpoint_correto(self):
        with patch("bling_erp._request", return_value={"data": {}}) as mock_request:
            bling_erp.get_nfse_detalhe(654)
            mock_request.assert_called_once_with("nfse/654")
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_bling_erp.py -k "nfce or nfse" -v`
Expected: FAIL — `AttributeError`.

- [ ] **Step 3: Implementar os wrappers**

Em `hermes_agents/bling_erp.py`, adicionar (posição sugerida: logo após `get_nfe_detail`):

```python
# ── NFC-e (nota de consumidor) ──

def listar_nfce(pagina: int = 1, limite: int = 100) -> dict:
    return _request("nfce", {"pagina": pagina, "limite": limite})

def get_nfce_detalhe(id_nota: int) -> dict:
    return _request(f"nfce/{id_nota}")

# ── NFS-e (nota de serviço) ──

def listar_nfse(pagina: int = 1, limite: int = 100) -> dict:
    return _request("nfse", {"pagina": pagina, "limite": limite})

def get_nfse_detalhe(id_nota: int) -> dict:
    return _request(f"nfse/{id_nota}")
```

- [ ] **Step 4: Rodar e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_bling_erp.py -k "nfce or nfse" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/bling_erp.py hermes_agents/tests/test_bling_erp.py
git commit -m "feat: wrappers de API Bling para NFC-e e NFS-e"
```

---

### Task 2: Coluna `tipo_documento` + extensão segura de `_upsert_nota_fiscal`

Esta é a task de maior risco do plano. Leia com atenção: o objetivo é adicionar UM parâmetro
novo (`tipo_documento`) numa função que já tem 33 parâmetros posicionais, sem desalinhar
nenhum dos existentes.

**Files:**
- Modify: `hermes_agents/core/fiscal.py` (`_ensure_tables` ganha a coluna nova;
  `_upsert_nota_fiscal` ganha o parâmetro novo)
- Test: `hermes_agents/tests/test_fiscal_seguranca.py` (ou o arquivo de teste que já cobrir
  `_upsert_nota_fiscal`/sync de NF-e — confirme lendo os arquivos de teste existentes de
  `core/fiscal.py` antes de decidir onde adicionar; se `_upsert_nota_fiscal` já for testado em
  algum arquivo específico, os testes novos vão nele, não num arquivo novo)

**Interfaces:**
- Produces: `core.fiscal._upsert_nota_fiscal(db, bling_id: int, detalhe: dict, tipo_documento:
  str = "nfe") -> int` (assinatura estendida, todos os callers existentes continuam
  funcionando sem passar o novo argumento)

- [ ] **Step 1: Localizar e ler a função inteira antes de editar**

Leia `hermes_agents/core/fiscal.py` na íntegra a partir de `async def _upsert_nota_fiscal` até
o `return nota_id` (ou linha equivalente que fecha a função) — não edite sem ter lido a função
inteira uma vez. Anote quantos `$N` existem na query `UPDATE` e quantos na query `INSERT`
(confirme se ainda são 33 e 35 respectivamente, ou se mudou desde a escrita deste plano).

- [ ] **Step 2: Escrever o teste (RED) confirmando que `tipo_documento` é gravado**

Adicione ao arquivo de teste escolhido no Step anterior (ajuste os mocks de `get_db`/`run_async`
conforme o padrão já usado nos testes existentes de `core/fiscal.py` no mesmo arquivo):

```python
class TestUpsertNotaFiscalTipoDocumento(unittest.TestCase):
    def test_upsert_grava_tipo_documento_nfce_quando_informado(self):
        fake_db = AsyncMock()
        fake_db.fetchval.return_value = None  # nota nova
        fake_db.fetchrow.return_value = None
        detalhe_minimo = {
            "numero": "1001", "chaveAcesso": "chave-teste",
            "dataEmissao": "2026-08-20", "contato": {}, "naturezaOperacao": {},
            "tributos": {}, "itens": [],
        }
        run_async(core_fiscal._upsert_nota_fiscal(fake_db, 999, detalhe_minimo, tipo_documento="nfce"))
        insert_call = next(c for c in fake_db.execute.call_args_list if "INSERT INTO fiscal_notas_fiscais" in c.args[0])
        self.assertIn("nfce", insert_call.args)

    def test_upsert_default_continua_nfe_sem_passar_tipo_documento(self):
        fake_db = AsyncMock()
        fake_db.fetchval.return_value = None
        fake_db.fetchrow.return_value = None
        detalhe_minimo = {
            "numero": "1002", "chaveAcesso": "chave-teste-2",
            "dataEmissao": "2026-08-20", "contato": {}, "naturezaOperacao": {},
            "tributos": {}, "itens": [],
        }
        run_async(core_fiscal._upsert_nota_fiscal(fake_db, 998, detalhe_minimo))
        insert_call = next(c for c in fake_db.execute.call_args_list if "INSERT INTO fiscal_notas_fiscais" in c.args[0])
        self.assertIn("nfe", insert_call.args)
```

Ajuste os imports (`from core import fiscal as core_fiscal`, `from core import run_async`, etc)
conforme o padrão já usado no arquivo de teste escolhido — o esqueleto acima é o comportamento
esperado, não uma receita rígida de mock; se `run_async(_upsert_nota_fiscal(...))` não bater
com como a função real é chamada (ela pode já ser sempre chamada de dentro de outra corrotina
`async def`, sem `run_async` direto), adapte o teste pra chamar via `asyncio.run` ou o helper
de teste assíncrono que os outros testes de `core/fiscal.py` já usarem.

- [ ] **Step 2b: Rodar e confirmar que falha**

Run: `cd hermes_agents && python -m pytest tests/test_fiscal_seguranca.py -k "tipo_documento" -v`
(ajuste o caminho do arquivo se você escolheu outro no Step 1 da task)
Expected: FAIL — `TypeError: _upsert_nota_fiscal() got an unexpected keyword argument
'tipo_documento'`.

- [ ] **Step 3: Adicionar a coluna em `_ensure_tables`**

Em `hermes_agents/core/fiscal.py`, dentro de `_ensure_tables`, logo após o `CREATE TABLE IF
NOT EXISTS fiscal_notas_fiscais (...)`, adicionar:

```python
        await db.execute("ALTER TABLE fiscal_notas_fiscais ADD COLUMN IF NOT EXISTS tipo_documento VARCHAR(10) DEFAULT 'nfe'")
```

- [ ] **Step 4: Estender `_upsert_nota_fiscal` — adicionar o parâmetro e as duas colunas SQL**

Em `hermes_agents/core/fiscal.py`:

1. Mude a assinatura de `async def _upsert_nota_fiscal(db, bling_id: int, detalhe: dict) -> int:`
   para `async def _upsert_nota_fiscal(db, bling_id: int, detalhe: dict, tipo_documento: str =
   "nfe") -> int:`.

2. Na query `UPDATE fiscal_notas_fiscais SET ...`, adicione `tipo_documento=$N` no `SET` (onde
   `$N` é o próximo número depois do último `$` já usado nessa query — confirme o número exato
   lendo a query atual, não assuma que é `$33` sem conferir) e adicione `tipo_documento` como
   argumento posicional correspondente na chamada `await db.execute(...)` logo abaixo, na MESMA
   posição relativa (penúltimo argumento, antes do `bling_id` que fecha o `WHERE bling_id=$N`
   final — confirme que o `WHERE` continua sendo o ÚLTIMO placeholder da query, então
   `tipo_documento` entra IMEDIATAMENTE ANTES dele, não depois).

3. Na query `INSERT INTO fiscal_notas_fiscais (...) VALUES (...) RETURNING id`, adicione
   `tipo_documento` na lista de colunas e `$N` correspondente na lista de `VALUES` (mesmo
   raciocínio: confirme o próximo número livre lendo a query atual), e adicione
   `tipo_documento` como argumento posicional na MESMA posição relativa na chamada
   `db.fetchval(...)` logo abaixo (a lista de colunas do INSERT e a lista de argumentos
   posicionais têm que estar na MESMA ORDEM — é o erro mais fácil de cometer aqui).

- [ ] **Step 5: Rodar e confirmar que o teste novo passa**

Run: `cd hermes_agents && python -m pytest tests/test_fiscal_seguranca.py -k "tipo_documento" -v`
Expected: PASS

- [ ] **Step 6: Rodar TODA a suíte de fiscal, não só o teste novo — este é o passo mais
  importante desta task**

Run: `cd hermes_agents && python -m pytest tests/test_fiscal_seguranca.py tests/test_fiscal_apuracao_fechamento.py tests/test_fiscal_obrigacoes_ocorrencias.py -v`
(rode todos os arquivos de teste que existirem cobrindo `core/fiscal.py` — liste com `ls
hermes_agents/tests/test_fiscal*.py` antes de montar o comando final, pra não deixar nenhum de
fora)
Expected: TODOS passam exatamente como antes desta task — nenhum teste de NF-e pode mudar de
resultado. Se algum campo fiscal (valor_icms, valor_pis, etc) aparecer deslocado ou trocado em
qualquer teste, PARE — isso significa que a contagem de `$N` ficou errada e algum dado fiscal
está sendo gravado na coluna errada. Não prossiga pra próxima task até isso estar 100% certo.

- [ ] **Step 7: Rodar a suíte completa**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: mesmas 8 falhas pré-existentes (RH, compras, RBAC lojas), nenhuma nova.

- [ ] **Step 8: Commit**

```bash
git add hermes_agents/core/fiscal.py hermes_agents/tests/test_fiscal_seguranca.py
git commit -m "feat: coluna tipo_documento em fiscal_notas_fiscais + extensao segura de _upsert_nota_fiscal"
```

(ajuste o nome do arquivo de teste no `git add` conforme o caminho real escolhido)

---

### Task 3: Sync de NFC-e e NFS-e

Reaproveita `_upsert_nota_fiscal` (agora estendida) via duas funções de sync novas, seguindo o
mesmo padrão de paginação em lotes de `sincronizar_notas_fiscais_bling` (procure
`MAX_DETALHES_POR_CHAMADA` em `core/fiscal.py` como referência — o mesmo cuidado de evitar
timeout de proxy Cloudflare em contas com muitas notas se aplica aqui).

**Files:**
- Modify: `hermes_agents/core/fiscal.py` (adicionar `sincronizar_nfce_bling`,
  `sincronizar_nfse_bling`)
- Test: mesmo arquivo escolhido na Task 2

**Interfaces:**
- Consumes: `bling_erp.listar_nfce`, `bling_erp.get_nfce_detalhe`, `bling_erp.listar_nfse`,
  `bling_erp.get_nfse_detalhe` (Task 1), `core.fiscal._upsert_nota_fiscal(db, bling_id,
  detalhe, tipo_documento)` (Task 2)
- Produces:
  - `core.fiscal.sincronizar_nfce_bling(pagina: int = 1, limite: int = 100, pular: int = 0) -> dict`
  - `core.fiscal.sincronizar_nfse_bling(pagina: int = 1, limite: int = 100, pular: int = 0) -> dict`

- [ ] **Step 1: Escrever os testes (RED)**

```python
    def test_sincronizar_nfce_bling_usa_upsert_com_tipo_documento_nfce(self):
        fake_db = AsyncMock()
        fake_db.fetchval.return_value = None
        with patch("core.fiscal.get_access_token", return_value="tok"), \
             patch("core.fiscal.get_db", new=AsyncMock(return_value=fake_db)), \
             patch("core.fiscal.listar_nfce", return_value={"data": [{"id": 111}]}), \
             patch("core.fiscal.get_nfce_detalhe", return_value={"data": {
                 "numero": "5001", "chaveAcesso": "chave-nfce", "dataEmissao": "2026-08-20",
                 "contato": {}, "naturezaOperacao": {}, "tributos": {}, "itens": [],
             }}):
            resultado = core_fiscal.sincronizar_nfce_bling()
        self.assertEqual(resultado["sync"], 1)

    def test_sincronizar_nfse_bling_usa_upsert_com_tipo_documento_nfse(self):
        fake_db = AsyncMock()
        fake_db.fetchval.return_value = None
        with patch("core.fiscal.get_access_token", return_value="tok"), \
             patch("core.fiscal.get_db", new=AsyncMock(return_value=fake_db)), \
             patch("core.fiscal.listar_nfse", return_value={"data": [{"id": 222}]}), \
             patch("core.fiscal.get_nfse_detalhe", return_value={"data": {
                 "numero": "6001", "chaveAcesso": "chave-nfse", "dataEmissao": "2026-08-20",
                 "contato": {}, "naturezaOperacao": {}, "tributos": {}, "itens": [],
             }}):
            resultado = core_fiscal.sincronizar_nfse_bling()
        self.assertEqual(resultado["sync"], 1)
```

Ajuste os `patch(...)` conforme o padrão real de import usado em `sincronizar_notas_fiscais_bling`
(local, dentro da função — confirme lendo essa função de novo antes de escrever o mock).

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_fiscal_seguranca.py -k "nfce_bling or nfse_bling" -v`
Expected: FAIL — `AttributeError`.

- [ ] **Step 3: Implementar as duas funções**

Em `hermes_agents/core/fiscal.py`, logo após `sincronizar_uma_nota_fiscal`, adicionar (o corpo
segue exatamente o mesmo esqueleto de `sincronizar_notas_fiscais_bling`, só trocando os
wrappers de listagem/detalhe e passando `tipo_documento` pro upsert):

```python
def sincronizar_nfce_bling(pagina: int = 1, limite: int = 100, pular: int = 0) -> dict:
    """Sync de NFC-e (nota de consumidor, venda presencial) — mesmo padrao de paginacao em
    lotes de sincronizar_notas_fiscais_bling, gravando em fiscal_notas_fiscais com
    tipo_documento='nfce'."""
    from bling_erp import listar_nfce, get_nfce_detalhe, get_access_token, get_auth_url
    token = get_access_token()
    if not token: return {"error": "Bling nao autenticado", "auth_url": get_auth_url()}

    MAX_PAGINAS = 50
    MAX_DETALHES_POR_CHAMADA = 50
    notas_resumo = []
    erros = []
    pag = pagina
    mais_paginas = False
    for _ in range(MAX_PAGINAS):
        r = listar_nfce(pag, limite)
        dados = r.get("data", [])
        if not dados or r.get("error"):
            if r.get("error"): erros.append(f"pag {pag}: {r['error']}")
            break
        notas_resumo.extend(dados)
        if len(dados) < limite:
            break
        pag += 1
    else:
        mais_paginas = True
    if not notas_resumo:
        return {"sync": 0, "message": "sem dados", "erros": erros}

    lote = notas_resumo[pular:pular + MAX_DETALHES_POR_CHAMADA]
    proximo_pular = pular + len(lote)
    mais_notas = proximo_pular < len(notas_resumo) or mais_paginas

    async def _go():
        db = await get_db()
        total = 0
        for nf_resumo in lote:
            bling_id = nf_resumo.get("id")
            if not bling_id:
                continue
            detalhe = None
            for attempt in range(3):
                r_detalhe = get_nfce_detalhe(bling_id)
                if not r_detalhe.get("error"):
                    detalhe = r_detalhe.get("data", {})
                    break
                if r_detalhe.get("status_code") == 429:
                    time.sleep(2 ** attempt)
                    continue
                erros.append(f"nota {bling_id}: {r_detalhe['error']}")
                break
            if not detalhe:
                detalhe = nf_resumo
            try:
                await _upsert_nota_fiscal(db, bling_id, detalhe, tipo_documento="nfce")
                total += 1
            except Exception as e:
                log(AGENT, f"Erro sync NFC-e {nf_resumo.get('numero')}: {e}")
        return {"sync": total, "erros": erros, "mais_paginas": mais_paginas,
                "mais_notas": mais_notas, "proximo_pular": proximo_pular if mais_notas else 0,
                "total_notas": len(notas_resumo)}
    try:
        return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro sincronizar_nfce_bling: {e}")
        return {"error": str(e), "sync": 0}


def sincronizar_nfse_bling(pagina: int = 1, limite: int = 100, pular: int = 0) -> dict:
    """Sync de NFS-e (nota de servico) — mesmo padrao de sincronizar_nfce_bling, gravando
    com tipo_documento='nfse'."""
    from bling_erp import listar_nfse, get_nfse_detalhe, get_access_token, get_auth_url
    token = get_access_token()
    if not token: return {"error": "Bling nao autenticado", "auth_url": get_auth_url()}

    MAX_PAGINAS = 50
    MAX_DETALHES_POR_CHAMADA = 50
    notas_resumo = []
    erros = []
    pag = pagina
    mais_paginas = False
    for _ in range(MAX_PAGINAS):
        r = listar_nfse(pag, limite)
        dados = r.get("data", [])
        if not dados or r.get("error"):
            if r.get("error"): erros.append(f"pag {pag}: {r['error']}")
            break
        notas_resumo.extend(dados)
        if len(dados) < limite:
            break
        pag += 1
    else:
        mais_paginas = True
    if not notas_resumo:
        return {"sync": 0, "message": "sem dados", "erros": erros}

    lote = notas_resumo[pular:pular + MAX_DETALHES_POR_CHAMADA]
    proximo_pular = pular + len(lote)
    mais_notas = proximo_pular < len(notas_resumo) or mais_paginas

    async def _go():
        db = await get_db()
        total = 0
        for nf_resumo in lote:
            bling_id = nf_resumo.get("id")
            if not bling_id:
                continue
            detalhe = None
            for attempt in range(3):
                r_detalhe = get_nfse_detalhe(bling_id)
                if not r_detalhe.get("error"):
                    detalhe = r_detalhe.get("data", {})
                    break
                if r_detalhe.get("status_code") == 429:
                    time.sleep(2 ** attempt)
                    continue
                erros.append(f"nota {bling_id}: {r_detalhe['error']}")
                break
            if not detalhe:
                detalhe = nf_resumo
            try:
                await _upsert_nota_fiscal(db, bling_id, detalhe, tipo_documento="nfse")
                total += 1
            except Exception as e:
                log(AGENT, f"Erro sync NFS-e {nf_resumo.get('numero')}: {e}")
        return {"sync": total, "erros": erros, "mais_paginas": mais_paginas,
                "mais_notas": mais_notas, "proximo_pular": proximo_pular if mais_notas else 0,
                "total_notas": len(notas_resumo)}
    try:
        return run_async(_go())
    except Exception as e:
        log(AGENT, f"Erro sincronizar_nfse_bling: {e}")
        return {"error": str(e), "sync": 0}
```

- [ ] **Step 4: Rodar e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_fiscal_seguranca.py -k "nfce_bling or nfse_bling" -v`
Expected: PASS

- [ ] **Step 5: Rodar toda a suíte de fiscal de novo**

Run: `cd hermes_agents && python -m pytest tests/test_fiscal_seguranca.py tests/test_fiscal_apuracao_fechamento.py tests/test_fiscal_obrigacoes_ocorrencias.py -v`
(mesma lista de arquivos da Task 2, Step 6)
Expected: todos PASS, sem regressão em nenhum teste de NF-e existente.

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/core/fiscal.py hermes_agents/tests/test_fiscal_seguranca.py
git commit -m "feat: sync de NFC-e e NFS-e Bling reaproveitando fiscal_notas_fiscais"
```

---

### Task 4: Rotas HTTP para NFC-e e NFS-e em `bling_bp`

Adiciona rotas de sync e uma rota de leitura local nova (`GET /api/bling/notas?tipo=...`) que
lê de `fiscal_notas_fiscais` filtrando por `tipo_documento` — distinta da rota já existente
`GET /api/bling/financeiro/notas-fiscais`, que proxya direto pra API Bling ao vivo (só NF-e,
sem filtro de tipo, sem tocar o banco local).

**Files:**
- Modify: `hermes_agents/routes/integrations.py` (bloco `bling_bp`, logo após as rotas de
  pedidos de compra da fase anterior)
- Test: `hermes_agents/tests/test_bling_routes.py`

**Interfaces:**
- Consumes: `core.fiscal.sincronizar_nfce_bling`, `core.fiscal.sincronizar_nfse_bling`
  (Task 3)
- Produces:
  - `GET /api/bling/notas?tipo=nfce|nfse|nfe` (lê local de `fiscal_notas_fiscais`; sem query
    `tipo`, lista todas)
  - `POST /api/bling/nfce/sincronizar`
  - `POST /api/bling/nfse/sincronizar`

- [ ] **Step 1: Escrever os testes**

```python
    def test_notas_listar_route_sem_filtro(self):
        rv = self.client.get("/api/bling/notas")
        self.assertEqual(rv.status_code, 200)

    def test_notas_listar_route_com_filtro_tipo(self):
        rv = self.client.get("/api/bling/notas?tipo=nfce")
        self.assertEqual(rv.status_code, 200)

    def test_nfce_sincronizar_route(self):
        with patch("routes.integrations.sincronizar_nfce_bling", return_value={"sync": 1}) as mock_sync:
            rv = self.client.post("/api/bling/nfce/sincronizar")
            self.assertEqual(rv.status_code, 200)
            mock_sync.assert_called_once()

    def test_nfse_sincronizar_route(self):
        with patch("routes.integrations.sincronizar_nfse_bling", return_value={"sync": 1}) as mock_sync:
            rv = self.client.post("/api/bling/nfse/sincronizar")
            self.assertEqual(rv.status_code, 200)
            mock_sync.assert_called_once()
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_bling_routes.py -k "notas_listar or nfce_sincronizar or nfse_sincronizar" -v`
Expected: FAIL — 404.

- [ ] **Step 3: Adicionar os imports e as rotas**

Em `hermes_agents/routes/integrations.py`, adicionar import local dedicado dentro de cada
handler de escrita (seguindo a correção de import feita na fase anterior — NUNCA no nível de
módulo, pra não arrastar migração pesada pro boot):

```python
@bling_bp.route("/notas")
def api_notas_locais():
    tipo = request.args.get("tipo", "")
    async def _go():
        db = await get_db()
        if tipo:
            rows = await db.fetch("""SELECT id, numero, chave_acesso, tipo_documento, status,
                data_emissao, valor_nf, contato_nome, bling_id
                FROM fiscal_notas_fiscais WHERE tipo_documento = $1 ORDER BY data_emissao DESC""", tipo)
        else:
            rows = await db.fetch("""SELECT id, numero, chave_acesso, tipo_documento, status,
                data_emissao, valor_nf, contato_nome, bling_id
                FROM fiscal_notas_fiscais ORDER BY data_emissao DESC LIMIT 200""")
        return [dict(r) for r in rows]
    try:
        return jsonify(run_async(_go()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bling_bp.route("/nfce/sincronizar", methods=["POST"])
@requer_permissao("financeiro.ver")
def api_sincronizar_nfce():
    from core.fiscal import sincronizar_nfce_bling
    return jsonify(sincronizar_nfce_bling())


@bling_bp.route("/nfse/sincronizar", methods=["POST"])
@requer_permissao("financeiro.ver")
def api_sincronizar_nfse():
    from core.fiscal import sincronizar_nfse_bling
    return jsonify(sincronizar_nfse_bling())
```

Nota: as rotas de sync usam `@requer_permissao("financeiro.ver")`, mesmo padrão já usado pelas
rotas irmãs de contas a pagar/receber no mesmo arquivo (`api_contas_pagar`,
`api_contas_receber`) — lição da fase anterior (Pedidos de Compra) sobre rotas de escrita sem
RBAC.

- [ ] **Step 4: Rodar e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_bling_routes.py -k "notas_listar or nfce_sincronizar or nfse_sincronizar" -v`
Expected: PASS

- [ ] **Step 5: Rodar a suíte completa**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: mesmas 8 falhas pré-existentes, nenhuma nova.

- [ ] **Step 6: Commit**

```bash
git add hermes_agents/routes/integrations.py hermes_agents/tests/test_bling_routes.py
git commit -m "feat: rotas GET/POST para NFC-e/NFS-e (/api/bling/notas, /nfce/sincronizar, /nfse/sincronizar)"
```

---

### Task 5: Regressão final

Esta task precisa de atenção redobrada porque o plano tocou a função fiscal mais sensível do
sistema.

**Files:**
- Test: todos os arquivos `hermes_agents/tests/test_fiscal*.py`, `test_bling_routes.py`,
  `test_bling_erp.py`

- [ ] **Step 1: Listar e rodar TODOS os arquivos de teste de fiscal**

Run: `ls hermes_agents/tests/test_fiscal*.py`

Depois rode todos juntos:

Run: `cd hermes_agents && python -m pytest tests/test_fiscal_seguranca.py tests/test_fiscal_apuracao_fechamento.py tests/test_fiscal_obrigacoes_ocorrencias.py -v`
(adicione qualquer arquivo que o `ls` acima tiver listado e não estiver nesse comando)
Expected: 100% dos testes de fiscal passam exatamente como antes deste plano. Isso inclui
confirmar visualmente, olhando a saída, que nenhum teste que verifica valor de imposto
(`valor_icms`, `valor_pis`, `valor_cofins`, etc) mudou de resultado — não basta "mesmo número
de passed", precisa ser literalmente os mesmos testes com o mesmo veredito.

- [ ] **Step 2: Rodar a suíte Bling completa**

Run: `cd hermes_agents && python -m pytest tests/test_bling_routes.py tests/test_bling_erp.py -v`
Expected: todos PASS.

- [ ] **Step 3: Rodar a suíte inteira do projeto**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: mesmas 8 falhas pré-existentes documentadas (RH endpoints, compras segurança, RBAC
lojas), nenhuma nova.

- [ ] **Step 4: Smoke test de import da app completa**

Run: `cd hermes_agents && python -c "import athena_bridge"`
Expected: importa sem erro.

- [ ] **Step 5: Confirmar manualmente a contagem de parâmetros de `_upsert_nota_fiscal` uma
  última vez**

Leia a função `_upsert_nota_fiscal` inteira mais uma vez (mesmo já tendo lido na Task 2) e
conte: o número de colunas na lista do `INSERT INTO fiscal_notas_fiscais (...)` bate
exatamente com o número de `$N` na cláusula `VALUES (...)`, que bate exatamente com o número
de argumentos posicionais passados pra `db.fetchval(...)`? Mesma checagem pro `UPDATE ... SET
...` e seus argumentos. Documente no relatório final que essa contagem foi conferida
manualmente uma última vez, com os três números exatos encontrados.

- [ ] **Step 6: Commit (se houver qualquer ajuste feito nesta task)**

```bash
git status --porcelain
```

Confirme que nada de `hermes_agents/storage/`/`hermes_agents/uploads/` está staged. Se não
houver mudança de código real:

```bash
git commit -m "test: regressao final NFC-e/NFS-e Bling" --allow-empty
```
