import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import unittest
from unittest.mock import patch, AsyncMock

# core/memory.py (e outros modulos core/*) chamam _ensure_table()/_ensure_tables() no
# import do modulo, o que abre uma conexao real via asyncpg.create_pool — sem essa conexao
# de fachada, o import de core.compras falha ao tentar resolver um host de banco real.
# Mesmo padrao usado em tests/test_compras_seguranca.py.
async def _fake_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

_patcher = patch("asyncpg.create_pool", side_effect=_fake_pool)
_patcher.start()

from core import compras as core_compras


class TestSincronizarPedidosCompraBling(unittest.TestCase):
    def test_resolve_fornecedor_existente_por_documento_e_faz_upsert(self):
        fake_db = AsyncMock()
        # 1a chamada: checa se coluna bling_id existe em compras_pedidos -> None (nao existe, sera criada)
        # 2a chamada: busca fornecedor por documento -> encontra id 7
        # 3a chamada: busca pedido existente por bling_id -> None (novo)
        # 4a chamada: refetch do id apos INSERT INTO compras_pedidos -> 42
        fake_db.fetchval.side_effect = [None, 7, None, 42]
        fake_db.fetchrow.return_value = None
        # get_access_token/get_auth_url/listar_pedidos_compra/get_pedido_compra_detalhe sao
        # importados localmente dentro da funcao (from bling_erp import ...), entao o patch
        # tem que mirar no modulo de origem bling_erp, nao em core.compras. get_db, por sua
        # vez, e' importado no topo de core/compras.py, entao patch("core.compras.get_db")
        # funciona normalmente.
        with patch("bling_erp.get_access_token", return_value="tok"), \
             patch("core.compras.get_db", new=AsyncMock(return_value=fake_db)), \
             patch("bling_erp.get_pedido_compra_detalhe", return_value={"data": {
                 "id": 555, "numero": "PC-001", "total": 1200.50,
                 "situacao": {"valor": 6, "nome": "Em andamento"},
                 "data": "2026-08-20", "dataPrevista": "2026-08-27",
                 "fornecedor": {"nome": "Fornecedor XYZ", "numeroDocumento": "12.345.678/0001-99"},
                 "itens": [{"codigo": "SKU-1", "descricao": "Produto 1", "quantidade": 10, "valor": 100.0}],
             }}), \
             patch("bling_erp.listar_pedidos_compra", return_value={"data": [{"id": 555}]}):
            resultado = core_compras.sincronizar_pedidos_compra_bling()
        self.assertEqual(resultado["sync"], 1)
        sqls_executados = [c.args[0] for c in fake_db.execute.call_args_list]
        self.assertTrue(any("ALTER TABLE compras_pedidos ADD COLUMN" in s for s in sqls_executados))
        self.assertTrue(any("INSERT INTO compras_pedidos" in s for s in sqls_executados))
        self.assertTrue(any("INSERT INTO compras_itens" in s for s in sqls_executados))


if __name__ == "__main__":
    unittest.main()
