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


if __name__ == "__main__":
    unittest.main(verbosity=2)
