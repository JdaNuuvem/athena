"""Testes de integracao — import de catalogo i9Logic -> catalogo_produtos."""
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

import core.i9logic_catalogo as catalogo_i9logic
from core.estoque_app_client import EstoqueAppError


def _fake_db_com_conn(conn):
    """db (pool) so expõe acquire() - se o codigo chamar db.transaction()/
    db.fetchrow() por engano, levanta AttributeError imediatamente."""
    db = MagicMock(spec=["acquire"])
    db.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=conn), __aexit__=AsyncMock(return_value=None))
    return db


class TestUpsertProduto(unittest.TestCase):
    def test_codproduto_vazio_retorna_erro(self):
        resultado = catalogo_i9logic._upsert_produto({"id": 1, "codproduto": "  "})
        self.assertIn("erro", resultado)

    def test_grava_de_para_automatico_junto_com_upsert(self):
        chamadas_execute = []

        class TxMock:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return None

        async def _fetchrow(query, *args):
            return {"sku": args[0]}

        async def _execute(query, *args):
            chamadas_execute.append((query, args))
            return "OK"

        conn = AsyncMock()
        conn.transaction = MagicMock(return_value=TxMock())
        conn.fetchrow = _fetchrow
        conn.execute = _execute

        with patch("core.i9logic_catalogo.get_db", return_value=_fake_db_com_conn(conn)):
            resultado = catalogo_i9logic._upsert_produto(
                {"id": 99, "codproduto": "SKU-99", "descricao": "Teste", "ean": "123",
                 "ncm": "0000", "unidademedida": "UN", "peso": 1})

        self.assertEqual(resultado["sku"], "SKU-99")
        self.assertTrue(any("de_para_i9logic" in q for q, _ in chamadas_execute))
        query_depara, args_depara = next((q, a) for q, a in chamadas_execute if "de_para_i9logic" in q)
        self.assertEqual(args_depara, ("99", "SKU-99"))

    def test_upsert_sem_descricao_preserva_descricao_antiga(self):
        """Achado 1 (revisao final): produto do i9Logic sem descricao (string
        vazia) NAO pode apagar a descricao ja existente (ex: vinda do Bling) -
        o upsert precisa usar COALESCE(NULLIF($2,''), catalogo_produtos.descricao)
        no DO UPDATE SET, em vez de sobrescrever cegamente com $2. O fake
        fetchrow abaixo simula a semantica real do COALESCE/NULLIF do Postgres
        em cima de uma linha ja existente, pra provar que descricao (e
        ean/ncm/peso_bruto, mesma logica) preservam o valor antigo quando o
        i9Logic nao manda nada."""
        linha_existente = {
            "descricao": "Descricao Antiga do Bling", "ean": "7890000000000",
            "ncm": "12345678", "peso_bruto": 2.5,
        }

        class TxMock:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return None

        async def _fetchrow(query, *args):
            query_normalizada = " ".join(query.split())
            self.assertIn("COALESCE(NULLIF($2,''), catalogo_produtos.descricao)", query_normalizada)
            self.assertIn("COALESCE($3, catalogo_produtos.ean)", query_normalizada)
            self.assertIn("COALESCE($4, catalogo_produtos.ncm)", query_normalizada)
            self.assertIn("COALESCE(NULLIF($6,0), catalogo_produtos.peso_bruto)", query_normalizada)
            _sku, descricao, ean, ncm, _unidade, peso_bruto, _id = args
            # Simula o COALESCE/NULLIF real do Postgres em cima da linha ja existente
            return {
                "sku": "SKU-99",
                "descricao": descricao if descricao != "" else linha_existente["descricao"],
                "ean": ean if ean is not None else linha_existente["ean"],
                "ncm": ncm if ncm is not None else linha_existente["ncm"],
                "peso_bruto": peso_bruto if peso_bruto != 0 else linha_existente["peso_bruto"],
            }

        async def _execute(query, *args):
            return "OK"

        conn = AsyncMock()
        conn.transaction = MagicMock(return_value=TxMock())
        conn.fetchrow = _fetchrow
        conn.execute = _execute

        with patch("core.i9logic_catalogo.get_db", return_value=_fake_db_com_conn(conn)):
            # produto do i9Logic SEM descricao/ean/ncm/peso - so' codproduto e id
            resultado = catalogo_i9logic._upsert_produto({"id": 99, "codproduto": "SKU-99"})

        self.assertEqual(resultado["descricao"], "Descricao Antiga do Bling")
        self.assertEqual(resultado["ean"], "7890000000000")
        self.assertEqual(resultado["ncm"], "12345678")
        self.assertEqual(resultado["peso_bruto"], 2.5)

    def test_upsert_com_descricao_nova_sobrescreve_a_antiga(self):
        """Contraprova do teste acima: quando o i9Logic MANDA uma descricao de
        verdade, ela deve substituir a antiga normalmente - o COALESCE so'
        preserva quando o valor novo e' vazio/nulo, nao sempre."""
        linha_existente = {"descricao": "Descricao Antiga do Bling"}

        class TxMock:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return None

        async def _fetchrow(query, *args):
            _sku, descricao, *_resto = args
            return {"descricao": descricao if descricao != "" else linha_existente["descricao"]}

        async def _execute(query, *args):
            return "OK"

        conn = AsyncMock()
        conn.transaction = MagicMock(return_value=TxMock())
        conn.fetchrow = _fetchrow
        conn.execute = _execute

        with patch("core.i9logic_catalogo.get_db", return_value=_fake_db_com_conn(conn)):
            resultado = catalogo_i9logic._upsert_produto(
                {"id": 99, "codproduto": "SKU-99", "descricao": "Descricao Nova do i9Logic"})

        self.assertEqual(resultado["descricao"], "Descricao Nova do i9Logic")

    def test_pool_nao_pode_chamar_transaction_diretamente(self):
        """Verifica que chamar db.transaction() diretamente levanta AttributeError."""
        conn = AsyncMock()
        db = _fake_db_com_conn(conn)
        # db tem spec=["acquire"] entao qualquer outro metodo vai dar erro
        with self.assertRaises(AttributeError):
            db.transaction()  # type: ignore


class TestUpsertPagina(unittest.TestCase):
    def test_filtra_apenas_ativo_e_emlinha(self):
        """Testa que _upsert_pagina filtra produtos ativo=1 e emlinha=1"""
        chamadas_upsert = []

        class TxMock:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return None

        async def _upsert_mock(conn, produto):
            chamadas_upsert.append(produto.get("codproduto"))
            return {"sku": produto.get("codproduto")}

        pagina = [
            {"id": 1, "codproduto": "ATIVO1", "ativo": "1", "emlinha": "1"},
            {"id": 2, "codproduto": "INATIVO", "ativo": "0", "emlinha": "1"},
            {"id": 3, "codproduto": "FORADELINHA", "ativo": "1", "emlinha": "0"},
        ]

        conn = AsyncMock()
        conn.transaction = MagicMock(return_value=TxMock())

        with patch("core.i9logic_catalogo._upsert_produto_async", side_effect=_upsert_mock), \
             patch("core.i9logic_catalogo.get_db", return_value=_fake_db_com_conn(conn)):
            importados, erros = catalogo_i9logic._upsert_pagina(pagina)

        self.assertEqual(chamadas_upsert, ["ATIVO1"])
        self.assertEqual(importados, 1)
        self.assertEqual(len(erros), 0)

    def test_produto_malformado_e_pulado_sem_abortar_lote(self):
        """Testa que produtos malformados sao registrados sem abortar o lote"""

        class TxMock:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return None

        async def _upsert_mock(conn, produto):
            if not produto.get("codproduto"):
                return {"erro": "codproduto vazio"}
            return {"sku": produto.get("codproduto")}

        pagina = [
            {"id": 1, "codproduto": "", "ativo": "1", "emlinha": "1"},
            {"id": 2, "codproduto": "OK", "ativo": "1", "emlinha": "1"},
        ]

        conn = AsyncMock()
        conn.transaction = MagicMock(return_value=TxMock())

        with patch("core.i9logic_catalogo._upsert_produto_async", side_effect=_upsert_mock), \
             patch("core.i9logic_catalogo.get_db", return_value=_fake_db_com_conn(conn)):
            importados, erros = catalogo_i9logic._upsert_pagina(pagina)

        self.assertEqual(importados, 1)
        self.assertEqual(len(erros), 1)
        self.assertIn("codproduto vazio", erros[0]["erro"])

    def test_transacao_atomica_com_connexao_adquirida(self):
        """Testa que _upsert_produto_async usa transaction em conn adquirida"""
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
        result = asyncio.run(catalogo_i9logic._upsert_produto_async(conn,
            {"id": 99, "codproduto": "SKU-99", "descricao": "Teste"}))

        self.assertEqual(result["sku"], "SKU-99")
        self.assertIn("enter", chamadas_tx)
        self.assertIn("exit", chamadas_tx)


class TestSincronizarCatalogo(unittest.TestCase):
    def test_falha_ao_buscar_produtos_retorna_erro(self):
        with patch("core.i9logic_catalogo.fetch_produtos", side_effect=EstoqueAppError("produtos", "timeout")):
            resultado = catalogo_i9logic.sincronizar_catalogo_i9logic()
        self.assertIn("erro", resultado)

    def test_agrega_resultados_em_lotes(self):
        """3 produtos com TAMANHO_LOTE=2 vira 2 lotes (2 + 1) - confirma que
        os resultados de cada lote sao somados, nao sobrescritos."""
        produtos = [
            {"id": 1, "codproduto": "P1", "ativo": "1", "emlinha": "1"},
            {"id": 2, "codproduto": "P2", "ativo": "1", "emlinha": "1"},
            {"id": 3, "codproduto": "P3", "ativo": "1", "emlinha": "1"},
        ]

        def _fake_upsert_pagina(pagina):
            return len(pagina), []

        with patch("core.i9logic_catalogo.fetch_produtos", return_value=produtos), \
             patch("core.i9logic_catalogo.TAMANHO_LOTE", 2), \
             patch("core.i9logic_catalogo._upsert_pagina", side_effect=_fake_upsert_pagina):
            resultado = catalogo_i9logic.sincronizar_catalogo_i9logic()

        self.assertEqual(resultado["ok"], True)
        self.assertEqual(resultado["importados"], 3)
        self.assertEqual(resultado["total_recebidos"], 3)
        self.assertEqual(len(resultado["erros_registro"]), 0)

    def test_erros_de_lote_ficam_no_registro_mas_nao_abortam(self):
        produtos = [{"id": 1, "codproduto": "P1"}, {"id": 2, "codproduto": "P2"}]

        def _fake_upsert_pagina(pagina):
            return 1, [{"codproduto": "P2", "erro": "falhou"}]

        with patch("core.i9logic_catalogo.fetch_produtos", return_value=produtos), \
             patch("core.i9logic_catalogo._upsert_pagina", side_effect=_fake_upsert_pagina):
            resultado = catalogo_i9logic.sincronizar_catalogo_i9logic()

        self.assertEqual(resultado["ok"], True)
        self.assertEqual(len(resultado["erros_registro"]), 1)

    def test_sucesso_loga_inicio_e_conclusao(self):
        """sincronizar_catalogo_i9logic nao pode rodar em silencio - sem log
        nenhum, uma falha/lentidao no meio do import fica invisivel nos logs
        do agente ate' o fim."""
        with patch("core.i9logic_catalogo.fetch_produtos", return_value=[{"id": 1, "codproduto": "P1"}]), \
             patch("core.i9logic_catalogo._upsert_pagina", return_value=(1, [])), \
             patch("core.i9logic_catalogo.log") as mock_log:
            catalogo_i9logic.sincronizar_catalogo_i9logic()
        self.assertGreaterEqual(mock_log.call_count, 2)
        mensagens = [c.args[1] for c in mock_log.call_args_list]
        self.assertTrue(any("Iniciando" in m for m in mensagens))
        self.assertTrue(any("concluido" in m for m in mensagens))

    def test_falha_ao_buscar_loga_erro(self):
        with patch("core.i9logic_catalogo.fetch_produtos", side_effect=EstoqueAppError("produtos", "timeout")), \
             patch("core.i9logic_catalogo.log") as mock_log:
            catalogo_i9logic.sincronizar_catalogo_i9logic()
        mensagens = [c.args[1] for c in mock_log.call_args_list]
        self.assertTrue(any("falhou ao buscar produtos" in m for m in mensagens))


class TestSincronizarEstoqueLojasFisicas(unittest.TestCase):
    def test_falha_ao_buscar_retorna_erro(self):
        with patch("core.i9logic_catalogo.fetch_produtos", side_effect=EstoqueAppError("produtos", "timeout")):
            resultado = catalogo_i9logic.sincronizar_estoque_lojas_fisicas()
        self.assertIn("erro", resultado)

    def test_sem_filial_mapeada_retorna_erro_claro(self):
        with patch("core.i9logic_catalogo.fetch_produtos", return_value=[]), \
             patch("core.i9logic_catalogo.fetch_estoques", return_value=[]), \
             patch("core.i9logic_catalogo.listar_mapeamentos", return_value=[]):
            resultado = catalogo_i9logic.sincronizar_estoque_lojas_fisicas()
        self.assertIn("erro", resultado)
        self.assertIn("nenhuma filial", resultado["erro"])

    def test_grava_apenas_estoque_fisico_da_filial_mapeada(self):
        """tipoestoque=2 (contabil) e itens de filial nao mapeada devem ser
        ignorados - so' tipoestoque=1 da filial com de-para conta."""
        produtos = [{"id": 10, "codproduto": "SKU-A"}, {"id": 20, "codproduto": "SKU-B"}]
        estoques = [
            {"filial": 69, "idproduto": 10, "qtd": 5, "tipoestoque": 1},
            {"filial": 69, "idproduto": 10, "qtd": 999, "tipoestoque": 2},  # contabil, ignorado
            {"filial": 999, "idproduto": 20, "qtd": 7, "tipoestoque": 1},  # filial sem mapeamento
        ]
        mapeamentos = [{"id_i9logic": "69", "codigo_athena": "Loja Centro"}]
        gravados = []

        async def _execute(query, *args):
            gravados.append(args)
            return "OK"

        class TxMock:
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return None

        conn = AsyncMock()
        conn.transaction = MagicMock(return_value=TxMock())
        conn.execute = _execute

        with patch("core.i9logic_catalogo.fetch_produtos", return_value=produtos), \
             patch("core.i9logic_catalogo.fetch_estoques", return_value=estoques), \
             patch("core.i9logic_catalogo.listar_mapeamentos", return_value=mapeamentos), \
             patch("core.i9logic_catalogo.get_db", return_value=_fake_db_com_conn(conn)):
            resultado = catalogo_i9logic.sincronizar_estoque_lojas_fisicas()

        self.assertEqual(resultado["ok"], True)
        self.assertEqual(resultado["atualizados"], 1)
        self.assertEqual(gravados, [("SKU-A", "Loja Centro", 5.0)])

    def test_item_sem_sku_mapeado_e_contado_mas_nao_grava(self):
        produtos = []  # nenhum produto conhecido -> idproduto 10 nao resolve sku
        estoques = [{"filial": 69, "idproduto": 10, "qtd": 5, "tipoestoque": 1}]
        mapeamentos = [{"id_i9logic": "69", "codigo_athena": "Loja Centro"}]

        class TxMock:
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return None

        conn = AsyncMock()
        conn.transaction = MagicMock(return_value=TxMock())

        with patch("core.i9logic_catalogo.fetch_produtos", return_value=produtos), \
             patch("core.i9logic_catalogo.fetch_estoques", return_value=estoques), \
             patch("core.i9logic_catalogo.listar_mapeamentos", return_value=mapeamentos), \
             patch("core.i9logic_catalogo.get_db", return_value=_fake_db_com_conn(conn)):
            resultado = catalogo_i9logic.sincronizar_estoque_lojas_fisicas()

        self.assertEqual(resultado["atualizados"], 0)
        self.assertEqual(resultado["sem_sku_mapeado"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
