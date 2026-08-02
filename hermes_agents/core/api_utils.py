"""Helpers HTTP compartilhados entre blueprints de CRUD generico
(core.crm, core.atendimento, ...) — evita duplicar a mesma logica de
traducao de erro em cada routes/*.py."""


def status_for_resultado(resultado: dict) -> int:
    """Traduz o {"error": ...} devolvido pelos modulos core.* em status HTTP —
    sem isso, um insert/update/delete que falha (coluna filtrada, FK invalida,
    registro nao encontrado, etc.) parece sucesso (200) pro frontend."""
    if not isinstance(resultado, dict) or "error" not in resultado:
        return 200
    erro = str(resultado.get("error", "")).lower()
    if "not found" in erro:
        return 404
    return 400
