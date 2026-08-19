"""
GET /api/kpi/overview (athena_bridge.py) — cards "Ticket medio" e "Receita
(30d)" da dashboard.

Contexto: receita_total/total_pedidos vinham da tabela `vendas`, que so' e'
alimentada por POST /api/shopee/sync-orders — rota que nao e' chamada por
nenhuma funcao do frontend (web/src/lib/api.ts) nem pelo scheduler. Tabela
orfa desde que foi escrita: os dois cards sempre mostravam 0 (ou dado
congelado, se alguem um dia bateu na rota manualmente via curl/Postman).
Corrigido pra somar vendas_pedidos + pdv_vendas, mesma fonte real que todo
o resto da dashboard ja usa (core/relatorios.py::_union_vendas).
"""
import sys, os, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, AsyncMock, MagicMock


async def _mock_create_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(
        __aenter__=AsyncMock(return_value=AsyncMock(
            fetch=AsyncMock(return_value=[]),
            fetchrow=AsyncMock(return_value=None),
            fetchval=AsyncMock(return_value=0),
            execute=AsyncMock(return_value="OK"),
        )),
        __aexit__=AsyncMock(return_value=None),
    )
    return m


_pool_patcher = patch("asyncpg.create_pool", side_effect=_mock_create_pool)
_pool_patcher.start()

try:
    _psycopg_patcher = patch("psycopg2.connect", autospec=True)
    _psycopg_patcher.start()
except Exception:
    # psycopg2.connect ja' patcheado (autospec=True) por outro arquivo de
    # teste importado antes deste no mesmo processo — autospec em cima de
    # um alvo que ja' e' Mock levanta InvalidSpecError. Nao precisa
    # repatchear: cada teste aqui patcheia athena_bridge._db_sync direto.
    pass

os.environ.setdefault("ATHENA_TOKEN", "test-master-token-32-bytes-long!!")

import athena_bridge
import core.rbac as rbac

app = athena_bridge.app
USER_TOKEN = rbac.gerar_token_sessao(1, "kpi-test@athena.local", "admin")


class _FakeCursor:
    """Registra toda chamada execute() e devolve, em ordem, os valores de
    fetchone()/fetchall() configurados pelo teste — permite inspecionar
    exatamente qual SQL foi rodado por cada bloco de kpi_overview()."""

    def __init__(self, fetchone_values, fetchall_values=None):
        self.executed = []
        self._fetchone_values = list(fetchone_values)
        self._fetchall_values = list(fetchall_values or [])

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return self._fetchone_values.pop(0) if self._fetchone_values else {"v": 0}

    def fetchall(self):
        return self._fetchall_values.pop(0) if self._fetchall_values else []

    def close(self):
        pass


class _FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self, cursor_factory=None):
        return self._cursor

    def close(self):
        pass


class TestKpiOverviewFonteDeVendas(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.headers = {"Authorization": f"Bearer {USER_TOKEN}"}

    def _rodar_com_cursor(self, cursor):
        with patch("athena_bridge._db_sync", return_value=_FakeConn(cursor)):
            return self.client.get("/api/kpi/overview", headers=self.headers)

    def test_receita_e_pedidos_nao_consultam_a_tabela_vendas_orfa(self):
        cursor = _FakeCursor(
            fetchone_values=[
                {"v": 500.0},  # receita vendas_pedidos
                {"v": 300.0},  # receita pdv_vendas
                {"v": 5},      # pedidos vendas_pedidos
                {"v": 3},      # pedidos pdv_vendas
                {"v": 0},      # total_produtos (fichas_tecnicas)
                {"v": 0},      # total_anuncios
                {"v": 0},      # receita_shopee
                {"v": 0},      # receita_ml
            ],
            fetchall_values=[[]],  # top_skus
        )
        r = self._rodar_com_cursor(cursor)
        self.assertEqual(r.status_code, 200)

        sqls_receita_pedidos = [sql for sql, _ in cursor.executed[:4]]
        for sql in sqls_receita_pedidos:
            self.assertNotIn(
                " FROM vendas ", sql,
                f"consulta de receita/pedidos ainda le' a tabela orfa 'vendas': {sql!r}")
        self.assertTrue(
            any("vendas_pedidos" in sql for sql in sqls_receita_pedidos),
            "esperava pelo menos uma query em vendas_pedidos entre as 4 primeiras")
        self.assertTrue(
            any("pdv_vendas" in sql for sql in sqls_receita_pedidos),
            "esperava pelo menos uma query em pdv_vendas entre as 4 primeiras")

    def test_receita_total_soma_vendas_pedidos_e_pdv(self):
        cursor = _FakeCursor(
            fetchone_values=[
                {"v": 500.0}, {"v": 300.0},  # receita: 500 + 300
                {"v": 5}, {"v": 3},          # pedidos: 5 + 3
                {"v": 0}, {"v": 0}, {"v": 0}, {"v": 0},
            ],
            fetchall_values=[[]],
        )
        r = self._rodar_com_cursor(cursor)
        data = r.get_json()
        self.assertEqual(data["receita_total"], 800.0)
        self.assertEqual(data["total_pedidos"], 8)
        self.assertEqual(data["ticket_medio"], round(800.0 / 8, 2))

    def test_filtro_de_loja_aplicado_nas_duas_fontes(self):
        cursor = _FakeCursor(
            fetchone_values=[
                {"v": 100.0}, {"v": 0.0},
                {"v": 1}, {"v": 0},
                {"v": 0}, {"v": 0}, {"v": 0}, {"v": 0},
            ],
            fetchall_values=[[]],
        )
        with patch("athena_bridge._db_sync", return_value=_FakeConn(cursor)):
            r = self.client.get("/api/kpi/overview?loja_id=7", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        sql_vp, params_vp = cursor.executed[0]
        self.assertIn("loja_id", sql_vp)
        self.assertIn(7, params_vp)
        sql_pdv, params_pdv = cursor.executed[1]
        self.assertIn("pdv_caixas", sql_pdv)
        self.assertIn(7, params_pdv)


class TestKpiOverviewTopSkus(unittest.TestCase):
    """top_skus vinha de uma query direta na tabela orfa 'vendas' (nunca
    alimentada), com campos {sku,nome,qtd,receita,margem} — o frontend
    (dashboard/page.tsx) sempre leu a chave errada (`top_produtos`, que nao
    existe) E esperava campos {nome,valor,margem} (BarChart dataKey="valor").
    Corrigido pra reusar core.relatorios.ranking_produtos (ja' fonteado de
    vendas_pedidos+pdv_vendas) e mapear pro shape que o frontend consome."""

    def setUp(self):
        self.client = app.test_client()
        self.headers = {"Authorization": f"Bearer {USER_TOKEN}"}

    def _rodar(self):
        cursor = _FakeCursor(fetchone_values=[
            {"v": 0.0}, {"v": 0.0}, {"v": 0}, {"v": 0},
            {"v": 0}, {"v": 0}, {"v": 0}, {"v": 0},
        ])
        with patch("athena_bridge._db_sync", return_value=_FakeConn(cursor)):
            return self.client.get("/api/kpi/overview", headers=self.headers)

    @patch("core.relatorios.ranking_produtos")
    def test_mapeia_descricao_receita_e_margem_pro_shape_do_frontend(self, mock_ranking):
        mock_ranking.return_value = [
            {"sku": "SKU-A", "descricao": "Produto A", "quantidade": 5,
             "receita": 100.0, "margem_pct": 20.0},
            {"sku": "SKU-B", "descricao": "Produto B", "quantidade": 2,
             "receita": 300.0, "margem_pct": 40.0},
        ]
        r = self._rodar()
        data = r.get_json()
        # ordenado por receita desc — SKU-B (300) antes de SKU-A (100)
        self.assertEqual(data["top_skus"][0], {"sku": "SKU-B", "nome": "Produto B", "valor": 300.0, "margem": 40.0, "atributo": None, "produto_pai": None})
        self.assertEqual(data["top_skus"][1], {"sku": "SKU-A", "nome": "Produto A", "valor": 100.0, "margem": 20.0, "atributo": None, "produto_pai": None})

    @patch("core.relatorios.ranking_produtos")
    def test_limita_a_10_itens(self, mock_ranking):
        mock_ranking.return_value = [
            {"sku": f"SKU-{i}", "descricao": f"Produto {i}", "quantidade": 1,
             "receita": float(i), "margem_pct": 10.0}
            for i in range(15)
        ]
        r = self._rodar()
        data = r.get_json()
        self.assertEqual(len(data["top_skus"]), 10)

    @patch("core.relatorios.ranking_produtos")
    def test_erro_no_ranking_nao_quebra_a_rota(self, mock_ranking):
        mock_ranking.side_effect = Exception("falha ao calcular ranking")
        r = self._rodar()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["top_skus"], [])

    @patch("core.relatorios.ranking_produtos")
    def test_repassa_loja_id_pro_ranking_produtos(self, mock_ranking):
        mock_ranking.return_value = []
        cursor = _FakeCursor(fetchone_values=[
            {"v": 0.0}, {"v": 0.0}, {"v": 0}, {"v": 0},
            {"v": 0}, {"v": 0}, {"v": 0}, {"v": 0},
        ])
        with patch("athena_bridge._db_sync", return_value=_FakeConn(cursor)):
            self.client.get("/api/kpi/overview?loja_id=7", headers=self.headers)
        mock_ranking.assert_called_once_with(30, 7)


class TestKpiOverviewTipoLoja(unittest.TestCase):
    """?tipo_loja=virtual agrega todas as lojas daquele tipo (aba "Virtuais"
    do dashboard) — tem prioridade sobre loja_id singular quando ambos
    vierem na query string (ver dashboard/page.tsx)."""

    def setUp(self):
        self.client = app.test_client()
        self.headers = {"Authorization": f"Bearer {USER_TOKEN}"}

    def _cursor_padrao(self):
        return _FakeCursor(fetchone_values=[
            {"v": 100.0}, {"v": 50.0}, {"v": 2}, {"v": 1},
            {"v": 0}, {"v": 0}, {"v": 0}, {"v": 0},
        ], fetchall_values=[[]])

    @patch("core.lojas.listar_ids_por_tipo", return_value=[10, 11])
    def test_tipo_loja_usa_any_e_ignora_loja_id_singular(self, mock_listar):
        cursor = self._cursor_padrao()
        with patch("athena_bridge._db_sync", return_value=_FakeConn(cursor)):
            r = self.client.get("/api/kpi/overview?loja_id=999&tipo_loja=virtual", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        mock_listar.assert_called_once_with("virtual")
        sql_vp, params_vp = cursor.executed[0]
        self.assertIn("ANY(%s)", sql_vp)
        self.assertIn([10, 11], params_vp)
        self.assertNotIn(999, params_vp)

    @patch("core.relatorios.ranking_produtos")
    @patch("core.lojas.listar_ids_por_tipo", return_value=[10, 11])
    def test_tipo_loja_repassa_loja_ids_pro_ranking_produtos(self, mock_listar, mock_ranking):
        mock_ranking.return_value = []
        cursor = self._cursor_padrao()
        with patch("athena_bridge._db_sync", return_value=_FakeConn(cursor)):
            self.client.get("/api/kpi/overview?tipo_loja=virtual", headers=self.headers)
        mock_ranking.assert_called_once_with(30, loja_ids=[10, 11])

    def test_sem_tipo_loja_modo_legado_continua_igual(self):
        """Sem tipo_loja, o comportamento com loja_id singular precisa ficar
        identico ao anterior (ja coberto por TestKpiOverviewFonteDeVendas,
        reforcado aqui explicitamente pro contraste com o teste acima)."""
        cursor = self._cursor_padrao()
        with patch("athena_bridge._db_sync", return_value=_FakeConn(cursor)):
            r = self.client.get("/api/kpi/overview?loja_id=7", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        sql_vp, params_vp = cursor.executed[0]
        self.assertIn("loja_id=%s", sql_vp)
        self.assertIn(7, params_vp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
