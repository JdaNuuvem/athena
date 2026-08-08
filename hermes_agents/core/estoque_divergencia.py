"""Classificacao de divergencia de saldo — compartilhada entre reconciliacao
i9Logic (fisico x contabil, e Athena x fisico) e Shopee (Athena x saldo do
marketplace). Extraida de core/i9logic.py: a regra sempre foi generica
(compara um "saldo de referencia" contra um "saldo de comparacao"), sem
nada especifico de i9Logic no corpo."""

LIMIAR_ALERTA_ABSOLUTO = 5
LIMIAR_ALERTA_PERCENTUAL = 0.10
TOLERANCIA_ZERO = 0.5


def classificar_divergencia(qtd_referencia: float, qtd_comparacao: float) -> str:
    """qtd_comparacao e' o contabil (i9Logic isolado, modo seed/auditoria),
    o disponivel do Athena (modo monitoramento continuo i9Logic ou Shopee) —
    a mesma regra de classificacao serve pros tres casos, so' muda o que se
    compara contra o fisico/referencia. Nunca ajusta nada sozinho, so'
    classifica pra fila de revisao."""
    divergencia = abs(float(qtd_comparacao) - float(qtd_referencia))
    if divergencia <= TOLERANCIA_ZERO:
        return "sem_acao"
    base = max(float(qtd_referencia), 1)
    if divergencia >= LIMIAR_ALERTA_ABSOLUTO or (divergencia / base) >= LIMIAR_ALERTA_PERCENTUAL:
        return "alerta"
    return "registrado"
