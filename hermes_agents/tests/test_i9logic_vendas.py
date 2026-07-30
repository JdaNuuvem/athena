"""Testes de integracao — sync de vendas PDV i9Logic -> Athena."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import date
from unittest.mock import patch, AsyncMock, MagicMock

async def _mp(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import core.i9logic_vendas as vendas_i9logic


def _fake_db_com_conn(conn):
    """db (pool) so' expoe acquire() - mesmo padrao de test_i9logic_catalogo.py:
    se o codigo chamar db.fetchval/db.transaction direto por engano na pool
    (em vez de conn.*), quebra com AttributeError em vez de passar batido."""
    db = MagicMock(spec=["acquire"])
    db.acquire.return_value = AsyncMock(
        __aenter__=AsyncMock(return_value=conn), __aexit__=AsyncMock(return_value=None))
    return db


class TestBuscarDadosPedido(unittest.TestCase):
    def test_filial_sem_depara_retorna_none_sem_buscar_itens_pagamentos(self):
        chamadas = []
        def _fake_paginar(endpoint, params, on_pagina=None):
            chamadas.append(endpoint)
            if endpoint == "pedidos":
                return [{"id": 322643, "filial_venda": 999, "valor_total": 25.97,
                         "cancelado": "0", "data": "2026-07-29"}]
            return []
        with patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar), \
             patch("core.i9logic_vendas.buscar_codigo_athena", return_value=None):
            resultado = vendas_i9logic._buscar_dados_pedido(322643)
        self.assertIsNone(resultado)
        self.assertEqual(chamadas, ["pedidos"])

    def test_filial_mapeada_monta_pedido_completo(self):
        def _fake_paginar(endpoint, params, on_pagina=None):
            if endpoint == "pedidos":
                return [{"id": 322643, "filial_venda": 1, "valor_total": 25.97,
                         "cancelado": "0", "data": "2026-07-29"}]
            if endpoint == "pedidos_produtos":
                return [{"codproduto": "012810", "qtd": 1, "valorvenda": 1.99, "descricao": "Pinca"}]
            if endpoint == "pedidos_pagamentos":
                return [{"formadepagamento": 335, "valor": 25.97, "codautorizacao": ""}]
            return []
        with patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar), \
             patch("core.i9logic_vendas.buscar_codigo_athena", return_value="Loja Matriz"):
            resultado = vendas_i9logic._buscar_dados_pedido(322643)
        self.assertEqual(resultado["loja_athena"], "Loja Matriz")
        self.assertEqual(resultado["pedido"]["id"], 322643)
        self.assertEqual(len(resultado["itens"]), 1)
        self.assertEqual(len(resultado["pagamentos"]), 1)

    def test_pedido_nao_encontrado_levanta_erro(self):
        def _fake_paginar(endpoint, params, on_pagina=None):
            return []
        with patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar):
            with self.assertRaises(Exception):
                vendas_i9logic._buscar_dados_pedido(999999)


class TestJanelaPadrao(unittest.TestCase):
    def test_janela_padrao_e_data_string_com_inicio_antes_do_fim(self):
        data_de, data_ate = vendas_i9logic._janela_padrao()
        self.assertRegex(data_de, r"^\d{4}-\d{2}-\d{2}$")
        self.assertRegex(data_ate, r"^\d{4}-\d{2}-\d{2}$")
        self.assertLessEqual(data_de, data_ate)


class TestSincronizarPedidos(unittest.TestCase):
    def test_sem_base_url_retorna_erro(self):
        with patch("core.i9logic_vendas.BASE_URL", ""):
            resultado = vendas_i9logic.sincronizar_pedidos_i9logic()
        self.assertIn("erro", resultado)

    def test_pedido_ja_sincronizado_nao_gasta_chamada_de_busca(self):
        def _fake_paginar_pedidos(endpoint, params, on_pagina=None):
            self.assertEqual(endpoint, "pedidos")
            return [{"id": 1}, {"id": 2}]
        chamou_buscar_dados = []
        def _fake_buscar_dados(pid):
            chamou_buscar_dados.append(pid)
            return None
        with patch("core.i9logic_vendas.BASE_URL", "https://fake"), \
             patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar_pedidos), \
             patch("core.i9logic_vendas._ja_sincronizados", return_value={1}), \
             patch("core.i9logic_vendas._buscar_dados_pedido", side_effect=_fake_buscar_dados):
            vendas_i9logic.sincronizar_pedidos_i9logic()
        self.assertEqual(chamou_buscar_dados, [2])

    def test_falha_isolada_em_um_pedido_nao_impede_os_demais(self):
        def _fake_paginar_pedidos(endpoint, params, on_pagina=None):
            return [{"id": 1}, {"id": 2}]
        def _fake_buscar_dados(pid):
            if pid == 1:
                raise Exception("erro de rede")
            return {"pedido": {"id": 2, "cancelado": "0", "valor_total": 10, "data": "2026-07-29"},
                    "loja_athena": "Loja X", "itens": [], "pagamentos": []}
        gravados = []
        def _fake_gravar(dados):
            gravados.append(dados["pedido"]["id"])
            return {"ok": True}
        with patch("core.i9logic_vendas.BASE_URL", "https://fake"), \
             patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar_pedidos), \
             patch("core.i9logic_vendas._ja_sincronizados", return_value=set()), \
             patch("core.i9logic_vendas._buscar_dados_pedido", side_effect=_fake_buscar_dados), \
             patch("core.i9logic_vendas._gravar_pedido", side_effect=_fake_gravar):
            resultado = vendas_i9logic.sincronizar_pedidos_i9logic()
        self.assertEqual(gravados, [2])
        self.assertEqual(len(resultado["erros"]), 1)
        self.assertEqual(resultado["sincronizados"], 1)

    def test_teto_max_pedidos_novos_por_ciclo_e_respeitado(self):
        muitos_pedidos = [{"id": i} for i in range(1, 150)]
        def _fake_paginar_pedidos(endpoint, params, on_pagina=None):
            return muitos_pedidos
        processados = []
        def _fake_buscar_dados(pid):
            processados.append(pid)
            return None
        with patch("core.i9logic_vendas.BASE_URL", "https://fake"), \
             patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar_pedidos), \
             patch("core.i9logic_vendas._ja_sincronizados", return_value=set()), \
             patch("core.i9logic_vendas._buscar_dados_pedido", side_effect=_fake_buscar_dados):
            resultado = vendas_i9logic.sincronizar_pedidos_i9logic()
        self.assertEqual(len(processados), vendas_i9logic.MAX_PEDIDOS_NOVOS_POR_CICLO)
        self.assertTrue(resultado["truncado"])

    def test_backfill_com_datas_explicitas_repassa_para_paginar(self):
        params_capturados = {}
        def _fake_paginar(endpoint, params, on_pagina=None):
            params_capturados.update(params)
            return []
        with patch("core.i9logic_vendas.BASE_URL", "https://fake"), \
             patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar), \
             patch("core.i9logic_vendas._ja_sincronizados", return_value=set()):
            vendas_i9logic.sincronizar_pedidos_i9logic(data_de="2026-01-01", data_ate="2026-01-31")
        self.assertEqual(params_capturados["data_de"], "2026-01-01")
        self.assertEqual(params_capturados["data_ate"], "2026-01-31")


class TestGravarPedido(unittest.TestCase):
    def test_grava_pedido_novo_itens_e_pagamentos(self):
        execucoes = []
        args_insert_pedido = []
        dados = {
            "pedido": {"id": 322643, "cancelado": "0", "valor_total": 25.97, "data": "2026-07-29"},
            "loja_athena": "Loja Matriz",
            "itens": [{"codproduto": "012810", "descricao": "Pinca", "qtd": 1, "valorvenda": 1.99}],
            "pagamentos": [{"formadepagamento": 335, "valor": 25.97, "codautorizacao": ""}],
        }
        # fetchval do conn cobre: loja_id (lojas), checagem de pedido existente (None = novo),
        # e o INSERT em vendas_pedidos retornando o id novo
        async def _fetchval(query, *args):
            if "lojas" in query:
                return 7
            if "SELECT id FROM vendas_pedidos WHERE id_i9logic" in query:
                return None
            if "INSERT INTO vendas_pedidos" in query:
                args_insert_pedido.extend(args)
                return 55
            return None
        async def _execute(query, *args):
            execucoes.append(query)
            return "OK"
        # db (a pool) so' expoe acquire() - se o codigo voltar a chamar
        # db.transaction()/db.fetchval() direto por engano, o teste quebra
        # com AttributeError em vez de passar batido (mesmo bug que ja
        # aconteceu no import de catalogo, corrigido la).
        conn = AsyncMock()
        conn.fetchval = _fetchval
        conn.execute = _execute
        # conn.transaction precisa ser um MagicMock (chamada SINCRONA que
        # devolve um context manager), nao um AsyncMock puro: conn e' AsyncMock
        # sem spec, entao um atributo acessado nele (conn.transaction) vira
        # AsyncMock por padrao (ver unittest.mock.NonCallableMock._get_child_mock),
        # e "async with conn.transaction():" chamaria __aenter__ em cima da
        # CORROTINA (nao awaited) devolvida por essa chamada, nao no context
        # manager configurado via .return_value - mesma classe de bug do
        # acquire/transaction ja corrigida em test_i9logic_catalogo.py
        # (conn.transaction = MagicMock(return_value=TxMock())).
        conn.transaction = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=None), __aexit__=AsyncMock(return_value=None)))
        with patch("core.i9logic_vendas.get_db") as mock_get_db:
            mock_get_db.return_value = _fake_db_com_conn(conn)
            resultado = vendas_i9logic._gravar_pedido(dados)
        self.assertTrue(resultado["ok"])
        self.assertTrue(any("vendas_itens" in q for q in execucoes))
        self.assertTrue(any("vendas_pagamentos" in q for q in execucoes))
        # bug critical (review): asyncpg rejeita bind de str numa coluna DATE
        # ("DataError: invalid input for query argument $4: '...' ('str'
        # object has no attribute 'toordinal')"). Os fakes de fetchval/execute
        # acima nao validam tipo (por isso o bug passou batido nos testes
        # originais) - aqui checamos explicitamente que o 4o parametro do
        # INSERT (data) chega como datetime.date de verdade, nao a string
        # crua "2026-07-29" vinda da API i9Logic.
        self.assertEqual(len(args_insert_pedido), 6)
        self.assertIsInstance(args_insert_pedido[3], date)
        self.assertNotIsInstance(args_insert_pedido[3], str)
        self.assertEqual(args_insert_pedido[3], date(2026, 7, 29))

    def test_pedido_com_data_invalida_nao_quebra_grava_data_nula(self):
        """Fallback do mesmo fix: data malformada (ou ausente) na API nao
        pode derrubar a gravacao do pedido inteiro - so' grava data=None em
        vez de propagar erro de parsing pra fora de _gravar_pedido."""
        args_insert_pedido = []
        dados = {
            "pedido": {"id": 322644, "cancelado": "0", "valor_total": 10, "data": "nao-e-uma-data"},
            "loja_athena": "Loja Matriz",
            "itens": [],
            "pagamentos": [],
        }
        async def _fetchval(query, *args):
            if "lojas" in query:
                return 7
            if "SELECT id FROM vendas_pedidos WHERE id_i9logic" in query:
                return None
            if "INSERT INTO vendas_pedidos" in query:
                args_insert_pedido.extend(args)
                return 56
            return None
        async def _execute(query, *args):
            return "OK"
        conn = AsyncMock()
        conn.fetchval = _fetchval
        conn.execute = _execute
        conn.transaction = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=None), __aexit__=AsyncMock(return_value=None)))
        with patch("core.i9logic_vendas.get_db") as mock_get_db:
            mock_get_db.return_value = _fake_db_com_conn(conn)
            resultado = vendas_i9logic._gravar_pedido(dados)
        self.assertTrue(resultado["ok"])
        self.assertIsNone(args_insert_pedido[3])


if __name__ == "__main__":
    unittest.main(verbosity=2)
