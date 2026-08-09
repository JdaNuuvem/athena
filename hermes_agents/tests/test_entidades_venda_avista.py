"""Testes — core.entidades.ao_concluir_venda_avista / backfill_fluxo_caixa_vendas
(Fluxo de Caixa real gerado a partir de vendas Shopee/i9Logic concluidas,
substituindo o seed mockado do Financeiro)."""
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

patch("asyncpg.create_pool", side_effect=_mp).start()

import core.entidades as entidades


class _FakeDBFluxoCaixa:
    """Simula fin_fluxo_caixa com estado real (set de pedido_id ja lancados),
    pra testar idempotencia de verdade (INSERT ... WHERE NOT EXISTS) em vez
    de so' mockar um retorno fixo."""
    def __init__(self, pedido: dict | None):
        self.pedido = pedido
        self.lancados = set()
        self.inserts = 0

    async def fetchrow(self, query, *args):
        if "SELECT * FROM vendas_pedidos" in query:
            return self.pedido
        if "INSERT INTO fin_fluxo_caixa" in query:
            pedido_id = args[-1]
            if pedido_id in self.lancados:
                return None
            self.lancados.add(pedido_id)
            self.inserts += 1
            return {"id": self.inserts}
        return None


class TestAoConcluirVendaAvista(unittest.TestCase):
    def test_pedido_nao_encontrado_retorna_erro(self):
        db = _FakeDBFluxoCaixa(pedido=None)
        with patch("core.entidades.get_db", return_value=db):
            resultado = entidades.ao_concluir_venda_avista(999)
        self.assertIn("error", resultado)

    def test_pedido_nao_concluido_e_ignorado_sem_lancar(self):
        pedido = {"id": 1, "status": "enviado", "total": 100, "data": "2026-08-01",
                   "marketplace": "shopee", "origem": "shopee", "numero": None, "bling_numero": None}
        db = _FakeDBFluxoCaixa(pedido=pedido)
        with patch("core.entidades.get_db", return_value=db):
            resultado = entidades.ao_concluir_venda_avista(1)
        self.assertIn("skip", resultado)
        self.assertEqual(db.inserts, 0)

    def test_pedido_concluido_lanca_entrada_no_fluxo_de_caixa(self):
        pedido = {"id": 1, "status": "concluido", "total": 150.0, "data": "2026-08-01",
                   "marketplace": "shopee", "origem": "shopee", "numero": "SN1", "bling_numero": None}
        db = _FakeDBFluxoCaixa(pedido=pedido)
        with patch("core.entidades.get_db", return_value=db):
            resultado = entidades.ao_concluir_venda_avista(1)
        self.assertTrue(resultado["ok"])
        self.assertTrue(resultado["lancado"])
        self.assertEqual(db.inserts, 1)

    def test_chamar_duas_vezes_e_idempotente_nao_duplica(self):
        """Sync roda a cada 5-10min e reprocessa pedido ja concluido — sem
        idempotencia (pedido_id + WHERE NOT EXISTS), duplicaria lancamento a
        cada rodada."""
        pedido = {"id": 1, "status": "concluido", "total": 150.0, "data": "2026-08-01",
                   "marketplace": "shopee", "origem": "shopee", "numero": "SN1", "bling_numero": None}
        db = _FakeDBFluxoCaixa(pedido=pedido)
        with patch("core.entidades.get_db", return_value=db):
            r1 = entidades.ao_concluir_venda_avista(1)
            r2 = entidades.ao_concluir_venda_avista(1)
        self.assertTrue(r1["lancado"])
        self.assertFalse(r2["lancado"])
        self.assertEqual(db.inserts, 1)


class TestBackfillFluxoCaixaVendas(unittest.TestCase):
    def test_processa_todos_pedidos_concluidos_shopee_e_i9logic(self):
        pedidos_concluidos = [{"id": 1}, {"id": 2}]
        chamados = []
        async def _fetch(query, *args):
            return pedidos_concluidos
        db = AsyncMock(fetch=_fetch)
        def _fake_hook(pedido_id):
            chamados.append(pedido_id)
            return {"ok": True, "lancado": True}
        with patch("core.entidades.get_db", return_value=db), \
             patch("core.entidades.ao_concluir_venda_avista", side_effect=_fake_hook):
            resultado = entidades.backfill_fluxo_caixa_vendas()
        self.assertEqual(chamados, [1, 2])
        self.assertEqual(resultado["total_pedidos"], 2)
        self.assertEqual(resultado["lancados"], 2)

    def test_erro_em_um_pedido_nao_impede_os_demais(self):
        pedidos_concluidos = [{"id": 1}, {"id": 2}]
        async def _fetch(query, *args):
            return pedidos_concluidos
        db = AsyncMock(fetch=_fetch)
        def _fake_hook(pedido_id):
            if pedido_id == 1:
                return {"error": "falha de banco"}
            return {"ok": True, "lancado": True}
        with patch("core.entidades.get_db", return_value=db), \
             patch("core.entidades.ao_concluir_venda_avista", side_effect=_fake_hook):
            resultado = entidades.backfill_fluxo_caixa_vendas()
        self.assertEqual(resultado["lancados"], 1)
        self.assertEqual(len(resultado["erros"]), 1)
        self.assertEqual(resultado["erros"][0]["pedido_id"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
