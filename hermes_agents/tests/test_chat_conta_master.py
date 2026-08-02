"""Testes — conta master (login ATHENA_ADMIN_EMAIL, user_id=0, is_master=True)
no chat interno.

Bug: toda rota de chat checava "if not user_id" / "if not usuario.get('user_id')".
0 e' falsy em Python, entao a conta master era barrada de TODO o chat — o
frontend recebia 401 em /api/chat/conversas e redirecionava pro login (relato
do usuario: "quando entro nesse link ele me manda pra pagina de login").

Cobre tambem o efeito colateral da correcao: chat_participantes/chat_mensagens
tem FK pra rbac_usuarios(id), e a conta master nao tem linha real la (login
via env var, sem cadastro) — sem guarda, "consertar" so' o 401 teria trocado
um erro por outro (violacao de FK crua) na hora de enviar mensagem ou entrar
numa DM/grupo."""
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


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(chat_bp)
    return app.test_client()


def _token_master():
    return rbac.gerar_token_sessao(0, "admin@athena.com", "admin", is_master=True)


class TestUsuarioEParticipanteMaster(unittest.TestCase):
    """Unidade: is_master destrava canal/ticket, mas nunca dm/grupo (privacidade)."""

    def test_master_entra_em_canal_departamento_mesmo_sem_estar_na_lista(self):
        with patch("core.chat._obter_conversa", return_value={"id": 5, "tipo": "canal_departamento"}), \
             patch("core.chat.participantes_ids", return_value=[1, 2, 3]):
            self.assertTrue(chat.usuario_e_participante(5, 0, is_master=True))

    def test_master_entra_em_ticket_mesmo_sem_estar_na_lista(self):
        with patch("core.chat._obter_conversa", return_value={"id": 5, "tipo": "ticket"}), \
             patch("core.chat.participantes_ids", return_value=[1, 2, 3]):
            self.assertTrue(chat.usuario_e_participante(5, 0, is_master=True))

    def test_master_nao_entra_em_dm_alheia(self):
        with patch("core.chat._obter_conversa", return_value={"id": 5, "tipo": "dm"}), \
             patch("core.chat.participantes_ids", return_value=[1, 2]):
            self.assertFalse(chat.usuario_e_participante(5, 0, is_master=True))

    def test_master_nao_entra_em_grupo_alheio(self):
        with patch("core.chat._obter_conversa", return_value={"id": 5, "tipo": "grupo"}), \
             patch("core.chat.participantes_ids", return_value=[1, 2]):
            self.assertFalse(chat.usuario_e_participante(5, 0, is_master=True))

    def test_usuario_comum_sem_is_master_mantem_comportamento_antigo(self):
        with patch("core.chat._obter_conversa", return_value={"id": 5, "tipo": "canal_departamento"}), \
             patch("core.chat.participantes_ids", return_value=[1, 2, 3]):
            self.assertFalse(chat.usuario_e_participante(5, 999, is_master=False))


class TestListagensMaster(unittest.TestCase):
    def test_canais_departamento_master_ve_todos_sem_checar_permissao(self):
        with patch("core.chat.run_async", return_value=[{"id": 1, "departamento": "financeiro"}]), \
             patch("core.rbac.get_permissoes_por_usuario") as mock_perms:
            resultado = chat._canais_departamento_permitidos(0, is_master=True)
        self.assertEqual(len(resultado), 1)
        mock_perms.assert_not_called()

    def test_canais_departamento_usuario_comum_ainda_filtra_por_permissao(self):
        with patch("core.chat.run_async", return_value=[{"id": 1, "departamento": "financeiro"}]), \
             patch("core.rbac.get_permissoes_por_usuario", return_value=[]):
            resultado = chat._canais_departamento_permitidos(7, is_master=False)
        self.assertEqual(resultado, [])


class TestRotasContaMaster(unittest.TestCase):
    def setUp(self):
        self.client = _app()

    def test_listar_conversas_master_nao_401(self):
        """Regressao direta do bug relatado: user_id=0 nao pode virar 401."""
        with patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-key"}):
            headers = {"Authorization": f"Bearer {_token_master()}"}
            with patch("routes.chat.listar_conversas_usuario", return_value=[]) as mock_listar:
                r = self.client.get("/api/chat/conversas", headers=headers)
            self.assertEqual(r.status_code, 200)
            mock_listar.assert_called_once_with(0, True)

    def test_criar_dm_master_bloqueia_com_mensagem_amigavel(self):
        with patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-key"}):
            headers = {"Authorization": f"Bearer {_token_master()}"}
            with patch("routes.chat.criar_conversa_dm") as mock_criar:
                r = self.client.post("/api/chat/conversas", json={"tipo": "dm", "user_id": 9}, headers=headers)
            self.assertEqual(r.status_code, 400)
            mock_criar.assert_not_called()
            self.assertIn("master", r.get_json()["error"].lower())

    def test_criar_grupo_master_bloqueia_com_mensagem_amigavel(self):
        with patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-key"}):
            headers = {"Authorization": f"Bearer {_token_master()}"}
            with patch("routes.chat.criar_conversa_grupo") as mock_criar:
                r = self.client.post("/api/chat/conversas", json={"tipo": "grupo", "nome": "Time X"}, headers=headers)
            self.assertEqual(r.status_code, 400)
            mock_criar.assert_not_called()

    def test_enviar_mensagem_canal_master_bloqueia_sem_estourar_fk(self):
        """Sem a guarda, isso cairia em enviar_mensagem() -> INSERT com
        remetente_id=0, violando a FK pra rbac_usuarios(id)."""
        with patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-key"}):
            headers = {"Authorization": f"Bearer {_token_master()}"}
            with patch("routes.chat.usuario_e_participante", return_value=True), \
                 patch("routes.chat.obter_conversa", return_value={"id": 5, "tipo": "canal_departamento"}), \
                 patch("routes.chat.enviar_mensagem") as mock_enviar:
                r = self.client.post("/api/chat/conversas/5/mensagens", json={"texto": "oi"}, headers=headers)
            self.assertEqual(r.status_code, 400)
            mock_enviar.assert_not_called()

    def test_enviar_mensagem_ticket_master_funciona(self):
        """Ticket escapa da FK — atend_mensagens guarda remetente como texto,
        entao master consegue responder ticket normalmente."""
        with patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-key"}):
            headers = {"Authorization": f"Bearer {_token_master()}"}
            with patch("routes.chat.usuario_e_participante", return_value=True), \
                 patch("routes.chat.obter_conversa", return_value={"id": 5, "tipo": "ticket", "ticket_ref_id": 77}), \
                 patch("core.atendimento.adicionar_mensagem",
                       return_value={"id": 9, "conteudo": "resposta", "enviado_em": None}) as mock_add, \
                 patch("routes.chat.broadcast_para_participantes"):
                r = self.client.post("/api/chat/conversas/5/mensagens", json={"texto": "resposta"}, headers=headers)
            self.assertEqual(r.status_code, 200)
            mock_add.assert_called_once()

    def test_upload_anexo_master_bloqueia_sem_estourar_fk(self):
        with patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-key"}):
            headers = {"Authorization": f"Bearer {_token_master()}"}
            r = self.client.post("/api/chat/anexos", headers=headers)
            self.assertEqual(r.status_code, 400)
            self.assertIn("master", r.get_json()["error"].lower())

    def test_marcar_lido_master_nao_persiste_mas_responde_sucesso(self):
        with patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-key"}):
            headers = {"Authorization": f"Bearer {_token_master()}"}
            with patch("routes.chat.usuario_e_participante", return_value=True), \
                 patch("routes.chat.marcar_lido") as mock_marcar:
                r = self.client.post("/api/chat/conversas/5/lido", json={"ultima_mensagem_id": 1}, headers=headers)
            self.assertEqual(r.status_code, 200)
            mock_marcar.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
