"""Testes de integracao — import de catalogo/estoque do app de bipagem/estoque -> Athena."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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

import core.produtos_bipador as bipador
from core.estoque_app_client import EstoqueAppError


def _fake_db_com_conn(conn):
    """db (pool) so expõe acquire() - se o codigo chamar db.transaction()/
    db.fetchrow() por engano, levanta AttributeError imediatamente."""
    db = MagicMock(spec=["acquire"])
    db.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=conn), __aexit__=AsyncMock(return_value=None))
    return db


class _TxMock:
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        return None


class TestUpsertProduto(unittest.TestCase):
    def test_codproduto_vazio_retorna_erro(self):
        resultado = bipador._upsert_produto({"produtoId": 1, "codproduto": "  "})
        self.assertIn("erro", resultado)

    def test_grava_de_para_automatico_junto_com_upsert(self):
        chamadas_execute = []

        async def _fetchrow(query, *args):
            return {"sku": args[0]}

        async def _execute(query, *args):
            chamadas_execute.append((query, args))
            return "OK"

        conn = AsyncMock()
        conn.transaction = MagicMock(return_value=_TxMock())
        conn.fetchrow = _fetchrow
        conn.execute = _execute

        with patch("core.produtos_bipador.get_db", return_value=_fake_db_com_conn(conn)):
            resultado = bipador._upsert_produto(
                {"produtoId": 99, "codproduto": "SKU-99", "descricao": "Teste", "ean": "123",
                 "ncm": "0000", "unidademedida": "UN"})

        self.assertEqual(resultado["sku"], "SKU-99")
        self.assertTrue(any("de_para_i9logic" in q for q, _ in chamadas_execute))
        query_depara, args_depara = next((q, a) for q, a in chamadas_execute if "de_para_i9logic" in q)
        self.assertEqual(args_depara, ("99", "SKU-99"))

    def test_upsert_sem_descricao_preserva_descricao_antiga(self):
        """Produto sem descricao (string vazia) NAO pode apagar a descricao
        ja existente (ex: vinda do Bling) - o upsert precisa usar
        COALESCE(NULLIF($2,''), catalogo_produtos.descricao) no DO UPDATE
        SET, em vez de sobrescrever cegamente com $2. O fake fetchrow abaixo
        simula a semantica real do COALESCE/NULLIF do Postgres em cima de
        uma linha ja existente, pra provar que descricao (e ean/ncm, mesma
        logica) preservam o valor antigo quando o payload nao manda nada."""
        linha_existente = {
            "descricao": "Descricao Antiga do Bling", "ean": "7890000000000",
            "ncm": "12345678",
        }

        async def _fetchrow(query, *args):
            query_normalizada = " ".join(query.split())
            self.assertIn("COALESCE(NULLIF($2,''), catalogo_produtos.descricao)", query_normalizada)
            self.assertIn("COALESCE($3, catalogo_produtos.ean)", query_normalizada)
            self.assertIn("COALESCE($4, catalogo_produtos.ncm)", query_normalizada)
            _sku, descricao, ean, ncm, _unidade, _id = args
            # Simula o COALESCE/NULLIF real do Postgres em cima da linha ja existente
            return {
                "sku": "SKU-99",
                "descricao": descricao if descricao != "" else linha_existente["descricao"],
                "ean": ean if ean is not None else linha_existente["ean"],
                "ncm": ncm if ncm is not None else linha_existente["ncm"],
            }

        async def _execute(query, *args):
            return "OK"

        conn = AsyncMock()
        conn.transaction = MagicMock(return_value=_TxMock())
        conn.fetchrow = _fetchrow
        conn.execute = _execute

        with patch("core.produtos_bipador.get_db", return_value=_fake_db_com_conn(conn)):
            # produto SEM descricao/ean/ncm - so' codproduto e produtoId
            resultado = bipador._upsert_produto({"produtoId": 99, "codproduto": "SKU-99"})

        self.assertEqual(resultado["descricao"], "Descricao Antiga do Bling")
        self.assertEqual(resultado["ean"], "7890000000000")
        self.assertEqual(resultado["ncm"], "12345678")

    def test_upsert_com_descricao_nova_sobrescreve_a_antiga(self):
        """Contraprova do teste acima: quando o payload MANDA uma descricao
        de verdade, ela deve substituir a antiga normalmente - o COALESCE
        so' preserva quando o valor novo e' vazio/nulo, nao sempre."""
        linha_existente = {"descricao": "Descricao Antiga do Bling"}

        async def _fetchrow(query, *args):
            _sku, descricao, *_resto = args
            return {"descricao": descricao if descricao != "" else linha_existente["descricao"]}

        async def _execute(query, *args):
            return "OK"

        conn = AsyncMock()
        conn.transaction = MagicMock(return_value=_TxMock())
        conn.fetchrow = _fetchrow
        conn.execute = _execute

        with patch("core.produtos_bipador.get_db", return_value=_fake_db_com_conn(conn)):
            resultado = bipador._upsert_produto(
                {"produtoId": 99, "codproduto": "SKU-99", "descricao": "Descricao Nova"})

        self.assertEqual(resultado["descricao"], "Descricao Nova")

    def test_pool_nao_pode_chamar_transaction_diretamente(self):
        """Verifica que chamar db.transaction() diretamente levanta AttributeError."""
        conn = AsyncMock()
        db = _fake_db_com_conn(conn)
        # db tem spec=["acquire"] entao qualquer outro metodo vai dar erro
        with self.assertRaises(AttributeError):
            db.transaction()  # type: ignore


class TestDeduplicarPorSku(unittest.TestCase):
    def test_primeira_ocorrencia_vence(self):
        produtos = [
            {"codproduto": "A", "descricao": "Primeira", "filialId": 1},
            {"codproduto": "A", "descricao": "Segunda", "filialId": 2},
            {"codproduto": "B", "descricao": "Unica", "filialId": 1},
        ]
        unicos = bipador._deduplicar_por_sku(produtos)
        self.assertEqual(len(unicos), 2)
        skus = {p["codproduto"]: p for p in unicos}
        self.assertEqual(skus["A"]["descricao"], "Primeira")

    def test_codproduto_vazio_e_descartado(self):
        produtos = [{"codproduto": ""}, {"codproduto": "  "}, {"codproduto": "OK"}]
        unicos = bipador._deduplicar_por_sku(produtos)
        self.assertEqual([p["codproduto"] for p in unicos], ["OK"])


class TestUpsertLote(unittest.TestCase):
    def test_filtra_apenas_ativo(self):
        chamadas_upsert = []

        async def _upsert_mock(conn, produto):
            chamadas_upsert.append(produto.get("codproduto"))
            return {"sku": produto.get("codproduto")}

        lote = [
            {"produtoId": 1, "codproduto": "ATIVO1", "ativo": "1"},
            {"produtoId": 2, "codproduto": "INATIVO", "ativo": "0"},
        ]

        conn = AsyncMock()
        conn.transaction = MagicMock(return_value=_TxMock())

        with patch("core.produtos_bipador._upsert_produto_async", side_effect=_upsert_mock), \
             patch("core.produtos_bipador.get_db", return_value=_fake_db_com_conn(conn)):
            importados, erros = bipador._upsert_lote(lote)

        self.assertEqual(chamadas_upsert, ["ATIVO1"])
        self.assertEqual(importados, 1)
        self.assertEqual(len(erros), 0)

    def test_produto_malformado_e_pulado_sem_abortar_lote(self):
        async def _upsert_mock(conn, produto):
            if not produto.get("codproduto"):
                return {"erro": "codproduto vazio"}
            return {"sku": produto.get("codproduto")}

        lote = [
            {"produtoId": 1, "codproduto": "", "ativo": "1"},
            {"produtoId": 2, "codproduto": "OK", "ativo": "1"},
        ]

        conn = AsyncMock()
        conn.transaction = MagicMock(return_value=_TxMock())

        with patch("core.produtos_bipador._upsert_produto_async", side_effect=_upsert_mock), \
             patch("core.produtos_bipador.get_db", return_value=_fake_db_com_conn(conn)):
            importados, erros = bipador._upsert_lote(lote)

        self.assertEqual(importados, 1)
        self.assertEqual(len(erros), 1)
        self.assertIn("codproduto vazio", erros[0]["erro"])

    def test_transacao_atomica_com_conexao_adquirida(self):
        chamadas_tx = []

        class TxMock:
            async def __aenter__(self):
                chamadas_tx.append("enter")
                return self
            async def __aexit__(self, *args):
                chamadas_tx.append("exit")
                return None

        async def _fetchrow(query, *args):
            return {"sku": args[0]}

        async def _execute(query, *args):
            return "OK"

        conn = AsyncMock()
        conn.transaction = MagicMock(return_value=TxMock())
        conn.fetchrow = _fetchrow
        conn.execute = _execute

        import asyncio
        result = asyncio.run(bipador._upsert_produto_async(conn,
            {"produtoId": 99, "codproduto": "SKU-99", "descricao": "Teste"}))

        self.assertEqual(result["sku"], "SKU-99")
        self.assertIn("enter", chamadas_tx)
        self.assertIn("exit", chamadas_tx)


class TestSincronizarCatalogo(unittest.TestCase):
    def test_falha_ao_buscar_produtos_retorna_erro(self):
        with patch("core.produtos_bipador.fetch_produtos_existentes", side_effect=EstoqueAppError("produtos", "timeout")):
            resultado = bipador.sincronizar_catalogo_bipador()
        self.assertIn("erro", resultado)

    def test_agrega_resultados_em_lotes_e_deduplica(self):
        """4 linhas (uma delas repetida por filial) com TAMANHO_LOTE=2 vira
        3 unicos -> 2 lotes (2 + 1) - confirma dedupe + soma entre lotes."""
        produtos = [
            {"produtoId": 1, "codproduto": "P1", "ativo": "1", "filialId": 1},
            {"produtoId": 1, "codproduto": "P1", "ativo": "1", "filialId": 2},  # mesma sku, outra filial
            {"produtoId": 2, "codproduto": "P2", "ativo": "1", "filialId": 1},
            {"produtoId": 3, "codproduto": "P3", "ativo": "1", "filialId": 1},
        ]

        def _fake_upsert_lote(lote):
            return len(lote), []

        with patch("core.produtos_bipador.fetch_produtos_existentes", return_value=produtos), \
             patch("core.produtos_bipador.TAMANHO_LOTE", 2), \
             patch("core.produtos_bipador._upsert_lote", side_effect=_fake_upsert_lote):
            resultado = bipador.sincronizar_catalogo_bipador()

        self.assertEqual(resultado["ok"], True)
        self.assertEqual(resultado["total_recebidos"], 4)
        self.assertEqual(resultado["skus_unicos"], 3)
        self.assertEqual(resultado["importados"], 3)
        self.assertEqual(len(resultado["erros_registro"]), 0)

    def test_erros_de_lote_ficam_no_registro_mas_nao_abortam(self):
        produtos = [{"produtoId": 1, "codproduto": "P1"}, {"produtoId": 2, "codproduto": "P2"}]

        def _fake_upsert_lote(lote):
            return 1, [{"codproduto": "P2", "erro": "falhou"}]

        with patch("core.produtos_bipador.fetch_produtos_existentes", return_value=produtos), \
             patch("core.produtos_bipador._upsert_lote", side_effect=_fake_upsert_lote):
            resultado = bipador.sincronizar_catalogo_bipador()

        self.assertEqual(resultado["ok"], True)
        self.assertEqual(len(resultado["erros_registro"]), 1)

    def test_sucesso_loga_inicio_e_conclusao(self):
        """sincronizar_catalogo_bipador nao pode rodar em silencio - sem log
        nenhum, uma falha/lentidao no meio do import fica invisivel nos logs
        do agente ate' o fim."""
        with patch("core.produtos_bipador.fetch_produtos_existentes", return_value=[{"produtoId": 1, "codproduto": "P1"}]), \
             patch("core.produtos_bipador._upsert_lote", return_value=(1, [])), \
             patch("core.produtos_bipador.log") as mock_log:
            bipador.sincronizar_catalogo_bipador()
        self.assertGreaterEqual(mock_log.call_count, 2)
        mensagens = [c.args[1] for c in mock_log.call_args_list]
        self.assertTrue(any("Iniciando" in m for m in mensagens))
        self.assertTrue(any("concluido" in m for m in mensagens))

    def test_falha_ao_buscar_loga_erro(self):
        with patch("core.produtos_bipador.fetch_produtos_existentes", side_effect=EstoqueAppError("produtos", "timeout")), \
             patch("core.produtos_bipador.log") as mock_log:
            bipador.sincronizar_catalogo_bipador()
        mensagens = [c.args[1] for c in mock_log.call_args_list]
        self.assertTrue(any("falhou ao buscar produtos" in m for m in mensagens))


class TestSincronizarEstoqueLojasFisicas(unittest.TestCase):
    def test_falha_ao_buscar_retorna_erro(self):
        with patch("core.produtos_bipador.fetch_produtos_existentes", side_effect=EstoqueAppError("produtos", "timeout")):
            resultado = bipador.sincronizar_estoque_lojas_fisicas()
        self.assertIn("erro", resultado)

    def test_sem_filial_mapeada_retorna_erro_claro(self):
        with patch("core.produtos_bipador.fetch_produtos_existentes", return_value=[]), \
             patch("core.produtos_bipador.listar_mapeamentos", return_value=[]):
            resultado = bipador.sincronizar_estoque_lojas_fisicas()
        self.assertIn("erro", resultado)
        self.assertIn("nenhuma filial", resultado["erro"])

    def test_grava_qtd_contada_da_filial_mapeada_e_ignora_o_resto(self):
        """qtdContada None (escaneado sem quantidade) e item de filial sem
        de-para devem ser ignorados - so' conta item com qtdContada != None
        de uma filial mapeada."""
        produtos = [
            {"codproduto": "SKU-A", "filialId": 69, "qtdContada": 5},
            {"codproduto": "SKU-B", "filialId": 69, "qtdContada": None},  # sem quantidade, ignorado
            {"codproduto": "SKU-C", "filialId": 999, "qtdContada": 7},  # filial sem mapeamento
        ]
        mapeamentos = [{"id_i9logic": "69", "codigo_athena": "Loja Centro"}]
        gravados = []

        async def _execute(query, *args):
            gravados.append(args)
            return "OK"

        conn = AsyncMock()
        conn.transaction = MagicMock(return_value=_TxMock())
        conn.execute = _execute

        with patch("core.produtos_bipador.fetch_produtos_existentes", return_value=produtos), \
             patch("core.produtos_bipador.listar_mapeamentos", return_value=mapeamentos), \
             patch("core.produtos_bipador.get_db", return_value=_fake_db_com_conn(conn)):
            resultado = bipador.sincronizar_estoque_lojas_fisicas()

        self.assertEqual(resultado["ok"], True)
        self.assertEqual(resultado["atualizados"], 1)
        self.assertEqual(resultado["sem_qtd_contada"], 1)
        self.assertEqual(resultado["sem_filial_mapeada"], 1)
        self.assertEqual(gravados, [("SKU-A", "Loja Centro", 5.0)])
        self.assertEqual(resultado["por_loja"], {"Loja Centro": 1})


if __name__ == "__main__":
    unittest.main(verbosity=2)
