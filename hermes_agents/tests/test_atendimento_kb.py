"""Testes — feature Atendimento > Base de Conhecimento (KB).

Cobre o que foi corrigido/completado especificamente para kb_artigos:
(1) visualizacoes/util_sim/util_nao eram colunas mortas, nunca incrementadas
por nenhuma rota — agora visualizar_artigo_kb/votar_artigo_kb fazem isso;
(2) as novas rotas /kb_artigos/<id>/visualizar e /votar precisam exigir
atendimento.ver, igual ao resto do CRUD generico; (3) campo "publicado"
estava na whitelist mas nunca era enviado por nenhum client — regressao pra
garantir que continua aceito; (4) _list usava LIMIT 100 fixo, artigos alem
dos 100 mais recentes ficavam inacessiveis — bump pra 500."""
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
from routes.atendimento import atendimento_bp
import core.rbac as rbac
import core.atendimento as atend


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(atendimento_bp)
    return app.test_client()


class TestVisualizarArtigoKB(unittest.TestCase):
    def test_incrementa_visualizacoes(self):
        db_mock = AsyncMock()
        db_mock.fetchrow = AsyncMock(return_value={"id": 1, "visualizacoes": 5})

        async def _fake_get_db():
            return db_mock

        with patch("core.atendimento.get_db", _fake_get_db):
            r = atend.visualizar_artigo_kb(1)

        self.assertEqual(r, {"id": 1, "visualizacoes": 5})
        query = db_mock.fetchrow.call_args.args[0]
        self.assertIn("visualizacoes = visualizacoes + 1", query)
        self.assertIn("atend_kb_artigos", query)

    def test_artigo_inexistente_retorna_not_found(self):
        db_mock = AsyncMock()
        db_mock.fetchrow = AsyncMock(return_value=None)

        async def _fake_get_db():
            return db_mock

        with patch("core.atendimento.get_db", _fake_get_db):
            r = atend.visualizar_artigo_kb(999)
        self.assertEqual(r, {"error": "not found"})


class TestVotarArtigoKB(unittest.TestCase):
    def test_voto_util_incrementa_util_sim(self):
        db_mock = AsyncMock()
        db_mock.fetchrow = AsyncMock(return_value={"id": 1, "util_sim": 3})

        async def _fake_get_db():
            return db_mock

        with patch("core.atendimento.get_db", _fake_get_db):
            atend.votar_artigo_kb(1, True)

        query = db_mock.fetchrow.call_args.args[0]
        self.assertIn("util_sim = util_sim + 1", query)
        self.assertNotIn("util_nao", query)

    def test_voto_nao_util_incrementa_util_nao(self):
        db_mock = AsyncMock()
        db_mock.fetchrow = AsyncMock(return_value={"id": 1, "util_nao": 2})

        async def _fake_get_db():
            return db_mock

        with patch("core.atendimento.get_db", _fake_get_db):
            atend.votar_artigo_kb(1, False)

        query = db_mock.fetchrow.call_args.args[0]
        self.assertIn("util_nao = util_nao + 1", query)
        self.assertNotIn("util_sim", query)


class TestKbColunaPublicado(unittest.TestCase):
    def test_publicado_esta_na_whitelist(self):
        self.assertIn("publicado", atend.ATEND_COLUNAS["kb_artigos"])

    def test_create_aceita_publicado(self):
        with patch.object(atend, "_create", return_value={"id": 1}) as mock_create:
            atend.create("kb_artigos", {"titulo": "Como resetar senha", "publicado": False})
        mock_create.assert_called_once_with(
            "atend_kb_artigos", {"titulo": "Como resetar senha", "publicado": False})


class TestListLimite(unittest.TestCase):
    def test_list_usa_limit_500(self):
        db_mock = AsyncMock()
        db_mock.fetch = AsyncMock(return_value=[])

        async def _fake_get_db():
            return db_mock

        with patch("core.atendimento.get_db", _fake_get_db):
            atend._list("atend_kb_artigos")

        query = db_mock.fetch.call_args.args[0]
        self.assertIn("LIMIT 500", query)


class TestRotasKbVisualizarVotarExigemPermissao(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_visualizar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.atendimento.visualizar_artigo_kb") as mock_v:
            r = self.client.post("/api/atendimento/kb_artigos/1/visualizar", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_v.assert_not_called()

    def test_visualizar_com_permissao_libera(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.atendimento.visualizar_artigo_kb", return_value={"id": 1, "visualizacoes": 6}) as mock_v:
            r = self.client.post("/api/atendimento/kb_artigos/1/visualizar", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_v.assert_called_once_with(1)

    def test_votar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.atendimento.votar_artigo_kb") as mock_v:
            r = self.client.post("/api/atendimento/kb_artigos/1/votar", json={"util": True}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_v.assert_not_called()

    def test_votar_com_permissao_libera_util_true(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.atendimento.votar_artigo_kb", return_value={"id": 1, "util_sim": 1}) as mock_v:
            r = self.client.post("/api/atendimento/kb_artigos/1/votar", json={"util": True}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_v.assert_called_once_with(1, True)

    def test_votar_artigo_inexistente_retorna_404(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.atendimento.votar_artigo_kb", return_value={"error": "not found"}):
            r = self.client.post("/api/atendimento/kb_artigos/999/votar", json={"util": True}, headers=headers)
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
