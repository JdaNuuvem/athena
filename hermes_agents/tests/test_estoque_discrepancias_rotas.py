"""Testes — GET /api/estoque/relatorio-discrepancias.

Bug: rota nao tinha NENHUMA checagem de permissao (unica leitura deste
blueprint sem @requer_permissao, ao lado de rotas de escrita todas gated por
"estoque.aprovar") — qualquer usuario autenticado, independente de papel,
podia ver quem esta perdendo mais estoque por loja/operador. Corrigido com
"estoque.ver", mesmo padrao usado em crm.ver."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

# Mesmo motivo do test_estoque_analise_rotas.py: mocka asyncpg antes de
# qualquer import de rota, pra nao abrir conexao real no import em cascata.
async def _mock_create_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"),
    )), __aexit__=AsyncMock(return_value=None))
    return m

patch("asyncpg.create_pool", side_effect=_mock_create_pool).start()

import core.rbac as rbac


def _app():
    from flask import Flask
    from routes.estoque import estoque_bp
    app = Flask(__name__)
    app.register_blueprint(estoque_bp)
    return app.test_client()


class TestRelatorioDiscrepanciasPermissao(unittest.TestCase):
    def setUp(self):
        self.client = _app()

    def test_sem_token_nega(self):
        r = self.client.get("/api/estoque/relatorio-discrepancias")
        self.assertEqual(r.status_code, 403)

    def test_com_token_sem_permissao_nega(self):
        with patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-key"}):
            token = rbac.gerar_token_sessao(11, "u@x.com", "Vendedor")
            headers = {"Authorization": f"Bearer {token}"}
            with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
                 patch("core.estoque_relatorios.por_loja") as mock_loja:
                r = self.client.get("/api/estoque/relatorio-discrepancias", headers=headers)
            self.assertEqual(r.status_code, 403)
            mock_loja.assert_not_called()

    def test_com_permissao_libera(self):
        with patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-key"}):
            token = rbac.gerar_token_sessao(11, "u@x.com", "Gerente")
            headers = {"Authorization": f"Bearer {token}"}
            with patch("core.rbac.get_permissoes_por_usuario", return_value=["estoque.ver"]), \
                 patch("core.estoque_relatorios.por_loja", return_value=[{"loja": "A"}]) as mock_loja, \
                 patch("core.estoque_relatorios.por_operador", return_value=[{"operador": "X"}]) as mock_op:
                r = self.client.get("/api/estoque/relatorio-discrepancias", headers=headers)
            self.assertEqual(r.status_code, 200)
            body = r.get_json()
            self.assertEqual(body["por_loja"], [{"loja": "A"}])
            self.assertEqual(body["por_operador"], [{"operador": "X"}])
            mock_loja.assert_called_once_with(30)
            mock_op.assert_called_once_with(30)

    def test_master_sempre_libera(self):
        with patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-key"}):
            token = rbac.gerar_token_sessao(0, "admin@athena.com", "admin", is_master=True)
            headers = {"Authorization": f"Bearer {token}"}
            with patch("core.estoque_relatorios.por_loja", return_value=[]), \
                 patch("core.estoque_relatorios.por_operador", return_value=[]):
                r = self.client.get("/api/estoque/relatorio-discrepancias", headers=headers)
            self.assertEqual(r.status_code, 200)


class TestRelatorioDiscrepanciasDiasClamp(unittest.TestCase):
    def setUp(self):
        self.client = _app()

    def _headers(self):
        token = rbac.gerar_token_sessao(11, "u@x.com", "Gerente")
        return {"Authorization": f"Bearer {token}"}

    def test_dias_acima_do_limite_clampa_em_365(self):
        with patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-key"}):
            with patch("core.rbac.get_permissoes_por_usuario", return_value=["estoque.ver"]), \
                 patch("core.estoque_relatorios.por_loja", return_value=[]) as mock_loja, \
                 patch("core.estoque_relatorios.por_operador", return_value=[]):
                self.client.get("/api/estoque/relatorio-discrepancias?dias=99999", headers=self._headers())
            mock_loja.assert_called_once_with(365)

    def test_dias_negativo_clampa_em_1(self):
        with patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-key"}):
            with patch("core.rbac.get_permissoes_por_usuario", return_value=["estoque.ver"]), \
                 patch("core.estoque_relatorios.por_loja", return_value=[]) as mock_loja, \
                 patch("core.estoque_relatorios.por_operador", return_value=[]):
                self.client.get("/api/estoque/relatorio-discrepancias?dias=-10", headers=self._headers())
            mock_loja.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
