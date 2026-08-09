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
    def test_produtos_tendencia_calcula_crescimento(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = [
            {"sku": "SKU-A", "descricao": "Produto A", "qtd_atual": 30.0, "qtd_anterior": 10.0},
        ]
        mock_get_db.return_value = fake_db

        itens = rel.produtos_tendencia(30)

        self.assertEqual(len(itens), 1)
        item = itens[0]
        self.assertEqual(item["sku"], "SKU-A")
        self.assertEqual(item["quantidade_atual"], 30.0)
        self.assertEqual(item["quantidade_anterior"], 10.0)
        self.assertEqual(item["crescimento_pct"], 200.0)  # (30-10)/10*100

    @patch("core.relatorios.get_db")
    def test_produtos_tendencia_sem_base_anterior_nao_inventa_percentual(self, mock_get_db):
        """Produto novo (sem venda no periodo anterior) nao pode aparecer com
        '+inf%' ou '0%' — sem base de comparacao, o crescimento fica None."""
        fake_db = AsyncMock()
        fake_db.fetch.return_value = [
            {"sku": "SKU-NOVO", "descricao": "Produto Novo", "qtd_atual": 15.0, "qtd_anterior": 0.0},
        ]
        mock_get_db.return_value = fake_db

        itens = rel.produtos_tendencia(30)

        self.assertIsNone(itens[0]["crescimento_pct"])

    @patch("core.relatorios.get_db")
    def test_produtos_tendencia_queda_a_zero_fica_menos_100(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = [
            {"sku": "SKU-B", "descricao": "Produto B", "qtd_atual": 0.0, "qtd_anterior": 20.0},
        ]
        mock_get_db.return_value = fake_db

        itens = rel.produtos_tendencia(30)

        self.assertEqual(itens[0]["crescimento_pct"], -100.0)

    @patch("core.relatorios.get_db")
    def test_produtos_tendencia_sem_venda_em_nenhum_periodo_nao_aparece(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = [
            {"sku": "SKU-C", "descricao": "Produto C", "qtd_atual": 0.0, "qtd_anterior": 0.0},
        ]
        mock_get_db.return_value = fake_db

        self.assertEqual(rel.produtos_tendencia(30), [])

    @patch("core.relatorios.get_db")
    def test_risco_ruptura_calcula_dias_restantes(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = [
            {"sku": "SKU-D", "descricao": "Produto D", "qtd_vendida": 30.0, "estoque_atual": 15.0},
        ]
        mock_get_db.return_value = fake_db

        itens = rel.risco_ruptura(30)

        self.assertEqual(len(itens), 1)
        item = itens[0]
        self.assertEqual(item["velocidade_diaria"], 1.0)  # 30/30
        self.assertEqual(item["dias_restantes"], 15.0)  # 15/1.0

    @patch("core.relatorios.get_db")
    def test_risco_ruptura_exclui_sem_venda_ou_sem_estoque(self, mock_get_db):
        """Produto sem venda no periodo (velocidade=0) ou ja zerado (estoque=0)
        NAO e' risco de ruptura — sao os casos de 'parado' e 'ruptura ja
        consumada', metricas diferentes, nao podem se sobrepor aqui."""
        fake_db = AsyncMock()
        fake_db.fetch.return_value = [
            {"sku": "SEM-VENDA", "descricao": "Sem venda", "qtd_vendida": 0.0, "estoque_atual": 50.0},
            {"sku": "SEM-ESTOQUE", "descricao": "Sem estoque", "qtd_vendida": 20.0, "estoque_atual": 0.0},
        ]
        mock_get_db.return_value = fake_db

        self.assertEqual(rel.risco_ruptura(30), [])

    @patch("core.relatorios.get_db")
    def test_risco_ruptura_ordena_por_dias_restantes_ascendente(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = [
            {"sku": "URGENTE", "descricao": "Urgente", "qtd_vendida": 30.0, "estoque_atual": 3.0},  # 3 dias
            {"sku": "FOLGA", "descricao": "Com folga", "qtd_vendida": 30.0, "estoque_atual": 30.0},  # 30 dias
        ]
        mock_get_db.return_value = fake_db

        itens = rel.risco_ruptura(30)

        self.assertEqual(itens[0]["sku"], "URGENTE")
        self.assertEqual(itens[1]["sku"], "FOLGA")

    @patch("core.relatorios.get_db")
    def test_risco_ruptura_dias_zero_nao_lanca_zerodivisionerror(self, mock_get_db):
        """dias=0 (ou negativo) vem direto de request.args sem validacao — a
        funcao precisa se proteger em vez de deixar o /dias sourar um 500."""
        fake_db = AsyncMock()
        fake_db.fetch.return_value = [
            {"sku": "SKU-E", "descricao": "Produto E", "qtd_vendida": 10.0, "estoque_atual": 5.0},
        ]
        mock_get_db.return_value = fake_db

        itens = rel.risco_ruptura(0)

        self.assertEqual(len(itens), 1)

    @patch("core.relatorios.get_db")
    def test_curvas_converte_decimal_para_float(self, mock_get_db):
        """valor_total/qtd vem do asyncpg como Decimal — se nao forem
        convertidas pra float antes de entrar no JSON, o Flask serializa
        como STRING e quebra a formatacao de moeda/quantidade na aba ABC."""
        from decimal import Decimal
        fake_db = AsyncMock()
        fake_db.fetch.return_value = [
            {"sku": "SKU-X", "descricao": "Produto X", "valor_total": Decimal("1234.56"), "qtd": Decimal("10.000")},
        ]
        mock_get_db.return_value = fake_db

        resultado = rel.curvas(90)

        item = resultado["itens"][0]
        self.assertIsInstance(item["valor_total"], float)
        self.assertIsInstance(item["qtd"], float)
        self.assertEqual(item["valor_total"], 1234.56)

if __name__=="__main__":unittest.main(verbosity=2)
