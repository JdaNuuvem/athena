"""
Core infrastructure for Hermes Agent Swarm.
Database connection, config loading, shared utilities.
"""
import os
import json
import asyncio
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, asdict, field

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")) / "factory_config.json"

@dataclass
class FactoryConfig:
    db_host: str = os.environ.get("DB_HOST", "postgresql-database-h3bdeft4hgsbg9rcxklxidwt")
    db_port: int = int(os.environ.get("DB_PORT", "5432"))
    db_name: str = os.environ.get("DB_NAME", "hermes_factory")
    db_user: str = os.environ.get("DB_USER", "postgres")
    db_password: str = os.environ.get("DB_PASSWORD", "")

    def __post_init__(self):
        # ponytail: parse DATABASE_URL if set (Coolify-style connection string)
        db_url = os.environ.get("DATABASE_URL", "")
        if db_url:
            from urllib.parse import urlparse
            parsed = urlparse(db_url)
            self.db_user = parsed.username or self.db_user
            self.db_password = parsed.password or self.db_password
            self.db_host = parsed.hostname or self.db_host
            self.db_port = parsed.port or self.db_port
            self.db_name = parsed.path.lstrip("/") or self.db_name

    # Marketplaces
    mercado_livre_authorization: str = ""
    shopee_partner_id: str = ""
    shopee_partner_key: str = ""
    amazon_access_key: str = ""
    amazon_secret_key: str = ""

    # Telegram
    telegram_bot_token: str = ""

    # Alerta
    margem_minima_pct: float = 15.0
    ruptura_estoque_dias: int = 7
    frete_medio_shopee: float = 15.0

    @classmethod
    def load(cls) -> "FactoryConfig":
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return cls(**data)
        return cls()

    def save(self):
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

_db_pool: Optional[Any] = None
_db_pool_loop: Optional[Any] = None

async def get_db():
    """Retorna ou cria pool de conexões asyncpg.

    run_async() roda cada chamada em um asyncio.run() novo (loop novo e
    descartado ao final). Um pool asyncpg fica preso ao loop em que foi
    criado, entao cachear _db_pool globalmente quebra silenciosamente a
    partir da segunda chamada. Recriamos o pool sempre que o loop mudar.
    """
    global _db_pool, _db_pool_loop
    if not HAS_ASYNCPG:
        raise RuntimeError("asyncpg não instalado")
    current_loop = asyncio.get_running_loop()
    if _db_pool is None or _db_pool_loop is not current_loop:
        cfg = FactoryConfig.load()
        _db_pool = await asyncpg.create_pool(
            host=cfg.db_host,
            port=cfg.db_port,
            database=cfg.db_name,
            user=cfg.db_user,
            password=cfg.db_password,
            min_size=2,
            max_size=10,
        )
        _db_pool_loop = current_loop
    return _db_pool

def run_async(coro):
    """Helper para rodar async em contexto síncrono."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as ex:
            return ex.submit(lambda: asyncio.run(coro)).result()
    return asyncio.run(coro)

# ---------------------------------------------------------------------------
# Logging & utils
# ---------------------------------------------------------------------------

def log(agent: str, msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{agent}] {msg}")

def hoje() -> str:
    return date.today().isoformat()

def pct(v1: float, v2: float) -> float:
    """Retorna percentual v1 / v2 * 100."""
    return round((v1 / v2 * 100) if v2 else 0, 1)
