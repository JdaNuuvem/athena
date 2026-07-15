"""Scheduler — background sync jobs (no external deps)."""
import threading
import time
from core import log

AGENT = "Scheduler"
JOBS = []

def add_job(fn, name: str, interval_seconds: int):
    JOBS.append((fn, name, interval_seconds))

def _worker():
    while True:
        for fn, name, interval in JOBS:
            try:
                fn()
            except Exception as e:
                log(AGENT, f"Job '{name}' error: {e}")
        # sleep in chunks so shutdown is responsive
        for _ in range(60):
            time.sleep(1)

_started = False

def start():
    global _started
    if _started: return
    t = threading.Thread(target=_worker, daemon=True, name="bling-scheduler")
    t.start()
    _started = True
    log(AGENT, f"Started with {len(JOBS)} jobs")

def _sync_pedidos():
    try:
        from core.vendas import sincronizar_pedidos_bling
        r = sincronizar_pedidos_bling()
        if r.get("sync", 0) > 0: log(AGENT, f"Pedidos sync: {r['sync']}")
    except: pass

def _sync_contatos():
    try:
        from core.entidades import sincronizar_contatos_bling
        r = sincronizar_contatos_bling()
        if r.get("sync", 0) > 0: log(AGENT, f"Contatos sync: {r['sync']}")
    except: pass

def _sync_nf():
    try:
        from core.fiscal import sincronizar_notas_fiscais_bling
        r = sincronizar_notas_fiscais_bling()
        if r.get("sync", 0) > 0: log(AGENT, f"NF sync: {r['sync']}")
    except: pass

def _sync_cr_cp():
    try:
        from core.fiscal import sincronizar_contas_receber_bling, sincronizar_contas_pagar_bling
        r1 = sincronizar_contas_receber_bling()
        r2 = sincronizar_contas_pagar_bling()
        log(AGENT, f"CR/CP sync: CR={r1.get('sync',0)} CP={r2.get('sync',0)}")
    except: pass

def _sync_categorias():
    try:
        from bling_erp import listar_categorias, get_access_token
        if not get_access_token(): return
        r = listar_categorias()
        dados = r.get("data", [])
        if dados:
            from core import run_async, get_db
            async def _go():
                db = await get_db()
                await db.execute("CREATE TABLE IF NOT EXISTS bling_categorias (id SERIAL PRIMARY KEY, bling_id BIGINT UNIQUE, nome VARCHAR(200), created_at TIMESTAMP DEFAULT NOW())")
                for cat in dados:
                    try:
                        cid = cat.get("id"); nome = cat.get("descricao","")
                        if cid and nome:
                            await db.execute("INSERT INTO bling_categorias (bling_id, nome) VALUES ($1,$2) ON CONFLICT (bling_id) DO UPDATE SET nome=$2", cid, nome)
                    except: pass
                return len(dados)
            c = run_async(_go())
            log(AGENT, f"Categorias sync: {c}")
    except: pass

# ponytail: jobs run every N seconds. Adjust intervals based on volume.
add_job(_sync_pedidos, "bling-pedidos", 300)          # 5 min
add_job(_sync_nf, "bling-nf", 600)                     # 10 min
add_job(_sync_contatos, "bling-contatos", 1800)        # 30 min
add_job(_sync_cr_cp, "bling-cr-cp", 3600)              # 1 hour
add_job(_sync_categorias, "bling-categorias", 7200)     # 2 hours
