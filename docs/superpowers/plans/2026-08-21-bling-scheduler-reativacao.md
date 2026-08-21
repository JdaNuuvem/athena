# Bling — Isolamento do Scheduler e Reativação dos Jobs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer os syncs Bling voltarem a rodar automaticamente sem reintroduzir o problema que
motivou a desativação deles — para isso, primeiro isolar a execução dos jobs do scheduler (hoje
sequencial numa thread só), depois religar os quatro jobs Bling que estão comentados.

**Architecture:** `core/scheduler.py::_worker()` percorre `JOBS` e chama `job["fn"]()` **de
forma bloqueante** dentro do próprio loop. Consequência: qualquer job lento atrasa todos os
outros. É por isso que os jobs Bling foram comentados — um sync de NF-e pode paginar até 50
notas com backoff de até 7s cada em rate limit, segurando o loop por minutos, e nesse meio tempo
`shopee-renovar-tokens` (a cada 15 min, renova token que expira em ≤30 min) não roda. A correção
é o worker passar a **disparar cada job numa thread própria**, com uma trava por job (`running`)
que impede a mesma função de ser reexecutada enquanto a anterior não terminou.

**Decisões (confirmadas com o usuário):** (1) isolar os jobs antes de reativar qualquer coisa;
(2) religar apenas os **quatro jobs que já existem** e estão comentados — `bling-pedidos`,
`bling-nf`, `bling-cr-cp`, `bling-categorias`. Jobs novos para os syncs das fases 4a/4b/5
(pedidos de compra, NFC-e, NFS-e, situações, canais, plano de contas) ficam **fora deste
escopo**.

**Tech Stack:** Python (threading da stdlib, sem dependência externa), pytest.

**Spec:** `docs/superpowers/specs/2026-08-20-modulo-bling-design.md` (seção "Contexto",
item "Scheduler com quase todos os jobs Bling comentados/desativados")

## Global Constraints

- **Sem dependência nova.** O módulo declara no docstring "no external deps" — nada de
  APScheduler, Celery ou afins. `threading` da stdlib resolve.
- **Nenhuma função `_sync_*` muda de comportamento.** Existem quatro arquivos de teste
  (`tests/test_scheduler_*.py`) que chamam essas funções diretamente; todos precisam continuar
  passando sem edição.
- **A trava por job é obrigatória.** Sem ela, o isolamento piora as coisas: `last_run` é marcado
  no início da execução, então um job que demore mais que o próprio intervalo passaria a ser
  disparado de novo em paralelo consigo mesmo, multiplicando chamadas à API do Bling.
- **Intervalos preservados.** Os quatro jobs voltam com exatamente os intervalos que já estavam
  escritos nas linhas comentadas (300/600/3600/7200 s). Não é hora de reajustar cadência — se
  precisar, é decisão separada com o usuário.
- Rodar a suíte completa (`cd hermes_agents && python -m pytest tests/ -q`) ao final de cada
  task. Baseline conhecido: **8 falhas pré-existentes** (RH endpoints, compras segurança, RBAC
  lojas). Nenhuma falha nova é aceitável.

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `hermes_agents/core/scheduler.py` | `_deve_rodar` (decisão pura), `_run_job` (execução isolada), `_worker` disparando threads; religa os 4 jobs Bling |
| `hermes_agents/tests/test_scheduler_isolamento.py` | Testes da lógica de elegibilidade e da liberação da trava |

---

### Task 1: Isolar a execução dos jobs

**Files:**
- Modify: `hermes_agents/core/scheduler.py` (`add_job` linhas ~9-10, `_worker` linhas ~13-24)
- Test: `hermes_agents/tests/test_scheduler_isolamento.py` (arquivo novo)

**Interfaces:**
- Produces:
  - `core.scheduler._deve_rodar(job: dict, now: float) -> bool`
  - `core.scheduler._run_job(job: dict) -> None`
- `add_job` passa a registrar a chave `"running": False` em cada job.

- [ ] **Step 1: Escrever os testes (RED)**

Criar `hermes_agents/tests/test_scheduler_isolamento.py`. A lógica de decisão é extraída numa
função pura justamente pra ser testável sem thread nem sleep — teste de concorrência com
`time.sleep` é flaky e não seria confiável em CI.

```python
"""_worker() (core/scheduler.py) rodava os jobs em sequencia na mesma thread:
um sync Bling lento (NF-e pagina ate' 50 notas com backoff de ate' 7s cada em
rate limit) segurava o loop por minutos, e nesse meio tempo o job
shopee-renovar-tokens — que precisa rodar a cada 15min pra renovar token que
expira em 30min — nao rodava. Por isso os jobs Bling viviam comentados.
Agora cada job roda em thread propria, com trava por job pra nao sobrepor
execucoes do mesmo sync (o que multiplicaria chamadas a API do Bling)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scheduler import _deve_rodar, _run_job, add_job, JOBS


class TestDeveRodar(unittest.TestCase):
    def _job(self, **kw):
        base = {"fn": lambda: None, "name": "x", "interval": 300,
                "last_run": 0.0, "running": False}
        base.update(kw)
        return base

    def test_roda_quando_intervalo_passou_e_nao_esta_rodando(self):
        self.assertTrue(_deve_rodar(self._job(last_run=0.0), now=301.0))

    def test_nao_roda_antes_do_intervalo(self):
        self.assertFalse(_deve_rodar(self._job(last_run=100.0), now=200.0))

    def test_nao_roda_se_execucao_anterior_ainda_esta_em_andamento(self):
        """last_run e' marcado no INICIO da execucao. Sem essa trava, um job
        que demore mais que o proprio intervalo seria disparado de novo em
        paralelo consigo mesmo."""
        self.assertFalse(_deve_rodar(self._job(last_run=0.0, running=True), now=99999.0))


class TestRunJob(unittest.TestCase):
    def test_libera_a_trava_ao_terminar(self):
        job = {"fn": lambda: None, "name": "ok", "interval": 1, "last_run": 0.0, "running": True}
        _run_job(job)
        self.assertFalse(job["running"])

    def test_libera_a_trava_mesmo_com_excecao_e_nao_propaga(self):
        def explode(): raise RuntimeError("falhou")
        job = {"fn": explode, "name": "ruim", "interval": 1, "last_run": 0.0, "running": True}
        _run_job(job)  # nao deve levantar
        self.assertFalse(job["running"])


class TestAddJob(unittest.TestCase):
    def test_job_novo_nasce_destravado(self):
        marcador = "job-teste-isolamento"
        add_job(lambda: None, marcador, 60)
        try:
            job = next(j for j in JOBS if j["name"] == marcador)
            self.assertFalse(job["running"])
            self.assertEqual(job["last_run"], 0.0)
        finally:
            JOBS[:] = [j for j in JOBS if j["name"] != marcador]


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar e confirmar que falham**

Run: `cd hermes_agents && python -m pytest tests/test_scheduler_isolamento.py -v`
Expected: FAIL — `ImportError: cannot import name '_deve_rodar' from 'core.scheduler'`.

- [ ] **Step 3: Implementar**

Em `hermes_agents/core/scheduler.py`, substituir `add_job` e `_worker` por:

```python
def add_job(fn, name: str, interval_seconds: int):
    JOBS.append({"fn": fn, "name": name, "interval": interval_seconds,
                 "last_run": 0.0, "running": False})

def _deve_rodar(job: dict, now: float) -> bool:
    """Um job so' e' disparado se o intervalo venceu E a execucao anterior ja'
    terminou. A segunda condicao importa porque last_run e' marcado no INICIO
    da execucao: sem ela, um sync que demore mais que o proprio intervalo seria
    disparado de novo em paralelo consigo mesmo, multiplicando chamadas a API."""
    if job.get("running"):
        return False
    return now - job["last_run"] >= job["interval"]

def _run_job(job: dict):
    """Corpo executado na thread do job. Libera a trava no finally — se um sync
    estourar excecao e a trava ficar presa, aquele job nunca mais roda ate' o
    processo reiniciar."""
    try:
        job["fn"]()
    except Exception as e:
        log(AGENT, f"Job '{job['name']}' error: {e}")
    finally:
        job["running"] = False

def _worker():
    # ponytail: antes isso chamava job["fn"]() direto no loop, em sequencia.
    # Um job lento atrasava todos os outros — inclusive shopee-renovar-tokens,
    # que roda a cada 15min pra renovar token que expira em 30min. Foi
    # exatamente por isso que os jobs Bling foram comentados em vez de
    # consertados. Agora cada job sai numa thread propria e o loop segue.
    while True:
        now = time.time()
        for job in JOBS:
            if not _deve_rodar(job, now):
                continue
            job["last_run"] = now
            job["running"] = True
            threading.Thread(target=_run_job, args=(job,), daemon=True,
                             name=f"job-{job['name']}").start()
        # sleep in chunks so shutdown is responsive
        for _ in range(10):
            time.sleep(1)
```

- [ ] **Step 4: Rodar e confirmar que passam**

Run: `cd hermes_agents && python -m pytest tests/test_scheduler_isolamento.py -v`
Expected: PASS

- [ ] **Step 5: Rodar os testes de scheduler existentes**

Run: `cd hermes_agents && python -m pytest tests/test_scheduler_i9logic.py tests/test_scheduler_pedidos_shopee.py tests/test_scheduler_shopee_token.py tests/test_scheduler_sync_contatos.py -v`
Expected: todos PASS sem nenhuma edição — eles chamam as funções `_sync_*` diretamente, que não
mudaram.

- [ ] **Step 6: Suíte completa**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: mesmas 8 falhas pré-existentes, nenhuma nova.

- [ ] **Step 7: Commit**

```bash
git add hermes_agents/core/scheduler.py hermes_agents/tests/test_scheduler_isolamento.py
git commit -m "fix: jobs do scheduler rodam isolados em thread propria (job lento nao atrasa mais os outros)"
```

---

### Task 2: Religar os quatro jobs Bling

**Files:**
- Modify: `hermes_agents/core/scheduler.py` (bloco de `add_job` no fim do arquivo, linhas ~178-192)

- [ ] **Step 1: Descomentar os quatro jobs e atualizar o comentário**

O comentário atual justifica a desativação com "modulo nao usado no momento" — informação que
deixou de valer quando o módulo `/bling` foi construído (fases 1-7). Substituir o bloco inteiro
por:

```python
# ponytail: jobs run every N seconds. Adjust intervals based on volume.
# Os jobs Bling ficaram comentados por um tempo porque o _worker rodava tudo
# em sequencia numa thread so' e um sync Bling lento atrasava os jobs Shopee.
# Com a execucao isolada por job (ver _worker/_run_job acima), isso deixou de
# ser um problema e eles voltaram — com os mesmos intervalos de antes.
add_job(_sync_pedidos, "bling-pedidos", 300)           # 5 min
add_job(_sync_pedidos_shopee, "shopee-pedidos", 300)   # 5 min
add_job(_sync_nf, "bling-nf", 600)                     # 10 min
add_job(_sync_contatos, "bling-contatos", 1800)        # 30 min
add_job(_sync_cr_cp, "bling-cr-cp", 3600)              # 1 hour
add_job(_sync_categorias, "bling-categorias", 7200)    # 2 hours
add_job(_persistir_rotacao_estoque, "estoque-rotacao", 86400)  # daily
add_job(_reconciliar_loja_id, "estoque-reconciliar-loja-id", 3600)  # 1 hour
add_job(_renovar_tokens_shopee, "shopee-renovar-tokens", 900)  # 15 min
add_job(_sync_pedidos_i9logic, "i9logic-pedidos", 600)  # 10 min
```

Antes de editar, confirme lendo o arquivo que os nomes das funções batem exatamente
(`_sync_pedidos`, `_sync_nf`, `_sync_cr_cp`, `_sync_categorias`) e que nenhuma outra linha do
bloco foi perdida na substituição — o bloco tem jobs não-Bling no meio que precisam continuar
registrados.

- [ ] **Step 2: Verificar que os dez jobs estão registrados**

Run: `cd hermes_agents && python -c "import core.scheduler as s; print(len(s.JOBS)); [print(' ', j['name'], j['interval']) for j in s.JOBS]"`
Expected: 10 jobs, incluindo `bling-pedidos`, `bling-nf`, `bling-cr-cp` e `bling-categorias`.
(As linhas de erro de conexão com o banco são esperadas fora do servidor.)

- [ ] **Step 3: Suíte completa**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: mesmas 8 falhas pré-existentes, nenhuma nova.

- [ ] **Step 4: Commit**

```bash
git add hermes_agents/core/scheduler.py
git commit -m "feat: reativa os jobs de sync Bling no scheduler (pedidos, NF, CR/CP, categorias)"
```

---

### Task 3: Verificação final

- [ ] **Step 1: Nenhum job Bling comentado sobrando**

Run: `grep -n "^# add_job" hermes_agents/core/scheduler.py`
Expected: nenhuma linha.

- [ ] **Step 2: Suíte de scheduler inteira**

Run: `cd hermes_agents && python -m pytest tests/test_scheduler_isolamento.py tests/test_scheduler_i9logic.py tests/test_scheduler_pedidos_shopee.py tests/test_scheduler_shopee_token.py tests/test_scheduler_sync_contatos.py -v`
Expected: todos PASS.

- [ ] **Step 3: Suíte completa**

Run: `cd hermes_agents && python -m pytest tests/ -q`
Expected: mesmas 8 falhas pré-existentes, nenhuma nova.

- [ ] **Step 4: Smoke test de import**

Run: `cd hermes_agents && python -c "import athena_bridge; print('import OK')"`
Expected: imprime `import OK`.

- [ ] **Step 5: Commit final**

```bash
git status --porcelain
```

Se não houver mudança de código real:

```bash
git commit -m "test: verificacao final do isolamento e reativacao dos jobs Bling" --allow-empty
```
