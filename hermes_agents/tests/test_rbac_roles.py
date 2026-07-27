"""Testes de integracao — tela de Cargos (/roles) exige que GET /api/rbac/roles
devolva os codigos de permissao de cada papel junto (list_roles_com_permissoes),
e que os papeis novos do negocio (Estoquista, Comprador, Contador, RH,
Administracao, Producao, E-commerce, Atendimento, Diretor) e o papel renomeado
Operador Loja -> Vendedor estejam definidos corretamente."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

_TEST_TOKEN = "test-master-token-32-bytes-long!!"

async def _mp(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import core.rbac as rbac


class TestListRolesComPermissoes(unittest.TestCase):
    def test_devolve_papeis_com_codigos_de_permissao(self):
        with patch("core.rbac.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch.side_effect = [
                [{"id": 1, "nome": "Gerente", "descricao": "Gestao de loja"}],
                [{"codigo": "estoque.ver"}, {"codigo": "estoque.editar"}],
            ]
            mock_get_db.return_value = db
            roles = rbac.list_roles_com_permissoes()
        self.assertEqual(len(roles), 1)
        self.assertEqual(roles[0]["nome"], "Gerente")
        self.assertEqual(roles[0]["permissoes"], ["estoque.ver", "estoque.editar"])


class TestRolesExtrasDefinidos(unittest.TestCase):
    """Cada papel novo proposto para o negocio precisa existir na lista e
    apontar so' para codigos de permissao validos (modulo.acao reais)."""

    def _codigos_validos(self):
        return {f"{m}.{a}" for m in rbac.MODULOS for a, _ in rbac.ACOES_PADRAO} | {"pdv.operar", "bling.sincronizar"}

    def test_papeis_esperados_estao_presentes(self):
        nomes = {nome for nome, _, _ in rbac.ROLES_EXTRAS}
        esperados = {"Estoquista", "Comprador", "Contador", "RH", "Administracao", "Producao", "E-commerce", "Atendimento", "Diretor"}
        self.assertEqual(nomes, esperados)

    def test_todos_os_codigos_de_permissao_sao_validos(self):
        validos = self._codigos_validos()
        for nome, _, perms in rbac.ROLES_EXTRAS:
            for codigo in perms:
                self.assertIn(codigo, validos, f"{nome} referencia permissao inexistente: {codigo}")

    def test_comprador_tem_compras_e_estoque(self):
        perms = dict((n, p) for n, _, p in rbac.ROLES_EXTRAS)["Comprador"]
        self.assertIn("compras.criar", perms)
        self.assertIn("compras.aprovar", perms)
        self.assertIn("estoque.editar", perms)

    def test_contador_nao_tem_acesso_de_escrita_ao_financeiro(self):
        """Contador cuida de fiscal/compliance — nao deveria poder criar ou
        editar lancamentos financeiros, so' ver e exportar para relatorios."""
        perms = dict((n, p) for n, _, p in rbac.ROLES_EXTRAS)["Contador"]
        self.assertIn("financeiro.ver", perms)
        self.assertNotIn("financeiro.criar", perms)
        self.assertNotIn("financeiro.editar", perms)

    def test_diretor_so_tem_permissoes_de_visualizacao(self):
        """Papel executivo: leitura ampla, sem criar/editar/excluir em nada."""
        perms = dict((n, p) for n, _, p in rbac.ROLES_EXTRAS)["Diretor"]
        for codigo in perms:
            self.assertTrue(codigo.endswith(".ver") or codigo.endswith(".exportar"), f"Diretor tem permissao de escrita: {codigo}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
