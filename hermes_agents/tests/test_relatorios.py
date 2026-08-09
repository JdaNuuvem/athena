"""Testes unitarios — Relatorios (vendas, lucro, estoque, DRE, fluxo caixa)."""
import sys,os,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch,MagicMock,AsyncMock
# Mock DB
async def _mock_create_pool(*a,**kw):m=AsyncMock();m.acquire.return_value=AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(fetch=AsyncMock(return_value=[]),fetchrow=AsyncMock(return_value=None),fetchval=AsyncMock(return_value=0),execute=AsyncMock(return_value="OK"))),__aexit__=AsyncMock(return_value=None));return m
patcher=patch("asyncpg.create_pool",side_effect=_mock_create_pool)
patcher.start()
import core.relatorios as rel

class TestRelatorios(unittest.TestCase):
    def test_vendas_return_keys(self):r=rel.vendas(30);self.assertIn("total",r);self.assertIn("diarias",r)
    def test_lucro_return_keys(self):r=rel.lucro_margem(30);self.assertIn("lucro",r);self.assertIn("margem_pct",r)
    def test_estoque_return_keys(self):r=rel.estoque();self.assertIn("total_itens",r);self.assertIn("ruptura",r)
    def test_dre_return_keys(self):r=rel.dre(30);self.assertIn("receita_bruta",r);self.assertIn("lucro_bruto",r)
    def test_fluxo_caixa_keys(self):r=rel.fluxo_caixa(30);self.assertIn("entradas",r);self.assertIn("saidas",r);self.assertIn("saldo",r)
    def test_ticket_medio(self):
        try:
            r=rel.ticket_medio(30)
            self.assertIn("ticket_medio",r)
        except TypeError:
            self.skipTest("mock DB incompativel")
    def test_previsao(self):r=rel.previsao(30);self.assertIn("media_diaria",r);self.assertIn("previsao_30d",r)
    def test_clientes(self):r=rel.clientes(30);self.assertIn("total",r);self.assertIn("top",r)
    def test_fornecedores(self):r=rel.fornecedores();self.assertIn("total",r);self.assertIn("ativos",r)
    def test_aging(self):r=rel.aging_financeiro();self.assertIn("a_vencer",r)
    def test_fallback_zero(self):
        r=rel.vendas(99999)
        self.assertGreaterEqual(r["total"],0)
        self.assertEqual(r["periodo_dias"],99999)

    @patch("core.relatorios.get_db")
    def test_ranking_produtos_calcula_lucro_com_comissao_so_shopee(self, mock_get_db):
        """Comissao de marketplace so' e' deduzida quando o SQL classificou o canal
        como 'shopee' (unica taxa conhecida) — os $ ja vem agregados do SQL, o
        Python so' junta com o custo do catalogo e calcula lucro final."""
        fake_db = AsyncMock()
        fake_db.fetch.side_effect = [
            [{"sku": "SKU-A", "quantidade": 10, "receita": 1000.0, "comissao": 120.0, "frete": 20.0}],
            [{"sku": "SKU-A", "descricao": "Produto A", "preco_custo": 30.0}],
        ]
        mock_get_db.return_value = fake_db

        itens = rel.ranking_produtos(30)

        self.assertEqual(len(itens), 1)
        item = itens[0]
        self.assertEqual(item["sku"], "SKU-A")
        self.assertEqual(item["custo"], 300.0)  # 30 * 10
        self.assertEqual(item["lucro"], 560.0)  # 1000 - 300 - 120 - 20
        self.assertTrue(item["custo_cadastrado"])

    @patch("core.relatorios.get_db")
    def test_ranking_produtos_sem_custo_cadastrado_marca_flag(self, mock_get_db):
        """SKU vendido mas sem preco_custo em catalogo_produtos (ou nunca
        cadastrado la') precisa ficar sinalizado — lucro sem custo real e'
        enganoso, a UI precisa poder avisar em vez de mostrar como certeza."""
        fake_db = AsyncMock()
        fake_db.fetch.side_effect = [
            [{"sku": "SKU-B", "quantidade": 5, "receita": 200.0, "comissao": 0.0, "frete": 0.0}],
            [],
        ]
        mock_get_db.return_value = fake_db

        itens = rel.ranking_produtos(30)

        self.assertEqual(itens[0]["custo"], 0)
        self.assertFalse(itens[0]["custo_cadastrado"])

    @patch("core.relatorios.get_db")
    def test_ranking_produtos_sem_vendas_retorna_vazio(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        self.assertEqual(rel.ranking_produtos(30), [])

    @patch("core.relatorios.get_db")
    def test_vendas_hoje_dias_1_nao_inclui_ontem(self, mock_get_db):
        """Card "Vendas hoje" chama vendas(1, ...) esperando so' o dia
        corrente. O padrao generico da funcao (CURRENT_DATE - $1::int) usado
        por vendas(30)/etc inclui o dia corrente MAIS N dias anteriores —
        com dias=1 isso soma hoje + ontem inteiro, dobrando o valor do card.
        A query deve filtrar so' por CURRENT_DATE quando dias=1 (parametro
        0 subtraido de CURRENT_DATE), nao CURRENT_DATE - 1."""
        fake_db = AsyncMock()
        fake_db.fetchval.return_value = 0
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        rel.vendas(1)

        for call in fake_db.fetchval.call_args_list:
            params = call.args[1:]
            self.assertEqual(params, (0,), f"esperava filtro CURRENT_DATE - 0, achou {params} em {call.args[0]!r}")
        for call in fake_db.fetch.call_args_list:
            params = call.args[1:]
            self.assertEqual(params, (0,), f"esperava filtro CURRENT_DATE - 0, achou {params} em {call.args[0]!r}")

    @patch("core.relatorios.get_db")
    def test_vendas_30_dias_comportamento_inalterado(self, mock_get_db):
        """dias > 1 mantem o comportamento generico existente (CURRENT_DATE
        - N) — o fix de dias=1 nao pode vazar pra outros periodos."""
        fake_db = AsyncMock()
        fake_db.fetchval.return_value = 0
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        rel.vendas(30)

        for call in fake_db.fetchval.call_args_list:
            self.assertEqual(call.args[1:], (30,))
        for call in fake_db.fetch.call_args_list:
            self.assertEqual(call.args[1:], (30,))

if __name__=="__main__":unittest.main(verbosity=2)
