"""
GET /api/shopee/dashboard (routes/shopee.py::shopee_dashboard_consolidado) —
painel consolidado Shopee em /integracoes/shopee/dashboard.

Contexto: TODA a rota lia da tabela orfa `vendas` (marketplace='shopee'),
alimentada so' por POST /api/shopee/sync-orders — rota que nao e' chamada
por nenhuma funcao do frontend nem pelo scheduler (mesma causa raiz ja'
corrigida em kpi_overview/dashboard principal, 2026-08-09). Corrigido pra
ler de vendas_pedidos/vendas_itens (marketplace='shopee'), a mesma fonte
real que o job "shopee-pedidos" do scheduler mantem atualizada.
"""
import sys, os, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, AsyncMock

async def _mock_create_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(
        __aenter__=AsyncMock(return_value=AsyncMock(
            fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
            fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"),
        )), __aexit__=AsyncMock(return_value=None))
    return m

_pool_patcher = patch("asyncpg.create_pool", side_effect=_mock_create_pool)
_pool_patcher.start()

try:
    _psycopg_patcher = patch("psycopg2.connect", autospec=True)
    _psycopg_patcher.start()
except Exception:
    pass  # ja' patcheado (autospec) por outro arquivo de teste importado antes

os.environ.setdefault("ATHENA_TOKEN", "test-master-token-32-bytes-long!!")

import athena_bridge
import core.rbac as rbac

app = athena_bridge.app
USER_TOKEN = rbac.gerar_token_sessao(1, "shopee-dash-test@athena.local", "admin")


class _FakeCursor:
    """execute() so' registra (sql, params). fetchone()/fetchall() chamam
    um responder(sql, params) fornecido pelo teste, que decide o retorno
    pelo TEXTO da query — evita depender da ordem exata das ~15 chamadas
    sequenciais desta rota (fragil e dificil de manter em ordem)."""

    def __init__(self, responder_one=None, responder_all=None):
        self.executed = []
        self._responder_one = responder_one or (lambda sql, params: {})
        self._responder_all = responder_all or (lambda sql, params: [])

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        sql, params = self.executed[-1]
        return self._responder_one(sql, params)

    def fetchall(self):
        sql, params = self.executed[-1]
        return self._responder_all(sql, params)

    def close(self):
        pass


class _FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self, cursor_factory=None):
        return self._cursor

    def close(self):
        pass


_UMA_LOJA = [{"id": 7, "nome": "Loja Shopee A", "shopee_shop_id": "SHOP7", "tem_token": True, "shopee_token_expira_em": None}]


class TestShopeeDashboardFonteDeVendas(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.headers = {"Authorization": f"Bearer {USER_TOKEN}"}

    def _rodar(self, responder_one=None, responder_all=None, dias=None, loja_id=None):
        cursor = _FakeCursor(responder_one, responder_all)
        params_qs = []
        if dias:
            params_qs.append(f"dias={dias}")
        if loja_id:
            params_qs.append(f"loja_id={loja_id}")
        qs = f"?{'&'.join(params_qs)}" if params_qs else ""
        with patch("routes.shopee._db_sync", return_value=_FakeConn(cursor)), \
             patch("core.lojas.listar_lojas_shopee", return_value=_UMA_LOJA):
            r = self.client.get(f"/api/shopee/dashboard{qs}", headers=self.headers)
        return r, cursor

    def test_nenhuma_query_le_a_tabela_orfa_vendas(self):
        r, cursor = self._rodar()
        self.assertEqual(r.status_code, 200)
        import re
        padrao_tabela_orfa = re.compile(r"\bFROM\s+vendas\b(?!_)", re.IGNORECASE)
        ofensoras = [sql for sql, _ in cursor.executed if padrao_tabela_orfa.search(sql)]
        self.assertEqual(ofensoras, [], f"queries ainda lendo a tabela orfa 'vendas': {ofensoras}")
        self.assertTrue(
            any("vendas_pedidos" in sql for sql, _ in cursor.executed),
            "esperava pelo menos uma query em vendas_pedidos")

    def test_receita_da_loja_nao_duplica_por_fan_out_de_item(self):
        """Se receita (nivel pedido) e unidades (nivel item) forem calculadas
        na MESMA query com JOIN vendas_pedidos+vendas_itens, um pedido com 3
        itens faz SUM(total) contar a receita do pedido 3x (fan-out). Testa
        que a receita retornada bate com o total real do pedido, nao um
        multiplo dele."""
        def responder_one(sql, params):
            if "SUM(vp.quantidade)" in sql or ("vendas_itens" in sql and "SUM" in sql and "quantidade" in sql.lower()):
                return {"unidades": 5, "skus_vendidos": 2}
            if "vendas_pedidos" in sql and "receita" in sql.lower() and "COUNT(*)" not in sql:
                return {"receita": 300.0}
            return {"receita": 0, "unidades": 0, "skus_vendidos": 0, "pedidos": 0, "custo": 0}
        r, cursor = self._rodar(responder_one=responder_one)
        data = r.get_json()
        self.assertEqual(data["lojas"][0]["receita"], 300.0)

    def test_serie_diaria_le_vendas_pedidos(self):
        def responder_all(sql, params):
            if "GROUP BY data" in sql and "vendas_pedidos" in sql:
                from datetime import date
                return [
                    {"dia": date(2026, 8, 1), "receita": 100.0, "pedidos": 2},
                    {"dia": date(2026, 8, 2), "receita": 50.0, "pedidos": 1},
                ]
            return []
        r, cursor = self._rodar(responder_all=responder_all)
        data = r.get_json()
        self.assertEqual(len(data["serie_diaria"]), 2)
        self.assertEqual(data["serie_diaria"][0]["dia"], "2026-08-01")
        self.assertEqual(data["serie_diaria"][0]["receita"], 100.0)

    def test_top_produtos_hoje_le_vendas_itens(self):
        def responder_all(sql, params):
            if "vendas_itens" in sql and "CURRENT_DATE" in sql and "LIMIT 8" in sql:
                return [{"sku": "SKU-A", "descricao": "Produto A", "quantidade": 10, "receita": 500.0}]
            return []
        r, cursor = self._rodar(responder_all=responder_all)
        data = r.get_json()
        self.assertEqual(len(data["top_produtos_hoje"]), 1)
        self.assertEqual(data["top_produtos_hoje"][0]["sku"], "SKU-A")

    def test_dias_query_param_aplicado_na_serie_diaria(self):
        r, cursor = self._rodar(dias=7)
        serie_sql = [sql for sql, params in cursor.executed if "GROUP BY data" in sql and "vendas_pedidos" in sql]
        self.assertEqual(len(serie_sql), 1)
        sql, params = next((s, p) for s, p in cursor.executed if s in serie_sql)
        self.assertIn(7, params)

    def test_loja_id_filtra_serie_diaria_e_top_produtos(self):
        """Quando loja_id e' passado na query string, as queries agregadas
        (que hoje somam TODAS as lojas Shopee) precisam ganhar o filtro de
        loja e o param correspondente — pra pagina /integracoes/shopee/dashboard
        mostrar so' a loja selecionada, nao um agregado."""
        r, cursor = self._rodar(loja_id=7)
        self.assertEqual(r.status_code, 200)

        serie_sql, serie_params = next(
            (s, p) for s, p in cursor.executed if "GROUP BY data" in s and "vendas_pedidos" in s)
        self.assertIn("AND loja_id = %s", serie_sql)
        self.assertIn(7, serie_params)

        top_sql, top_params = next(
            (s, p) for s, p in cursor.executed if "vendas_itens" in s and "CURRENT_DATE" in s and "LIMIT 8" in s)
        self.assertIn("AND vp.loja_id = %s", top_sql)
        self.assertIn(7, top_params)

    def test_loja_id_filtra_produtos_parados_anuncios_e_subquery(self):
        """produtos_parados usa `anuncios` (que so' tem shop_id, nao loja_id)
        + uma subquery correlacionada em vendas_pedidos (que tem loja_id de
        verdade) — o filtro de loja precisa entrar nos dois lugares."""
        r, cursor = self._rodar(loja_id=7)
        self.assertEqual(r.status_code, 200)

        parados_sql, parados_params = next(
            (s, p) for s, p in cursor.executed if "FROM anuncios a" in s and "NOT EXISTS" in s)
        self.assertIn("AND a.shop_id = ANY(%s)", parados_sql)
        self.assertIn("AND vp.loja_id = %s", parados_sql)
        self.assertIn(["SHOP7"], parados_params)
        self.assertIn(7, parados_params)

    def test_sem_loja_id_nao_filtra_nenhuma_query_agregada(self):
        """Sem loja_id na query string, o comportamento deve ficar identico
        ao de antes: nenhuma query agregada ganha filtro de loja extra."""
        r, cursor = self._rodar()
        self.assertEqual(r.status_code, 200)
        serie_sql, _ = next(
            (s, p) for s, p in cursor.executed if "GROUP BY data" in s and "vendas_pedidos" in s)
        self.assertNotIn("AND loja_id = %s", serie_sql)
        parados_sql, _ = next(
            (s, p) for s, p in cursor.executed if "FROM anuncios a" in s and "NOT EXISTS" in s)
        self.assertNotIn("a.shop_id = ANY(%s)", parados_sql)

    def test_erro_de_query_nao_quebra_a_rota(self):
        def responder_one(sql, params):
            raise Exception("falha simulada de banco")
        r, cursor = self._rodar(responder_one=responder_one)
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("error", data)
        self.assertEqual(data["lojas"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
