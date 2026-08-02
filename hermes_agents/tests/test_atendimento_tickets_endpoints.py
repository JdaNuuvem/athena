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


class TestUploadAnexoTicket(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_upload_anexo_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]):
            r = self.client.post(
                "/api/atendimento/tickets/1/anexo", headers=headers,
                data={"arquivo": (io.BytesIO(b"conteudo"), "teste.pdf")},
                content_type="multipart/form-data")
        self.assertEqual(r.status_code, 403)

    def test_upload_anexo_com_permissao_grava_mensagem(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.atendimento.adicionar_mensagem", return_value={"id": 9, "tipo": "anexo"}) as mock_add:
            r = self.client.post(
                "/api/atendimento/tickets/1/anexo", headers=headers,
                data={"arquivo": (io.BytesIO(b"conteudo"), "teste.pdf")},
                content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200)
        mock_add.assert_called_once()
        self.assertEqual(mock_add.call_args[0][0], 1)  # ticket_id
        self.assertEqual(mock_add.call_args[0][3], "anexo")  # tipo

    def test_upload_sem_arquivo_retorna_400(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.post("/api/atendimento/tickets/1/anexo", headers=headers,
                             data={}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)

    def test_upload_anexo_filename_com_traversal_e_sanitizado(self):
        """Regressao de seguranca: nome de arquivo com ../ nao deve sobreviver
        a secure_filename() nem gerar anexo_url fora do diretorio de uploads."""
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.atendimento.adicionar_mensagem", return_value={"id": 9, "tipo": "anexo"}) as mock_add:
            r = self.client.post(
                "/api/atendimento/tickets/1/anexo", headers=headers,
                data={"arquivo": (io.BytesIO(b"conteudo"), "../../../etc/passwd")},
                content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200)
        anexo_url = mock_add.call_args.kwargs["anexo_url"]
        self.assertNotIn("..", anexo_url)
        self.assertNotIn("/", anexo_url)
        self.assertNotIn("\\", anexo_url)

    def test_download_anexo_com_traversal_retorna_404(self):
        """Regressao de seguranca: nome_arquivo com ../ nao deve escapar do
        diretorio de uploads e servir arquivo arbitrario do disco."""
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.get(
            "/api/atendimento/tickets/1/anexo/../../../../etc/passwd", headers=headers)
        self.assertEqual(r.status_code, 404)

    def test_download_anexo_de_outro_ticket_retorna_404(self):
        """IDOR: atendimento.ver e' permissao global, nao por ticket. Sem
        checar que o anexo pertence ao ticket da URL, um usuario com essa
        permissao podia baixar o anexo de QUALQUER ticket so' adivinhando/
        reaproveitando o nome do arquivo em disco. arquivo EXISTE de verdade
        no disco (isfile=True) — se ainda assim vier 404, e' a checagem de
        posse que bloqueou, nao a ausencia do arquivo."""
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.atendimento.listar_mensagens_ticket", return_value=[
                {"id": 1, "anexo_url": "1_1234_meu.pdf"}]), \
             patch("os.path.isfile", return_value=True):
            r = self.client.get(
                "/api/atendimento/tickets/1/anexo/2_1234_outro.pdf", headers=headers)
        self.assertEqual(r.status_code, 404)

    def test_download_anexo_do_proprio_ticket_libera(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.atendimento.listar_mensagens_ticket", return_value=[
                {"id": 9, "anexo_url": "1_1234_relatorio.pdf"}]), \
             patch("routes.atendimento.send_file", return_value="arquivo") as mock_send, \
             patch("os.path.isfile", return_value=True):
            r = self.client.get(
                "/api/atendimento/tickets/1/anexo/1_1234_relatorio.pdf", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_send.assert_called_once()

    def test_upload_anexo_maior_que_25mb_retorna_413(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        conteudo_grande = b"x" * (25 * 1024 * 1024 + 1)
        with patch("core.atendimento.adicionar_mensagem") as mock_add:
            r = self.client.post(
                "/api/atendimento/tickets/1/anexo", headers=headers,
                data={"arquivo": (io.BytesIO(conteudo_grande), "grande.bin")},
                content_type="multipart/form-data")
        self.assertEqual(r.status_code, 413)
        mock_add.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)