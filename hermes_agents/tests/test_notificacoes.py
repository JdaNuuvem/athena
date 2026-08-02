"""Testes — core de notificacoes (sino generico)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

async def _mock_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m
patcher = patch("asyncpg.create_pool", side_effect=_mock_pool)
patcher.start()

import core.notificacoes as notif


class TestNotificacoesCore(unittest.TestCase):
    @patch("core.notificacoes.get_db")
    def test_criar_notificacao_grava_e_retorna_linha(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetchrow = AsyncMock(return_value={"id": 1, "usuario_id": 5, "tipo": "ticket_atribuido",
                                                     "titulo": "Ticket #0001", "mensagem": "", "link": "/x",
                                                     "lida": False, "created_at": "2026-08-01T10:00:00"})
        mock_get_db.return_value = fake_db
        r = notif.criar_notificacao(5, "ticket_atribuido", "Ticket #0001", "", "/x")
        self.assertEqual(r["usuario_id"], 5)
        self.assertFalse(r["lida"])

    @patch("core.notificacoes.get_db")
    def test_marcar_lida_idempotente(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetchrow = AsyncMock(return_value={"id": 1, "usuario_id": 5, "lida": True})
        mock_get_db.return_value = fake_db
        r1 = notif.marcar_lida(1, 5)
        r2 = notif.marcar_lida(1, 5)
        self.assertTrue(r1["lida"])
        self.assertTrue(r2["lida"])

    @patch("core.notificacoes.get_db")
    def test_marcar_lida_de_outro_usuario_nao_encontra(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetchrow = AsyncMock(return_value=None)
        mock_get_db.return_value = fake_db
        r = notif.marcar_lida(1, 999)
        self.assertIn("error", r)


if __name__ == "__main__":
    unittest.main(verbosity=2)
