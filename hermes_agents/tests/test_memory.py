"""Testes — core/memory.py (AG-09 Extended, memoria conversacional do Hermes)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock


async def _mp(*a, **kw):
    # get_db() devolve o pool asyncpg direto (core/__init__.py) — o codigo
    # chama db.fetchrow()/db.fetch()/etc direto no pool, sem acquire().
    m = AsyncMock()
    m.fetch = AsyncMock(return_value=[])
    m.fetchrow = AsyncMock(return_value={"id": 42})
    m.fetchval = AsyncMock(return_value=0)
    m.execute = AsyncMock(return_value="OK")
    return m


patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import core.memory as memory


class TestStore(unittest.TestCase):
    def test_store_nao_lanca_typeerror_de_run_async(self):
        """store() chamava run_async(_go(), default=None), mas run_async() so
        aceita um parametro posicional (core/__init__.py) desde o commit
        69514dc, que corrigiu todas as outras chamadas de core/memory.py
        exceto esta — quebrava com 500 em toda mensagem do chat Hermes.

        Nao afirma o valor exato de retorno: o pool asyncpg e' cacheado por
        processo (core.get_db), entao rodar este arquivo junto de outros
        testes pode reutilizar um pool mockado por outro arquivo. O que
        importa pra esta regressao e' so' nao lancar TypeError."""
        try:
            memory.store(
                "produtos em alta", "resposta de teste", agent_id="ag_01",
                category="marketing", metadata={"user_id": "1", "nome": "Teste"})
        except TypeError as e:
            self.fail(f"store() lancou TypeError (regressao do commit 69514dc): {e}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
