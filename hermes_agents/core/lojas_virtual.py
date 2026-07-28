"""Configuracoes de loja virtual (dominio/SEO/pixels) e delivery — colunas
adicionais na tabela "lojas" ja criada por core/lojas.py."""
from core import get_db, run_async
from core.lojas import _log_erro, _update_campos

_VIRTUAL_DDL = [
    ("dominio", "VARCHAR(200)"),
    ("subdominio", "VARCHAR(100)"),
    ("tema", "VARCHAR(50)"),
    ("seo_title", "VARCHAR(200)"),
    ("seo_description", "VARCHAR(500)"),
    ("google_analytics_id", "VARCHAR(50)"),
    ("google_tag_manager_id", "VARCHAR(50)"),
    ("pixel_meta", "VARCHAR(50)"),
    ("pixel_tiktok", "VARCHAR(50)"),
    ("pixel_kwai", "VARCHAR(50)"),
    ("politica_privacidade", "TEXT"),
    ("termos_uso", "TEXT"),
]
_DELIVERY_DDL = [
    ("raio_entrega_km", "NUMERIC(6,2)"),
    ("taxa_entrega", "NUMERIC(8,2)"),
    ("tempo_medio_entrega_min", "INT"),
    ("regioes_atendidas", "TEXT"),
    ("retirada_loja", "BOOLEAN DEFAULT TRUE"),
]
CAMPOS_VIRTUAL = {nome for nome, _ in _VIRTUAL_DDL}
CAMPOS_DELIVERY = {nome for nome, _ in _DELIVERY_DDL}


def _ensure_cols():
    async def _go():
        db = await get_db()
        for col, ddl in _VIRTUAL_DDL + _DELIVERY_DDL:
            try: await db.execute(f"ALTER TABLE lojas ADD COLUMN IF NOT EXISTS {col} {ddl}")
            except Exception as e: _log_erro(f"ALTER lojas.{col} (virtual)", e)
    try: run_async(_go())
    except Exception as e: _log_erro("lojas_virtual._ensure_cols (run_async)", e)


_ensure_cols()


def atualizar_virtual(id_loja: int, campos: dict) -> bool:
    return _update_campos(id_loja, campos, CAMPOS_VIRTUAL)


def atualizar_delivery(id_loja: int, campos: dict) -> bool:
    return _update_campos(id_loja, campos, CAMPOS_DELIVERY)
