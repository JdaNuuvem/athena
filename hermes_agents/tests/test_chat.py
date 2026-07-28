"""Testes de integracao — permissao e isolamento do chat interno."""
import sys, os, unittest
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

import core.chat as chat
from flask import Flask
from routes.chat import chat_bp
import core.rbac as rbac


class TestChatConversas(unittest.TestCase):
    def test_participantes_ids_conversa_inexistente_retorna_vazio(self):
        with patch("core.chat._obter_conversa", return_value=None):
            self.assertEqual(chat.participantes_ids(999), [])

    def test_usuario_e_participante_false_quando_fora_da_lista(self):
        with patch("core.chat.participantes_ids", return_value=[1, 2, 3]):
            self.assertFalse(chat.usuario_e_participante(5, 42))

    def test_usuario_e_participante_true_quando_na_lista(self):
        with patch("core.chat.participantes_ids", return_value=[1, 2, 3]):
            self.assertTrue(chat.usuario_e_participante(5, 2))


class TestChatMensagens(unittest.TestCase):
    def test_listar_mensagens_erro_de_db_retorna_lista_vazia(self):
        with patch("core.chat.get_db", side_effect=RuntimeError("sem conexao")):
            self.assertEqual(chat.listar_mensagens(1), [])

    def test_editar_mensagem_sem_ser_autor_retorna_error(self):
        async def _fetchrow(*a, **kw): return None
        with patch("core.chat.get_db") as mock_get_db:
            mock_db = AsyncMock(fetchrow=_fetchrow)
            mock_get_db.return_value = mock_db
            resultado = chat.editar_mensagem(1, 999, "novo texto")
        self.assertIn("error", resultado)

    def test_listar_conversas_usuario_ordena_por_atividade_recente(self):
        with patch("core.chat.get_db") as mock_get_db, \
             patch("core.chat._canais_departamento_permitidos", return_value=[]), \
             patch("core.chat._conversas_ticket_permitidas", return_value=[]):
            async def _fetch(*a, **kw):
                return [
                    {"id": 1, "tipo": "dm", "created_at": "2026-01-01", "ultima_atividade": "2026-01-01"},
                    {"id": 2, "tipo": "grupo", "created_at": "2026-01-01", "ultima_atividade": "2026-06-01"},
                ]
            mock_db = AsyncMock(fetch=_fetch)
            mock_get_db.return_value = mock_db
            resultado = chat.listar_conversas_usuario(7)
        self.assertEqual(resultado[0]["id"], 2)


class TestChatPonteTicket(unittest.TestCase):
    def test_criar_conversa_ticket_reaproveita_existente(self):
        with patch("core.chat.run_async", return_value=None), \
             patch("core.chat.conversa_id_do_ticket", return_value=42), \
             patch("core.chat._obter_conversa", return_value={"id": 42, "tipo": "ticket", "ticket_ref_id": 7}) as mock_obter:
            resultado = chat.criar_conversa_ticket(7)
        self.assertEqual(resultado["id"], 42)
        mock_obter.assert_called_once_with(42)


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(chat_bp)
    return app.test_client()


class TestChatRotasPermissao(unittest.TestCase):
    def setUp(self):
        self.client = _app()

    def test_listar_mensagens_nao_participante_nega(self):
        with patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-key"}):
            token = rbac.gerar_token_sessao(11, "u@x.com", "Vendedor")
            headers = {"Authorization": f"Bearer {token}"}
            with patch("routes.chat.usuario_e_participante", return_value=False):
                r = self.client.get("/api/chat/conversas/5/mensagens", headers=headers)
            self.assertEqual(r.status_code, 403)

    def test_listar_mensagens_participante_libera(self):
        with patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-key"}):
            token = rbac.gerar_token_sessao(11, "u@x.com", "Vendedor")
            headers = {"Authorization": f"Bearer {token}"}
            with patch("routes.chat.usuario_e_participante", return_value=True), \
                 patch("routes.chat.listar_mensagens", return_value=[{"id": 1, "texto": "oi"}]) as mock_listar:
                r = self.client.get("/api/chat/conversas/5/mensagens", headers=headers)
            self.assertEqual(r.status_code, 200)
            mock_listar.assert_called_once()

    def test_enviar_mensagem_nao_participante_nega(self):
        with patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-key"}):
            token = rbac.gerar_token_sessao(11, "u@x.com", "Vendedor")
            headers = {"Authorization": f"Bearer {token}"}
            with patch("routes.chat.usuario_e_participante", return_value=False), \
                 patch("routes.chat.enviar_mensagem") as mock_enviar:
                r = self.client.post("/api/chat/conversas/5/mensagens", json={"texto": "oi"}, headers=headers)
            self.assertEqual(r.status_code, 403)
            mock_enviar.assert_not_called()

    def test_adicionar_participante_exige_papel_admin(self):
        with patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-key"}):
            token = rbac.gerar_token_sessao(11, "u@x.com", "Vendedor")
            headers = {"Authorization": f"Bearer {token}"}
            with patch("routes.chat.papel_do_usuario", return_value="membro"), \
                 patch("routes.chat.adicionar_participante") as mock_add:
                r = self.client.post("/api/chat/conversas/5/participantes", json={"user_id": 9}, headers=headers)
            self.assertEqual(r.status_code, 403)
            mock_add.assert_not_called()

    def test_adicionar_participante_owner_libera(self):
        with patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-key"}):
            token = rbac.gerar_token_sessao(11, "u@x.com", "Vendedor")
            headers = {"Authorization": f"Bearer {token}"}
            with patch("routes.chat.papel_do_usuario", return_value="owner"), \
                 patch("routes.chat.adicionar_participante", return_value={"conversa_id": 5, "user_id": 9}) as mock_add:
                r = self.client.post("/api/chat/conversas/5/participantes", json={"user_id": 9}, headers=headers)
            self.assertEqual(r.status_code, 200)
            mock_add.assert_called_once()


class TestChatWebsocketBroadcastIsolamento(unittest.TestCase):
    def test_broadcast_so_alcanca_participantes(self):
        from core.chat_ws import broadcast_para_participantes, registrar_conexao, remover_conexao

        enviados = []

        class FakeWs:
            def __init__(self, uid): self.uid = uid
            def send(self, payload): enviados.append((self.uid, payload))

        ws_membro = FakeWs(1)
        ws_estranho = FakeWs(2)
        registrar_conexao(1, ws_membro)
        registrar_conexao(2, ws_estranho)
        try:
            with patch("core.chat.participantes_ids", return_value=[1]):
                broadcast_para_participantes(99, {"evento": "nova_mensagem"})
        finally:
            remover_conexao(1, ws_membro)
            remover_conexao(2, ws_estranho)

        uids_notificados = [uid for uid, _ in enviados]
        self.assertIn(1, uids_notificados)
        self.assertNotIn(2, uids_notificados)


if __name__ == "__main__":
    unittest.main(verbosity=2)
