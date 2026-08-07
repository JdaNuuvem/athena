"""Testes de core/estoque_analise.py — giro/ruptura/cobertura sobre dado
real (asyncpg mockado, sem banco de verdade)."""
import sys, os, unittest
from datetime import date, datetime, timedelta
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


# ── Task 6 (vinculo fisica x virtual): giro/ruptura/cobertura resolvem
# `loja` (nome/id de uma loja virtual com vinculo ativo) pro nome da fisica
# vinculada ANTES de montar os WHEREs de estoque_lojas/vendas_pedidos —
# mesmo padrao ja' estabelecido em core/estoque_saldos.py (Tasks 3-4,
# test_estoque_saldos.py::TestVinculoEstoque*) e core/estoque.py (Task 5,
# test_estoque_vinculo.py).
#
# Patch-target (mesmo cuidado documentado/reconfirmado nas Tasks 3-5): o
# alvo e' `core.estoque_analise._loja_efetiva_async`/`_log_erro` (os NOMES
# importados dentro DESTE modulo via `from core.lojas import
# _loja_efetiva_async, _log_erro`), NAO `core.lojas._loja_efetiva_async`/
# `core.lojas._log_erro` — com `from ... import ...`, o modulo consumidor
# fica com sua propria referencia ao objeto funcao; patchar so' o modulo de
# origem nao intercepta a chamada feita a partir de core/estoque_analise.py.
#
# Nota de design importante: as assercoes de "qual loja foi usada na
# query" abaixo SEMPRE rodam DEPOIS do bloco `with` (via
# db.fetch.call_args_list), nunca dentro do proprio fake_fetch. Um
# self.assertIn/assertEqual que falhasse DENTRO do fake_fetch levantaria
# AssertionError na coroutine de _go(), que e' capturada pelo `except
# Exception: return []` de giro()/ruptura()/cobertura() (AssertionError e'
# uma Exception) — o teste passaria silenciosamente mesmo com o vinculo
# quebrado, porque a excecao nunca chegaria ao test runner (confirmado
# empiricamente). Por isso o fake_fetch aqui so' RETORNA dado canned,
# nunca afirma nada — toda verificacao fica no nivel do metodo de teste.
class TestGiroResolveVinculo(unittest.TestCase):
    def test_giro_com_loja_virtual_vinculada_consulta_saldo_da_fisica(self):
        with patch("core.estoque_analise.get_db") as mock_get_db, \
             patch("core.estoque_analise._loja_efetiva_async",
                   AsyncMock(return_value="Loja Fisica Central")) as mock_resolver:
            db = AsyncMock()
            db.fetch.return_value = []
            mock_get_db.return_value = db
            resultado = analise.giro(loja="Loja Virtual A")
        mock_resolver.assert_called_once_with("Loja Virtual A")
        self.assertEqual(resultado, [])
        self.assertEqual(len(db.fetch.call_args_list), 2)
        saldo_args = db.fetch.call_args_list[0][0]
        vendas_args = db.fetch.call_args_list[1][0]
        self.assertIn("Loja Fisica Central", saldo_args)
        self.assertIn("Loja Fisica Central", vendas_args)

    def test_giro_resolver_indisponivel_usa_loja_original_retorna_dado_real(self):
        """Fail-open: o resolver real (core.lojas._loja_efetiva_async) abre
        sua PROPRIA conexao via get_db(), independente do `db` fakeado
        aqui — uma excecao (DB indisponivel) precisa ser tratada como
        no-op (giro() continua usando 'loja' ORIGINAL), nunca propagar e
        fazer o try/except externo de _go() devolver [] silenciosamente.
        Usa retorno NAO-vazio pra distinguir "usou loja original e
        calculou dado real" de "excecao engolida pelo except: return []"."""
        async def fake_fetch(query, *params):
            q = " ".join(query.split())
            if "FROM estoque_lojas" in q:
                return [{"sku": "ABC-1", "produto": "Produto ABC", "saldo_atual": 50}]
            if "FROM vendas_itens" in q:
                return [{"sku": "ABC-1", "saidas_periodo": 40, "saidas_periodo_anterior": 10}]
            return []
        erro_original = RuntimeError("DB indisponivel")
        with patch("core.estoque_analise.get_db") as mock_get_db, \
             patch("core.estoque_analise._loja_efetiva_async",
                   AsyncMock(side_effect=erro_original)) as mock_resolver, \
             patch("core.estoque_analise._log_erro") as mock_log_erro:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.giro(loja="Loja Virtual A")
        mock_resolver.assert_called_once_with("Loja Virtual A")
        self.assertEqual(resultado, [{
            "sku": "ABC-1", "produto": "Produto ABC",
            "saidas_30d": 40, "estoque_medio": 50, "giro": 0.8, "tendencia": "up",
        }])
        self.assertEqual(len(db.fetch.call_args_list), 2)
        saldo_args = db.fetch.call_args_list[0][0]
        vendas_args = db.fetch.call_args_list[1][0]
        self.assertIn("Loja Virtual A", saldo_args)
        self.assertIn("Loja Virtual A", vendas_args)
        mock_log_erro.assert_called_once()
        onde, exc = mock_log_erro.call_args[0]
        self.assertIn("resolver_loja_efetiva", onde)
        self.assertIs(exc, erro_original)

    def test_giro_resolver_devolve_valor_invalido_usa_loja_original_retorna_dado_real(self):
        """Outra face da regression acima: resolver que NAO levanta excecao
        mas devolve algo que nao e' um nome de loja valido (None) precisa
        ser ignorado (usa 'loja' original) e logado via _log_erro."""
        async def fake_fetch(query, *params):
            q = " ".join(query.split())
            if "FROM estoque_lojas" in q:
                return [{"sku": "ABC-1", "produto": "Produto ABC", "saldo_atual": 50}]
            if "FROM vendas_itens" in q:
                return [{"sku": "ABC-1", "saidas_periodo": 40, "saidas_periodo_anterior": 10}]
            return []
        with patch("core.estoque_analise.get_db") as mock_get_db, \
             patch("core.estoque_analise._loja_efetiva_async",
                   AsyncMock(return_value=None)) as mock_resolver, \
             patch("core.estoque_analise._log_erro") as mock_log_erro:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.giro(loja="Loja Virtual A")
        mock_resolver.assert_called_once_with("Loja Virtual A")
        self.assertEqual(resultado, [{
            "sku": "ABC-1", "produto": "Produto ABC",
            "saidas_30d": 40, "estoque_medio": 50, "giro": 0.8, "tendencia": "up",
        }])
        self.assertEqual(len(db.fetch.call_args_list), 2)
        saldo_args = db.fetch.call_args_list[0][0]
        vendas_args = db.fetch.call_args_list[1][0]
        self.assertIn("Loja Virtual A", saldo_args)
        self.assertIn("Loja Virtual A", vendas_args)
        mock_log_erro.assert_called_once()
        onde, exc = mock_log_erro.call_args[0]
        self.assertIn("resolver_loja_efetiva", onde)
        self.assertIsInstance(exc, Exception)


class TestRupturaResolveVinculo(unittest.TestCase):
    """A query principal de ruptura() tem DOIS formatos SQL dependendo de
    `if loja:` (com override de produtos_loja) ou nao (so' o minimo do
    catalogo) — os testes abaixo sempre passam loja truthy, entao so'
    exercitam o branch `if loja:`; o branch sem loja ja' tem cobertura em
    TestRuptura.test_nenhum_sku_abaixo_do_minimo_retorna_vazio (chamado
    sem argumento)."""

    def test_ruptura_com_loja_virtual_vinculada_consulta_saldo_da_fisica(self):
        with patch("core.estoque_analise.get_db") as mock_get_db, \
             patch("core.estoque_analise._loja_efetiva_async",
                   AsyncMock(return_value="Loja Fisica Central")) as mock_resolver:
            db = AsyncMock()
            db.fetch.return_value = []
            mock_get_db.return_value = db
            resultado = analise.ruptura(loja="Loja Virtual A")
        mock_resolver.assert_called_once_with("Loja Virtual A")
        self.assertEqual(resultado, [])
        self.assertEqual(len(db.fetch.call_args_list), 1)
        self.assertIn("Loja Fisica Central", db.fetch.call_args_list[0][0])

    def test_ruptura_resolver_indisponivel_usa_loja_original_retorna_dado_real(self):
        """Fail-open (mesmo raciocinio de TestGiroResolveVinculo). Reusa o
        cenario 'sku sem abastecimento registrado' pra manter o
        fake_fetch simples e nao precisar simular datas de abastecimento —
        o que importa aqui e' que o resultado NAO-vazio prova que a query
        principal rodou com a loja ORIGINAL, nao que a excecao do resolver
        foi engolida pelo except: return [] externo."""
        async def fake_fetch(query, *params):
            q = " ".join(query.split())
            if "FROM estoque_lojas" in q:
                return [{"sku": "XYZ-9", "produto": "Produto XYZ", "saldo_atual": 2, "estoque_minimo": 10}]
            if "estoque_movimentacoes" in q:
                return []  # nunca reabastecido
            return []
        erro_original = RuntimeError("DB indisponivel")
        with patch("core.estoque_analise.get_db") as mock_get_db, \
             patch("core.estoque_analise._loja_efetiva_async",
                   AsyncMock(side_effect=erro_original)) as mock_resolver, \
             patch("core.estoque_analise._log_erro") as mock_log_erro:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.ruptura(loja="Loja Virtual A")
        mock_resolver.assert_called_once_with("Loja Virtual A")
        self.assertEqual(resultado, [{
            "sku": "XYZ-9", "produto": "Produto XYZ",
            "dias_ruptura": 0, "vendas_perdidas_estimadas": 0,
            "impacto_receita": 0.0, "ultimo_abastecimento": None,
        }])
        self.assertEqual(len(db.fetch.call_args_list), 2)
        self.assertIn("Loja Virtual A", db.fetch.call_args_list[0][0])
        mock_log_erro.assert_called_once()
        onde, exc = mock_log_erro.call_args[0]
        self.assertIn("resolver_loja_efetiva", onde)
        self.assertIs(exc, erro_original)

    def test_ruptura_resolver_devolve_valor_invalido_usa_loja_original_retorna_dado_real(self):
        """Outra face da regression acima: resolver que devolve valor
        invalido sem excecao (None)."""
        async def fake_fetch(query, *params):
            q = " ".join(query.split())
            if "FROM estoque_lojas" in q:
                return [{"sku": "XYZ-9", "produto": "Produto XYZ", "saldo_atual": 2, "estoque_minimo": 10}]
            if "estoque_movimentacoes" in q:
                return []
            return []
        with patch("core.estoque_analise.get_db") as mock_get_db, \
             patch("core.estoque_analise._loja_efetiva_async",
                   AsyncMock(return_value=None)) as mock_resolver, \
             patch("core.estoque_analise._log_erro") as mock_log_erro:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.ruptura(loja="Loja Virtual A")
        mock_resolver.assert_called_once_with("Loja Virtual A")
        self.assertEqual(resultado, [{
            "sku": "XYZ-9", "produto": "Produto XYZ",
            "dias_ruptura": 0, "vendas_perdidas_estimadas": 0,
            "impacto_receita": 0.0, "ultimo_abastecimento": None,
        }])
        self.assertEqual(len(db.fetch.call_args_list), 2)
        self.assertIn("Loja Virtual A", db.fetch.call_args_list[0][0])
        mock_log_erro.assert_called_once()
        onde, exc = mock_log_erro.call_args[0]
        self.assertIn("resolver_loja_efetiva", onde)
        self.assertIsInstance(exc, Exception)

    def test_ruptura_com_abastecimento_registrado_consulta_velocidade_media_da_fisica(self):
        """Fecha um gap de cobertura flagado em review: nenhum teste deste
        arquivo (nem os 2 pre-existentes de TestRuptura, nem os outros 2
        acima) alcancava o branch `if loja:` ANINHADO dentro do loop por
        linha (alimenta a query de velocidade media/impacto de receita via
        db.fetchrow) — todos ou caiam no `if not rows: return []` precoce,
        ou usavam um fixture com `ultimo is None` (dispara o `continue`
        ANTES desse branch). Sem isso, um shadow/stale-variable bug
        reintroduzido especificamente nesse branch aninhado nao seria
        pego por nada neste arquivo.

        Fixture: abastecimento NAO-vazio (ultimo != None) faz o codigo
        seguir alem do `continue` ate' montar params_vendas e chamar
        db.fetchrow — e' so' ai' que a loja resolvida (ou nao) chega
        nessa query especifica."""
        ultimo_dt = datetime.now() - timedelta(days=15)
        async def fake_fetch(query, *params):
            q = " ".join(query.split())
            if "FROM estoque_lojas" in q:
                return [{"sku": "XYZ-9", "produto": "Produto XYZ", "saldo_atual": 2, "estoque_minimo": 10}]
            if "estoque_movimentacoes" in q:
                return [{"sku": "XYZ-9", "data": ultimo_dt}]  # ultimo NAO e' None
            return []
        with patch("core.estoque_analise.get_db") as mock_get_db, \
             patch("core.estoque_analise._loja_efetiva_async",
                   AsyncMock(return_value="Loja Fisica Central")) as mock_resolver:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            db.fetchrow = AsyncMock(return_value={"qtd": 15, "preco_medio": 20.0})
            mock_get_db.return_value = db
            resultado = analise.ruptura(loja="Loja Virtual A")
        mock_resolver.assert_called_once_with("Loja Virtual A")
        self.assertEqual(resultado, [{
            "sku": "XYZ-9", "produto": "Produto XYZ",
            "dias_ruptura": 15,
            "vendas_perdidas_estimadas": 7.5,
            "impacto_receita": 150.0,
            "ultimo_abastecimento": ultimo_dt.date().isoformat(),
        }])
        db.fetchrow.assert_called_once()
        fetchrow_args = db.fetchrow.call_args[0]
        self.assertIn("Loja Fisica Central", fetchrow_args)
        self.assertNotIn("Loja Virtual A", fetchrow_args)


class TestCoberturaResolveVinculo(unittest.TestCase):
    """A query de saldos de cobertura() tambem tem DOIS formatos SQL
    dependendo de `if loja:` (mesma logica de TestRupturaResolveVinculo);
    o branch sem loja ja' tem cobertura em TestCobertura (chamado sem
    argumento)."""

    def test_cobertura_com_loja_virtual_vinculada_consulta_saldo_da_fisica(self):
        with patch("core.estoque_analise.get_db") as mock_get_db, \
             patch("core.estoque_analise._loja_efetiva_async",
                   AsyncMock(return_value="Loja Fisica Central")) as mock_resolver:
            db = AsyncMock()
            db.fetch.return_value = []
            mock_get_db.return_value = db
            resultado = analise.cobertura(loja="Loja Virtual A")
        mock_resolver.assert_called_once_with("Loja Virtual A")
        self.assertEqual(resultado, [])
        self.assertEqual(len(db.fetch.call_args_list), 2)
        saldo_args = db.fetch.call_args_list[0][0]
        vendas_args = db.fetch.call_args_list[1][0]
        self.assertIn("Loja Fisica Central", saldo_args)
        self.assertIn("Loja Fisica Central", vendas_args)

    def test_cobertura_resolver_indisponivel_usa_loja_original_retorna_dado_real(self):
        """Fail-open (mesmo raciocinio de TestGiroResolveVinculo)."""
        async def fake_fetch(query, *params):
            q = " ".join(query.split())
            if "FROM estoque_lojas" in q:
                return [{"sku": "QQQ-1", "produto": "Produto QQQ", "estoque_atual": 50,
                          "estoque_minimo": 0, "estoque_maximo": 0}]
            if "FROM vendas_itens" in q:
                return []
            return []
        erro_original = RuntimeError("DB indisponivel")
        with patch("core.estoque_analise.get_db") as mock_get_db, \
             patch("core.estoque_analise._loja_efetiva_async",
                   AsyncMock(side_effect=erro_original)) as mock_resolver, \
             patch("core.estoque_analise._log_erro") as mock_log_erro:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.cobertura(loja="Loja Virtual A")
        mock_resolver.assert_called_once_with("Loja Virtual A")
        self.assertEqual(resultado, [{
            "sku": "QQQ-1", "produto": "Produto QQQ",
            "estoque_atual": 50, "demanda_diaria_media": 0.0, "cobertura_dias": 0,
            "estoque_minimo": 0, "estoque_maximo": 0, "status": "normal",
        }])
        self.assertEqual(len(db.fetch.call_args_list), 2)
        saldo_args = db.fetch.call_args_list[0][0]
        vendas_args = db.fetch.call_args_list[1][0]
        self.assertIn("Loja Virtual A", saldo_args)
        self.assertIn("Loja Virtual A", vendas_args)
        mock_log_erro.assert_called_once()
        onde, exc = mock_log_erro.call_args[0]
        self.assertIn("resolver_loja_efetiva", onde)
        self.assertIs(exc, erro_original)

    def test_cobertura_resolver_devolve_valor_invalido_usa_loja_original_retorna_dado_real(self):
        """Outra face da regression acima: resolver que devolve valor
        invalido sem excecao (None)."""
        async def fake_fetch(query, *params):
            q = " ".join(query.split())
            if "FROM estoque_lojas" in q:
                return [{"sku": "QQQ-1", "produto": "Produto QQQ", "estoque_atual": 50,
                          "estoque_minimo": 0, "estoque_maximo": 0}]
            if "FROM vendas_itens" in q:
                return []
            return []
        with patch("core.estoque_analise.get_db") as mock_get_db, \
             patch("core.estoque_analise._loja_efetiva_async",
                   AsyncMock(return_value=None)) as mock_resolver, \
             patch("core.estoque_analise._log_erro") as mock_log_erro:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.cobertura(loja="Loja Virtual A")
        mock_resolver.assert_called_once_with("Loja Virtual A")
        self.assertEqual(resultado, [{
            "sku": "QQQ-1", "produto": "Produto QQQ",
            "estoque_atual": 50, "demanda_diaria_media": 0.0, "cobertura_dias": 0,
            "estoque_minimo": 0, "estoque_maximo": 0, "status": "normal",
        }])
        self.assertEqual(len(db.fetch.call_args_list), 2)
        saldo_args = db.fetch.call_args_list[0][0]
        vendas_args = db.fetch.call_args_list[1][0]
        self.assertIn("Loja Virtual A", saldo_args)
        self.assertIn("Loja Virtual A", vendas_args)
        mock_log_erro.assert_called_once()
        onde, exc = mock_log_erro.call_args[0]
        self.assertIn("resolver_loja_efetiva", onde)
        self.assertIsInstance(exc, Exception)


class TestKpisPorDeposito(unittest.TestCase):
    def test_sem_linhas_retorna_lista_vazia(self):
        async def fake_fetch(query, *params):
            return []
        with patch("core.estoque_analise.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.kpis_por_deposito()
        self.assertEqual(resultado, [])

    def test_agrega_skus_e_valor_de_um_deposito(self):
        async def fake_fetch(query, *params):
            return [
                {"deposito_id": 10, "sku": "A", "saldo": 5, "minimo": 0, "preco_custo": 20.0},
                {"deposito_id": 10, "sku": "B", "saldo": 3, "minimo": 0, "preco_custo": 10.0},
            ]
        with patch("core.estoque_analise.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.kpis_por_deposito()
        self.assertEqual(resultado, [{"deposito_id": 10, "skus": 2, "valor": 130.0, "baixo_estoque": 0}])

    def test_saldo_abaixo_do_minimo_conta_em_baixo_estoque(self):
        async def fake_fetch(query, *params):
            return [{"deposito_id": 10, "sku": "A", "saldo": 2, "minimo": 5, "preco_custo": 0.0}]
        with patch("core.estoque_analise.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.kpis_por_deposito()
        self.assertEqual(resultado, [{"deposito_id": 10, "skus": 1, "valor": 0.0, "baixo_estoque": 1}])

    def test_dois_depositos_agregados_separadamente(self):
        async def fake_fetch(query, *params):
            return [
                {"deposito_id": 10, "sku": "A", "saldo": 5, "minimo": 0, "preco_custo": 1.0},
                {"deposito_id": 20, "sku": "A", "saldo": 5, "minimo": 0, "preco_custo": 1.0},
                {"deposito_id": 20, "sku": "B", "saldo": 5, "minimo": 0, "preco_custo": 1.0},
            ]
        with patch("core.estoque_analise.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.kpis_por_deposito()
        por_id = {r["deposito_id"]: r for r in resultado}
        self.assertEqual(por_id[10]["skus"], 1)
        self.assertEqual(por_id[20]["skus"], 2)

    def test_preco_custo_ausente_nao_quebra_soma(self):
        async def fake_fetch(query, *params):
            return [{"deposito_id": 10, "sku": "A", "saldo": 5, "minimo": 0, "preco_custo": 0.0}]
        with patch("core.estoque_analise.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            resultado = analise.kpis_por_deposito()
        self.assertEqual(resultado[0]["valor"], 0.0)

    def test_erro_de_banco_retorna_lista_vazia(self):
        with patch("core.estoque_analise.get_db", side_effect=Exception("db down")):
            resultado = analise.kpis_por_deposito()
        self.assertEqual(resultado, [])