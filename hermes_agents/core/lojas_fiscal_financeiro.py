"""Configuracoes fiscais, financeiras e de estoque da loja — colunas
adicionais na tabela "lojas" ja criada por core/lojas.py."""
from core import get_db, run_async
from core.lojas import _log_erro, _update_campos

_FISCAL_DDL = [
    ("regime_tributario", "VARCHAR(50)"),
    ("serie_nfe", "VARCHAR(10)"),
    ("serie_nfce", "VARCHAR(10)"),
    ("ambiente_fiscal", "VARCHAR(20) DEFAULT 'homologacao'"),
    ("certificado_digital", "VARCHAR(300)"),
    ("csc_nfce", "VARCHAR(100)"),
    ("token_fiscal", "VARCHAR(200)"),
]
_FINANCEIRO_DDL = [
    ("conta_bancaria", "VARCHAR(100)"),
    ("conta_caixa_padrao", "VARCHAR(100)"),
    ("centro_financeiro", "VARCHAR(100)"),
    ("carteira_padrao", "VARCHAR(100)"),
    ("gateway_pagamento", "VARCHAR(50)"),
    ("pix_chave", "VARCHAR(150)"),
]
_ESTOQUE_CONFIG_DDL = [
    ("deposito_principal", "VARCHAR(100)"),
    ("permitir_estoque_negativo", "BOOLEAN DEFAULT FALSE"),
    ("estoque_minimo_padrao", "NUMERIC(10,2)"),
    ("estoque_reservado", "BOOLEAN DEFAULT FALSE"),
]
CAMPOS_FISCAL = {nome for nome, _ in _FISCAL_DDL}
CAMPOS_FINANCEIRO = {nome for nome, _ in _FINANCEIRO_DDL}
CAMPOS_ESTOQUE_CONFIG = {nome for nome, _ in _ESTOQUE_CONFIG_DDL}

# Nunca devem voltar em texto puro em audit_log/system_logs.
CAMPOS_SENSIVEIS = {"certificado_digital", "csc_nfce", "token_fiscal", "pix_chave"}


def _ensure_cols():
    async def _go():
        db = await get_db()
        for col, ddl in _FISCAL_DDL + _FINANCEIRO_DDL + _ESTOQUE_CONFIG_DDL:
            try: await db.execute(f"ALTER TABLE lojas ADD COLUMN IF NOT EXISTS {col} {ddl}")
            except Exception as e: _log_erro(f"ALTER lojas.{col} (fiscal/financeiro)", e)
    try: run_async(_go())
    except Exception as e: _log_erro("lojas_fiscal_financeiro._ensure_cols (run_async)", e)


_ensure_cols()


def mascarar_para_auditoria(campos: dict) -> dict:
    """Substitui valor real dos campos sensiveis por um indicador booleano
    antes de gravar em audit_log — a auditoria registra QUE algo mudou, nunca
    o certificado/token/chave em si."""
    return {
        k: (f"configurado: {bool(v)}" if k in CAMPOS_SENSIVEIS else v)
        for k, v in campos.items()
    }


def atualizar_fiscal(id_loja: int, campos: dict) -> bool:
    return _update_campos(id_loja, campos, CAMPOS_FISCAL)


def atualizar_financeiro(id_loja: int, campos: dict) -> bool:
    return _update_campos(id_loja, campos, CAMPOS_FINANCEIRO)


def atualizar_estoque_config(id_loja: int, campos: dict) -> bool:
    return _update_campos(id_loja, campos, CAMPOS_ESTOQUE_CONFIG)
