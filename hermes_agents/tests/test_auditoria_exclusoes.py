"""Testes de integracao — exclusoes em financeiro/compras/rh/fiscal passam a
gravar quem excluiu o que no audit_log (antes, nao deixavam nenhum rastro)."""
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
import core.rbac as rbac
from core.seguranca import auditar_exclusao


def _app(bp):
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(bp)
    return app.test_client()


class TestAuditarExclusaoHelper(unittest.TestCase):
    """core.seguranca.auditar_exclusao usa a identidade real do token, nao
    texto livre — mesma garantia que ja existe para aprovacoes."""

    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.app = Flask(__name__)

        @self.app.route("/excluir-teste", methods=["POST"])
        def _rota():
            from flask import jsonify
            auditar_exclusao("teste", "algo", 42, {"nome": "registro antigo"})
            return jsonify({"ok": True})

        self.client = self.app.test_client()

    def tearDown(self):
        self._env_patch.stop()

    def test_grava_usuario_do_token_e_dados_antes(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.seguranca.auditar", return_value=1) as mock_auditar:
            self.client.post("/excluir-teste", headers=headers)
        mock_auditar.assert_called_once()
        args, kwargs = mock_auditar.call_args
        self.assertEqual(args[0], "excluir")
        self.assertEqual(args[1], "teste")
        self.assertEqual(args[2], "algo")
        self.assertEqual(args[3], 42)
        self.assertEqual(kwargs["dados_antes"], {"nome": "registro antigo"})
        self.assertEqual(kwargs["user_id"], 9)
        self.assertEqual(kwargs["email"], "gerente@x.com")


class TestFinanceiroDeleteAuditado(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        from routes.financeiro import financeiro_bp
        self.client = _app(financeiro_bp)

    def tearDown(self):
        self._env_patch.stop()

    def test_excluir_com_sucesso_grava_auditoria_com_dados_antes(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.financeiro.get", return_value={"id": 3, "fornecedor": "X", "valor": 500}), \
             patch("core.financeiro.delete", return_value={"success": True}), \
             patch("core.seguranca.auditar_exclusao") as mock_audit:
            r = self.client.delete("/api/financeiro/contas_pagar/3", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_audit.assert_called_once_with("financeiro", "contas_pagar", 3, {"id": 3, "fornecedor": "X", "valor": 500})

    def test_excluir_com_falha_nao_grava_auditoria(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.financeiro.get", return_value={"id": 3}), \
             patch("core.financeiro.delete", return_value={"error": "falhou"}), \
             patch("core.seguranca.auditar_exclusao") as mock_audit:
            r = self.client.delete("/api/financeiro/contas_pagar/3", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_audit.assert_not_called()

    def test_excluir_sem_permissao_nega_e_nao_chama_delete(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["pdv.operar"]), \
             patch("core.financeiro.delete") as mock_delete:
            r = self.client.delete("/api/financeiro/contas_pagar/3", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_delete.assert_not_called()


class TestComprasDeleteAuditado(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        from routes.compras import compras_bp
        self.client = _app(compras_bp)

    def tearDown(self):
        self._env_patch.stop()

    def test_excluir_com_sucesso_grava_auditoria(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.compras.get", return_value={"id": 1, "descricao": "Papel A4"}), \
             patch("core.compras.delete", return_value={"success": True}), \
             patch("core.seguranca.auditar_exclusao") as mock_audit:
            r = self.client.delete("/api/compras/solicitacoes/1", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_audit.assert_called_once_with("compras", "solicitacoes", 1, {"id": 1, "descricao": "Papel A4"})


class TestRHDeleteAuditado(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        from routes.rh import rh_bp
        self.client = _app(rh_bp)

    def tearDown(self):
        self._env_patch.stop()

    def test_excluir_com_sucesso_grava_auditoria(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.rh.get", return_value={"id": 2, "nome": "Fulano"}), \
             patch("core.rh.delete", return_value={"success": True}), \
             patch("core.seguranca.auditar_exclusao") as mock_audit:
            r = self.client.delete("/api/rh/funcionarios/2", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_audit.assert_called_once_with("rh", "funcionarios", 2, {"id": 2, "nome": "Fulano"})


class TestFiscalDeleteAuditado(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        from routes.fiscal import fiscal_bp
        self.client = _app(fiscal_bp)

    def tearDown(self):
        self._env_patch.stop()

    def test_excluir_com_sucesso_grava_auditoria(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.fiscal.get", return_value={"id": 5, "numero_nf": "123"}), \
             patch("core.fiscal.delete", return_value={"success": True}), \
             patch("core.seguranca.auditar_exclusao") as mock_audit:
            r = self.client.delete("/api/fiscal/notas_fiscais/5", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_audit.assert_called_once_with("fiscal", "notas_fiscais", 5, {"id": 5, "numero_nf": "123"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
