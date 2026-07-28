"""Testes de integracao — criar/editar/excluir loja fisica antes nao
checava nenhuma permissao: qualquer usuario autenticado podia criar ou
apagar uma das lojas do grupo."""
import sys, os, io, unittest
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
from routes.lojas_manage import lojas_bp
from routes.lojas_config import lojas_config_bp
from routes.lojas_responsaveis import lojas_responsaveis_bp
from routes.lojas_integracoes import lojas_integracoes_bp
from routes.lojas_midia import lojas_midia_bp
import core.rbac as rbac


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(lojas_bp)
    app.register_blueprint(lojas_config_bp)
    app.register_blueprint(lojas_responsaveis_bp)
    app.register_blueprint(lojas_integracoes_bp)
    app.register_blueprint(lojas_midia_bp)
    return app.test_client()


class TestLojasManageExigePermissao(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_criar_loja_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["compras.criar", "vendas.criar"]), \
             patch("core.lojas.criar") as mock_criar:
            r = self.client.post("/api/lojas/manage", json={"nome": "Loja Nova"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_criar.assert_not_called()

    def test_criar_loja_com_permissao_libera(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.lojas.criar", return_value={"id": 6, "nome": "Loja Nova"}) as mock_criar:
            r = self.client.post("/api/lojas/manage", json={"nome": "Loja Nova"}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_criar.assert_called_once()

    def test_editar_loja_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["compras.editar"]), \
             patch("core.lojas.atualizar") as mock_atualizar:
            r = self.client.put("/api/lojas/manage/1", json={"nome": "Loja X"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_atualizar.assert_not_called()

    def test_excluir_loja_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["compras.excluir"]), \
             patch("core.lojas.deletar") as mock_deletar:
            r = self.client.delete("/api/lojas/manage/1", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_deletar.assert_not_called()

    def test_excluir_loja_com_permissao_libera_e_audita(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.lojas.listar", return_value=[{"id": 1, "nome": "Loja Centro"}]), \
             patch("core.lojas.deletar", return_value=True) as mock_deletar, \
             patch("core.seguranca.auditar_exclusao") as mock_audit:
            r = self.client.delete("/api/lojas/manage/1", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_deletar.assert_called_once()
        mock_audit.assert_called_once_with("lojas", "manage", 1, {"id": 1, "nome": "Loja Centro"})

    def test_sync_bling_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.lojas.sincronizar_bling") as mock_sync:
            r = self.client.post("/api/lojas/sync/bling", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_sync.assert_not_called()

    def test_criar_loja_com_cnpj_invalido_rejeita_400(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.post("/api/lojas/manage", json={"nome": "Loja X", "cnpj_cpf": "11111111111111"},
                              headers=headers)
        self.assertEqual(r.status_code, 400)

    def test_criar_loja_com_email_invalido_rejeita_400(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.post("/api/lojas/manage", json={"nome": "Loja X", "email": "nao-e-email"},
                              headers=headers)
        self.assertEqual(r.status_code, 400)

    def test_atualizar_fiscal_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.lojas_fiscal_financeiro.atualizar_fiscal") as mock_fiscal:
            r = self.client.put("/api/lojas/manage/1/fiscal", json={"regime_tributario": "simples"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_fiscal.assert_not_called()

    def test_vincular_responsavel_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.lojas_responsaveis.vincular") as mock_vincular:
            r = self.client.post("/api/lojas/manage/1/responsaveis",
                                  json={"usuario_id": 7, "cargo": "gerente_geral"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_vincular.assert_not_called()

    def test_atualizar_integracao_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.lojas_integracoes.atualizar_status") as mock_atualizar:
            r = self.client.put("/api/lojas/manage/1/integracoes/mercado_livre",
                                 json={"status": "ativa"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_atualizar.assert_not_called()

    def test_vincular_midia_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.lojas_midia.vincular") as mock_vincular:
            r = self.client.post(
                "/api/lojas/manage/1/midia",
                data={"tipo": "logo", "arquivo": (io.BytesIO(b"fake"), "logo.png")},
                content_type="multipart/form-data", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_vincular.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
