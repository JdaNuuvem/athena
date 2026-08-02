"""Scheduler — background sync jobs (no external deps)."""
import threading
import time
from core import log

AGENT = "Scheduler"
JOBS = []

def add_job(fn, name: str, interval_seconds: int):
    JOBS.append({"fn": fn, "name": name, "interval": interval_seconds, "last_run": 0.0})

def _worker():
    while True:
        now = time.time()
        for job in JOBS:
            if now - job["last_run"] < job["interval"]:
                continue
            job["last_run"] = now
            try:
                job["fn"]()
            except Exception as e:
                log(AGENT, f"Job '{job['name']}' error: {e}")
        # sleep in chunks so shutdown is responsive
        for _ in range(10):
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
    except Exception as e: pass

def _sync_pedidos_shopee():
    """Chamava sincronizar_pedidos_shopee() sem loja_id — usava so' a config
    legada de loja unica, nunca de fato iterando as lojas Shopee conectadas
    (multiloja). Com 2+ lojas conectadas, so' a ultima autorizada seria
    sincronizada de verdade."""
    try:
        from core.vendas import sincronizar_pedidos_shopee
        from core.lojas import listar_lojas_shopee
        for loja in listar_lojas_shopee():
            if not loja.get("tem_token"):
                continue
            try:
                r = sincronizar_pedidos_shopee(loja_id=loja["id"])
                if r.get("sync", 0) > 0:
                    log(AGENT, f"Pedidos Shopee sync (loja {loja['id']}): {r['sync']}")
            except Exception as e:
                log(AGENT, f"Erro sync pedidos Shopee loja {loja['id']}: {e}")
    except Exception as e: pass

def _sync_contatos():
    """sincronizar_contatos_bling() so' processa uma pagina por chamada — sem
    paginar aqui, o job sempre re-sincronizava os mesmos 100 primeiros
    contatos do Bling a cada execucao e nunca alcancava o resto da base."""
    try:
        from core.entidades import sincronizar_contatos_bling
        pagina = 1
        total = 0
        while True:
            r = sincronizar_contatos_bling(pagina=pagina, limite=100)
            if r.get("error"):
                log(AGENT, f"Erro sync contatos (pagina {pagina}): {r['error']}")
                break
            total += r.get("sync", 0)
            if r.get("recebidos", 0) < 100:
                break
            pagina += 1
        if total > 0: log(AGENT, f"Contatos sync: {total}")
    except Exception as e: pass

def _sync_nf():
    try:
        from core.fiscal import sincronizar_notas_fiscais_bling
        r = sincronizar_notas_fiscais_bling()
        if r.get("sync", 0) > 0: log(AGENT, f"NF sync: {r['sync']}")
    except Exception as e: pass

def _sync_cr_cp():
    try:
        from core.fiscal import sincronizar_contas_receber_bling, sincronizar_contas_pagar_bling
        r1 = sincronizar_contas_receber_bling()
        r2 = sincronizar_contas_pagar_bling()
        log(AGENT, f"CR/CP sync: CR={r1.get('sync',0)} CP={r2.get('sync',0)}")
    except Exception as e: pass

def _persistir_rotacao_estoque():
    try:
        from core.estoque import persistir_sugestoes_rotacao
        r = persistir_sugestoes_rotacao()
        if r.get("total", 0) > 0: log(AGENT, f"Sugestoes de rotacao: {r['total']}")
    except Exception as e: pass

def _reconciliar_loja_id():
    try:
        from core.estoque import reconciliar_loja_id
        r = reconciliar_loja_id()
        if r.get("ok"): log(AGENT, f"Reconciliacao loja_id: {r['resultado']}")
    except Exception as e: pass

def _renovar_tokens_shopee():
    """Access_token da Shopee sempre expira em poucas horas (~4h, ditado pela propria
    Shopee via 'expire_in' na resposta — nao e' algo que o Athena controla ou pode
    esticar para 365 dias). O que da' a sensacao de token de longa duracao e' renovar
    proativamente com o refresh_token antes de expirar, entao aqui a gente renova
    qualquer loja Shopee cujo token expira nos proximos 30 min (ou ja expirou)."""
    try:
        from datetime import datetime, timedelta
        from core.lojas import listar_lojas_shopee
        from shopee import refresh_shopee_token
        limite = datetime.now() + timedelta(minutes=30)
        for loja in listar_lojas_shopee():
            expira_em = loja.get("shopee_token_expira_em")
            if not loja.get("tem_token") or not expira_em or expira_em > limite:
                continue
            r = refresh_shopee_token(loja_id=loja["id"])
            if r.get("success"):
                log(AGENT, f"Token Shopee renovado: loja {loja['id']} ({loja.get('nome')})")
            else:
                log(AGENT, f"Falha ao renovar token Shopee da loja {loja['id']}: {r.get('error')}")
    except Exception as e:
        log(AGENT, f"Erro _renovar_tokens_shopee: {e}")

def _sync_pedidos_i9logic():
    try:
        from core.i9logic_vendas import sincronizar_pedidos_i9logic
        r = sincronizar_pedidos_i9logic()
        if r.get("sincronizados", 0) > 0:
            log(AGENT, f"Pedidos i9Logic sync: {r['sincronizados']}")
    except Exception as e:
        log(AGENT, f"Erro sync pedidos i9Logic: {e}")

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
                    except Exception as e: pass
                return len(dados)
            c = run_async(_go())
            log(AGENT, f"Categorias sync: {c}")
    except Exception as e: pass

# ponytail: jobs run every N seconds. Adjust intervals based on volume.
# Bling desativado temporariamente (modulo nao usado no momento — ver core/lojas.py /
# integracoes) — jobs abaixo comentados para nao consumir a API do Bling nem
# competir por tempo de scheduler com os jobs Shopee.
# add_job(_sync_pedidos, "bling-pedidos", 300)          # 5 min
add_job(_sync_pedidos_shopee, "shopee-pedidos", 300)   # 5 min
# add_job(_sync_nf, "bling-nf", 600)                     # 10 min
add_job(_sync_contatos, "bling-contatos", 1800)        # 30 min
# add_job(_sync_cr_cp, "bling-cr-cp", 3600)              # 1 hour
# add_job(_sync_categorias, "bling-categorias", 7200)     # 2 hours
add_job(_persistir_rotacao_estoque, "estoque-rotacao", 86400)  # daily
add_job(_reconciliar_loja_id, "estoque-reconciliar-loja-id", 3600)  # 1 hour
add_job(_renovar_tokens_shopee, "shopee-renovar-tokens", 900)  # 15 min
add_job(_sync_pedidos_i9logic, "i9logic-pedidos", 600)  # 10 min
