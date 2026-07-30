"""Testes de integracao — sync de vendas PDV i9Logic -> Athena."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock, MagicMock

async def _mp(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import core.i9logic_vendas as vendas_i9logic


class TestBuscarDadosPedido(unittest.TestCase):
    def test_filial_sem_depara_retorna_none_sem_buscar_itens_pagamentos(self):
        chamadas = []
        def _fake_paginar(endpoint, params, on_pagina=None):
            chamadas.append(endpoint)
            if endpoint == "pedidos":
                return [{"id": 322643, "filial_venda": 999, "valor_total": 25.97,
                         "cancelado": "0", "data": "2026-07-29"}]
            return []
        with patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar), \
             patch("core.i9logic_vendas.buscar_codigo_athena", return_value=None):
            resultado = vendas_i9logic._buscar_dados_pedido(322643)
        self.assertIsNone(resultado)
        self.assertEqual(chamadas, ["pedidos"])

    def test_filial_mapeada_monta_pedido_completo(self):
        def _fake_paginar(endpoint, params, on_pagina=None):
            if endpoint == "pedidos":
                return [{"id": 322643, "filial_venda": 1, "valor_total": 25.97,
                         "cancelado": "0", "data": "2026-07-29"}]
            if endpoint == "pedidos_produtos":
                return [{"codproduto": "012810", "qtd": 1, "valorvenda": 1.99, "descricao": "Pinca"}]
            if endpoint == "pedidos_pagamentos":
                return [{"formadepagamento": 335, "valor": 25.97, "codautorizacao": ""}]
            return []
        with patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar), \
             patch("core.i9logic_vendas.buscar_codigo_athena", return_value="Loja Matriz"):
            resultado = vendas_i9logic._buscar_dados_pedido(322643)
        self.assertEqual(resultado["loja_athena"], "Loja Matriz")
        self.assertEqual(resultado["pedido"]["id"], 322643)
        self.assertEqual(len(resultado["itens"]), 1)
        self.assertEqual(len(resultado["pagamentos"]), 1)

    def test_pedido_nao_encontrado_levanta_erro(self):
        def _fake_paginar(endpoint, params, on_pagina=None):
            return []
        with patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar):
            with self.assertRaises(Exception):
                vendas_i9logic._buscar_dados_pedido(999999)


if __name__ == "__main__":
    unittest.main(verbosity=2)
