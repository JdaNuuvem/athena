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
        """Achado 5a: o cabecalho agora vem pronto do chamador (dict), _buscar_dados_pedido
        NAO deve mais chamar _paginar("pedidos", ...) pra rebuscar - so' o de-para de filial,
        e sem mapeamento nem itens/pagamentos sao buscados (chamadas fica vazia)."""
        chamadas = []
        def _fake_paginar(endpoint, params, on_pagina=None):
            chamadas.append(endpoint)
            return []
        pedido = {"id": 322643, "filial_venda": 999, "valor_total": 25.97,
                  "cancelado": "0", "data": "2026-07-29"}
        with patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar), \
             patch("core.i9logic_vendas.buscar_codigo_athena", return_value=None):
            resultado = vendas_i9logic._buscar_dados_pedido(pedido)
        self.assertIsNone(resultado)
        self.assertEqual(chamadas, [])
        self.assertNotIn("pedidos", chamadas)

    def test_filial_mapeada_monta_pedido_completo(self):
        """Achado 5a: cabecalho passado direto como dict - o teste so' precisa mockar
        pedidos_produtos/pedidos_pagamentos, nao mais o endpoint "pedidos"."""
        chamadas = []
        pedido = {"id": 322643, "filial_venda": 1, "valor_total": 25.97,
                  "cancelado": "0", "data": "2026-07-29"}
        def _fake_paginar(endpoint, params, on_pagina=None):
            chamadas.append(endpoint)
            if endpoint == "pedidos_produtos":
                return [{"codproduto": "012810", "qtd": 1, "valorvenda": 1.99, "descricao": "Pinca"}]
            if endpoint == "pedidos_pagamentos":
                return [{"formadepagamento": 335, "valor": 25.97, "codautorizacao": ""}]
            return []
        with patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar), \
             patch("core.i9logic_vendas.buscar_codigo_athena", return_value="Loja Matriz"):
            resultado = vendas_i9logic._buscar_dados_pedido(pedido)
        self.assertEqual(resultado["loja_athena"], "Loja Matriz")
        self.assertEqual(resultado["pedido"]["id"], 322643)
        self.assertEqual(len(resultado["itens"]), 1)
        self.assertEqual(len(resultado["pagamentos"]), 1)
        self.assertNotIn("pedidos", chamadas)


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
        def _fake_buscar_dados(pedido):
            chamou_buscar_dados.append(pedido["id"])
            return None
        with patch("core.i9logic_vendas.BASE_URL", "https://fake"), \
             patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar_pedidos), \
             patch("core.i9logic_vendas._status_sincronizados", return_value={1: "concluido"}), \
             patch("core.i9logic_vendas._buscar_dados_pedido", side_effect=_fake_buscar_dados):
            vendas_i9logic.sincronizar_pedidos_i9logic()
        self.assertEqual(chamou_buscar_dados, [2])

    def test_falha_isolada_em_um_pedido_nao_impede_os_demais(self):
        def _fake_paginar_pedidos(endpoint, params, on_pagina=None):
            return [{"id": 1}, {"id": 2}]
        def _fake_buscar_dados(pedido):
            if pedido["id"] == 1:
                raise Exception("erro de rede")
            return {"pedido": {"id": 2, "cancelado": "0", "valor_total": 10, "data": "2026-07-29"},
                    "loja_athena": "Loja X", "itens": [], "pagamentos": []}
        gravados = []
        def _fake_gravar(dados):
            gravados.append(dados["pedido"]["id"])
            return {"ok": True}
        with patch("core.i9logic_vendas.BASE_URL", "https://fake"), \
             patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar_pedidos), \
             patch("core.i9logic_vendas._status_sincronizados", return_value={}), \
             patch("core.i9logic_vendas._buscar_dados_pedido", side_effect=_fake_buscar_dados), \
             patch("core.i9logic_vendas._gravar_pedido", side_effect=_fake_gravar), \
             patch("core.i9logic_vendas.time.sleep") as mock_sleep:
            resultado = vendas_i9logic.sincronizar_pedidos_i9logic()
        self.assertEqual(gravados, [2])
        self.assertEqual(len(resultado["erros"]), 1)
        self.assertEqual(resultado["sincronizados"], 1)
        # Achado 5b: 2 pedidos novos -> dorme so' 1 vez (entre eles, nunca depois do ultimo)
        self.assertEqual(mock_sleep.call_count, 1)

    def test_teto_max_pedidos_novos_por_ciclo_e_respeitado(self):
        muitos_pedidos = [{"id": i} for i in range(1, 150)]
        def _fake_paginar_pedidos(endpoint, params, on_pagina=None):
            return muitos_pedidos
        processados = []
        def _fake_buscar_dados(pedido):
            processados.append(pedido["id"])
            return None
        with patch("core.i9logic_vendas.BASE_URL", "https://fake"), \
             patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar_pedidos), \
             patch("core.i9logic_vendas._status_sincronizados", return_value={}), \
             patch("core.i9logic_vendas._buscar_dados_pedido", side_effect=_fake_buscar_dados), \
             patch("core.i9logic_vendas.time.sleep"):
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
             patch("core.i9logic_vendas._status_sincronizados", return_value={}):
            vendas_i9logic.sincronizar_pedidos_i9logic(data_de="2026-01-01", data_ate="2026-01-31")
        self.assertEqual(params_capturados["data_de"], "2026-01-01")
        self.assertEqual(params_capturados["data_ate"], "2026-01-31")

    def test_rate_limit_dorme_entre_pedidos_mas_nao_apos_o_ultimo(self):
        """Achado 5b: espacamento entre pedidos processados no loop, reusando
        RATE_LIMIT_SLEEP_SEGUNDOS de core.i9logic - nunca dorme depois do
        ultimo pedido do lote (mesmo espirito do paginador da Task 1)."""
        from core.i9logic import RATE_LIMIT_SLEEP_SEGUNDOS
        tres_pedidos = [{"id": 1}, {"id": 2}, {"id": 3}]
        def _fake_paginar_pedidos(endpoint, params, on_pagina=None):
            return tres_pedidos
        def _fake_buscar_dados(pedido):
            return None
        with patch("core.i9logic_vendas.BASE_URL", "https://fake"), \
             patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar_pedidos), \
             patch("core.i9logic_vendas._status_sincronizados", return_value={}), \
             patch("core.i9logic_vendas._buscar_dados_pedido", side_effect=_fake_buscar_dados), \
             patch("core.i9logic_vendas.time.sleep") as mock_sleep:
            vendas_i9logic.sincronizar_pedidos_i9logic()
        # 3 pedidos novos -> dorme 2 vezes (entre 1-2 e 2-3), nunca apos o 3o
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_called_with(RATE_LIMIT_SLEEP_SEGUNDOS)

    def test_pedido_unico_novo_nao_dorme(self):
        """Achado 5b: um unico pedido novo no ciclo nao deve gerar nenhum sleep
        (nao ha 'proximo pedido' pra esperar)."""
        def _fake_paginar_pedidos(endpoint, params, on_pagina=None):
            return [{"id": 1}]
        with patch("core.i9logic_vendas.BASE_URL", "https://fake"), \
             patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar_pedidos), \
             patch("core.i9logic_vendas._status_sincronizados", return_value={}), \
             patch("core.i9logic_vendas._buscar_dados_pedido", return_value=None), \
             patch("core.i9logic_vendas.time.sleep") as mock_sleep:
            vendas_i9logic.sincronizar_pedidos_i9logic()
        mock_sleep.assert_not_called()


class TestStatusSincronizados(unittest.TestCase):
    def test_retorna_dict_id_para_status(self):
        async def _fetch(query, *args):
            return [{"id_i9logic": 1, "status": "concluido"}, {"id_i9logic": 2, "status": "cancelado"}]
        with patch("core.i9logic_vendas.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetch=_fetch)
            resultado = vendas_i9logic._status_sincronizados([1, 2])
        self.assertEqual(resultado, {1: "concluido", 2: "cancelado"})

    def test_erro_na_query_loga_e_retorna_dict_vazio(self):
        """Achado 2: excecao na query NAO pode ser engolida em silencio - sem log,
        todo pedido da janela viraria 'novo' pra sempre a cada ciclo (livelock
        silencioso + rajada de API). Confirma que loga e ainda assim retorna {}
        (autocura no proximo ciclo, sem propagar a excecao pro chamador)."""
        async def _fetch(query, *args):
            raise Exception("conexao recusada")
        with patch("core.i9logic_vendas.get_db") as mock_get_db, \
             patch("core.i9logic_vendas.log") as mock_log:
            mock_get_db.return_value = AsyncMock(fetch=_fetch)
            resultado = vendas_i9logic._status_sincronizados([1, 2])
        self.assertEqual(resultado, {})
        mock_log.assert_called_once()
        self.assertIn("Erro ao checar pedidos ja sincronizados", mock_log.call_args[0][1])


class TestAtualizarStatusSeMudou(unittest.TestCase):
    def test_status_inalterado_nao_grava_nada(self):
        pedido = {"id": 1, "cancelado": "0", "valor_total": 10}
        with patch("core.i9logic_vendas.get_db") as mock_get_db:
            resultado = vendas_i9logic._atualizar_status_se_mudou(pedido, "concluido")
        self.assertFalse(resultado)
        mock_get_db.assert_not_called()

    def test_pedido_cancelado_apos_sync_inicial_atualiza_status_e_total(self):
        """Achado 4: pedido ja sincronizado como 'concluido' que agora vem com
        cancelado='1' na listagem em lote deve gerar um UPDATE de status+total,
        sem tocar itens/pagamentos."""
        execucoes = []
        async def _execute(query, *args):
            execucoes.append((query, args))
            return "OK"
        pedido = {"id": 322643, "cancelado": "1", "valor_total": 0}
        with patch("core.i9logic_vendas.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(execute=_execute)
            resultado = vendas_i9logic._atualizar_status_se_mudou(pedido, "concluido")
        self.assertTrue(resultado)
        self.assertEqual(len(execucoes), 1)
        query, args = execucoes[0]
        self.assertIn("UPDATE vendas_pedidos", query)
        self.assertEqual(args, ("cancelado", 0, 322643))

    def test_erro_ao_gravar_loga_e_retorna_false(self):
        async def _execute(query, *args):
            raise Exception("timeout")
        pedido = {"id": 1, "cancelado": "1", "valor_total": 0}
        with patch("core.i9logic_vendas.get_db") as mock_get_db, \
             patch("core.i9logic_vendas.log") as mock_log:
            mock_get_db.return_value = AsyncMock(execute=_execute)
            resultado = vendas_i9logic._atualizar_status_se_mudou(pedido, "concluido")
        self.assertFalse(resultado)
        mock_log.assert_called_once()

    @patch("core.entidades.ao_concluir_venda_avista")
    def test_pedido_que_vira_concluido_aciona_fluxo_de_caixa(self, mock_hook):
        """Pedido ja sincronizado (ex: 'em_andamento' no i9Logic) que agora
        aparece concluido deve gerar entrada no Fluxo de Caixa."""
        async def _execute(query, *args):
            return "OK"
        async def _fetchval(query, *args):
            return 42  # id em vendas_pedidos
        pedido = {"id": 1, "cancelado": "0", "valor_total": 99.9}
        with patch("core.i9logic_vendas.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(execute=_execute, fetchval=_fetchval)
            resultado = vendas_i9logic._atualizar_status_se_mudou(pedido, "algo_diferente")
        self.assertTrue(resultado)
        mock_hook.assert_called_once_with(42)

    @patch("core.entidades.ao_concluir_venda_avista")
    def test_pedido_que_vira_cancelado_nao_aciona_fluxo_de_caixa(self, mock_hook):
        async def _execute(query, *args):
            return "OK"
        pedido = {"id": 1, "cancelado": "1", "valor_total": 0}
        with patch("core.i9logic_vendas.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(execute=_execute)
            resultado = vendas_i9logic._atualizar_status_se_mudou(pedido, "concluido")
        self.assertTrue(resultado)
        mock_hook.assert_not_called()


class TestSincronizarPedidosAtualizaStatus(unittest.TestCase):
    def test_pedido_ja_sincronizado_que_cancelou_gera_update_e_conta_em_atualizados(self):
        """Achado 4: sem essa correcao, cancelamento no PDV depois do sync inicial
        nunca era refletido no Athena - a versao antiga (_ja_sincronizados) so'
        retornava um set e excluia esses pedidos do processamento pra sempre,
        mesmo com o cabecalho da listagem em lote ja trazendo cancelado='1'."""
        def _fake_paginar_pedidos(endpoint, params, on_pagina=None):
            return [{"id": 500, "cancelado": "1", "valor_total": 0, "filial_venda": 1}]
        atualizados_chamados = []
        def _fake_atualizar(pedido, status_atual):
            atualizados_chamados.append((pedido["id"], status_atual))
            return True
        with patch("core.i9logic_vendas.BASE_URL", "https://fake"), \
             patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar_pedidos), \
             patch("core.i9logic_vendas._status_sincronizados", return_value={500: "concluido"}), \
             patch("core.i9logic_vendas._buscar_dados_pedido") as mock_buscar, \
             patch("core.i9logic_vendas._atualizar_status_se_mudou", side_effect=_fake_atualizar):
            resultado = vendas_i9logic.sincronizar_pedidos_i9logic()
        # pedido 500 ja estava sincronizado -> nao reprocessa via _buscar_dados_pedido/_gravar_pedido
        mock_buscar.assert_not_called()
        self.assertEqual(atualizados_chamados, [(500, "concluido")])
        self.assertEqual(resultado["atualizados"], 1)

    def test_pedido_ja_sincronizado_sem_mudanca_de_status_nao_conta_em_atualizados(self):
        def _fake_paginar_pedidos(endpoint, params, on_pagina=None):
            return [{"id": 501, "cancelado": "0", "valor_total": 10, "filial_venda": 1}]
        with patch("core.i9logic_vendas.BASE_URL", "https://fake"), \
             patch("core.i9logic_vendas._paginar", side_effect=_fake_paginar_pedidos), \
             patch("core.i9logic_vendas._status_sincronizados", return_value={501: "concluido"}), \
             patch("core.i9logic_vendas._buscar_dados_pedido") as mock_buscar:
            resultado = vendas_i9logic.sincronizar_pedidos_i9logic()
        mock_buscar.assert_not_called()
        self.assertEqual(resultado["atualizados"], 0)


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

    @patch("core.entidades.ao_concluir_venda_avista")
    def test_pedido_novo_concluido_aciona_fluxo_de_caixa(self, mock_hook):
        dados = {
            "pedido": {"id": 322645, "cancelado": "0", "valor_total": 25.97, "data": "2026-07-29"},
            "loja_athena": "Loja Matriz", "itens": [], "pagamentos": [],
        }
        async def _fetchval(query, *args):
            if "lojas" in query:
                return 7
            if "SELECT id FROM vendas_pedidos WHERE id_i9logic" in query:
                return None
            if "INSERT INTO vendas_pedidos" in query:
                return 60
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
            vendas_i9logic._gravar_pedido(dados)
        mock_hook.assert_called_once_with(60)

    @patch("core.entidades.ao_concluir_venda_avista")
    def test_pedido_novo_cancelado_nao_aciona_fluxo_de_caixa(self, mock_hook):
        dados = {
            "pedido": {"id": 322646, "cancelado": "1", "valor_total": 0, "data": "2026-07-29"},
            "loja_athena": "Loja Matriz", "itens": [], "pagamentos": [],
        }
        async def _fetchval(query, *args):
            if "lojas" in query:
                return 7
            if "SELECT id FROM vendas_pedidos WHERE id_i9logic" in query:
                return None
            if "INSERT INTO vendas_pedidos" in query:
                return 61
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
            vendas_i9logic._gravar_pedido(dados)
        mock_hook.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
