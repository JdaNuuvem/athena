"""Testes de integracao das rotas /oauth/* — mesmo padrao de
test_atendimento_seguranca.py: mocka asyncpg.create_pool antes de
importar os modulos, Flask test_client, tokens gerados via core.rbac."""
import sys, os, unittest
from unittest.mock import patch, AsyncMock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TEST_SECRET = "test-secret-32-bytes-long-enough!!"

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
from routes.oauth_provider import oauth_provider_bp
import core.rbac as rbac

_CLIENT_ID = "client-de-teste"
_CLIENT_SECRET = "segredo-de-teste"
_REDIRECT_URI = "https://chat.exemplo.com/_oauth/hermes"

_ENV_OAUTH = {
    "ATHENA_JWT_SECRET": _TEST_SECRET,
    "ROCKETCHAT_OAUTH_CLIENT_ID": _CLIENT_ID,
    "ROCKETCHAT_OAUTH_CLIENT_SECRET": _CLIENT_SECRET,
    "ROCKETCHAT_OAUTH_REDIRECT_URI": _REDIRECT_URI,
    "HERMES_LOGIN_URL": "https://athena.exemplo.com/login",
}


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(oauth_provider_bp)
    return app.test_client()


class TestAuthorize(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, _ENV_OAUTH)
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_sem_sessao_redireciona_para_login_do_hermes(self):
        r = self.client.get(
            "/oauth/authorize",
            query_string={"response_type": "code", "client_id": _CLIENT_ID, "redirect_uri": _REDIRECT_URI},
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers["Location"], "https://athena.exemplo.com/login")

    def test_com_sessao_valida_redireciona_com_code(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador")
        r = self.client.get(
            "/oauth/authorize",
            query_string={"response_type": "code", "client_id": _CLIENT_ID, "redirect_uri": _REDIRECT_URI, "state": "xyz"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(r.status_code, 302)
        location = r.headers["Location"]
        self.assertTrue(location.startswith(_REDIRECT_URI))
        self.assertIn("code=", location)
        self.assertIn("state=xyz", location)

    def test_com_sessao_valida_user_id_zero_redireciona_com_code(self):
        """user_id=0 e' um id real neste projeto (admin bootstrap) — 0 e'
        falsy em Python, entao um check tipo 'not payload.get(user_id)'
        trata sessao valida como ausente. Regressao ja vista em
        routes/chat.py e routes/chat_ws.py; ver test_chat_conta_master.py."""
        token = rbac.gerar_token_sessao(0, "admin@athena.com", "admin", is_master=True)
        r = self.client.get(
            "/oauth/authorize",
            query_string={"response_type": "code", "client_id": _CLIENT_ID, "redirect_uri": _REDIRECT_URI},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].startswith(_REDIRECT_URI))
        self.assertIn("code=", r.headers["Location"])

    def test_client_id_errado_rejeita(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador")
        r = self.client.get(
            "/oauth/authorize",
            query_string={"response_type": "code", "client_id": "outro", "redirect_uri": _REDIRECT_URI},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(r.status_code, 400)

    def test_redirect_uri_errado_rejeita(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador")
        r = self.client.get(
            "/oauth/authorize",
            query_string={"response_type": "code", "client_id": _CLIENT_ID, "redirect_uri": "https://outro.com/cb"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(r.status_code, 400)

    def test_response_type_invalido_rejeita(self):
        r = self.client.get(
            "/oauth/authorize",
            query_string={"response_type": "token", "client_id": _CLIENT_ID, "redirect_uri": _REDIRECT_URI},
        )
        self.assertEqual(r.status_code, 400)


class TestToken(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, _ENV_OAUTH)
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def _obter_code(self, user_id=7):
        from core.oauth_provider import gerar_authorization_code
        return gerar_authorization_code(user_id, _CLIENT_ID, _REDIRECT_URI)

    def test_troca_code_valido_por_access_token(self):
        code = self._obter_code()
        r = self.client.post("/oauth/token", data={
            "grant_type": "authorization_code",
            "client_id": _CLIENT_ID, "client_secret": _CLIENT_SECRET,
            "code": code, "redirect_uri": _REDIRECT_URI,
        })
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertIn("access_token", body)
        self.assertEqual(body["token_type"], "Bearer")
        self.assertEqual(body["expires_in"], 3600)

    def test_troca_code_valido_user_id_zero_por_access_token(self):
        code = self._obter_code(user_id=0)
        r = self.client.post("/oauth/token", data={
            "grant_type": "authorization_code",
            "client_id": _CLIENT_ID, "client_secret": _CLIENT_SECRET,
            "code": code, "redirect_uri": _REDIRECT_URI,
        })
        self.assertEqual(r.status_code, 200)
        self.assertIn("access_token", r.get_json())

    def test_client_secret_errado_rejeita(self):
        code = self._obter_code()
        r = self.client.post("/oauth/token", data={
            "grant_type": "authorization_code",
            "client_id": _CLIENT_ID, "client_secret": "errado",
            "code": code, "redirect_uri": _REDIRECT_URI,
        })
        self.assertEqual(r.status_code, 401)

    def test_code_invalido_rejeita(self):
        r = self.client.post("/oauth/token", data={
            "grant_type": "authorization_code",
            "client_id": _CLIENT_ID, "client_secret": _CLIENT_SECRET,
            "code": "code-invalido", "redirect_uri": _REDIRECT_URI,
        })
        self.assertEqual(r.status_code, 400)

    def test_grant_type_ausente_ou_errado_rejeita(self):
        code = self._obter_code()
        r = self.client.post("/oauth/token", data={
            "client_id": _CLIENT_ID, "client_secret": _CLIENT_SECRET,
            "code": code, "redirect_uri": _REDIRECT_URI,
        })
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()["error"], "unsupported_grant_type")

        r = self.client.post("/oauth/token", data={
            "grant_type": "client_credentials",
            "client_id": _CLIENT_ID, "client_secret": _CLIENT_SECRET,
            "code": code, "redirect_uri": _REDIRECT_URI,
        })
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()["error"], "unsupported_grant_type")


class TestUserinfo(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, _ENV_OAUTH)
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_token_valido_retorna_dados_do_usuario(self):
        from core.oauth_provider import gerar_access_token
        token = gerar_access_token(7)
        usuario = {"id": 7, "nome": "Fulano da Silva", "email": "fulano@x.com"}
        with patch("routes.oauth_provider._buscar_usuario", AsyncMock(return_value=usuario)):
            r = self.client.get("/oauth/userinfo", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertEqual(body["id"], 7)
        self.assertEqual(body["email"], "fulano@x.com")
        self.assertEqual(body["username"], "fulano")
        self.assertEqual(body["name"], "Fulano da Silva")

    def test_token_valido_user_id_zero_retorna_dados_do_usuario(self):
        from core.oauth_provider import gerar_access_token
        token = gerar_access_token(0)
        usuario = {"id": 0, "nome": "Admin Athena", "email": "admin@athena.com"}
        with patch("routes.oauth_provider._buscar_usuario", AsyncMock(return_value=usuario)):
            r = self.client.get("/oauth/userinfo", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["id"], 0)

    def test_token_invalido_rejeita(self):
        r = self.client.get("/oauth/userinfo", headers={"Authorization": "Bearer invalido"})
        self.assertEqual(r.status_code, 401)

    def test_usuario_inativo_ou_removido_rejeita(self):
        from core.oauth_provider import gerar_access_token
        token = gerar_access_token(999)
        with patch("routes.oauth_provider._buscar_usuario", AsyncMock(return_value=None)):
            r = self.client.get("/oauth/userinfo", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(r.status_code, 401)


if __name__ == "__main__":
    unittest.main()
