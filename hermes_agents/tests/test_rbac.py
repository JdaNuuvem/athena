"""Testes unitarios — RBAC / Sessao JWT por usuario."""
import sys, os, unittest, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

os.environ.setdefault("ATHENA_TOKEN", "test-master-token-32-bytes-long!!")

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


class TestRequerPermissao(unittest.TestCase):
    def setUp(self):
        from flask import Flask
        self.app = Flask(__name__)

        @self.app.route("/protegido", methods=["POST"])
        @rbac.requer_permissao("configuracoes.criar")
        def protegido():
            from flask import jsonify
            return jsonify({"ok": True})

        self.client = self.app.test_client()

    def test_sem_token_nega(self):
        r = self.client.post("/protegido")
        self.assertEqual(r.status_code, 403)

    def test_token_master_libera(self):
        headers = {"Authorization": f"Bearer {os.environ['ATHENA_TOKEN']}"}
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
