"""Testes de integracao — endpoints novos de tickets (filtros, atendentes, anexo)."""
import sys, os, io, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

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
from routes.atendimento import atendimento_bp
import core.rbac as rbac

_TEST_TOKEN = "test-master-token-32-bytes-long!!"


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(atendimento_bp)
    return app.test_client()


class TestListarTicketsFiltrado(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_listar_tickets_com_filtro_status(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.atendimento.listar_tickets_filtrado", return_value=[{"id": 1, "status": "aberto"}]) as mock_list:
            r = self.client.get("/api/atendimento/tickets?status=aberto", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["data"], [{"id": 1, "status": "aberto"}])
        mock_list.assert_called_once_with(
            status="aberto", prioridade=None, canal=None, atendente_id=None, q=None, de=None, ate=None)

    def test_listar_tickets_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.atendimento.listar_tickets_filtrado") as mock_list:
            r = self.client.get("/api/atendimento/tickets", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_list.assert_not_called()

    def test_rota_tickets_nao_cai_no_handler_generico(self):
        """Regressao: /tickets (estatico) precisa vencer /<tabela> (dinamico)."""
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.atendimento.listar_tickets_filtrado", return_value=[]) as mock_filtrado, \
             patch("core.atendimento.list") as mock_generico:
            self.client.get("/api/atendimento/tickets", headers=headers)
        mock_filtrado.assert_called_once()
        mock_generico.assert_not_called()

    def test_listar_tickets_atendente_id_invalido_retorna_400(self):
        """Fix round 1: atendente_id nao numerico retorna 400 com mensagem clara."""
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.atendimento.listar_tickets_filtrado") as mock_list:
            r = self.client.get("/api/atendimento/tickets?atendente_id=abc", headers=headers)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()["error"], "atendente_id invalido")
        mock_list.assert_not_called()


class TestListarAtendentes(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_listar_atendentes_com_permissao_ver(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.atendimento.listar_atendentes", return_value=[{"id": 5, "nome": "Joao"}]) as mock_list:
            r = self.client.get("/api/atendimento/atendentes", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["data"], [{"id": 5, "nome": "Joao"}])
        mock_list.assert_called_once()

    def test_listar_atendentes_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.atendimento.listar_atendentes") as mock_list:
            r = self.client.get("/api/atendimento/atendentes", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_list.assert_not_called()


class TestAtribuirTicketRota(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_atribuir_atendente_id_invalido_retorna_400(self):
        """Fix round 1: atendente_id nao numerico retorna 400 com mensagem
        clara em vez de deixar o ValueError de int() vazar como 500."""
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.atendimento.atribuir_ticket") as mock_atribuir:
            r = self.client.put("/api/atendimento/tickets/1/atribuir",
                                 json={"atendente_id": "abc"}, headers=headers)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()["error"], "atendente_id invalido")
        mock_atribuir.assert_not_called()

    def test_atribuir_atendente_id_ausente_retorna_400(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.atendimento.atribuir_ticket") as mock_atribuir:
            r = self.client.put("/api/atendimento/tickets/1/atribuir",
                                 json={}, headers=headers)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()["error"], "atendente_id obrigatorio")
        mock_atribuir.assert_not_called()

    def test_atribuir_atendente_id_valido_chama_core(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.atendimento.atribuir_ticket", return_value={"id": 1, "atendente_id": 5}) as mock_atribuir:
            r = self.client.put("/api/atendimento/tickets/1/atribuir",
                                 json={"atendente_id": 5}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_atribuir.assert_called_once_with(1, 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)