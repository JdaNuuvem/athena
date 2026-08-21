import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import unittest
from unittest.mock import patch, AsyncMock

# core/memory.py (e outros modulos core/*) chamam _ensure_table()/_ensure_tables() no
# import do modulo, o que abre uma conexao real via asyncpg.create_pool — sem essa conexao
# de fachada, o import de core.compras falha ao tentar resolver um host de banco real.
# Mesmo padrao usado em tests/test_compras_seguranca.py.
async def _fake_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

_patcher = patch("asyncpg.create_pool", side_effect=_fake_pool)
_patcher.start()

from core import compras as core_compras


class TestMapearSituacaoCompra(unittest.TestCase):
    """Achado CRITICO da revisao final: status cru do Bling ('Em andamento',
    'Cancelado', ...) era gravado direto em compras_pedidos.status, o que
    corrompia core.relatorios.fluxo_caixa (soma tudo, sem filtrar cancelado)
    e as comparacoes case-sensitive de core.bi/core.relatorios
    (status != 'cancelado', minusculo). _mapear_situacao_compra traduz pro
    vocabulario interno controlado antes do INSERT/UPDATE."""

    def test_situacao_com_cancel_no_nome_vira_cancelado(self):
        self.assertEqual(
            core_compras._mapear_situacao_compra({"valor": 10, "nome": "Cancelado"}), "cancelado")

    def test_situacao_cancel_case_insensitive(self):
        self.assertEqual(
            core_compras._mapear_situacao_compra({"valor": 10, "nome": "cancelada pelo fornecedor"}), "cancelado")
        self.assertEqual(
            core_compras._mapear_situacao_compra({"valor": 10, "nome": "CANCELADO"}), "cancelado")

    def test_situacao_qualquer_outra_cai_no_valor_neutro(self):
        self.assertEqual(
            core_compras._mapear_situacao_compra({"valor": 6, "nome": "Em andamento"}), "emitido")
        self.assertEqual(
            core_compras._mapear_situacao_compra({"valor": 1, "nome": "Em aberto"}), "emitido")

    def test_situacao_vazia_ou_ausente_cai_no_valor_neutro(self):
        self.assertEqual(core_compras._mapear_situacao_compra({}), "emitido")
        self.assertEqual(core_compras._mapear_situacao_compra(None), "emitido")


class TestSincronizarPedidosCompraBling(unittest.TestCase):
    def test_resolve_fornecedor_existente_por_documento_e_faz_upsert(self):
        fake_db = AsyncMock()
        # 1a chamada: checa se coluna bling_id existe em compras_pedidos -> None (nao existe, sera criada)
        # 2a chamada: busca fornecedor por documento -> encontra id 7
        # 3a chamada: busca pedido existente por bling_id -> None (novo)
        # 4a chamada: refetch do id apos INSERT INTO compras_pedidos -> 42
        fake_db.fetchval.side_effect = [None, 7, None, 42]
        fake_db.fetchrow.return_value = None
        # get_access_token/get_auth_url/listar_pedidos_compra/get_pedido_compra_detalhe sao
        # importados localmente dentro da funcao (from bling_erp import ...), entao o patch
        # tem que mirar no modulo de origem bling_erp, nao em core.compras. get_db, por sua
        # vez, e' importado no topo de core/compras.py, entao patch("core.compras.get_db")
        # funciona normalmente.
        with patch("bling_erp.get_access_token", return_value="tok"), \
             patch("core.compras.get_db", new=AsyncMock(return_value=fake_db)), \
             patch("bling_erp.get_pedido_compra_detalhe", return_value={"data": {
                 "id": 555, "numero": "PC-001", "total": 1200.50,
                 "situacao": {"valor": 6, "nome": "Em andamento"},
                 "data": "2026-08-20", "dataPrevista": "2026-08-27",
                 "fornecedor": {"nome": "Fornecedor XYZ", "numeroDocumento": "12.345.678/0001-99"},
                 "itens": [{"codigo": "SKU-1", "descricao": "Produto 1", "quantidade": 10, "valor": 100.0}],
             }}), \
             patch("bling_erp.listar_pedidos_compra", return_value={"data": [{"id": 555}]}):
            resultado = core_compras.sincronizar_pedidos_compra_bling()
        self.assertEqual(resultado["sync"], 1)
        sqls_executados = [c.args[0] for c in fake_db.execute.call_args_list]
        self.assertTrue(any("ALTER TABLE compras_pedidos ADD COLUMN" in s for s in sqls_executados))
        self.assertTrue(any("INSERT INTO compras_pedidos" in s for s in sqls_executados))
        self.assertTrue(any("INSERT INTO compras_itens" in s for s in sqls_executados))
        # Achado CRITICO: status gravado deve ser o valor mapeado ('emitido'), nunca o
        # texto cru do Bling ('Em andamento').
        insert_pedido_call = next(
            c for c in fake_db.execute.call_args_list if "INSERT INTO compras_pedidos" in c.args[0])
        self.assertIn("emitido", insert_pedido_call.args)
        self.assertNotIn("Em andamento", insert_pedido_call.args)

    def test_situacao_cancelada_no_bling_grava_status_cancelado(self):
        fake_db = AsyncMock()
        fake_db.fetchval.side_effect = [None, None, None, 43]
        fake_db.fetchrow.return_value = None
        with patch("bling_erp.get_access_token", return_value="tok"), \
             patch("core.compras.get_db", new=AsyncMock(return_value=fake_db)), \
             patch("bling_erp.get_pedido_compra_detalhe", return_value={"data": {
                 "id": 556, "numero": "PC-002", "total": 500.0,
                 "situacao": {"valor": 12, "nome": "Cancelado"},
                 "data": "2026-08-20", "dataPrevista": "2026-08-27",
                 "fornecedor": {"nome": "Fornecedor ABC", "numeroDocumento": ""},
                 "itens": [],
             }}), \
             patch("bling_erp.listar_pedidos_compra", return_value={"data": [{"id": 556}]}):
            resultado = core_compras.sincronizar_pedidos_compra_bling()
        self.assertEqual(resultado["sync"], 1)
        insert_pedido_call = next(
            c for c in fake_db.execute.call_args_list if "INSERT INTO compras_pedidos" in c.args[0])
        self.assertIn("cancelado", insert_pedido_call.args)
        self.assertNotIn("Cancelado", insert_pedido_call.args)


class TestSyncComprasAmbiente(unittest.TestCase):
    """Pedido de compra sincronizado em homologacao nao pode entrar
    classificado como producao."""

    @staticmethod
    def _fetchval_por_query(q, *a):
        """Responde pelo conteudo da query em vez de por posicao: o numero de
        fetchvals antes do lookup do pedido varia conforme o payload (fornecedor
        com/sem documento), e side_effect posicional silenciosamente manda o
        sync pro caminho de UPDATE quando a contagem erra."""
        if "FROM compras_pedidos WHERE bling_id" in q:
            return None   # pedido novo -> caminho de INSERT
        return None

    def test_sync_pedido_compra_grava_ambiente_corrente(self):
        fake_db = AsyncMock()
        fake_db.fetchval.side_effect = self._fetchval_por_query
        fake_db.fetchrow.return_value = None
        with patch("bling_erp.get_access_token", return_value="tok"),              patch("bling_erp.get_ambiente", return_value="homologacao"),              patch("core.compras.get_db", new=AsyncMock(return_value=fake_db)),              patch("bling_erp.get_pedido_compra_detalhe", return_value={"data": {
                 "id": 555, "numero": "PC-001", "total": 1000.0,
                 "data": "2026-08-21", "dataPrevista": "2026-08-28",
                 "situacao": {"valor": 6, "nome": "Em andamento"},
                 "fornecedor": {"nome": "Fornecedor XYZ", "numeroDocumento": "12.345.678/0001-99"},
                 "itens": [],
             }}),              patch("bling_erp.listar_pedidos_compra", return_value={"data": [{"id": 555}]}):
            resultado = core_compras.sincronizar_pedidos_compra_bling()
        self.assertEqual(resultado["sync"], 1)
        insert = next(c for c in fake_db.execute.call_args_list
                      if "INSERT INTO compras_pedidos" in c.args[0])
        self.assertIn("homologacao", insert.args)

    def test_sync_pedido_compra_em_producao_grava_producao(self):
        fake_db = AsyncMock()
        fake_db.fetchval.side_effect = self._fetchval_por_query
        fake_db.fetchrow.return_value = None
        with patch("bling_erp.get_access_token", return_value="tok"),              patch("bling_erp.get_ambiente", return_value="producao"),              patch("core.compras.get_db", new=AsyncMock(return_value=fake_db)),              patch("bling_erp.get_pedido_compra_detalhe", return_value={"data": {
                 "id": 556, "numero": "PC-002", "total": 500.0,
                 "data": "2026-08-21", "dataPrevista": "2026-08-28",
                 "situacao": {"valor": 6, "nome": "Em andamento"},
                 "fornecedor": {"nome": "Fornecedor ABC", "numeroDocumento": ""},
                 "itens": [],
             }}),              patch("bling_erp.listar_pedidos_compra", return_value={"data": [{"id": 556}]}):
            resultado = core_compras.sincronizar_pedidos_compra_bling()
        self.assertEqual(resultado["sync"], 1)
        insert = next(c for c in fake_db.execute.call_args_list
                      if "INSERT INTO compras_pedidos" in c.args[0])
        self.assertIn("producao", insert.args)

if __name__ == "__main__":
    unittest.main()
