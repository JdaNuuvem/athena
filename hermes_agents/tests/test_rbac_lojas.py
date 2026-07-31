"""Testes de core/rbac_lojas.py — RBAC por loja, FAIL-CLOSED: usuario sem
nenhum vinculo em usuario_lojas nao ve NENHUMA loja. So' fica sem restricao
(None) quem e' token master (user_id vazio) ou tem a permissao
"lojas.ver_todas" (Admin recebe automaticamente — ver core/rbac.py).

Substitui o piloto anterior (loja_responsaveis, "modo suave" — usuario sem
vinculo via tudo). Esse modo suave deixava qualquer rota que aceitasse
loja_id explicito completamente sem protecao (ver git history de
test_rbac_lojas_rotas.py antes desta mudanca)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch


async def _mp(*a, **kw):
    from unittest.mock import AsyncMock
    return AsyncMock()


patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import core.rbac_lojas as rbac_lojas


class TestLojasPermitidas(unittest.TestCase):

    def test_sem_user_id_retorna_none(self):
        """Token master (usuario_atual_da_request retorna user_id=None) —
        sem restricao."""
        self.assertIsNone(rbac_lojas.lojas_permitidas(None))

    @patch("core.rbac.get_permissoes_por_usuario", return_value=["lojas.ver_todas"])
    def test_usuario_com_permissao_ver_todas_retorna_none(self, mock_perms):
        self.assertIsNone(rbac_lojas.lojas_permitidas(7))

    @patch("core.rbac_lojas.listar_ids_lojas_do_usuario", return_value=[])
    @patch("core.rbac.get_permissoes_por_usuario", return_value=["produtos.ver"])
    def test_usuario_sem_vinculo_nenhum_retorna_lista_vazia_fail_closed(self, mock_perms, mock_ids):
        """Diferenca chave vs. o piloto anterior: sem vinculo = ve NADA, nao
        "sem restricao"."""
        self.assertEqual(rbac_lojas.lojas_permitidas(7), [])

    @patch("core.rbac_lojas.listar_ids_lojas_do_usuario", return_value=[3])
    @patch("core.rbac.get_permissoes_por_usuario", return_value=[])
    def test_usuario_com_vinculo_retorna_lista(self, mock_perms, mock_ids):
        self.assertEqual(rbac_lojas.lojas_permitidas(7), [3])

    @patch("core.rbac_lojas.listar_ids_lojas_do_usuario", return_value=[3, 5])
    @patch("core.rbac.get_permissoes_por_usuario", return_value=[])
    def test_usuario_com_multiplas_lojas(self, mock_perms, mock_ids):
        self.assertEqual(rbac_lojas.lojas_permitidas(7), [3, 5])

    @patch("core.rbac_lojas.listar_ids_lojas_do_usuario", side_effect=Exception("db down"))
    @patch("core.rbac.get_permissoes_por_usuario", return_value=[])
    def test_erro_de_banco_falha_fechado(self, mock_perms, mock_ids):
        # Fail-closed tambem no erro de infra — nega acesso em vez de abrir
        # "ve tudo" por causa de um erro transiente de banco.
        self.assertEqual(rbac_lojas.lojas_permitidas(7), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
