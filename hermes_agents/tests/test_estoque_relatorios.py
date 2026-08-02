"""Testes — core/estoque_relatorios.py (agregacao de discrepancias por loja
e por operador). Cobre a troca de f-string por query parametrizada (dias
deve chegar como bind param, nunca interpolado na string SQL) e a logica de
merge entre as 3 fontes (saidas aprovadas, transferencias com discrepancia,
contagens com falta)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

async def _mock_create_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"),
    )), __aexit__=AsyncMock(return_value=None))
    return m

patch("asyncpg.create_pool", side_effect=_mock_create_pool).start()

import core.estoque_relatorios as relatorios


class TestPorLoja(unittest.TestCase):
    def test_dias_e_bind_param_nunca_interpolado_na_query(self):
        """Regressao: query era f-string com INTERVAL '{dias} days' — nao
        explorava (dias ja vem int-cast na rota), mas fugia do padrao
        parametrizado usado no resto do projeto."""
        db = AsyncMock()
        db.fetch = AsyncMock(return_value=[])
        with patch("core.estoque_relatorios.get_db", AsyncMock(return_value=db)):
            relatorios.por_loja(45)
        for call in db.fetch.call_args_list:
            query = call.args[0]
            self.assertNotIn("45", query)
            self.assertIn("$1", query)
            self.assertEqual(call.args[1], 45)

    def test_agrega_tres_fontes_por_loja(self):
        respostas = [
            [{"loja": "Centro", "saidas_aprovadas_qtd": 50.0, "saidas_aprovadas_qtd_eventos": 3}],
            [{"loja": "Centro", "transferencias_discrepancia": 2}],
            [{"loja": "Centro", "contagens_com_falta": 1, "unidades_falta": 4.0},
             {"loja": "Norte", "contagens_com_falta": 2, "unidades_falta": 10.0}],
        ]
        db = AsyncMock()
        db.fetch = AsyncMock(side_effect=respostas)
        with patch("core.estoque_relatorios.get_db", AsyncMock(return_value=db)):
            resultado = relatorios.por_loja(30)

        por_nome = {r["loja"]: r for r in resultado}
        self.assertEqual(por_nome["Centro"]["saidas_aprovadas_qtd"], 50.0)
        self.assertEqual(por_nome["Centro"]["saidas_aprovadas_eventos"], 3)
        self.assertEqual(por_nome["Centro"]["transferencias_com_discrepancia"], 2)
        self.assertEqual(por_nome["Centro"]["contagens_com_falta"], 1)
        self.assertEqual(por_nome["Centro"]["unidades_falta_contagem"], 4.0)
        # Norte so' aparece na 3a fonte (contagens) mas ainda deve sair no
        # resultado, com as outras metricas zeradas.
        self.assertEqual(por_nome["Norte"]["saidas_aprovadas_qtd"], 0.0)
        self.assertEqual(por_nome["Norte"]["unidades_falta_contagem"], 10.0)
        # Norte tem mais "unidades_falta_contagem" (10 > 4) mas Centro tem
        # mais "saidas_aprovadas_qtd" (50); ordenacao e' pela SOMA das duas.
        self.assertEqual(resultado[0]["loja"], "Centro")

    def test_erro_de_db_retorna_lista_vazia(self):
        with patch("core.estoque_relatorios.get_db", side_effect=RuntimeError("sem conexao")):
            self.assertEqual(relatorios.por_loja(30), [])


class TestPorOperador(unittest.TestCase):
    def test_dias_e_bind_param_nunca_interpolado_na_query(self):
        db = AsyncMock()
        db.fetch = AsyncMock(return_value=[])
        with patch("core.estoque_relatorios.get_db", AsyncMock(return_value=db)):
            relatorios.por_operador(45)
        for call in db.fetch.call_args_list:
            query = call.args[0]
            self.assertNotIn("45", query)
            self.assertIn("$1", query)
            self.assertEqual(call.args[1], 45)

    def test_agrega_aprovacoes_e_contagens_por_operador(self):
        respostas = [
            [{"operador": "Joao", "saidas_grandes_solicitadas": 5,
              "saidas_grandes_aprovadas_qtd": 30.0, "saidas_grandes_rejeitadas": 1}],
            [{"operador": "Joao", "contagens_com_falta": 2, "unidades_falta": 8.0},
             {"operador": "Maria", "contagens_com_falta": 1, "unidades_falta": 1.0}],
        ]
        db = AsyncMock()
        db.fetch = AsyncMock(side_effect=respostas)
        with patch("core.estoque_relatorios.get_db", AsyncMock(return_value=db)):
            resultado = relatorios.por_operador(30)

        por_nome = {r["operador"]: r for r in resultado}
        self.assertEqual(por_nome["Joao"]["saidas_grandes_solicitadas"], 5)
        self.assertEqual(por_nome["Joao"]["saidas_grandes_aprovadas_qtd"], 30.0)
        self.assertEqual(por_nome["Joao"]["contagens_com_falta"], 2)
        # Maria so' aparece nas contagens, nao nas aprovacoes.
        self.assertEqual(por_nome["Maria"]["saidas_grandes_solicitadas"], 0)
        self.assertEqual(por_nome["Maria"]["unidades_falta_contagem"], 1.0)
        self.assertEqual(resultado[0]["operador"], "Joao")

    def test_erro_de_db_retorna_lista_vazia(self):
        with patch("core.estoque_relatorios.get_db", side_effect=RuntimeError("sem conexao")):
            self.assertEqual(relatorios.por_operador(30), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
