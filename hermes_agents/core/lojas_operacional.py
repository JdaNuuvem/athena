"""Configuracoes operacionais e comerciais da loja (horario, matriz/filial,
politica de precos, metas) — colunas adicionais na tabela "lojas" ja criada
por core/lojas.py."""
from core import get_db, run_async
from core.lojas import _log_erro, _update_campos

_OPERACIONAL_DDL = [
    ("horario_funcionamento", "JSONB"),
    ("dias_funcionamento", "VARCHAR(50)"),
    ("fuso_horario", "VARCHAR(50) DEFAULT 'America/Sao_Paulo'"),
    ("moeda", "VARCHAR(3) DEFAULT 'BRL'"),
    ("idioma", "VARCHAR(10) DEFAULT 'pt-BR'"),
    ("loja_matriz_id", "INT REFERENCES lojas(id)"),
    ("codigo_interno", "VARCHAR(30)"),
    ("codigo_erp", "VARCHAR(30)"),
    ("centro_custo", "VARCHAR(50)"),
    ("regiao", "VARCHAR(100)"),
    ("area_atuacao", "VARCHAR(200)"),
]
_COMERCIAL_DDL = [
    ("politica_precos", "VARCHAR(50)"),
    ("tabela_precos_padrao", "VARCHAR(100)"),
    ("desconto_maximo_pct", "NUMERIC(5,2)"),
    ("comissao_padrao_pct", "NUMERIC(5,2)"),
    ("meta_mensal", "NUMERIC(14,2)"),
    ("meta_anual", "NUMERIC(14,2)"),
]
CAMPOS_OPERACIONAL = {nome for nome, _ in _OPERACIONAL_DDL}
CAMPOS_COMERCIAL = {nome for nome, _ in _COMERCIAL_DDL}


def _ensure_cols():
    async def _go():
        db = await get_db()
        for col, ddl in _OPERACIONAL_DDL + _COMERCIAL_DDL:
            try: await db.execute(f"ALTER TABLE lojas ADD COLUMN IF NOT EXISTS {col} {ddl}")
            except Exception as e: _log_erro(f"ALTER lojas.{col} (operacional)", e)
    try: run_async(_go())
    except Exception as e: _log_erro("lojas_operacional._ensure_cols (run_async)", e)


_ensure_cols()


def atualizar_operacional(id_loja: int, campos: dict) -> bool:
    """horario_funcionamento vem como dict (ex: {"seg": "08:00-18:00", ...}) —
    convertido pra JSON antes de gravar."""
    campos = dict(campos)
    if "horario_funcionamento" in campos and isinstance(campos["horario_funcionamento"], dict):
        import json
        campos["horario_funcionamento"] = json.dumps(campos["horario_funcionamento"], ensure_ascii=False)
    return _update_campos(id_loja, campos, CAMPOS_OPERACIONAL)


def atualizar_comercial(id_loja: int, campos: dict) -> bool:
    return _update_campos(id_loja, campos, CAMPOS_COMERCIAL)
