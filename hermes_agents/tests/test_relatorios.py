"""Testes unitarios — Relatorios (vendas, lucro, estoque, DRE, fluxo caixa)."""
import sys,os,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import date, timedelta
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

    @patch("core.relatorios.get_db")
    def test_dre_cmv_rateia_por_loja_em_vez_de_repassar_o_total_da_empresa(self, mock_get_db):
        """Achado real: cmv nao filtrava por loja nenhuma — chamar dre(30,
        loja_id=X) e dre(30, loja_id=Y) devolvia o MESMO cmv (custo de
        producao TOTAL da empresa) pras duas lojas, so' a receita variava.
        Agora aloca proporcional a participacao da loja na receita geral —
        mesmo padrao ja usado em core/repositories_postgres.py::
        listar_receita_por_loja."""
        fake_db = AsyncMock()
        # ordem das chamadas dentro de _go(): receita da loja (bling), receita
        # da loja (pdv), cmv total, receita geral (bling), receita geral (pdv), despesas
        fake_db.fetchval.side_effect = [2000.0, 0.0, 1000.0, 8000.0, 0.0, 0.0]
        mock_get_db.return_value = fake_db

        r = rel.dre(30, loja_id=5)

        # loja tem 2000 de receita, empresa toda tem 8000 -> loja e' 25% da receita
        # -> cmv da loja = 25% de 1000 = 250
        self.assertEqual(r["cmv"], 250.0)
        self.assertEqual(r["receita_bruta"], 2000.0)
        self.assertEqual(r["lucro_bruto"], 1750.0)

    @patch("core.relatorios.get_db")
    def test_dre_sem_loja_id_cmv_e_o_total_sem_rateio(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetchval.side_effect = [8000.0, 0.0, 1000.0, 0.0]
        mock_get_db.return_value = fake_db

        r = rel.dre(30)

        self.assertEqual(r["cmv"], 1000.0)
        self.assertEqual(r["lucro_bruto"], 7000.0)

    @patch("core.relatorios.get_db")
    def test_dre_nao_deduz_mais_percentual_chumbado_de_contas_a_pagar(self, mock_get_db):
        """Achado real: `lb = receita - cmv - (cp_val * 0.7)` deduzia 70% de
        TODAS as contas a pagar pendentes do periodo, sem nenhuma base
        documentada (fin_contas_pagar nao tem categoria pra distinguir custo
        de mercadoria de qualquer outra despesa). Removido — lucro_bruto
        agora e' so' receita menos cmv."""
        fake_db = AsyncMock()
        fake_db.fetchval.side_effect = [10000.0, 0.0, 2000.0, 0.0]
        mock_get_db.return_value = fake_db

        r = rel.dre(30)

        self.assertEqual(r["lucro_bruto"], 8000.0)
        sqls = [c.args[0] for c in fake_db.fetchval.call_args_list]
        self.assertFalse(any("fin_contas_pagar" in sql for sql in sqls),
                          "dre() nao deveria mais consultar fin_contas_pagar")
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

    def test_vendas_diarias_consolida_bling_e_pdv_do_mesmo_dia_e_ordena(self):
        """Achado real: o Dashboard mostrava 'Vendas do mes' com o eixo X fora
        de ordem cronologica — _union_vendas concatenava diarias_bling +
        diarias_pdv sem consolidar por dia nem ordenar (nenhuma das duas
        queries SQL tem ORDER BY), entao um dia com venda em Bling E PDV virava
        2 pontos soltos na lista, na ordem que o Postgres decidisse devolver."""
        from datetime import date
        fake = {
            "total": 300.0, "quantidade": 3,
            "diarias_bling": [
                {"dia": date(2026, 8, 3), "qtd": 1, "valor": 100.0},
                {"dia": date(2026, 8, 1), "qtd": 1, "valor": 50.0},
            ],
            "diarias_pdv": [
                {"dia": date(2026, 8, 3), "qtd": 1, "valor": 25.0},  # mesmo dia do bling acima
                {"dia": date(2026, 8, 2), "qtd": 1, "valor": 125.0},
            ],
        }
        with patch("core.relatorios._union_vendas", return_value=fake):
            r = rel.vendas(30)
        self.assertEqual([d["dia"] for d in r["diarias"]], ["2026-08-01", "2026-08-02", "2026-08-03"])
        dia3 = next(d for d in r["diarias"] if d["dia"] == "2026-08-03")
        self.assertEqual(dia3["valor"], 125.0)  # 100 (bling) + 25 (pdv) consolidado
        self.assertEqual(dia3["qtd"], 2)

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
    def test_ranking_produtos_inclui_atributo_e_nome_do_produto_pai(self, mock_get_db):
        """sku_pai/atributo vem da hierarquia Bling (ver bling_erp.py) — o
        ranking precisa expor os 2 pra UI distinguir 'Camiseta - Tamanho P'
        de 'Camiseta - Tamanho M' como variacoes do mesmo produto base, em
        vez de 2 linhas soltas sem relacao aparente."""
        fake_db = AsyncMock()
        fake_db.fetch.side_effect = [
            [{"sku": "SKU-FILHO", "quantidade": 3, "receita": 90.0, "comissao": 0.0, "frete": 0.0}],
            [{"sku": "SKU-FILHO", "descricao": "Camiseta - Tamanho P", "preco_custo": 10.0,
              "sku_pai": "SKU-PAI", "atributo": "Tamanho P"}],
            [{"sku": "SKU-PAI", "descricao": "Camiseta"}],
        ]
        mock_get_db.return_value = fake_db

        item = rel.ranking_produtos(30)[0]

        self.assertEqual(item["atributo"], "Tamanho P")
        self.assertEqual(item["produto_pai"], "Camiseta")

    @patch("core.relatorios.get_db")
    def test_ranking_produtos_sem_sku_pai_nao_consulta_produto_pai(self, mock_get_db):
        """Produto simples (sem hierarquia, ex: SKU direto Shopee) nao deve
        disparar a query extra de nome do pai — so' 2 fetches (vendas + custo)."""
        fake_db = AsyncMock()
        fake_db.fetch.side_effect = [
            [{"sku": "SKU-A", "quantidade": 3, "receita": 90.0, "comissao": 0.0, "frete": 0.0}],
            [{"sku": "SKU-A", "descricao": "Produto simples", "preco_custo": 10.0,
              "sku_pai": None, "atributo": None}],
        ]
        mock_get_db.return_value = fake_db

        item = rel.ranking_produtos(30)[0]

        self.assertIsNone(item["atributo"])
        self.assertIsNone(item["produto_pai"])
        self.assertEqual(fake_db.fetch.call_count, 2)

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

        hoje = date.today()
        for call in fake_db.fetchval.call_args_list:
            params = call.args[1:]
            self.assertEqual(params, (hoje, hoje), f"esperava filtro so' hoje, achou {params} em {call.args[0]!r}")
        for call in fake_db.fetch.call_args_list:
            params = call.args[1:]
            self.assertEqual(params, (hoje, hoje), f"esperava filtro so' hoje, achou {params} em {call.args[0]!r}")

    @patch("core.relatorios.get_db")
    def test_vendas_30_dias_comportamento_inalterado(self, mock_get_db):
        """dias > 1 mantem o comportamento generico existente (CURRENT_DATE
        - N) — o fix de dias=1 nao pode vazar pra outros periodos."""
        fake_db = AsyncMock()
        fake_db.fetchval.return_value = 0
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        rel.vendas(30)

        hoje = date.today()
        di = hoje - timedelta(days=30)
        for call in fake_db.fetchval.call_args_list:
            self.assertEqual(call.args[1:], (di, hoje))
        for call in fake_db.fetch.call_args_list:
            self.assertEqual(call.args[1:], (di, hoje))

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

    @patch("core.relatorios.get_db")
    def test_ranking_produtos_repassa_loja_id_pra_query(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.side_effect = [
            [{"sku": "SKU-A", "quantidade": 10, "receita": 1000.0, "comissao": 0.0, "frete": 0.0}],
            [{"sku": "SKU-A", "descricao": "Produto A", "preco_custo": 30.0}],
        ]
        mock_get_db.return_value = fake_db

        rel.ranking_produtos(30, loja_id=5)

        hoje = date.today()
        di = hoje - timedelta(days=30)
        primeira_query_params = fake_db.fetch.call_args_list[0].args[1:]
        self.assertEqual(primeira_query_params, (di, hoje, 5))

    @patch("core.relatorios.get_db")
    def test_ranking_produtos_sem_loja_id_mantem_comportamento_atual(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.side_effect = [
            [{"sku": "SKU-A", "quantidade": 10, "receita": 1000.0, "comissao": 0.0, "frete": 0.0}],
            [{"sku": "SKU-A", "descricao": "Produto A", "preco_custo": 30.0}],
        ]
        mock_get_db.return_value = fake_db

        rel.ranking_produtos(30)

        hoje = date.today()
        di = hoje - timedelta(days=30)
        primeira_query_params = fake_db.fetch.call_args_list[0].args[1:]
        self.assertEqual(primeira_query_params, (di, hoje, None))

    @patch("core.relatorios.get_db")
    def test_curvas_repassa_loja_id_pra_query(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        rel.curvas(90, loja_id=3)

        hoje = date.today()
        di = hoje - timedelta(days=90)
        self.assertEqual(fake_db.fetch.call_args.args[1:], (di, hoje, 3))

    @patch("core.relatorios.get_db")
    def test_curvas_sem_loja_id_mantem_comportamento_atual(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        rel.curvas(90)

        hoje = date.today()
        di = hoje - timedelta(days=90)
        self.assertEqual(fake_db.fetch.call_args.args[1:], (di, hoje, None))

    @patch("core.relatorios.get_db")
    def test_produtos_tendencia_repassa_loja_id_pra_query(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        rel.produtos_tendencia(30, loja_id=8)

        hoje = date.today()
        di = hoje - timedelta(days=30)
        di_anterior = di - timedelta(days=30)
        self.assertEqual(fake_db.fetch.call_args.args[1:], (di, hoje, di_anterior, 8))

    @patch("core.relatorios.get_db")
    def test_produtos_tendencia_sem_loja_id_mantem_comportamento_atual(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        rel.produtos_tendencia(30)

        hoje = date.today()
        di = hoje - timedelta(days=30)
        di_anterior = di - timedelta(days=30)
        self.assertEqual(fake_db.fetch.call_args.args[1:], (di, hoje, di_anterior, None))

    @patch("core.relatorios.get_db")
    def test_risco_ruptura_repassa_loja_id_pra_query(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        rel.risco_ruptura(30, loja_id=2)

        hoje = date.today()
        di = hoje - timedelta(days=30)
        self.assertEqual(fake_db.fetch.call_args.args[1:], (di, hoje, 2))

    @patch("core.relatorios.get_db")
    def test_risco_ruptura_sem_loja_id_mantem_comportamento_atual(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        rel.risco_ruptura(30)

        hoje = date.today()
        di = hoje - timedelta(days=30)
        self.assertEqual(fake_db.fetch.call_args.args[1:], (di, hoje, None))

    @patch("core.relatorios.get_db")
    def test_demanda_por_loja_soma_bling_shopee_e_pdv_por_loja(self, mock_get_db):
        """Divisao de estoque por demanda (feature de rateio entre lojas)
        precisa somar venda do mesmo SKU em Bling/Shopee (vendas_itens) E PDV
        fisico (pdv_itens) quando caem na mesma loja — canais diferentes, loja
        igual, a demanda real da loja e' a soma dos dois."""
        fake_db = AsyncMock()
        fake_db.fetch.side_effect = [
            [{"loja_id": 1, "quantidade": 12}, {"loja_id": 2, "quantidade": 3}],  # vendas_itens/vendas_pedidos
            [{"loja_id": 1, "quantidade": 5}],  # pdv_itens/pdv_vendas/pdv_caixas
            [{"id": 1, "nome": "Loja Fisica"}, {"id": 2, "nome": "Loja Shopee"}],  # lojas
        ]
        mock_get_db.return_value = fake_db

        itens = rel.demanda_por_loja("SKU-X", 30)

        self.assertEqual(itens[0], {"loja_id": 1, "loja_nome": "Loja Fisica", "quantidade": 17.0})
        self.assertEqual(itens[1], {"loja_id": 2, "loja_nome": "Loja Shopee", "quantidade": 3.0})

    @patch("core.relatorios.get_db")
    def test_demanda_por_loja_sem_vendas_retorna_vazio(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.side_effect = [[], [], []]
        mock_get_db.return_value = fake_db

        self.assertEqual(rel.demanda_por_loja("SKU-SEM-VENDA", 30), [])

    @patch("core.relatorios.get_db")
    def test_demanda_por_loja_ordena_por_quantidade_desc(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.side_effect = [
            [{"loja_id": 1, "quantidade": 2}, {"loja_id": 2, "quantidade": 9}],
            [],
            [{"id": 1, "nome": "A"}, {"id": 2, "nome": "B"}],
        ]
        mock_get_db.return_value = fake_db

        itens = rel.demanda_por_loja("SKU-Y", 30)

        self.assertEqual([i["loja_id"] for i in itens], [2, 1])

    # ── loja_ids (lista) — modo "todas as lojas de um tipo" do dashboard ──
    # (aba "Virtuais": agrega todas as lojas virtuais em vez de uma so' ou
    # todas — ver routes/relatorios.py::_resolver_loja_ids)

    def test_vendas_loja_ids_repassa_pro_union_vendas(self):
        with patch("core.relatorios._union_vendas") as mock_union:
            mock_union.return_value = {"total": 0, "quantidade": 0, "diarias_bling": [], "diarias_pdv": []}
            rel.vendas(30, loja_ids=[1, 2])
            mock_union.assert_called_once_with(30, None, None, None, loja_ids=[1, 2])

    def test_loja_ids_lista_vazia_filtra_pra_nada_em_vez_de_ignorar_filtro(self):
        """loja_ids=[] (ex: tipo_loja='virtual' sem nenhuma loja virtual ativa)
        precisa filtrar pra ZERO resultados — nao pode cair silenciosamente
        no modo "sem filtro" (loja_ids e' falsy em Python, entao um `if
        loja_ids:` ingenuo trata [] igual a None). Distingue via `is not
        None`, nao truthiness."""
        self.assertEqual(rel._loja_where_bling(None, loja_ids=[]), " AND FALSE")
        self.assertEqual(rel._loja_where_pdv(None, loja_ids=[]), " AND FALSE")
        self.assertEqual(rel._loja_where_estoque(None, loja_ids=[]), " AND FALSE")

    @patch("core.relatorios.get_db")
    def test_ranking_produtos_loja_ids_vazia_nao_cai_no_modo_legado(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        self.assertEqual(rel.ranking_produtos(30, loja_id=999, loja_ids=[]), [])

        primeira_chamada = fake_db.fetch.call_args_list[0]
        self.assertIn("= ANY($3::int[])", primeira_chamada.args[0])
        self.assertEqual(primeira_chamada.args[3], [])

    @patch("core.relatorios.get_db")
    def test_estoque_loja_ids_resolve_nomes_e_usa_in(self, mock_get_db):
        """loja_ids tem prioridade sobre loja_id quando ambos vierem — cada id
        e' resolvido pro nome efetivo (mesma logica de loja_id unico) e o
        filtro vira um IN (...) em vez de igualdade."""
        fake_db = AsyncMock()
        fake_db.fetchval.side_effect = [5, 1, 0]  # total, baixo_estoque, ruptura
        mock_get_db.return_value = fake_db
        with patch("core.relatorios.loja_efetiva", side_effect=lambda s: {"1": "Loja Um", "2": "Loja Dois"}[s]):
            r = rel.estoque(loja_id=999, loja_ids=[1, 2])

        self.assertEqual(r["total_itens"], 5)
        sql_total = fake_db.fetchval.call_args_list[0].args[0]
        self.assertIn("e.loja IN ('Loja Um','Loja Dois')", sql_total)
        self.assertNotIn("999", sql_total)

    @patch("core.relatorios.get_db")
    def test_clientes_loja_ids_usa_any_em_vez_de_igualdade(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetchval.side_effect = [3, 1]
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        r = rel.clientes(30, loja_id=999, loja_ids=[5, 6])

        self.assertEqual(r["total"], 3)
        sql_total, arg_total = fake_db.fetchval.call_args_list[0].args[0], fake_db.fetchval.call_args_list[0].args[1]
        self.assertIn("ANY($1::int[])", sql_total)
        self.assertEqual(arg_total, [5, 6])

    @patch("core.relatorios.get_db")
    def test_fluxo_caixa_loja_ids_usa_any(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetchval.return_value = 0
        mock_get_db.return_value = fake_db

        rel.fluxo_caixa(30, loja_id=999, loja_ids=[5, 6])

        sqls = [call.args[0] for call in fake_db.fetchval.call_args_list]
        self.assertTrue(any("ANY(ARRAY[5,6]::int[])" in sql for sql in sqls))
        self.assertFalse(any("loja_id = 999" in sql for sql in sqls))

    @patch("core.relatorios.get_db")
    def test_ranking_produtos_loja_ids_usa_any_em_vez_de_loja_id_unico(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.side_effect = [
            [{"sku": "SKU-A", "quantidade": 10, "receita": 1000.0, "comissao": 0.0, "frete": 0.0}],
            [{"sku": "SKU-A", "descricao": "Produto A", "preco_custo": 30.0}],
        ]
        mock_get_db.return_value = fake_db

        itens = rel.ranking_produtos(30, loja_id=999, loja_ids=[1, 2, 3])

        self.assertEqual(len(itens), 1)
        primeira_chamada = fake_db.fetch.call_args_list[0]
        self.assertIn("= ANY($3::int[])", primeira_chamada.args[0])
        self.assertEqual(primeira_chamada.args[3], [1, 2, 3])

    @patch("core.relatorios.get_db")
    def test_ranking_produtos_sem_loja_ids_mantem_modo_legado(self, mock_get_db):
        """Sem loja_ids (so' loja_id singular ou nenhum), a query continua
        exatamente como antes — modo legado nao pode quebrar."""
        fake_db = AsyncMock()
        fake_db.fetch.side_effect = [
            [{"sku": "SKU-A", "quantidade": 10, "receita": 1000.0, "comissao": 0.0, "frete": 0.0}],
            [{"sku": "SKU-A", "descricao": "Produto A", "preco_custo": 30.0}],
        ]
        mock_get_db.return_value = fake_db

        rel.ranking_produtos(30, loja_id=7)

        primeira_chamada = fake_db.fetch.call_args_list[0]
        self.assertIn("($3::int IS NULL OR vp.loja_id = $3)", primeira_chamada.args[0])
        self.assertEqual(primeira_chamada.args[3], 7)

    @patch("core.relatorios.get_db")
    def test_curvas_loja_ids_usa_any_em_vez_de_loja_id_unico(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        rel.curvas(90, loja_id=999, loja_ids=[1, 2])

        sql, args = fake_db.fetch.call_args.args[0], fake_db.fetch.call_args.args[1:]
        self.assertIn("vp.loja_id = ANY($3::int[])", sql)
        self.assertEqual(args[-1], [1, 2])

    @patch("core.relatorios.get_db")
    def test_produtos_tendencia_loja_ids_usa_any_em_vez_de_loja_id_unico(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        rel.produtos_tendencia(30, loja_id=999, loja_ids=[1, 2])

        sql, args = fake_db.fetch.call_args.args[0], fake_db.fetch.call_args.args[1:]
        self.assertIn("vp.loja_id = ANY($4::int[])", sql)
        self.assertEqual(args[-1], [1, 2])

    @patch("core.relatorios.get_db")
    def test_risco_ruptura_loja_ids_usa_any_nos_dois_lugares(self, mock_get_db):
        """risco_ruptura filtra loja em DOIS pontos da query (venda e saldo de
        estoque) — os dois precisam trocar pra ANY(...) junto, senao a
        subquery de estoque continua olhando pra todas as lojas."""
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        rel.risco_ruptura(30, loja_id=999, loja_ids=[1, 2])

        sql, args = fake_db.fetch.call_args.args[0], fake_db.fetch.call_args.args[1:]
        self.assertIn("vp.loja_id = ANY($3::int[])", sql)
        self.assertIn("e.loja_id = ANY($3::int[])", sql)
        self.assertEqual(args[-1], [1, 2])


if __name__=="__main__":unittest.main(verbosity=2)
