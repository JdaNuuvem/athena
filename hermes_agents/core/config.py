"""
Configurações unificadas para APIs (Telegram, Bling, Shopee)
Persistência via PostgreSQL — sobrevive a deploys. Arquivo como cache/fallback.
"""
from typing import Optional
from pathlib import Path
import json
import os

CONFIG_PATH = Path(__file__).parent.parent / "config" / "api_config.json"

# Inicializar configurações (fallback)
_config = {
    "telegram": {
        "token": "",
        "webhook_url": "https://177.7.45.242:8000/telegram/webhook"
    },
    "bling": {
        "api_key": "",
        "api_url": "https://bling.com.br/Api/v3",
        "client_id": "",
        "client_secret": "",
        "access_token": "",
        "refresh_token": ""
    },
    "shopee": {
        "partner_id": "",
        "shop_id": "",
        "api_key": "",
        "access_token": ""
    },
    "whatsapp": {
        "api_url": "http://localhost:8080",
        "api_key": "",
        "instance_name": "hermes"
    }
}

_db_ok = False

def _ensure_db_table():
    global _db_ok
    if _db_ok:
        return True
    try:
        from core import get_db, run_async
        async def _go():
            db = await get_db()
            await db.execute("""
                CREATE TABLE IF NOT EXISTS configs (
                    sistema VARCHAR(50) NOT NULL,
                    chave VARCHAR(100) NOT NULL,
                    valor TEXT DEFAULT '',
                    updated_at TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (sistema, chave)
                )
            """)
        run_async(_go())
        _db_ok = True
        return True
    except Exception:
        return False

def _load_db_config():
    """Carrega todas as configs do banco e mescla no _config em memória."""
    if not _ensure_db_table():
        return
    try:
        from core import get_db, run_async
        async def _go():
            db = await get_db()
            rows = await db.fetch("SELECT sistema, chave, valor FROM configs")
            for r in rows:
                s, k, v = r["sistema"], r["chave"], r["valor"]
                if s not in _config:
                    _config[s] = {}
                _config[s][k] = v
        run_async(_go())
    except Exception:
        pass

def _load_config():
    """Carrega do arquivo (cache) e depois do banco (source of truth)."""
    global _config
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, 'r') as f:
                loaded = json.load(f)
                _config.update(loaded)
        except Exception:
            pass
    # DB overrides file (source of truth)
    _load_db_config()

def _save_config():
    """Salva no arquivo (cache) e no banco (source of truth)."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        json.dump(_config, f, indent=2)

def _save_db_config(sistema: str, chave: str, valor: str):
    """Persiste uma config no banco."""
    if not _ensure_db_table():
        return
    try:
        from core import get_db, run_async
        async def _go():
            db = await get_db()
            await db.execute("""
                INSERT INTO configs (sistema, chave, valor, updated_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (sistema, chave) DO UPDATE SET valor = $3, updated_at = NOW()
            """, sistema, chave, valor)
        run_async(_go())
    except Exception:
        pass

def get_config(sistema: str, chave: str) -> Optional[str]:
    """Obtém configuração. Prioridade: env var > memória > DB (já carregado em memória)."""
    env_key = f"{sistema.upper()}_{chave.upper()}"
    env_val = os.environ.get(env_key)
    if env_val:
        return env_val
    return _config.get(sistema, {}).get(chave, "")

def set_config(sistema: str, chave: str, valor: str):
    """Define configuração. Salva em memória + arquivo + banco."""
    if sistema not in _config:
        _config[sistema] = {}
    _config[sistema][chave] = valor
    _save_config()
    _save_db_config(sistema, chave, valor)

def get_all_config() -> dict:
    """Retorna todas as configurações."""
    return _config

def set_config_bulk(sistema: str, configs: dict):
    """Define múltiplas configurações de um sistema."""
    if sistema not in _config:
        _config[sistema] = {}
    _config[sistema].update(configs)
    _save_config()
    for k, v in configs.items():
        _save_db_config(sistema, k, v)

# Carregar ao iniciar
_load_config()
