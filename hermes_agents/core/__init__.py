"""
Core infrastructure for Hermes Agent Swarm.
Database connection, config loading, shared utilities.
"""
import os
import json
import asyncio
import threading
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

_db_pools: dict = {}  # id(loop) -> pool; pool asyncpg fica preso ao loop em que foi criado
_worker_loop: Optional[asyncio.AbstractEventLoop] = None
_worker_loop_lock = threading.Lock()


def _get_worker_loop() -> asyncio.AbstractEventLoop:
    """Loop asyncio unico, vivo pelo processo inteiro numa thread dedicada —
    caminho comum de toda chamada (requests Flask, scheduler).

    Antes, run_async() criava um asyncio.run() (loop novo) a cada chamada,
    entao get_db() recriava o pool sempre que o loop mudava — e o pool
    anterior nunca era fechado, vazando conexoes ate estourar
    max_connections do Postgres. Mantendo um unico loop persistente, o
    pool desse loop so' e' criado uma vez e nunca precisa ser recriado.
    """
    global _worker_loop
    if _worker_loop is None:
        with _worker_loop_lock:
            if _worker_loop is None:
                loop = asyncio.new_event_loop()
                threading.Thread(target=loop.run_forever, daemon=True, name="hermes-db-loop").start()
                _worker_loop = loop
    return _worker_loop


async def get_db():
    """Retorna ou cria o pool asyncpg do loop atual (cacheado por loop)."""
    global _db_pools
    if not HAS_ASYNCPG:
        raise RuntimeError("asyncpg não instalado")
    key = id(asyncio.get_running_loop())
    pool = _db_pools.get(key)
    if pool is None:
        cfg = FactoryConfig.load()
        pool = await asyncpg.create_pool(
            host=cfg.db_host,
            port=cfg.db_port,
            database=cfg.db_name,
            user=cfg.db_user,
            password=cfg.db_password,
            min_size=2,
            max_size=10,
        )
        _db_pools[key] = pool
    return pool

def run_async(coro):
    """Roda coro no loop persistente (thread dedicada), bloqueando a thread
    chamadora ate' o resultado — funciona tanto de codigo sync quanto de
    dentro de outro loop (ex.: jobs assincronos do scheduler).

    Chamada reentrante (run_async disparado de dentro de uma coroutine que
    ja' esta' rodando no proprio loop persistente — ex.: import tardio no
    meio de um _ensure_tables() que dispara o _ensure_tables() de outro
    modulo) usa um loop isolado e descartavel: rodar no loop persistente
    travaria pra sempre, pois a chamada de fora esta' ocupando o unico
    thread que serve esse loop. O pool desse loop isolado e' fechado ao
    final pra nao vazar conexao."""
    worker_loop = _get_worker_loop()
    try:
        reentrante = asyncio.get_running_loop() is worker_loop
    except RuntimeError:
        reentrante = False
    if reentrante:
        import concurrent.futures

        async def _isolado():
            try:
                return await coro
            finally:
                loop = asyncio.get_running_loop()
                pool = _db_pools.pop(id(loop), None)
                if pool is not None:
                    await pool.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(asyncio.run, _isolado()).result()
    return asyncio.run_coroutine_threadsafe(coro, worker_loop).result()

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
