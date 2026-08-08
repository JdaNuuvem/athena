"""Testes — shopee.divergencia (comparacao Athena x saldo Shopee, Task 4/5
da spec de Divergencia de Saldo)."""
import sys, os, unittest, threading
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

async def _mock_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"),
    )), __aexit__=AsyncMock(return_value=None))
    return m

patch("asyncpg.create_pool", side_effect=_mock_pool).start()

import shopee.divergencia as divergencia


class TestExecutarColetaLoja(unittest.TestCase):
    def test_grava_snapshot_por_item(self):
        itens_shopee = [
            {"item_id": 111, "sku": "SKU-A", "name": "Produto A", "status": "NORMAL", "stock": 50, "reserved": 0, "price": 10.0},
            {"item_id": 222, "sku": "SKU-B", "name": "Produto B", "status": "NORMAL", "stock": 30, "reserved": 2, "price": 20.0},
        ]
        gravados = []
        async def fake_fetchrow(query, *params):
            gravados.append(params)
            return {"id": len(gravados)}
        with patch("shopee.divergencia.sync_all_items", return_value=itens_shopee), \
             patch("shopee.divergencia.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetchrow = AsyncMock(side_effect=fake_fetchrow)
            mock_get_db.return_value = db
            resultado = divergencia.executar_coleta_loja(1)
        self.assertEqual(resultado["gravados"], 2)
        self.assertEqual(len(gravados), 2)

    def test_item_sem_sku_real_ainda_e_gravado(self):
        # sku == str(item_id) e' o fallback da propria Shopee quando nao ha' item_sku
        itens_shopee = [{"item_id": 999, "sku": "999", "name": "Sem SKU", "status": "NORMAL", "stock": 5, "reserved": 0, "price": 1.0}]
        async def fake_fetchrow(query, *params):
            return {"id": 1}
        with patch("shopee.divergencia.sync_all_items", return_value=itens_shopee), \
             patch("shopee.divergencia.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetchrow = AsyncMock(side_effect=fake_fetchrow)
            mock_get_db.return_value = db
            resultado = divergencia.executar_coleta_loja(1)
        self.assertEqual(resultado["gravados"], 1)

    def test_erro_de_api_shopee_nao_quebra_retorna_erro(self):
        with patch("shopee.divergencia.sync_all_items", side_effect=Exception("timeout Shopee")):
            resultado = divergencia.executar_coleta_loja(1)
        self.assertIn("erro", resultado)

    def test_itens_que_falharam_ao_gravar_viram_erro_visivel(self):
        """O contador `erros` era calculado e descartado por
        _coleta_em_background — ninguem via que N itens nao entraram."""
        itens_shopee = [{"item_id": 111, "sku": "SKU-A", "stock": 50}]
        async def fetchrow_que_falha(query, *params):
            raise Exception("valor longo demais pra coluna")
        with patch("shopee.divergencia.sync_all_items", return_value=itens_shopee), \
             patch("shopee.divergencia.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch = AsyncMock(return_value=[])
            db.fetchrow = AsyncMock(side_effect=fetchrow_que_falha)
            mock_get_db.return_value = db
            resultado = divergencia.executar_coleta_loja(1)
        self.assertEqual(resultado["erros"], 1)
        self.assertIn("erro", resultado)


class TestRevisadoPersisteEntreColetas(unittest.TestCase):
    """Cada corrida insere linhas NOVAS (data_coleta faz parte da UNIQUE), entao
    sem herdar o flag toda divergencia marcada como revisada reaparecia como
    nova a cada <=30min — esvaziando o unico diferencial do lado Shopee."""

    def _coletar(self, itens_shopee, revisados_anteriores):
        gravados = []
        async def fake_fetchrow(query, *params):
            gravados.append(params)
            return {"id": len(gravados)}
        with patch("shopee.divergencia.sync_all_items", return_value=itens_shopee), \
             patch("shopee.divergencia.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch = AsyncMock(return_value=revisados_anteriores)
            db.fetchrow = AsyncMock(side_effect=fake_fetchrow)
            mock_get_db.return_value = db
            divergencia.executar_coleta_loja(1)
        return gravados

    def test_sku_revisado_com_mesma_qtd_continua_revisado(self):
        gravados = self._coletar(
            [{"item_id": 111, "sku": "SKU-A", "stock": 50}],
            [{"sku": "SKU-A", "qtd_shopee": 50}])
        self.assertTrue(gravados[0][5])  # parametro $6 = revisado

    def test_sku_revisado_com_qtd_diferente_volta_a_nao_revisado(self):
        # Divergencia mudou -> e' outra divergencia, tem que ser revista de novo.
        gravados = self._coletar(
            [{"item_id": 111, "sku": "SKU-A", "stock": 42}],
            [{"sku": "SKU-A", "qtd_shopee": 50}])
        self.assertFalse(gravados[0][5])

    def test_sku_nunca_revisado_entra_como_nao_revisado(self):
        gravados = self._coletar(
            [{"item_id": 222, "sku": "SKU-B", "stock": 30}],
            [{"sku": "SKU-A", "qtd_shopee": 50}])
        self.assertFalse(gravados[0][5])

    def test_falha_ao_ler_estado_anterior_nao_derruba_a_coleta(self):
        """Degradacao aceitavel: perder o flag e' menos grave que perder a coleta."""
        gravados = []
        async def fake_fetchrow(query, *params):
            gravados.append(params)
            return {"id": 1}
        with patch("shopee.divergencia.sync_all_items",
                   return_value=[{"item_id": 111, "sku": "SKU-A", "stock": 50}]), \
             patch("shopee.divergencia.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch = AsyncMock(side_effect=Exception("erro na leitura anterior"))
            db.fetchrow = AsyncMock(side_effect=fake_fetchrow)
            mock_get_db.return_value = db
            resultado = divergencia.executar_coleta_loja(1)
        self.assertEqual(resultado["gravados"], 1)
        self.assertFalse(gravados[0][5])


class TestSnapshotMaisRecente(unittest.TestCase):
    def test_sem_coleta_retorna_none_e_lista_vazia(self):
        with patch("shopee.divergencia.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetchval = AsyncMock(return_value=None)
            mock_get_db.return_value = db
            data_coleta, itens = divergencia.snapshot_mais_recente(1)
        self.assertIsNone(data_coleta)
        self.assertEqual(itens, [])

    def test_com_coleta_retorna_itens_da_corrida_mais_recente(self):
        agora = datetime.now()
        async def fake_fetch(query, *params):
            return [{"sku": "SKU-A", "qtd_shopee": 50, "item_id_shopee": "111"}]
        with patch("shopee.divergencia.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetchval = AsyncMock(return_value=agora)
            db.fetch = AsyncMock(side_effect=fake_fetch)
            mock_get_db.return_value = db
            data_coleta, itens = divergencia.snapshot_mais_recente(1)
        self.assertEqual(data_coleta, agora)
        self.assertEqual(len(itens), 1)


class TestDispararColetaSeNecessario(unittest.TestCase):
    def setUp(self):
        divergencia._coleta_em_andamento.clear()
        divergencia._ultima_falha.clear()
        divergencia._coleta_erro_recente.clear()

    def test_sem_snapshot_dispara_coleta(self):
        with patch("shopee.divergencia.threading.Thread") as mock_thread:
            resultado = divergencia.disparar_coleta_se_necessario(1, None)
        self.assertTrue(resultado)
        mock_thread.assert_called_once()

    def test_snapshot_fresco_nao_dispara(self):
        agora = datetime.now()
        with patch("shopee.divergencia.threading.Thread") as mock_thread:
            resultado = divergencia.disparar_coleta_se_necessario(1, agora)
        self.assertFalse(resultado)
        mock_thread.assert_not_called()

    def test_snapshot_velho_dispara_coleta(self):
        velho = datetime.now() - timedelta(minutes=divergencia.FRESCOR_MAXIMO_MINUTOS + 5)
        with patch("shopee.divergencia.threading.Thread") as mock_thread:
            resultado = divergencia.disparar_coleta_se_necessario(1, velho)
        self.assertTrue(resultado)
        mock_thread.assert_called_once()

    def test_coleta_ja_em_andamento_nao_dispara_segunda_thread(self):
        divergencia._coleta_em_andamento.add(1)
        try:
            with patch("shopee.divergencia.threading.Thread") as mock_thread:
                resultado = divergencia.disparar_coleta_se_necessario(1, None)
            self.assertTrue(resultado)
            mock_thread.assert_not_called()
        finally:
            divergencia._coleta_em_andamento.discard(1)

    def test_falha_recente_segura_nova_coleta_por_cooldown(self):
        """Sem cooldown, uma coleta que falha rapido (token expirado) libera o
        lock em ~1s e o polling de 5s da tela redispara indefinidamente —
        martelando a API da Shopee. Retorna False (nao 'processando') pra tela
        parar de fazer polling e mostrar o erro."""
        divergencia._ultima_falha[1] = datetime.now()
        with patch("shopee.divergencia.threading.Thread") as mock_thread:
            resultado = divergencia.disparar_coleta_se_necessario(1, None)
        self.assertFalse(resultado)
        mock_thread.assert_not_called()

    def test_falha_antiga_ja_saiu_do_cooldown_e_dispara(self):
        divergencia._ultima_falha[1] = datetime.now() - timedelta(
            seconds=divergencia.COOLDOWN_APOS_FALHA_SEGUNDOS + 5)
        with patch("shopee.divergencia.threading.Thread") as mock_thread:
            resultado = divergencia.disparar_coleta_se_necessario(1, None)
        self.assertTrue(resultado)
        mock_thread.assert_called_once()


class TestColetaEmBackgroundRegistraErro(unittest.TestCase):
    def setUp(self):
        divergencia._coleta_em_andamento.clear()
        divergencia._ultima_falha.clear()
        divergencia._coleta_erro_recente.clear()

    def test_erro_retornado_por_executar_coleta_e_registrado(self):
        """executar_coleta_loja CAPTURA suas excecoes e devolve {"erro":...} —
        so' o `except` de _coleta_em_background nunca detectava nada, entao
        _coleta_erro_recente ficava eternamente vazio e a tela nunca sabia da
        falha. O retorno tem que ser inspecionado."""
        with patch("shopee.divergencia.executar_coleta_loja",
                   return_value={"erro": "token Shopee expirado"}):
            divergencia._coleta_em_background(1)
        self.assertEqual(divergencia._coleta_erro_recente.get(1), "token Shopee expirado")
        self.assertIn(1, divergencia._ultima_falha)
        self.assertNotIn(1, divergencia._coleta_em_andamento)

    def test_coleta_bem_sucedida_limpa_erro_e_cooldown(self):
        divergencia._coleta_erro_recente[1] = "falha antiga"
        divergencia._ultima_falha[1] = datetime.now()
        with patch("shopee.divergencia.executar_coleta_loja", return_value={"ok": True, "erros": 0}):
            divergencia._coleta_em_background(1)
        self.assertNotIn(1, divergencia._coleta_erro_recente)
        self.assertNotIn(1, divergencia._ultima_falha)

    def test_excecao_inesperada_tambem_e_registrada(self):
        with patch("shopee.divergencia.executar_coleta_loja", side_effect=Exception("boom")):
            divergencia._coleta_em_background(1)
        self.assertIn("boom", divergencia._coleta_erro_recente.get(1, ""))


class TestListarDivergencias(unittest.TestCase):
    def test_calcula_divergencia_contra_saldo_athena(self):
        itens = [{"id": 1, "sku": "SKU-A", "item_id_shopee": "111", "qtd_shopee": 50}]
        with patch("shopee.divergencia.snapshot_mais_recente", return_value=(datetime.now(), itens)), \
             patch("shopee.divergencia.disparar_coleta_se_necessario", return_value=False), \
             patch("shopee.divergencia.obter_loja", return_value={"id": 1, "nome": "Loja Online"}), \
             patch("core.estoque_saldos.saldos_em_lote", return_value={"SKU-A": 44.0}):
            resultado = divergencia.listar_divergencias(1)
        self.assertEqual(len(resultado["data"]), 1)
        item = resultado["data"][0]
        self.assertEqual(item["qtd_shopee"], 50.0)
        self.assertEqual(item["disponivel_athena"], 44.0)
        self.assertEqual(item["divergencia"], -6.0)
        self.assertEqual(item["classificacao"], "alerta")
        self.assertEqual(resultado["status"], "pronto")

    def test_snapshot_ausente_dispara_coleta_e_retorna_processando(self):
        with patch("shopee.divergencia.snapshot_mais_recente", return_value=(None, [])), \
             patch("shopee.divergencia.disparar_coleta_se_necessario", return_value=True), \
             patch("shopee.divergencia.obter_loja", return_value={"id": 1, "nome": "Loja Online"}):
            resultado = divergencia.listar_divergencias(1)
        self.assertEqual(resultado["data"], [])
        self.assertEqual(resultado["status"], "processando")

    def test_item_revisado_no_banco_aparece_revisado_true(self):
        # snapshot_mais_recente busca 'revisado' no SELECT (fix pos-review) — sem
        # isso o campo sempre caia no default False mesmo apos marcar_revisado.
        itens = [{"id": 1, "sku": "SKU-A", "item_id_shopee": "111", "qtd_shopee": 50, "revisado": True}]
        with patch("shopee.divergencia.snapshot_mais_recente", return_value=(datetime.now(), itens)), \
             patch("shopee.divergencia.disparar_coleta_se_necessario", return_value=False), \
             patch("shopee.divergencia.obter_loja", return_value={"id": 1, "nome": "Loja Online"}), \
             patch("core.estoque_saldos.saldos_em_lote", return_value={"SKU-A": 50.0}):
            resultado = divergencia.listar_divergencias(1)
        self.assertTrue(resultado["data"][0]["revisado"])

    def test_le_saldos_numa_unica_query_em_lote(self):
        """Regressao de performance: era um saldo() por sku dentro do loop."""
        itens = [
            {"id": 1, "sku": "SKU-A", "item_id_shopee": "111", "qtd_shopee": 50},
            {"id": 2, "sku": "SKU-B", "item_id_shopee": "222", "qtd_shopee": 30},
        ]
        with patch("shopee.divergencia.snapshot_mais_recente", return_value=(datetime.now(), itens)), \
             patch("shopee.divergencia.disparar_coleta_se_necessario", return_value=False), \
             patch("shopee.divergencia.obter_loja", return_value={"id": 1, "nome": "Loja Online"}), \
             patch("core.estoque_saldos.saldos_em_lote",
                   return_value={"SKU-A": 50.0, "SKU-B": 30.0}) as mock_lote:
            resultado = divergencia.listar_divergencias(1)
        mock_lote.assert_called_once()
        self.assertEqual(mock_lote.call_args.args[0], ["SKU-A", "SKU-B"])
        self.assertEqual(mock_lote.call_args.args[1], "Loja Online")
        self.assertEqual(len(resultado["data"]), 2)

    def test_falha_ao_ler_saldos_retorna_erro_em_vez_de_zeros(self):
        itens = [{"id": 1, "sku": "SKU-A", "item_id_shopee": "111", "qtd_shopee": 50}]
        with patch("shopee.divergencia.snapshot_mais_recente", return_value=(datetime.now(), itens)), \
             patch("shopee.divergencia.disparar_coleta_se_necessario", return_value=False), \
             patch("shopee.divergencia.obter_loja", return_value={"id": 1, "nome": "Loja Online"}), \
             patch("core.estoque_saldos.saldos_em_lote", side_effect=Exception("conexao caiu")):
            resultado = divergencia.listar_divergencias(1)
        self.assertIn("erro", resultado)
        self.assertNotIn("data", resultado)

    def test_erro_da_ultima_coleta_e_exposto_na_resposta(self):
        """Sem esse campo, uma loja com token Shopee expirado ficava em silencio
        total: lista vazia, nenhum aviso, usuario sem saber que a coleta falhou.
        Mesmo campo que estoque_fisico_por_loja ja' expunha no lado i9Logic."""
        divergencia._coleta_erro_recente[1] = "token Shopee expirado"
        try:
            with patch("shopee.divergencia.snapshot_mais_recente", return_value=(None, [])), \
                 patch("shopee.divergencia.disparar_coleta_se_necessario", return_value=False), \
                 patch("shopee.divergencia.obter_loja", return_value={"id": 1, "nome": "Loja Online"}):
                resultado = divergencia.listar_divergencias(1)
            self.assertEqual(resultado["erro_ultima_coleta"], "token Shopee expirado")
        finally:
            divergencia._coleta_erro_recente.pop(1, None)


class TestMarcarRevisado(unittest.TestCase):
    def test_marca_revisado_true(self):
        async def fake_fetchrow(query, *params):
            return {"id": 1, "sku": "SKU-A", "revisado": True}
        with patch("shopee.divergencia.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetchrow = AsyncMock(side_effect=fake_fetchrow)
            mock_get_db.return_value = db
            resultado = divergencia.marcar_revisado(1)
        self.assertTrue(resultado["ok"])

    def test_snapshot_inexistente_retorna_erro(self):
        async def fake_fetchrow(query, *params):
            return None
        with patch("shopee.divergencia.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetchrow = AsyncMock(side_effect=fake_fetchrow)
            mock_get_db.return_value = db
            resultado = divergencia.marcar_revisado(999)
        self.assertIn("erro", resultado)


class TestAplicarAjusteDivergencia(unittest.TestCase):
    def test_aplica_ajuste_com_sucesso(self):
        async def fake_buscar():
            return {"sku": "SKU-A", "loja_id": 1, "qtd_shopee": 50}
        with patch("shopee.divergencia._buscar_snapshot", return_value={"sku": "SKU-A", "loja_id": 1, "qtd_shopee": 50}), \
             patch("shopee.divergencia._snapshot_mais_recente_id", return_value=1), \
             patch("shopee.divergencia.obter_loja", return_value={"id": 1, "nome": "Loja Online"}), \
             patch("shopee.divergencia.ajustar_absoluto", return_value={"ok": True}) as mock_ajustar, \
             patch("shopee.divergencia.marcar_revisado", return_value={"ok": True}):
            resultado = divergencia.aplicar_ajuste_divergencia(1, usuario_id=7, usuario_nome="Op")
        self.assertTrue(resultado["ok"])
        mock_ajustar.assert_called_once_with(
            "SKU-A", "Loja Online", 50, motivo="ajuste_inventario", usuario_id=7, usuario_nome="Op")

    def test_snapshot_desatualizado_recusa_ajuste(self):
        with patch("shopee.divergencia._buscar_snapshot", return_value={"sku": "SKU-A", "loja_id": 1, "qtd_shopee": 50}), \
             patch("shopee.divergencia._snapshot_mais_recente_id", return_value=2):
            resultado = divergencia.aplicar_ajuste_divergencia(1)
        self.assertIn("erro", resultado)
        self.assertIn("nao e' o mais recente", resultado["erro"])

    def test_snapshot_nao_encontrado_retorna_erro(self):
        with patch("shopee.divergencia._buscar_snapshot", return_value=None):
            resultado = divergencia.aplicar_ajuste_divergencia(999)
        self.assertIn("erro", resultado)

    def test_erro_ao_verificar_frescor_bloqueia_ajuste_fail_closed(self):
        # Guarda de frescor precisa ser fail-closed: se a query de "mais recente"
        # falhar (erro de conexao/timeout), o ajuste NAO pode prosseguir sem
        # checar frescor — bug encontrado na revisao (fail-open silencioso).
        with patch("shopee.divergencia._buscar_snapshot", return_value={"sku": "SKU-A", "loja_id": 1, "qtd_shopee": 50}), \
             patch("shopee.divergencia._snapshot_mais_recente_id", side_effect=Exception("erro de conexao com o banco")), \
             patch("shopee.divergencia.ajustar_absoluto") as mock_ajustar:
            resultado = divergencia.aplicar_ajuste_divergencia(1)
        self.assertIn("erro", resultado)
        mock_ajustar.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
