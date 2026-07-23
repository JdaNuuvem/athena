"""Testes — DRE por Loja (Fase 2)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

async def _mock_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(
        __aenter__=AsyncMock(return_value=AsyncMock(
            fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
            fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"),
        )), __aexit__=AsyncMock(return_value=None),
    )
    return m
patcher = patch("asyncpg.create_pool", side_effect=_mock_pool)
patcher.start()

import core.relatorios as rel

class TestDREPorLoja(unittest.TestCase):
    """Fase 2 — DRE por loja."""

    def test_dre_sem_lojas(self):
        with patch("core.relatorios.run_async", return_value=[]):
            r = rel.dre_por_loja(dias=30)
        self.assertEqual(r, [])

    def test_dre_com_uma_loja(self):
        result = [{
            "loja_id": 1, "loja_nome": "Loja A",
            "receita": 5000.0, "qtd_vendas": 25,
            "comissao_pct": 14.0, "comissao_valor": 700.0,
            "frete": 200.0, "custos_producao": 800.0,
            "lucro": 3300.0, "margem_pct": 66.0, "periodo_dias": 30,
        }]
        with patch("core.relatorios.run_async", return_value=result):
            r = rel.dre_por_loja(dias=30)
        self.assertEqual(len(r), 1)
        l = r[0]
        self.assertEqual(l["loja_nome"], "Loja A")
        self.assertEqual(l["receita"], 5000.0)
        self.assertAlmostEqual(l["comissao_valor"], 700.0, delta=1)
        self.assertAlmostEqual(l["lucro"], 3300.0, delta=1)

    def test_dre_ordena_por_lucro(self):
        result = [
            {"loja_nome": "Loja B", "lucro": 5000.0, "receita": 10000.0},
            {"loja_nome": "Loja A", "lucro": 3000.0, "receita": 6000.0},
        ]
        with patch("core.relatorios.run_async", return_value=result):
            r = rel.dre_por_loja(dias=30)
        self.assertGreaterEqual(len(r), 2)

if __name__ == "__main__":
    unittest.main(verbosity=2)
