"""Testes de rota — GET /api/cadastros/clientes com pagina+filtros roteia
para listar_clientes_filtrado; outras tabelas continuam em list_paginado
(regressao); tags-disponiveis exige cadastros.ver."""
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

from flask import Flask
from routes.cadastros import cadastros_bp


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(cadastros_bp)
    return app.test_client()


class TestRotaClientesFiltrado(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_clientes_com_pagina_usa_listar_clientes_filtrado(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.cadastros.listar_clientes_filtrado", return_value={"data": [], "total": 0, "pagina": 1, "por_pagina": 20, "total_paginas": 1}) as mock_filtrado, \
             patch("core.cadastros.list_paginado") as mock_generico:
            r = self.client.get(
                "/api/cadastros/clientes?pagina=1&status=ativo&tag=VIP&whatsapp=true&sem_comprar_dias=30&sort=nome&order=asc",
                headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_filtrado.assert_called_once()
        mock_generico.assert_not_called()
        args = mock_filtrado.call_args.args
        self.assertEqual(args[0], 1)
        self.assertEqual(args[3], "nome")
        self.assertEqual(args[4], "asc")
        self.assertEqual(args[5], "ativo")
        self.assertEqual(args[6], "VIP")
        self.assertTrue(args[7])
        self.assertEqual(args[8], 30)

    def test_outra_tabela_continua_em_list_paginado(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.cadastros.list_paginado", return_value={"data": [], "total": 0, "pagina": 1, "por_pagina": 50, "total_paginas": 1}) as mock_generico, \
             patch("core.cadastros.listar_clientes_filtrado") as mock_filtrado:
            r = self.client.get("/api/cadastros/fornecedores?pagina=1", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_generico.assert_called_once_with("fornecedores", 1, 50, None)
        mock_filtrado.assert_not_called()

    def test_clientes_sem_pagina_mantem_comportamento_antigo(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.cadastros.list", return_value=[{"id": 1}]) as mock_list, \
             patch("core.cadastros.listar_clientes_filtrado") as mock_filtrado:
            r = self.client.get("/api/cadastros/clientes", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_list.assert_called_once_with("clientes")
        mock_filtrado.assert_not_called()

    def test_tags_disponiveis_exige_permissao(self):
        import core.rbac as rbac
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["pdv.operar"]), \
             patch("core.cadastros.tags_disponiveis") as mock_tags:
            r = self.client.get("/api/cadastros/clientes/tags-disponiveis", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_tags.assert_not_called()

    def test_tags_disponiveis_com_permissao_retorna_lista(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.cadastros.tags_disponiveis", return_value=["VIP", "Atacado"]) as mock_tags:
            r = self.client.get("/api/cadastros/clientes/tags-disponiveis", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["data"], ["VIP", "Atacado"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
