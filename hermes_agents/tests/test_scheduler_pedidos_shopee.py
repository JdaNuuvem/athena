"""
Job de sync automatico de pedidos Shopee (core/scheduler.py::_sync_pedidos_shopee).

Contexto: o job chamava sincronizar_pedidos_shopee() sem loja_id, usando so' a
config legada de loja unica — nunca de fato iterava as lojas Shopee conectadas
(multiloja). Com 2+ lojas conectadas, so' a ultima autorizada seria
sincronizada de verdade a cada 5 minutos. Corrigido para iterar
listar_lojas_shopee() e sincronizar cada loja com token ativo.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock
import unittest

# Mock DB pool global (mesmo padrao de test_shopee_flow.py) para o import de
# core.lojas (disparado ao resolver o alvo do @patch) nao tentar uma conexao
# real ao Postgres de producao — core.lojas roda _ensure_shopee_cols() no
# import do modulo.
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

_db_table_patcher = patch("core.config._ensure_db_table", return_value=False)
_db_table_patcher.start()

from core.scheduler import _sync_pedidos_shopee


class TestSyncPedidosShopeeMultiloja(unittest.TestCase):

    @patch("core.vendas.sincronizar_pedidos_shopee")
    @patch("core.lojas.listar_lojas_shopee")
    def test_sincroniza_cada_loja_com_token(self, mock_listar, mock_sync):
        mock_listar.return_value = [
            {"id": 7, "nome": "Shopee A", "tem_token": True},
            {"id": 9, "nome": "Shopee B", "tem_token": True},
        ]
        mock_sync.return_value = {"sync": 1}
        _sync_pedidos_shopee()
        self.assertEqual(mock_sync.call_count, 2)
        chamados_loja_id = [c.kwargs.get("loja_id") for c in mock_sync.call_args_list]
        self.assertEqual(sorted(chamados_loja_id), [7, 9])

    @patch("core.vendas.sincronizar_pedidos_shopee")
    @patch("core.lojas.listar_lojas_shopee")
    def test_pula_loja_sem_token(self, mock_listar, mock_sync):
        mock_listar.return_value = [
            {"id": 7, "nome": "Shopee A", "tem_token": True},
            {"id": 9, "nome": "Shopee Desconectada", "tem_token": False},
        ]
        mock_sync.return_value = {"sync": 0}
        _sync_pedidos_shopee()
        mock_sync.assert_called_once_with(loja_id=7)

    @patch("core.vendas.sincronizar_pedidos_shopee")
    @patch("core.lojas.listar_lojas_shopee")
    def test_erro_em_uma_loja_nao_impede_as_outras(self, mock_listar, mock_sync):
        mock_listar.return_value = [
            {"id": 7, "nome": "Shopee A", "tem_token": True},
            {"id": 9, "nome": "Shopee B", "tem_token": True},
        ]
        mock_sync.side_effect = [Exception("token expirado"), {"sync": 2}]
        try:
            _sync_pedidos_shopee()
        except Exception as e:
            self.fail(f"_sync_pedidos_shopee nao deveria propagar excecao: {e}")
        self.assertEqual(mock_sync.call_count, 2)

    @patch("core.vendas.sincronizar_pedidos_shopee")
    @patch("core.lojas.listar_lojas_shopee", return_value=[])
    def test_sem_lojas_conectadas_nao_chama_sync(self, mock_listar, mock_sync):
        _sync_pedidos_shopee()
        mock_sync.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
