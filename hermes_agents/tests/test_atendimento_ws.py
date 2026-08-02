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


class TestAtribuirTicket(unittest.TestCase):
    @patch("core.atendimento.get_db")
    def test_atribui_dispara_evento_e_notificacao(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetchrow = AsyncMock(return_value={"id": 5, "nome": "Joao"})
        mock_get_db.return_value = fake_db
        with patch.object(atend, "update", return_value={"id": 1, "numero": "#0001", "assunto": "Duvida"}), \
             patch("core.chat.conversa_id_do_ticket", return_value=42), \
             patch("core.chat_ws.broadcast_para_participantes") as mock_broadcast, \
             patch("core.chat_ws.enviar_para_usuario") as mock_enviar, \
             patch("core.notificacoes.criar_notificacao", return_value={"id": 99, "usuario_id": 5}) as mock_notif:
            r = atend.atribuir_ticket(1, 5)
        self.assertEqual(r["id"], 1)
        mock_broadcast.assert_called_once_with(42, {
            "evento": "ticket_atendente_alterado", "ticket_id": 1,
            "atendente_id": 5, "atendente_nome": "Joao", "conversa_id": 42,
        })
        mock_notif.assert_called_once_with(
            5, "ticket_atribuido", "Ticket #0001 atribuido a voce", "Duvida", "/atendimento/tickets/1")
        mock_enviar.assert_called_once_with(5, {"evento": "notificacao", "id": 99, "usuario_id": 5})

    @patch("core.atendimento.get_db")
    def test_atendente_inexistente_retorna_erro(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetchrow = AsyncMock(return_value=None)
        mock_get_db.return_value = fake_db
        with patch.object(atend, "update") as mock_update:
            r = atend.atribuir_ticket(1, 999)
        self.assertIn("error", r)
        mock_update.assert_not_called()


class TestAdicionarMensagemBroadcastUnico(unittest.TestCase):
    """Regressao: antes deste fix, adicionar_mensagem (core/atendimento.py) e
    chat_enviar_mensagem (routes/chat.py) juntos disparavam 2 frames
    nova_mensagem com shapes diferentes para a mesma mensagem de ticket."""

    def test_adicionar_mensagem_emite_exatamente_um_broadcast_normalizado(self):
        with patch.object(atend, "create", return_value={
                "id": 10, "ticket_id": 1, "conteudo": "oi", "remetente": "Ana",
                "tipo": "texto", "anexo_url": None, "enviado_em": "2026-08-01T10:00:00"}), \
             patch("core.chat.conversa_id_do_ticket", return_value=42), \
             patch("core.chat_ws.broadcast_para_participantes") as mock_broadcast:
            atend.adicionar_mensagem(1, "Ana", "oi")
        mock_broadcast.assert_called_once()
        _, evento = mock_broadcast.call_args[0]
        self.assertEqual(evento["evento"], "nova_mensagem")
        self.assertEqual(evento["mensagem"]["conversa_id"], 42)
        self.assertEqual(evento["mensagem"]["texto"], "oi")
        self.assertEqual(evento["mensagem"]["remetente_nome"], "Ana")
        self.assertIsNone(evento["mensagem"]["remetente_id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
