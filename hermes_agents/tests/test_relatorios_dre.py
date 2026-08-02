"""Testes — DRE por Loja.

Contexto (achado real numa auditoria de producao-readiness): os testes
originais mockavam em core.relatorios.run_async — um nivel acima de get_db,
substituindo o corpo inteiro de _go() (SQL + calculo de comissao/lucro/margem)
por um valor fixo escrito a mao no proprio teste. Isso significava que
NENHUMA linha de SQL real, nem a formula de comissao/lucro, era exercitada —
os testes so' verificavam que run_async devolvia o que run_async "devolveu".
Por causa disso, um bug real (producao_custos.loja_id nao existe — a query
lancava UndefinedColumnError, engolida pelo except generico, fazendo
dre_por_loja() SEMPRE retornar [] em qualquer ambiente com o schema real)
nunca foi detectado por teste nenhum.

Esta versao mocka em dois niveis:
- TestDrePorLojaCalculo: repositorio fake (respeita o DIP do proprio modulo)
  — testa a formula de negocio (comissao so' sobre receita_shopee, lucro,
  margem, ticket medio, ordenacao) sem tocar SQL.
- TestPostgresFinanceiroRepositoryListarReceitaPorLoja: get_db mockado com
  fetchval/fetch reais — testa a query em si, incluindo guarda de regressao
  pro bug de producao_custos.loja_id.
"""
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
from core.repositories import ReceitaLoja


class _FakeFinanceiroRepo:
    def __init__(self, rows):
        self._rows = rows

    async def listar_receita_por_loja(self, dias):
        return self._rows

    async def listar_lojas_ativas(self):
        return []


class TestDrePorLojaCalculo(unittest.TestCase):
    """Formula de negocio de _dre_via_repo, via repositorio fake — sem SQL."""

    def test_sem_lojas_retorna_vazio(self):
        r = rel._dre_via_repo(_FakeFinanceiroRepo([]), dias=30, comissao_pct=12.0)
        self.assertEqual(r, [])

    def test_comissao_incide_so_sobre_receita_shopee_nao_receita_online_toda(self):
        """receita_online inclui Bling/i9Logic alem de Shopee — comissao de
        marketplace so' pode incidir sobre a parte que e' de fato Shopee."""
        rows = [ReceitaLoja(
            loja_id=1, loja_nome="Loja A",
            receita_online=1000.0, receita_shopee=400.0, receita_pdv=0.0,
            frete=0.0, custos_producao=0.0, qtd_vendas=10, qtd_vendas_pdv=0,
        )]
        r = rel._dre_via_repo(_FakeFinanceiroRepo(rows), dias=30, comissao_pct=12.0)
        self.assertEqual(len(r), 1)
        # 12% de 400 (so' shopee), nao de 1000 (online total)
        self.assertEqual(r[0]["comissao_valor"], 48.0)

    def test_lucro_e_margem_descontam_comissao_frete_e_custos(self):
        rows = [ReceitaLoja(
            loja_id=1, loja_nome="Loja A",
            receita_online=1000.0, receita_shopee=1000.0, receita_pdv=0.0,
            frete=50.0, custos_producao=150.0, qtd_vendas=10, qtd_vendas_pdv=0,
        )]
        r = rel._dre_via_repo(_FakeFinanceiroRepo(rows), dias=30, comissao_pct=12.0)
        item = r[0]
        # receita 1000 - comissao 120 - frete 50 - custos 150 = 680
        self.assertEqual(item["lucro"], 680.0)
        self.assertEqual(item["margem_pct"], 68.0)
        self.assertEqual(item["ticket_medio"], 100.0)  # 1000 / 10 vendas

    def test_ordena_por_lucro_descendente(self):
        rows = [
            ReceitaLoja(loja_id=1, loja_nome="Loja A", receita_online=1000.0, receita_shopee=1000.0, qtd_vendas=1),
            ReceitaLoja(loja_id=2, loja_nome="Loja B", receita_online=5000.0, receita_shopee=0.0, qtd_vendas=1),
        ]
        r = rel._dre_via_repo(_FakeFinanceiroRepo(rows), dias=30, comissao_pct=12.0)
        self.assertEqual([item["loja_nome"] for item in r], ["Loja B", "Loja A"])

    def test_receita_zero_nao_causa_divisao_por_zero(self):
        rows = [ReceitaLoja(loja_id=1, loja_nome="Loja Sem Venda", qtd_vendas=0, qtd_vendas_pdv=0)]
        r = rel._dre_via_repo(_FakeFinanceiroRepo(rows), dias=30, comissao_pct=12.0)
        self.assertEqual(r[0]["margem_pct"], 0)
        self.assertEqual(r[0]["ticket_medio"], 0)


class _FakeDB:
    """DB fake que responde por substring de query — mesmo padrao usado em
    test_shopee_sync.py/test_vendas.py pra exercitar SQL real sem banco."""
    def __init__(self, lojas, respostas_fetchval):
        self._lojas = lojas
        self._respostas = respostas_fetchval  # dict: substring da query -> valor
        self.queries_executadas = []

    async def fetch(self, q, *a):
        self.queries_executadas.append(q)
        if "FROM lojas" in q:
            return self._lojas
        return []

    async def fetchval(self, q, *a):
        self.queries_executadas.append(q)
        for chave, valor in self._respostas.items():
            if chave in q:
                return valor
        return 0


class TestPostgresFinanceiroRepositoryListarReceitaPorLoja(unittest.TestCase):
    """Testa a query real (nao um mock de run_async) — teria pego o bug de
    producao_custos.loja_id se a query ainda referenciasse essa coluna."""

    def test_nenhuma_query_filtra_producao_custos_por_loja_id(self):
        """Guarda de regressao do bug real: producao_custos nao tem coluna
        loja_id (fabrica unica) — filtrar por ela lancava UndefinedColumnError,
        engolido pelo except generico, fazendo o endpoint sempre voltar []."""
        from core.repositories_postgres import PostgresFinanceiroRepository
        db = _FakeDB(
            lojas=[{"id": 1, "nome": "Loja A"}],
            respostas_fetchval={"SUM(total)": 1000.0, "SUM(v.total)": 0, "SUM(frete)": 0,
                                 "COUNT(*)": 5, "producao_custos": 300.0},
        )
        with patch("core.repositories_postgres.get_db", AsyncMock(return_value=db)):
            repo = PostgresFinanceiroRepository()
            rows = rel.run_async(repo.listar_receita_por_loja(30))
        for q in db.queries_executadas:
            if "producao_custos" in q:
                self.assertNotIn("loja_id", q, f"producao_custos nao tem loja_id, essa query quebraria: {q}")
        self.assertEqual(len(rows), 1)

    def test_custos_producao_alocado_proporcionalmente_a_receita(self):
        """Sem coluna loja_id em producao_custos, o custo do periodo e' somado
        uma vez (nao por loja) e alocado proporcionalmente pela participacao
        de cada loja na receita total — nao e' rastreio real, e' estimativa."""
        from core.repositories_postgres import PostgresFinanceiroRepository

        class _DB2:
            def __init__(self):
                self.queries_executadas = []

            async def fetch(self, q, *a):
                self.queries_executadas.append(q)
                return [{"id": 1, "nome": "Loja A"}, {"id": 2, "nome": "Loja B"}]

            async def fetchval(self, q, *a):
                self.queries_executadas.append(q)
                if "producao_custos" in q:
                    return 300.0  # custo total do periodo, uma vez
                if "SUM(total)" in q and "marketplace" not in q:
                    # receita online: Loja A = 1, Loja B = ... (id via args[0])
                    return 3000.0 if a and a[0] == 1 else 1000.0
                if "COUNT(*)" in q:
                    return 1
                return 0

        db = _DB2()
        with patch("core.repositories_postgres.get_db", AsyncMock(return_value=db)):
            rows = rel.run_async(PostgresFinanceiroRepository().listar_receita_por_loja(30))
        por_id = {r.loja_id: r for r in rows}
        # Loja A tem 3000 de receita, Loja B tem 1000 — total 4000. Custo 300
        # alocado proporcional: Loja A = 300*3000/4000=225, Loja B = 300*1000/4000=75.
        self.assertAlmostEqual(por_id[1].custos_producao, 225.0, delta=0.01)
        self.assertAlmostEqual(por_id[2].custos_producao, 75.0, delta=0.01)


if __name__ == "__main__":
    unittest.main(verbosity=2)
