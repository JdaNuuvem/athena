"""Testes do core do OAuth provider — geracao/validacao de authorization
code e access token como JWTs curtos, sem estado em memoria/banco."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

os.environ.setdefault("ATHENA_JWT_SECRET", "test-secret-32-bytes-long-enough!!")

async def _mock_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mock_pool)
patcher.start()

from core.oauth_provider import (
    gerar_authorization_code, validar_authorization_code,
    gerar_access_token, validar_access_token,
)

_CLIENT_ID = "rocketchat"
_REDIRECT_URI = "https://chat.exemplo.com/_oauth/hermes"


class TestAuthorizationCode(unittest.TestCase):
    def test_code_valido_retorna_user_id(self):
        code = gerar_authorization_code(42, _CLIENT_ID, _REDIRECT_URI)
        self.assertEqual(validar_authorization_code(code, _CLIENT_ID, _REDIRECT_URI), 42)

    def test_code_com_client_id_errado_rejeita(self):
        code = gerar_authorization_code(42, _CLIENT_ID, _REDIRECT_URI)
        self.assertIsNone(validar_authorization_code(code, "outro-client", _REDIRECT_URI))

    def test_code_com_redirect_uri_errado_rejeita(self):
        code = gerar_authorization_code(42, _CLIENT_ID, _REDIRECT_URI)
        self.assertIsNone(validar_authorization_code(code, _CLIENT_ID, "https://outro.com/cb"))

    def test_code_vazio_rejeita(self):
        self.assertIsNone(validar_authorization_code("", _CLIENT_ID, _REDIRECT_URI))

    def test_code_expirado_rejeita(self):
        import core.oauth_provider as op
        original = op.CODE_EXPIRACAO_SEGUNDOS
        op.CODE_EXPIRACAO_SEGUNDOS = -1
        try:
            code = gerar_authorization_code(42, _CLIENT_ID, _REDIRECT_URI)
        finally:
            op.CODE_EXPIRACAO_SEGUNDOS = original
        self.assertIsNone(validar_authorization_code(code, _CLIENT_ID, _REDIRECT_URI))

    def test_access_token_nao_e_aceito_como_code(self):
        token = gerar_access_token(42)
        self.assertIsNone(validar_authorization_code(token, _CLIENT_ID, _REDIRECT_URI))


class TestAccessToken(unittest.TestCase):
    def test_token_valido_retorna_user_id(self):
        token = gerar_access_token(42)
        self.assertEqual(validar_access_token(token), 42)

    def test_token_invalido_rejeita(self):
        self.assertIsNone(validar_access_token("token-invalido"))

    def test_token_vazio_rejeita(self):
        self.assertIsNone(validar_access_token(""))

    def test_authorization_code_nao_e_aceito_como_access_token(self):
        code = gerar_authorization_code(42, _CLIENT_ID, _REDIRECT_URI)
        self.assertIsNone(validar_access_token(code))


if __name__ == "__main__":
    unittest.main()
