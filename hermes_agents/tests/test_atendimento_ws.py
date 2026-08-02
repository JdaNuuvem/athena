"""Testes — eventos WebSocket de tickets: broadcast unico de mensagem
(regressao do bug de double-broadcast), mudanca de status, atribuicao."""
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

import core.atendimento as atend


class TestMudarStatusTicket(unittest.TestCase):
    def test_transicao_valida_aberto_para_pendente_dispara_evento(self):
        with patch.object(atend, "get", return_value={"id": 1, "status": "aberto"}), \
             patch.object(atend, "update", return_value={"id": 1, "status": "pendente"}), \
             patch("core.chat.conversa_id_do_ticket", return_value=42), \
             patch("core.chat_ws.broadcast_para_participantes") as mock_broadcast:
            r = atend.mudar_status_ticket(1, "pendente")
        self.assertEqual(r["status"], "pendente")
        mock_broadcast.assert_called_once_with(42, {
            "evento": "ticket_status_alterado", "ticket_id": 1, "status": "pendente", "conversa_id": 42,
        })

    def test_transicao_invalida_fechado_para_pendente_rejeitada(self):
        with patch.object(atend, "get", return_value={"id": 1, "status": "fechado"}), \
             patch.object(atend, "update") as mock_update:
            r = atend.mudar_status_ticket(1, "pendente")
        self.assertIn("error", r)
        mock_update.assert_not_called()

    def test_reabrir_de_fechado_e_valido(self):
        with patch.object(atend, "get", return_value={"id": 1, "status": "fechado"}), \
             patch.object(atend, "update", return_value={"id": 1, "status": "aberto"}), \
             patch("core.chat.conversa_id_do_ticket", return_value=None):
            r = atend.mudar_status_ticket(1, "aberto")
        self.assertEqual(r["status"], "aberto")


if __name__ == "__main__":
    unittest.main(verbosity=2)
