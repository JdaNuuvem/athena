"""Testes de integracao — permissao e isolamento do chat interno."""
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

import core.chat as chat


class TestChatConversas(unittest.TestCase):
    def test_participantes_ids_conversa_inexistente_retorna_vazio(self):
        with patch("core.chat._obter_conversa", return_value=None):
            self.assertEqual(chat.participantes_ids(999), [])

    def test_usuario_e_participante_false_quando_fora_da_lista(self):
        with patch("core.chat.participantes_ids", return_value=[1, 2, 3]):
            self.assertFalse(chat.usuario_e_participante(5, 42))

    def test_usuario_e_participante_true_quando_na_lista(self):
        with patch("core.chat.participantes_ids", return_value=[1, 2, 3]):
            self.assertTrue(chat.usuario_e_participante(5, 2))


class TestChatMensagens(unittest.TestCase):
    def test_listar_mensagens_erro_de_db_retorna_lista_vazia(self):
        with patch("core.chat.get_db", side_effect=RuntimeError("sem conexao")):
            self.assertEqual(chat.listar_mensagens(1), [])

    def test_editar_mensagem_sem_ser_autor_retorna_error(self):
        async def _fetchrow(*a, **kw): return None
        with patch("core.chat.get_db") as mock_get_db:
            mock_db = AsyncMock(fetchrow=_fetchrow)
            mock_get_db.return_value = mock_db
            resultado = chat.editar_mensagem(1, 999, "novo texto")
        self.assertIn("error", resultado)

    def test_listar_conversas_usuario_ordena_por_atividade_recente(self):
        with patch("core.chat.get_db") as mock_get_db, \
             patch("core.chat._canais_departamento_permitidos", return_value=[]), \
             patch("core.chat._conversas_ticket_permitidas", return_value=[]):
            async def _fetch(*a, **kw):
                return [
                    {"id": 1, "tipo": "dm", "created_at": "2026-01-01", "ultima_atividade": "2026-01-01"},
                    {"id": 2, "tipo": "grupo", "created_at": "2026-01-01", "ultima_atividade": "2026-06-01"},
                ]
            mock_db = AsyncMock(fetch=_fetch)
            mock_get_db.return_value = mock_db
            resultado = chat.listar_conversas_usuario(7)
        self.assertEqual(resultado[0]["id"], 2)


class TestChatPonteTicket(unittest.TestCase):
    def test_criar_conversa_ticket_reaproveita_existente(self):
        with patch("core.chat.run_async", return_value=None), \
             patch("core.chat.conversa_id_do_ticket", return_value=42), \
             patch("core.chat._obter_conversa", return_value={"id": 42, "tipo": "ticket", "ticket_ref_id": 7}) as mock_obter:
            resultado = chat.criar_conversa_ticket(7)
        self.assertEqual(resultado["id"], 42)
        mock_obter.assert_called_once_with(42)


if __name__ == "__main__":
    unittest.main(verbosity=2)
