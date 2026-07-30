"""Job de sync automatico de vendas PDV i9Logic (core/scheduler.py::_sync_pedidos_i9logic)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock
import unittest

_fake_conn = AsyncMock()
_fake_conn.fetch.return_value = []
_fake_conn.fetchrow.return_value = None
_fake_conn.fetchval.return_value = 0
_fake_conn.execute.return_value = "OK"

async def _mock_create_pool(*a, **kw):
    pool = AsyncMock()
    pool.acquire.return_value = _fake_conn
    return pool

_pool_patcher = patch("asyncpg.create_pool", side_effect=_mock_create_pool)
_pool_patcher.start()

from core.scheduler import _sync_pedidos_i9logic


class TestSyncPedidosI9Logic(unittest.TestCase):
    @patch("core.i9logic_vendas.sincronizar_pedidos_i9logic")
    def test_chama_sincronizacao(self, mock_sync):
        mock_sync.return_value = {"ok": True, "sincronizados": 3}
        _sync_pedidos_i9logic()
        mock_sync.assert_called_once_with()

    @patch("core.i9logic_vendas.sincronizar_pedidos_i9logic")
    def test_erro_nao_propaga(self, mock_sync):
        mock_sync.side_effect = Exception("API fora do ar")
        try:
            _sync_pedidos_i9logic()
        except Exception as e:
            self.fail(f"_sync_pedidos_i9logic nao deveria propagar excecao: {e}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
