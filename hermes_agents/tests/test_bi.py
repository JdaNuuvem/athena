"""Testes de integracao — core/bi.py substitui os dados mockados do
frontend por calculo real a partir do banco (vendas, estoque, clientes).
Sem numero inventado: indicadores que dependem de dado que o sistema nao
rastreia (balanco patrimonial) sao omitidos, nao fabricados."""
import sys, os, unittest
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

async def _mp(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import core.bi as bi


class TestFormatadores(unittest.TestCase):
    def test_fmt_brl(self):
        self.assertEqual(bi._fmt_brl(1234.5), "R$ 1.234,50")

    def test_fmt_pct(self):
        self.assertEqual(bi._fmt_pct(12.34), "12.3%")


class TestDashboard(unittest.TestCase):
    def test_kpis_reais_quando_ha_dado_e_dash_quando_nao_ha(self):
        with patch("core.relatorios.vendas", return_value={"total": 15000.0, "quantidade": 20, "diarias": [], "periodo_dias": 30}), \
             patch("core.relatorios.ticket_medio", return_value={"ticket_medio": 750.0, "total_vendas": 15000, "qtd_vendas": 20, "periodo_dias": 30}), \
             patch("core.relatorios.dre", return_value={"receita_bruta": 15000, "cmv": 5000, "lucro_bruto": 10000, "despesas": 2000, "margem_bruta_pct": 66.7, "periodo_dias": 30}), \
             patch("core.relatorios.previsao", return_value={"media_diaria": 500, "previsao_30d": 15000}), \
             patch("core.bi.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetchval.return_value = 0
            mock_get_db.return_value = db
            resultado = bi.dashboard()
        kpis = {k["label"]: k for k in resultado["kpis"]}
        self.assertEqual(kpis["Receita (mês)"]["value"], "R$ 15.000,00")
        self.assertEqual(kpis["Ticket Médio"]["value"], "R$ 750,00")
        self.assertEqual(kpis["Margem Média"]["value"], "66.7%")
        # ROI nao e' calculavel com o dado disponivel — nao pode virar numero inventado.
        self.assertEqual(kpis["ROI"]["value"], "--")


class TestVendasDiarias(unittest.TestCase):
    def test_soma_bling_e_pdv_no_mesmo_dia(self):
        with patch("core.relatorios._union_vendas", return_value={
            "diarias_bling": [{"dia": date(2026, 7, 1), "qtd": 2, "valor": 100.0}],
            "diarias_pdv": [{"dia": date(2026, 7, 1), "qtd": 1, "valor": 50.0}],
        }):
            resultado = bi.vendas_diarias(30)
        self.assertEqual(resultado, [{"dia": "01/07", "valor": 150.0, "custo": 0, "margem": 0}])


class TestVendasCategorias(unittest.TestCase):
    def test_agrupa_por_categoria_e_calcula_margem_real(self):
        linha_bling = {"categoria": "Ferragens", "sku": "SKU1", "nome": "Parafuso", "qtd": 10.0, "valor": 100.0, "preco_custo": 5.0}
        linha_pdv = {"categoria": "Ferragens", "sku": "SKU2", "nome": "Porca", "qtd": 5.0, "valor": 50.0, "preco_custo": 2.0}
        with patch("core.bi.get_db"), \
             patch("core.bi.run_async", return_value=[linha_bling, linha_pdv]):
            resultado = bi.vendas_categorias(30)
        self.assertEqual(len(resultado), 1)
        cat = resultado[0]
        self.assertEqual(cat["categoria"], "Ferragens")
        self.assertEqual(cat["valor"], 150.0)
        self.assertEqual(cat["percentual"], 100.0)
        produto1 = next(p for p in cat["produtos"] if p["sku"] == "SKU1")
        # margem = (100 - 5*10) / 100 * 100 = 50%
        self.assertEqual(produto1["margem"], 50.0)


class TestIndicadores(unittest.TestCase):
    def test_omite_indicador_quando_dado_nao_existe(self):
        """giro de estoque sem estoque cadastrado (estoque_valor=0) deve ser
        omitido, nunca virar um numero fabricado (ex: divisao por zero)."""
        with patch("core.relatorios.dre", return_value={"margem_bruta_pct": 40.0}), \
             patch("core.relatorios.lucro_margem", return_value={"margem_pct": 12.0}), \
             patch("core.bi.run_async", return_value=(
                 {"margem_bruta_pct": 40.0}, None, None, None, None,
             )):
            resultado = bi.indicadores()
        ids = {i["id"] for i in resultado}
        self.assertIn("margem-bruta", ids)
        self.assertNotIn("giro-estoque", ids)
        self.assertNotIn("prazo-medio-receb", ids)
        self.assertNotIn("crescimento-receita", ids)

    def test_calcula_giro_de_estoque_quando_ha_dado(self):
        with patch("core.relatorios.dre", return_value={"margem_bruta_pct": 40.0}), \
             patch("core.relatorios.lucro_margem", return_value={"margem_pct": 12.0}), \
             patch("core.bi.run_async", return_value=(
                 {"margem_bruta_pct": 40.0}, 8.5, 20, 35, 5.0,
             )):
            resultado = bi.indicadores()
        giro = next(i for i in resultado if i["id"] == "giro-estoque")
        self.assertEqual(giro["valor"], 8.5)

    def test_prazo_de_recebimento_curto_e_bom_prazo_longo_e_ruim(self):
        """Prazo de recebimento e' 'menor e' melhor' — 20 dias (< 30) deve
        ser status good, 50 dias (> 45) deve ser status danger."""
        with patch("core.relatorios.dre", return_value={"margem_bruta_pct": 40.0}), \
             patch("core.relatorios.lucro_margem", return_value={"margem_pct": 12.0}), \
             patch("core.bi.run_async", return_value=({"margem_bruta_pct": 40.0}, None, 20, None, None)):
            resultado = bi.indicadores()
        prazo = next(i for i in resultado if i["id"] == "prazo-medio-receb")
        self.assertEqual(prazo["status"], "good")

        with patch("core.relatorios.dre", return_value={"margem_bruta_pct": 40.0}), \
             patch("core.relatorios.lucro_margem", return_value={"margem_pct": 12.0}), \
             patch("core.bi.run_async", return_value=({"margem_bruta_pct": 40.0}, None, 50, None, None)):
            resultado = bi.indicadores()
        prazo = next(i for i in resultado if i["id"] == "prazo-medio-receb")
        self.assertEqual(prazo["status"], "danger")


class TestForecast(unittest.TestCase):
    def test_projeta_media_historica_com_cenarios(self):
        diarias_bling = [{"dia": date(2026, 7, i), "qtd": 1, "valor": 100.0} for i in range(1, 11)]
        with patch("core.relatorios._union_vendas", return_value={"diarias_bling": diarias_bling, "diarias_pdv": []}):
            resultado = bi.forecast(dias_historico=10, dias_previsao=5)
        self.assertEqual(len(resultado["pontos"]), 15)
        # sem variacao (todo dia = 100), desvio padrao e' zero -> confianca maxima
        self.assertEqual(resultado["resumo"]["confianca"], 100)
        self.assertEqual(resultado["resumo"]["cenarios"]["esperado"], 500.0)


class TestMLSegmentos(unittest.TestCase):
    def test_classifica_cliente_sem_compra_como_inativo(self):
        with patch("core.bi.get_db"), \
             patch("core.bi.run_async", return_value=[{"id": 1, "nome": "Cliente Sumido", "ultima_compra": None, "freq": 0, "monetario": 0}]):
            resultado = bi.ml_segmentos()
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["segmento"], "Inativos")
        self.assertEqual(resultado[0]["churn"], 100.0)

    def test_classifica_cliente_recente_frequente_e_de_alto_valor_como_campeao(self):
        hoje = date.today()
        clientes = [{"id": 1, "nome": "Cliente Top", "ultima_compra": hoje - timedelta(days=5), "freq": 6, "monetario": 5000.0}]
        with patch("core.bi.get_db"), patch("core.bi.run_async", return_value=clientes):
            resultado = bi.ml_segmentos()
        self.assertEqual(resultado[0]["segmento"], "Campeões")
        self.assertEqual(resultado[0]["clientes"][0]["nome"], "Cliente Top")


class TestMLRecomendacoes(unittest.TestCase):
    def test_confianca_e_suporte_classico_de_regra_de_associacao(self):
        pares = [{"sku_a": "A", "sku_b": "B", "juntos": 8, "receita": 800.0}]
        totais = {"A": 10}
        nomes = {"A": "Produto A", "B": "Produto B"}
        with patch("core.bi.get_db"), patch("core.bi.run_async", return_value=(pares, totais, nomes)):
            resultado = bi.ml_recomendacoes()
        self.assertEqual(len(resultado), 1)
        # confianca = 8/10 * 100 = 80% (P(B comprado | A comprado))
        self.assertEqual(resultado[0]["confianca"], 80.0)
        self.assertEqual(resultado[0]["receitaEstimada"], 800.0)


class TestEstoqueParado(unittest.TestCase):
    @patch("core.bi.get_db")
    def test_estoque_parado_repassa_loja_id_pra_query(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        bi.estoque_parado(60, 10, loja_id=4)

        hoje = date.today()
        di = hoje - timedelta(days=60)
        self.assertEqual(fake_db.fetch.call_args.args[1:], (di, hoje, 4))

    @patch("core.bi.get_db")
    def test_estoque_parado_sem_loja_id_mantem_comportamento_atual(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        bi.estoque_parado(60, 10)

        hoje = date.today()
        di = hoje - timedelta(days=60)
        self.assertEqual(fake_db.fetch.call_args.args[1:], (di, hoje, None))

    @patch("core.bi.get_db")
    def test_estoque_parado_loja_ids_usa_any_em_vez_de_loja_id_unico(self, mock_get_db):
        """loja_ids (ex: tipo_loja='virtual' no dashboard) tem prioridade
        sobre loja_id — filtra por ANY(...) tanto no saldo de estoque quanto
        na subquery de venda, ignorando loja_id singular quando ambos vierem."""
        fake_db = AsyncMock()
        fake_db.fetch.return_value = []
        mock_get_db.return_value = fake_db

        bi.estoque_parado(60, 10, loja_id=999, loja_ids=[1, 2, 3])

        sql, args = fake_db.fetch.call_args.args[0], fake_db.fetch.call_args.args[1:]
        self.assertIn("e.loja_id = ANY($3::int[])", sql)
        self.assertIn("p.loja_id = ANY($3::int[])", sql)
        self.assertEqual(args[-1], [1, 2, 3])


if __name__ == "__main__":
    unittest.main(verbosity=2)
