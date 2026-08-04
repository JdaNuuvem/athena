"""Testes unitarios — RBAC / Sessao JWT por usuario."""
# ponytail: NAO setar ATHENA_TOKEN no nivel do modulo (via os.environ.setdefault) —
# isso "vaza" para outros arquivos de teste na mesma sessao pytest, porque
# athena_bridge.API_TOKEN so' e' lido uma vez, na primeira importacao do modulo em
# todo o processo. Se ATHENA_TOKEN estiver setado nesse momento (mesmo que so'
# durante a fase de coleta do pytest), o valor fica preso para o resto da sessao,
# quebrando testes de outros arquivos que esperam rodar sem nenhum token
# configurado. Cada teste abaixo usa patch.dict escopado quando precisa da env var.
import sys, os, unittest, time
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


class TestTokenSessao(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()

    def tearDown(self):
        self._env_patch.stop()

    def test_gera_e_verifica_token_valido(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador")
        payload = rbac.verificar_token_sessao(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["user_id"], 7)
        self.assertEqual(payload["role"], "Operador")
        self.assertFalse(payload["is_master"])

    def test_token_adulterado_e_invalido(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador")
        adulterado = token[:-2] + "xx"
        self.assertIsNone(rbac.verificar_token_sessao(adulterado))

    def test_token_vazio_e_invalido(self):
        self.assertIsNone(rbac.verificar_token_sessao(""))

    def test_token_de_usuario_diferente_nao_pode_ser_forjado(self):
        """Ao contrario do cookie user_id solto (nao assinado), o payload do
        JWT nao pode ser trocado sem invalidar a assinatura."""
        token_user7 = rbac.gerar_token_sessao(7, "op@x.com", "Operador")
        # Simula uma tentativa de adulterar o payload trocando uma secao do JWT
        header, payload_b64, sig = token_user7.split(".")
        token_falsificado = f"{header}.{payload_b64}modificado.{sig}"
        self.assertIsNone(rbac.verificar_token_sessao(token_falsificado))

    def test_is_master_flag(self):
        token = rbac.gerar_token_sessao(None, "admin@x.com", "admin", is_master=True)
        payload = rbac.verificar_token_sessao(token)
        self.assertTrue(payload["is_master"])
        self.assertIsNone(payload["user_id"])

    def test_sem_segredo_configurado_falha_seguro_sem_fallback_hardcoded(self):
        """Sem ATHENA_JWT_SECRET/ATHENA_TOKEN, gerar token deve falhar alto (nao
        assinar com uma chave publica conhecida no codigo-fonte) e verificar
        deve retornar None (nao propagar a excecao)."""
        with patch.dict(os.environ, {"ATHENA_TOKEN": "", "ATHENA_JWT_SECRET": ""}, clear=False):
            with self.assertRaises(RuntimeError):
                rbac.gerar_token_sessao(1, "x@x.com", "admin")
            self.assertIsNone(rbac.verificar_token_sessao("qualquer.token.aqui"))

    def test_athena_jwt_secret_tem_prioridade_sobre_athena_token(self):
        with patch.dict(os.environ, {"ATHENA_TOKEN": "token-master", "ATHENA_JWT_SECRET": "segredo-jwt-dedicado"}):
            token = rbac.gerar_token_sessao(1, "x@x.com", "admin")
        # assinado com ATHENA_JWT_SECRET — decodificar com ATHENA_TOKEN deve falhar
        with patch.dict(os.environ, {"ATHENA_TOKEN": "token-master", "ATHENA_JWT_SECRET": ""}):
            self.assertIsNone(rbac.verificar_token_sessao(token))
        with patch.dict(os.environ, {"ATHENA_TOKEN": "token-master", "ATHENA_JWT_SECRET": "segredo-jwt-dedicado"}):
            self.assertIsNotNone(rbac.verificar_token_sessao(token))


class TestTokenSessaoRejeitaTokensOAuth(unittest.TestCase):
    """Regressao: um code/access_token do OAuth provider (core/oauth_provider.py)
    e' assinado com o mesmo ATHENA_JWT_SECRET e carrega user_id, mas NAO pode
    valer como sessao completa do Hermes — verificar_token_sessao deve
    rejeitar qualquer payload com claim `typ` (so' os tokens OAuth setam essa
    claim; tokens de sessao normais, gerados por gerar_token_sessao, nunca
    setam)."""

    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-32-bytes-long-enough!!"})
        self._env_patch.start()

    def tearDown(self):
        self._env_patch.stop()

    def test_oauth_access_token_nao_vale_como_sessao(self):
        from core.oauth_provider import gerar_access_token
        token = gerar_access_token(7)
        self.assertIsNone(rbac.verificar_token_sessao(token))

    def test_oauth_authorization_code_nao_vale_como_sessao(self):
        from core.oauth_provider import gerar_authorization_code
        code = gerar_authorization_code(7, "client-x", "https://exemplo.com/cb")
        self.assertIsNone(rbac.verificar_token_sessao(code))

    def test_token_de_sessao_normal_continua_valido(self):
        """Sem regressao no caminho de auth normal, usado em todo o resto do app."""
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador")
        payload = rbac.verificar_token_sessao(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["user_id"], 7)


class TestRequerPermissao(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        from flask import Flask
        self.app = Flask(__name__)

        @self.app.route("/protegido", methods=["POST"])
        @rbac.requer_permissao("configuracoes.criar")
        def protegido():
            from flask import jsonify
            return jsonify({"ok": True})

        self.client = self.app.test_client()

    def tearDown(self):
        self._env_patch.stop()

    def test_sem_token_nega(self):
        r = self.client.post("/protegido")
        self.assertEqual(r.status_code, 403)

    def test_token_master_libera(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.post("/protegido", headers=headers)
        self.assertEqual(r.status_code, 200)

    def test_sessao_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["pdv.operar"]):
            r = self.client.post("/protegido", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_sessao_com_permissao_libera(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["configuracoes.criar"]):
            r = self.client.post("/protegido", headers=headers)
        self.assertEqual(r.status_code, 200)

    def test_sessao_is_master_libera_sem_checar_permissao(self):
        token = rbac.gerar_token_sessao(None, "admin@x.com", "admin", is_master=True)
        headers = {"Authorization": f"Bearer {token}"}
        r = self.client.post("/protegido", headers=headers)
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
