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


class TestRuptura(unittest.TestCase):
    def test_nenhum_sku_abaixo_do_minimo_retorna_vazio(self):
        async def fake_fetch(query, *params):
            return []
        with patch("core.estoque_analise.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.ruptura()
        self.assertEqual(resultado, [])

    def test_sku_sem_abastecimento_registrado_nao_quebra_e_nao_inventa_numero(self):
        async def fake_fetch(query, *params):
            q = " ".join(query.split())
            if "estoque_movimentacoes" in q:
                return []  # nunca reabastecido
            return [{"sku": "XYZ-9", "produto": "Produto XYZ", "saldo_atual": 2, "estoque_minimo": 10}]
        with patch("core.estoque_analise.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.ruptura()
        self.assertEqual(resultado, [{
            "sku": "XYZ-9", "produto": "Produto XYZ",
            "dias_ruptura": 0, "vendas_perdidas_estimadas": 0,
            "impacto_receita": 0.0, "ultimo_abastecimento": None,
        }])


class TestCobertura(unittest.TestCase):
    def test_sem_minimo_maximo_e_sem_demanda_cai_em_normal(self):
        async def fake_fetch(query, *params):
            q = " ".join(query.split())
            if "FROM estoque_lojas" in q:
                return [{"sku": "QQQ-1", "produto": "Produto QQQ", "estoque_atual": 50,
                          "estoque_minimo": 0, "estoque_maximo": 0}]
            if "FROM vendas_itens" in q:
                return []
            return []
        with patch("core.estoque_analise.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.cobertura()
        self.assertEqual(resultado, [{
            "sku": "QQQ-1", "produto": "Produto QQQ",
            "estoque_atual": 50, "demanda_diaria_media": 0.0, "cobertura_dias": 0,
            "estoque_minimo": 0, "estoque_maximo": 0, "status": "normal",
        }])

    def test_saldo_zero_e_critico(self):
        async def fake_fetch(query, *params):
            q = " ".join(query.split())
            if "FROM estoque_lojas" in q:
                return [{"sku": "RRR-1", "produto": "Produto RRR", "estoque_atual": 0,
                          "estoque_minimo": 10, "estoque_maximo": 100}]
            return []
        with patch("core.estoque_analise.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.cobertura()
        self.assertEqual(resultado[0]["status"], "critico")