"""Bling Logger — Logs estruturados com Correlation ID para toda a integracao Bling."""
import os, json, time, uuid, traceback
from datetime import datetime
from core import log

AGENT = "Bling Logger"

def corr_id() -> str:
    """Gera um Correlation ID unico para rastrear todo o fluxo."""
    return uuid.uuid4().hex[:12]

def _redact(data: dict | None) -> dict | None:
    """Remove dados sensiveis antes de logar."""
    if not data: return data
    redacted = dict(data)
    for k in ("access_token", "refresh_token", "client_secret", "api_key", "authorization", "password"):
        if k in redacted: redacted[k] = "***REDACTED***"
    return redacted

def log_start(operacao: str, cid: str = "", params: dict = None) -> str:
    cid = cid or corr_id()
    log(AGENT, f"[{cid}] START {operacao}" + (f" params={json.dumps(_redact(params), ensure_ascii=False)[:200]}" if params else ""))
    return cid

def log_end(operacao: str, cid: str, duracao_ms: float, status: str = "OK", extras: dict = None):
    log(AGENT, f"[{cid}] END   {operacao} | {duracao_ms:.0f}ms | {status}" + (f" | {json.dumps(extras, ensure_ascii=False)[:200]}" if extras else ""))

def log_req(operacao: str, cid: str, method: str, url: str, status_code: int, duracao_ms: float):
    log(AGENT, f"[{cid}] REQ   {method} {url} -> {status_code} ({duracao_ms:.0f}ms)")

def log_retry(operacao: str, cid: str, attempt: int, max_attempts: int):
    log(AGENT, f"[{cid}] RETRY {operacao} attempt={attempt}/{max_attempts}")

def log_error(operacao: str, cid: str, error: str, tb: str = ""):
    log(AGENT, f"[{cid}] ERROR {operacao}: {error}" + (f"\n{tb[:300]}" if tb else ""))

def log_webhook(operacao: str, cid: str, evento: str, id_externo: str = ""):
    log(AGENT, f"[{cid}] WEBHOOK {operacao} evento={evento}" + (f" id={id_externo}" if id_externo else ""))

def log_alteracao(operacao: str, cid: str, entidade: str, id_entidade: str, antes: dict = None, depois: dict = None):
    delta = ""
    if antes and depois:
        mudadas = {k: f"{antes.get(k)}->{depois.get(k)}" for k in depois if k in antes and antes.get(k) != depois.get(k)}
        delta = json.dumps(mudadas, ensure_ascii=False)[:200]
    log(AGENT, f"[{cid}] CHANGE {operacao} {entidade}#{id_entidade}" + (f" {delta}" if delta else ""))

if __name__ == "__main__":
    cid = log_start("sync_produtos")
    log_end("sync_produtos", cid, 1500, "OK", {"sincronizados": 234})
    print("Bling Logger OK")
