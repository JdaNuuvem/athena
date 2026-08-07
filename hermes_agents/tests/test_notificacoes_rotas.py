"""Testes — rotas de notificacoes com conta master (user_id=0, is_master=True).

Bug: as 3 rotas guardavam com "if not usuario.get('user_id')". 0 e' falsy em
Python, entao a conta master (login ATHENA_ADMIN_EMAIL, via
gerar_token_sessao(0, email, "admin", is_master=True) em athena_bridge.py)
era barrada de TODA a rota. NotificationBell monta em web/src/app/layout.tsx
(em toda pagina) e dispara api.notificacoes.listar() a cada navegacao —
recebia 401, handleUnauthorized() apagava o token e redirecionava pro
/login: a conta master era expulsa do app inteiro so' de navegar.

Mesmo bug ja corrigido em routes/chat.py / core/chat_ws.py, com regressao em
tests/test_chat_conta_master.py — este arquivo espelha aquele padrao pras
rotas de notificacoes."""
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

from flask import Flask
from routes.notificacoes import notificacoes_bp
import core.rbac as rbac


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(notificacoes_bp)
    return app.test_client()


def _token_master():
    return rbac.gerar_token_sessao(0, "admin@athena.com", "admin", is_master=True)


class TestNotificacoesRotasContaMaster(unittest.TestCase):
    def setUp(self):
        self.client = _app()

    def test_listar_notificacoes_master_nao_401(self):
        """Regressao direta do bug relatado: user_id=0 nao pode virar 401."""
        with patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-key"}):
            headers = {"Authorization": f"Bearer {_token_master()}"}
            with patch("core.notificacoes.listar_notificacoes", return_value=[]) as mock_listar:
                r = self.client.get("/api/notificacoes", headers=headers)
            self.assertEqual(r.status_code, 200)
            mock_listar.assert_called_once_with(0)

    def test_marcar_lida_master_nao_401(self):
        with patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-key"}):
            headers = {"Authorization": f"Bearer {_token_master()}"}
            with patch("core.notificacoes.marcar_lida", return_value={"id": 1, "lida": True}) as mock_marcar:
                r = self.client.post("/api/notificacoes/1/lida", headers=headers)
            self.assertEqual(r.status_code, 200)
            mock_marcar.assert_called_once_with(1, 0)

    def test_marcar_todas_lidas_master_nao_401(self):
        with patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-key"}):
            headers = {"Authorization": f"Bearer {_token_master()}"}
            with patch("core.notificacoes.marcar_todas_lidas", return_value={"success": True}) as mock_marcar:
                r = self.client.post("/api/notificacoes/marcar-todas-lidas", headers=headers)
            self.assertEqual(r.status_code, 200)
            mock_marcar.assert_called_once_with(0)

    def test_sem_token_continua_401(self):
        """Guarda ainda barra requisicao sem autenticacao nenhuma (user_id=None)."""
        r = self.client.get("/api/notificacoes")
        self.assertEqual(r.status_code, 401)


if __name__ == "__main__":
    unittest.main(verbosity=2)
