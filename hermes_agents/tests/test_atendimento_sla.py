"""Testes — SLA no Atendimento + Webhook Dispatcher (Fase 2)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

async def _mock_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(
        __aenter__=AsyncMock(return_value=AsyncMock(
            fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
            fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"),
        )),
        __aexit__=AsyncMock(return_value=None),
    )
    return m
patcher = patch("asyncpg.create_pool", side_effect=_mock_pool)
patcher.start()
_fake_db = AsyncMock()
_fake_db.fetchval = AsyncMock(return_value=0)
_fake_db.fetchrow = AsyncMock(return_value=None)
_fake_db.fetch = AsyncMock(return_value=[])
_fake_db.execute = AsyncMock(return_value="OK")

import core.atendimento as atend

class TestSLAEnforcement(unittest.TestCase):
    """Fase 2 — SLA aplicado ao criar ticket."""

    @patch("core.atendimento.get_db", return_value=_fake_db)
    def test_criar_ticket_com_sla_urgente(self, mock_db):
        """Ticket urgente deve ter sla_vencimento = agora + 1h."""
        _fake_db.fetchrow.return_value = {"tempo_resposta_min": 60, "tempo_resolucao_h": 2}
        # mock _create to return a fake dict
        with patch.object(atend, "create", return_value={"id": 1, "status": "aberto"}) as mock_create:
            r = atend.criar_ticket("Cliente", "Assunto", canal="chat", prioridade="urgente")
        self.assertEqual(r["id"], 1)
        # verifica que create foi chamado com sla_vencimento e tempo_resposta_min
        args = mock_create.call_args[0][1]
        self.assertIsNotNone(args.get("sla_vencimento"))
        self.assertEqual(args["tempo_resposta_min"], 60)

    @patch("core.atendimento.get_db", return_value=_fake_db)
    def test_criar_ticket_sem_sla_configurado(self, mock_db):
        """Se SLA nao existe na tabela, cria sem sla_vencimento."""
        _fake_db.fetchrow.return_value = None
        with patch.object(atend, "create", return_value={"id": 2, "status": "aberto"}) as mock_create:
            r = atend.criar_ticket("Cliente", "Assunto", canal="email", prioridade="normal")
        self.assertEqual(r["id"], 2)
        args = mock_create.call_args[0][1]
        self.assertIsNone(args.get("sla_vencimento"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
