"""Validadores de formato usados na camada de rota (validacao no boundary,
antes de chamar qualquer funcao de core/lojas*.py)."""
import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _somente_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def _digito_verificador_cnpj_cpf(digitos: str, pesos: list) -> int:
    soma = sum(int(d) * p for d, p in zip(digitos, pesos))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def validar_cpf(cpf: str) -> bool:
    d = _somente_digitos(cpf)
    if len(d) != 11 or d == d[0] * 11:
        return False
    dv1 = _digito_verificador_cnpj_cpf(d[:9], list(range(10, 1, -1)))
    dv2 = _digito_verificador_cnpj_cpf(d[:9] + str(dv1), list(range(11, 1, -1)))
    return d[-2:] == f"{dv1}{dv2}"


def validar_cnpj(cnpj: str) -> bool:
    d = _somente_digitos(cnpj)
    if len(d) != 14 or d == d[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    dv1 = _digito_verificador_cnpj_cpf(d[:12], pesos1)
    dv2 = _digito_verificador_cnpj_cpf(d[:12] + str(dv1), pesos2)
    return d[-2:] == f"{dv1}{dv2}"


def validar_cnpj_cpf(valor: str) -> bool:
    """Aceita CNPJ (14 digitos) ou CPF (11 digitos), com ou sem mascara."""
    if not valor:
        return True  # campo opcional
    d = _somente_digitos(valor)
    if len(d) == 11:
        return validar_cpf(d)
    if len(d) == 14:
        return validar_cnpj(d)
    return False


def validar_cep(cep: str) -> bool:
    if not cep:
        return True
    return len(_somente_digitos(cep)) == 8


def validar_email(email: str) -> bool:
    if not email:
        return True
    return bool(_EMAIL_RE.match(email.strip()))
