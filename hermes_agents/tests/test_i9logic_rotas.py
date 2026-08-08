"""Testes de rota — /api/integrations/i9logic/divergencias-athena (comparacao
Athena x i9Logic em lote, Task 2/3 da spec de Divergencia de Saldo)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

_TEST_TOKEN = "test-master-token-32-bytes-long!!"

async def _mock_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"),
    )), __aexit__=AsyncMock(return_value=None))
    return m

patch("asyncpg.create_pool", side_effect=_mock_pool).start()

from flask import Flask
from routes.i9logic import i9logic_bp
import core.rbac as rbac


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(i9logic_bp)
    return app.test_client()


class TestDivergenciasAthenaRota(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def _headers(self):
        return {"Authorization": f"Bearer {_TEST_TOKEN}"}

    def test_listar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.i9logic.listar_divergencias_athena") as mock_fn:
            r = self.client.get("/api/integrations/i9logic/divergencias-athena?loja=Matriz", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_fn.assert_not_called()

    def test_listar_com_permissao_libera(self):
        with patch("core.i9logic.listar_divergencias_athena", return_value={"ok": True, "data": []}) as mock_fn:
            r = self.client.get("/api/integrations/i9logic/divergencias-athena?loja=Matriz", headers=self._headers())
        self.assertEqual(r.status_code, 200)
        mock_fn.assert_called_once_with("Matriz")

    def test_listar_com_permissao_granular_estoque_ver_libera(self):
        """Usa um token de sessao comum (nao master) com exatamente 'estoque.ver'
        concedida — fecha o buraco onde inverter os decorators GET/POST passaria
        despercebido (token master ignora RBAC granular e nao pegaria isso)."""
        token = rbac.gerar_token_sessao(8, "ver@x.com", "Operador")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["estoque.ver"]), \
             patch("core.i9logic.listar_divergencias_athena", return_value={"ok": True, "data": []}) as mock_fn:
            r = self.client.get("/api/integrations/i9logic/divergencias-athena?loja=Matriz", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_fn.assert_called_once_with("Matriz")

    def test_ajustar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.estoque.ajustar_absoluto") as mock_fn:
            r = self.client.post("/api/integrations/i9logic/divergencias-athena/ajustar",
                                  json={"sku": "SKU-A", "loja": "Matriz"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_fn.assert_not_called()

    def test_ajustar_com_permissao_libera_e_aplica(self):
        with patch("core.i9logic.qtd_fisico_mais_recente", return_value=100), \
             patch("core.estoque.ajustar_absoluto", return_value={"ok": True}) as mock_fn:
            r = self.client.post("/api/integrations/i9logic/divergencias-athena/ajustar",
                                  json={"sku": "SKU-A", "loja": "Matriz", "quantidade": 100},
                                  headers=self._headers())
        self.assertEqual(r.status_code, 200)
        mock_fn.assert_called_once()
        self.assertEqual(mock_fn.call_args.args[0], "SKU-A")
        self.assertEqual(mock_fn.call_args.args[1], "Matriz")
        self.assertEqual(mock_fn.call_args.args[2], 100)

    def test_ajustar_com_permissao_granular_estoque_editar_libera(self):
        """Usa um token de sessao comum (nao master) com exatamente 'estoque.editar'
        concedida — mesma logica de test_listar_com_permissao_granular_estoque_ver_libera,
        mas pra rota POST."""
        token = rbac.gerar_token_sessao(9, "editar@x.com", "Operador")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["estoque.editar"]), \
             patch("core.i9logic.qtd_fisico_mais_recente", return_value=100), \
             patch("core.estoque.ajustar_absoluto", return_value={"ok": True}) as mock_fn:
            r = self.client.post("/api/integrations/i9logic/divergencias-athena/ajustar",
                                  json={"sku": "SKU-A", "loja": "Matriz", "quantidade": 100},
                                  headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_fn.assert_called_once()

    def test_ajustar_com_quantidade_desatualizada_retorna_409(self):
        """Guarda de frescor: a `quantidade` vem da lista em cache no navegador.
        Se o snapshot ja' mudou desde que a tela carregou, o ajuste tem que ser
        recusado em vez de gravar um fisico obsoleto (paridade com a guarda que
        o lado Shopee ja' tinha)."""
        with patch("core.i9logic.qtd_fisico_mais_recente", return_value=137), \
             patch("core.estoque.ajustar_absoluto") as mock_fn:
            r = self.client.post("/api/integrations/i9logic/divergencias-athena/ajustar",
                                  json={"sku": "SKU-A", "loja": "Matriz", "quantidade": 100},
                                  headers=self._headers())
        self.assertEqual(r.status_code, 409)
        self.assertIn("desatualizados", r.get_json()["erro"])
        mock_fn.assert_not_called()

    def test_ajustar_sem_snapshot_para_o_sku_retorna_400(self):
        with patch("core.i9logic.qtd_fisico_mais_recente", return_value=None), \
             patch("core.estoque.ajustar_absoluto") as mock_fn:
            r = self.client.post("/api/integrations/i9logic/divergencias-athena/ajustar",
                                  json={"sku": "SKU-X", "loja": "Matriz", "quantidade": 100},
                                  headers=self._headers())
        self.assertEqual(r.status_code, 400)
        mock_fn.assert_not_called()

    def test_ajustar_com_falha_na_guarda_de_frescor_nao_aplica(self):
        """Fail-closed: erro de banco na releitura do snapshot bloqueia o ajuste
        em vez de deixar passar sem checar."""
        with patch("core.i9logic.qtd_fisico_mais_recente", side_effect=Exception("timeout")), \
             patch("core.estoque.ajustar_absoluto") as mock_fn:
            r = self.client.post("/api/integrations/i9logic/divergencias-athena/ajustar",
                                  json={"sku": "SKU-A", "loja": "Matriz", "quantidade": 100},
                                  headers=self._headers())
        self.assertEqual(r.status_code, 400)
        mock_fn.assert_not_called()

    def test_ajustar_sem_sku_retorna_400(self):
        r = self.client.post("/api/integrations/i9logic/divergencias-athena/ajustar",
                              json={"loja": "Matriz", "quantidade": 100}, headers=self._headers())
        self.assertEqual(r.status_code, 400)

    def test_ajustar_quantidade_nao_numerica_retorna_400(self):
        with patch("core.estoque.ajustar_absoluto") as mock_fn:
            r = self.client.post("/api/integrations/i9logic/divergencias-athena/ajustar",
                                  json={"sku": "SKU-A", "loja": "Matriz", "quantidade": "abc"},
                                  headers=self._headers())
        self.assertEqual(r.status_code, 400)
        mock_fn.assert_not_called()
