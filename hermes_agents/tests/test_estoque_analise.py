"""Testes de core/estoque_analise.py — giro/ruptura/cobertura sobre dado
real (asyncpg mockado, sem banco de verdade)."""
import sys, os, unittest
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

# Patch asyncpg before importing hermes_agents
async def _mock_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]),
        fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0),
        execute=AsyncMock(return_value="OK")
    )), __aexit__=AsyncMock(return_value=None))
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mock_pool)
patcher.start()

import core.estoque_analise as analise


class TestGiro(unittest.TestCase):
    def test_sem_venda_no_periodo_giro_zero_sem_dividir_por_zero(self):
        async def fake_fetch(query, *params):
            q = " ".join(query.split())
            if "FROM estoque_lojas" in q:
                return [{"sku": "ABC-1", "produto": "Produto ABC", "saldo_atual": 0}]
            if "FROM vendas_itens" in q:
                return []
            return []
        with patch("core.estoque_analise.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.giro()
        self.assertEqual(resultado, [{
            "sku": "ABC-1", "produto": "Produto ABC",
            "saidas_30d": 0, "estoque_medio": 0, "giro": 0.0, "tendencia": "stable",
        }])

    def test_tendencia_up_quando_periodo_atual_vende_mais(self):
        async def fake_fetch(query, *params):
            q = " ".join(query.split())
            if "FROM estoque_lojas" in q:
                return [{"sku": "ABC-1", "produto": "Produto ABC", "saldo_atual": 50}]
            if "FROM vendas_itens" in q:
                return [{"sku": "ABC-1", "saidas_periodo": 40, "saidas_periodo_anterior": 10}]
            return []
        with patch("core.estoque_analise.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.giro()
        self.assertEqual(resultado[0]["tendencia"], "up")
        self.assertEqual(resultado[0]["giro"], 0.8)