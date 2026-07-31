"""RBAC por loja — restringe visao/operacao de dados as lojas vinculadas ao
usuario em usuario_lojas (tabela de controle de acesso, diferente de
loja_responsaveis que e' so' registro informativo). FAIL-CLOSED: usuario sem
nenhum vinculo nao ve NENHUMA loja, a nao ser que tenha bypass.

Chamado tanto pelo filtro "soft" de listagens (esconde o que nao pode ver)
quanto pelo decorator requer_acesso_loja (bloqueia com 403 quando o cliente
pede uma loja especifica fora da lista permitida) — ver core/rbac.py."""
from core import get_db, run_async
from core.lojas import _log_erro
from core.usuario_lojas import listar_ids_lojas_do_usuario


def lojas_permitidas(user_id) -> list:
    """None = sem restricao (token master/sem user_id, ou usuario com a
    permissao "lojas.ver_todas" — Admin recebe automaticamente). Lista = ids
    das lojas vinculadas ao usuario em usuario_lojas; pode vir VAZIA (usuario
    existe mas nao tem nenhuma loja vinculada ainda == nao ve nenhuma)."""
    if not user_id:
        return None
    from core.rbac import get_permissoes_por_usuario
    if "lojas.ver_todas" in get_permissoes_por_usuario(user_id):
        return None
    try:
        return listar_ids_lojas_do_usuario(user_id)
    except Exception as e:
        # Fail-closed tambem no erro de infra — consistente com o resto desta
        # funcao: melhor negar acesso por um erro transiente de banco do que
        # abrir "ve tudo" por acidente.
        _log_erro("lojas_permitidas", e)
        return []
