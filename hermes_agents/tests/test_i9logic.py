"""Testes de integracao — reconciliacao i9Logic."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timedelta
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

import core.i9logic as i9logic


class TestDeParaCRUD(unittest.TestCase):
    def test_criar_mapeamento_tipo_invalido_retorna_erro(self):
        resultado = i9logic.criar_mapeamento("invalido", "1", "SKU-1")
        self.assertIn("erro", resultado)

    def test_criar_mapeamento_id_i9logic_vazio_retorna_erro(self):
        resultado = i9logic.criar_mapeamento("produto", "", "SKU-X")
        self.assertIn("erro", resultado)

    def test_criar_mapeamento_produto_grava(self):
        async def _fetchrow(query, *args):
            return {"id": 1, "tipo": args[0], "id_i9logic": args[1], "codigo_athena": args[2]}
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow)
            resultado = i9logic.criar_mapeamento("produto", 29098, "SKU-29098")
        self.assertEqual(resultado["codigo_athena"], "SKU-29098")
        self.assertEqual(resultado["id_i9logic"], "29098")

    def test_buscar_codigo_athena_encontrado(self):
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchval=AsyncMock(return_value="SKU-29098"))
            resultado = i9logic.buscar_codigo_athena("produto", 29098)
        self.assertEqual(resultado, "SKU-29098")

    def test_buscar_codigo_athena_nao_encontrado_retorna_none(self):
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchval=AsyncMock(return_value=None))
            resultado = i9logic.buscar_codigo_athena("produto", 999)
        self.assertIsNone(resultado)

    def test_buscar_id_i9logic_encontrado(self):
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchval=AsyncMock(return_value="63"))
            resultado = i9logic.buscar_id_i9logic("filial", "Loja Matriz")
        self.assertEqual(resultado, "63")

    def test_buscar_id_i9logic_nao_encontrado_retorna_none(self):
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchval=AsyncMock(return_value=None))
            resultado = i9logic.buscar_id_i9logic("filial", "Loja Inexistente")
        self.assertIsNone(resultado)

    def test_listar_mapeamentos_filtra_por_tipo(self):
        async def _fetch(query, *args):
            self.assertIn("tipo=$1", query)
            self.assertEqual(args[0], "filial")
            return [{"id": 1, "tipo": "filial", "id_i9logic": "63", "codigo_athena": "Loja Matriz"}]
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetch=_fetch)
            resultado = i9logic.listar_mapeamentos("filial")
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["codigo_athena"], "Loja Matriz")


class TestMatchingAutomatico(unittest.TestCase):
    def test_matching_tipo_invalido_retorna_erro(self):
        resultado = i9logic.executar_matching_automatico("invalido", [])
        self.assertIn("erro", resultado)

    def test_matching_produto_casa_por_sku_igual(self):
        query_capturada = {}
        async def _fetchval(query, *args):
            query_capturada["query"] = query
            if "catalogo_produtos" in query:
                return args[0] if args[0] == "041725" else None
            return None
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchval=_fetchval, execute=AsyncMock(return_value="OK"))
            resultado = i9logic.executar_matching_automatico(
                "produto", [{"id_i9logic": 29098, "codigo_i9logic": "041725"}])
        self.assertEqual(resultado["casados"], 1)
        self.assertEqual(resultado["nao_casados"], [])
        # Verificar que a query usa igualdade EXATA, nunca fuzzy matching
        self.assertIn("sku=$1", query_capturada["query"].replace(" ", ""))
        self.assertNotIn("ILIKE", query_capturada["query"].upper())
        self.assertNotIn("LIKE", query_capturada["query"].upper())

    def test_matching_produto_nao_casado_vai_pro_relatorio(self):
        async def _fetchval(query, *args):
            return None
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchval=_fetchval, execute=AsyncMock(return_value="OK"))
            resultado = i9logic.executar_matching_automatico(
                "produto", [{"id_i9logic": 999, "codigo_i9logic": "SKU-INEXISTENTE"}])
        self.assertEqual(resultado["casados"], 0)
        self.assertEqual(len(resultado["nao_casados"]), 1)
        self.assertEqual(resultado["nao_casados"][0]["codigo_i9logic"], "SKU-INEXISTENTE")

    def test_matching_filial_consulta_tabela_lojas(self):
        query_capturada = {}
        async def _fetchval(query, *args):
            query_capturada["query"] = query
            self.assertIn("lojas", query)
            return "Loja Matriz"
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchval=_fetchval, execute=AsyncMock(return_value="OK"))
            resultado = i9logic.executar_matching_automatico(
                "filial", [{"id_i9logic": 63, "codigo_i9logic": "Loja Matriz"}])
        self.assertEqual(resultado["casados"], 1)
        # Verificar que a query usa igualdade EXATA, nunca fuzzy matching
        self.assertIn("nome=$1", query_capturada["query"].replace(" ", ""))
        self.assertNotIn("ILIKE", query_capturada["query"].upper())
        self.assertNotIn("LIKE", query_capturada["query"].upper())


class TestPaginarEstoques(unittest.TestCase):
    def _resposta(self, pagina, total, por_pagina=200):
        inicio = (pagina - 1) * por_pagina
        fim = min(inicio + por_pagina, total)
        dados = [{"idproduto": i, "codproduto": f"COD-{i}", "qtd": 10} for i in range(inicio, fim)]
        resp = MagicMock()
        resp.json.return_value = {"data": dados, "total": total}
        resp.raise_for_status.return_value = None
        return resp

    def test_pagina_completa_sem_duplicar_mais_de_200_registros(self):
        total = 450  # 3 paginas: 200, 200, 50
        def _get(url, params=None, headers=None, timeout=None):
            return self._resposta(params["page"], total)
        with patch("core.i9logic.requests.get", side_effect=_get), \
             patch("core.i9logic.time.sleep") as mock_sleep:
            resultado = i9logic._paginar_estoques(63, 1)
        self.assertEqual(len(resultado), total)
        ids = [r["idproduto"] for r in resultado]
        self.assertEqual(len(ids), len(set(ids)), "nao deve haver idproduto duplicado entre paginas")
        self.assertEqual(mock_sleep.call_count, 2)  # dorme entre paginas 1-2 e 2-3, nao depois da ultima
        mock_sleep.assert_called_with(i9logic.RATE_LIMIT_SLEEP_SEGUNDOS)

    def test_pagina_unica_nao_dorme(self):
        def _get(url, params=None, headers=None, timeout=None):
            return self._resposta(params["page"], 50)
        with patch("core.i9logic.requests.get", side_effect=_get), \
             patch("core.i9logic.time.sleep") as mock_sleep:
            resultado = i9logic._paginar_estoques(63, 2)
        self.assertEqual(len(resultado), 50)
        mock_sleep.assert_not_called()

    def test_paginacao_passa_tipoestoque_e_filial_corretos(self):
        chamadas = []
        def _get(url, params=None, headers=None, timeout=None):
            chamadas.append(params)
            return self._resposta(params["page"], 10)
        with patch("core.i9logic.requests.get", side_effect=_get), \
             patch("core.i9logic.time.sleep"):
            i9logic._paginar_estoques(63, 2)
        self.assertEqual(chamadas[0]["filial"], 63)
        self.assertEqual(chamadas[0]["tipoestoque"], 2)


class TestPaginarGenerico(unittest.TestCase):
    def _resposta(self, pagina, total, por_pagina=200):
        inicio = (pagina - 1) * por_pagina
        fim = min(inicio + por_pagina, total)
        dados = [{"id": i} for i in range(inicio, fim)]
        resp = MagicMock()
        resp.json.return_value = {"data": dados, "total": total}
        resp.raise_for_status.return_value = None
        return resp

    def test_retry_recupera_apos_falha_temporaria(self):
        chamadas = {"n": 0}
        def _get(url, params=None, headers=None, timeout=None):
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                raise Exception("timeout")
            return self._resposta(params["page"], 10)
        with patch("core.i9logic.requests.get", side_effect=_get), \
             patch("core.i9logic.time.sleep") as mock_sleep:
            resultado = i9logic._paginar("produtos", {})
        self.assertEqual(len(resultado), 10)
        self.assertEqual(chamadas["n"], 2)

    def test_esgotou_retries_levanta_erro_com_numero_da_pagina(self):
        def _get(url, params=None, headers=None, timeout=None):
            raise Exception("erro persistente")
        with patch("core.i9logic.requests.get", side_effect=_get), \
             patch("core.i9logic.time.sleep"):
            with self.assertRaises(i9logic.I9LogicPaginaError) as ctx:
                i9logic._paginar("produtos", {})
        self.assertEqual(ctx.exception.pagina, 1)

    def test_on_pagina_chamado_a_cada_pagina_com_registros_certos(self):
        total = 450
        paginas_recebidas = []
        def _get(url, params=None, headers=None, timeout=None):
            return self._resposta(params["page"], total)
        with patch("core.i9logic.requests.get", side_effect=_get), \
             patch("core.i9logic.time.sleep"):
            resultado = i9logic._paginar("produtos", {}, on_pagina=lambda regs: paginas_recebidas.append(len(regs)))
        self.assertEqual(paginas_recebidas, [200, 200, 50])
        self.assertEqual(len(resultado), total)

    def test_sem_on_pagina_nao_quebra(self):
        def _get(url, params=None, headers=None, timeout=None):
            return self._resposta(params["page"], 5)
        with patch("core.i9logic.requests.get", side_effect=_get), \
             patch("core.i9logic.time.sleep"):
            resultado = i9logic._paginar("produtos", {})
        self.assertEqual(len(resultado), 5)


class TestGravarSnapshot(unittest.TestCase):
    def test_grava_resolvendo_sku_e_loja_via_depara(self):
        chamadas_fetchval = []
        async def _fetchval(query, *args):
            chamadas_fetchval.append((query, args))
            if "tipo='produto'" in query:
                return "SKU-29098"
            if "tipo='filial'" in query:
                return "Loja Matriz"
            return None
        async def _fetchrow(query, *args):
            return {"id": 1, "idproduto_i9logic": args[0], "codproduto_i9logic": args[1],
                    "sku_athena": args[2], "filial_i9logic": args[3], "loja_athena": args[4],
                    "qtd_fisico": args[5], "qtd_contabil": args[6], "divergencia": args[6] - args[5]}
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchval=_fetchval, fetchrow=_fetchrow)
            resultado = i9logic.gravar_snapshot(29098, "041725", 63, 165, 348)
        self.assertEqual(resultado["sku_athena"], "SKU-29098")
        self.assertEqual(resultado["loja_athena"], "Loja Matriz")
        self.assertEqual(resultado["divergencia"], 183)

    def test_grava_com_athena_nulo_quando_sem_depara(self):
        async def _fetchval(query, *args):
            return None
        async def _fetchrow(query, *args):
            return {"id": 1, "idproduto_i9logic": args[0], "codproduto_i9logic": args[1],
                    "sku_athena": args[2], "filial_i9logic": args[3], "loja_athena": args[4],
                    "qtd_fisico": args[5], "qtd_contabil": args[6]}
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchval=_fetchval, fetchrow=_fetchrow)
            resultado = i9logic.gravar_snapshot(999, "SEM-DEPARA", 1, 10, 10)
        self.assertIsNone(resultado["sku_athena"])
        self.assertIsNone(resultado["loja_athena"])


class TestClassificarDivergencia(unittest.TestCase):
    def test_sem_divergencia_e_sem_acao(self):
        self.assertEqual(i9logic.classificar_divergencia(100, 100), "sem_acao")

    def test_divergencia_dentro_da_tolerancia_e_sem_acao(self):
        self.assertEqual(i9logic.classificar_divergencia(100, 100.5), "sem_acao")

    def test_divergencia_pequena_e_so_registrada(self):
        # divergencia = 2, abaixo do limiar absoluto (5) e percentual (10% de 100 = 10)
        self.assertEqual(i9logic.classificar_divergencia(100, 102), "registrado")

    def test_divergencia_exatamente_no_limiar_absoluto_e_alerta(self):
        # divergencia = 5, >= LIMIAR_ALERTA_ABSOLUTO
        self.assertEqual(i9logic.classificar_divergencia(100, 105), "alerta")

    def test_divergencia_exatamente_no_limiar_percentual_e_alerta(self):
        # fisico=10, divergencia=1 -> 1/10 = 10% exato, mas abs(1) < 5 -> ainda alerta pelo percentual
        self.assertEqual(i9logic.classificar_divergencia(10, 11), "alerta")

    def test_divergencia_grande_bate_os_dois_limiares_e_alerta(self):
        self.assertEqual(i9logic.classificar_divergencia(165, 348), "alerta")

    def test_qtd_fisico_zero_usa_base_minima_um_no_percentual(self):
        # fisico=0, comparacao=3 -> divergencia=3, abaixo do absoluto (5); percentual usa
        # max(0,1)=1 como base -> 3/1 = 300% -> alerta
        self.assertEqual(i9logic.classificar_divergencia(0, 3), "alerta")


class TestListarERevisar(unittest.TestCase):
    def test_listar_itens_para_revisao_filtra_por_tolerancia(self):
        async def _fetch(query, *args):
            self.assertEqual(args[0], False)
            return [{"id": 1, "divergencia": 183}]
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetch=_fetch)
            resultado = i9logic.listar_itens_para_revisao()
        self.assertEqual(len(resultado), 1)

    def test_marcar_revisado_nao_encontrado_retorna_erro(self):
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchrow=AsyncMock(return_value=None))
            resultado = i9logic.marcar_revisado(999)
        self.assertIn("erro", resultado)

    def test_marcar_revisado_encontrado_retorna_ok(self):
        async def _fetchrow(query, *args):
            return {"id": args[0], "revisado": True}
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow)
            resultado = i9logic.marcar_revisado(1)
        self.assertTrue(resultado["ok"])


class TestAplicarAjusteDivergencia(unittest.TestCase):
    def test_snapshot_nao_encontrado_retorna_erro(self):
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchrow=AsyncMock(return_value=None))
            resultado = i9logic.aplicar_ajuste_divergencia(999)
        self.assertIn("erro", resultado)

    def test_snapshot_sem_depara_resolvido_retorna_erro(self):
        async def _fetchrow(query, *args):
            return {"id": 1, "sku_athena": None, "loja_athena": None, "qtd_fisico": 165}
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow)
            resultado = i9logic.aplicar_ajuste_divergencia(1)
        self.assertIn("erro", resultado)

    def test_ajusta_via_ajustar_absoluto_e_marca_revisado(self):
        chamadas = {"n": 0}
        async def _fetchrow(query, *args):
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                return {"id": 1, "sku_athena": "SKU-29098", "loja_athena": "Loja Matriz", "qtd_fisico": 165}
            return {"id": 1, "revisado": True}
        with patch("core.i9logic.get_db") as mock_get_db, \
             patch("core.estoque.ajustar_absoluto", return_value={"ok": True, "atual": 165}) as mock_ajustar:
            # fetchval = guarda de frescor (mais recente) - retorna o MESMO id do
            # snapshot sendo testado, senao a guarda nova recusaria o ajuste.
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow, fetchval=AsyncMock(return_value=1))
            resultado = i9logic.aplicar_ajuste_divergencia(1, usuario_id=1, usuario_nome="Ana")
        mock_ajustar.assert_called_once_with(
            "SKU-29098", "Loja Matriz", 165.0, motivo="ajuste_inventario", usuario_id=1, usuario_nome="Ana")
        self.assertTrue(resultado["ok"])

    def test_ajustar_absoluto_com_erro_nao_marca_revisado(self):
        async def _fetchrow(query, *args):
            return {"id": 1, "sku_athena": "SKU-X", "loja_athena": "Loja Y", "qtd_fisico": 165}
        with patch("core.i9logic.get_db") as mock_get_db, \
             patch("core.estoque.ajustar_absoluto", return_value={"erro": "falha simulada"}):
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow, fetchval=AsyncMock(return_value=1))
            resultado = i9logic.aplicar_ajuste_divergencia(1)
        self.assertIn("erro", resultado)

    def test_ajuste_aplicado_mas_marcar_revisado_falha_propaga_erro(self):
        # ajustar_absoluto tem sucesso, mas o UPDATE de marcar_revisado nao encontra
        # mais a linha (ex: deletada concorrentemente) -> nao pode mascarar como ok.
        chamadas = {"n": 0}
        async def _fetchrow(query, *args):
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                return {"id": 1, "sku_athena": "SKU-29098", "loja_athena": "Loja Matriz", "qtd_fisico": 165}
            return None
        with patch("core.i9logic.get_db") as mock_get_db, \
             patch("core.estoque.ajustar_absoluto", return_value={"ok": True, "atual": 165}):
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow, fetchval=AsyncMock(return_value=1))
            resultado = i9logic.aplicar_ajuste_divergencia(1)
        self.assertIn("erro", resultado)
        self.assertNotIn("ok", resultado)

    def test_qtd_fisico_zero_sem_confirmar_zerar_recusa_e_nao_ajusta(self):
        async def _fetchrow(query, *args):
            return {"id": 1, "sku_athena": "SKU-29098", "loja_athena": "Loja Matriz", "qtd_fisico": 0}
        with patch("core.i9logic.get_db") as mock_get_db, \
             patch("core.estoque.ajustar_absoluto") as mock_ajustar:
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow, fetchval=AsyncMock(return_value=1))
            resultado = i9logic.aplicar_ajuste_divergencia(1)
        self.assertIn("erro", resultado)
        mock_ajustar.assert_not_called()

    def test_qtd_fisico_zero_com_confirmar_zerar_aplica_normalmente(self):
        chamadas = {"n": 0}
        async def _fetchrow(query, *args):
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                return {"id": 1, "sku_athena": "SKU-29098", "loja_athena": "Loja Matriz", "qtd_fisico": 0}
            return {"id": 1, "revisado": True}
        with patch("core.i9logic.get_db") as mock_get_db, \
             patch("core.estoque.ajustar_absoluto", return_value={"ok": True, "atual": 0}) as mock_ajustar:
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow, fetchval=AsyncMock(return_value=1))
            resultado = i9logic.aplicar_ajuste_divergencia(1, confirmar_zerar=True)
        mock_ajustar.assert_called_once()
        self.assertTrue(resultado["ok"])

    def test_qtd_fisico_none_sem_confirmar_zerar_recusa(self):
        async def _fetchrow(query, *args):
            return {"id": 1, "sku_athena": "SKU-29098", "loja_athena": "Loja Matriz", "qtd_fisico": None}
        with patch("core.i9logic.get_db") as mock_get_db, \
             patch("core.estoque.ajustar_absoluto") as mock_ajustar:
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow, fetchval=AsyncMock(return_value=1))
            resultado = i9logic.aplicar_ajuste_divergencia(1)
        self.assertIn("erro", resultado)
        mock_ajustar.assert_not_called()

    def test_snapshot_nao_e_o_mais_recente_recusa_e_nao_ajusta(self):
        async def _fetchrow(query, *args):
            return {"id": 1, "sku_athena": "SKU-29098", "loja_athena": "Loja Matriz", "qtd_fisico": 165}
        with patch("core.i9logic.get_db") as mock_get_db, \
             patch("core.estoque.ajustar_absoluto") as mock_ajustar:
            # id_mais_recente (42) diferente do snapshot_id sendo ajustado (1)
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow, fetchval=AsyncMock(return_value=42))
            resultado = i9logic.aplicar_ajuste_divergencia(1)
        self.assertIn("erro", resultado)
        mock_ajustar.assert_not_called()


class TestCompararComAthena(unittest.TestCase):
    def test_sem_snapshot_retorna_erro(self):
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchrow=AsyncMock(return_value=None))
            resultado = i9logic.comparar_com_athena("SKU-X", "Loja Y")
        self.assertIn("erro", resultado)

    def test_com_snapshot_calcula_divergencia_contra_saldo_athena(self):
        async def _fetchrow(query, *args):
            return {"qtd_fisico": 100, "data_coleta": "2026-07-29T00:00:00"}
        with patch("core.i9logic.get_db") as mock_get_db, \
             patch("core.estoque_saldos.saldo", return_value=95.0):
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow)
            resultado = i9logic.comparar_com_athena("SKU-X", "Loja Y")
        self.assertEqual(resultado["disponivel_athena"], 95.0)
        self.assertEqual(resultado["qtd_fisico_i9logic"], 100.0)
        self.assertEqual(resultado["divergencia"], -5.0)
        self.assertEqual(resultado["classificacao"], "alerta")


class TestExecutarColeta(unittest.TestCase):
    def test_coleta_filial_pareia_fisico_e_contabil_por_idproduto(self):
        def _paginar(filial, tipoestoque):
            if tipoestoque == 1:
                return [{"idproduto": 1, "codproduto": "A", "qtd": 10},
                        {"idproduto": 2, "codproduto": "B", "qtd": 20}]
            # contabeis em ordem DIFERENTE de fisicos - prova que o pareamento nao e por posicao
            return [{"idproduto": 2, "codproduto": "B", "qtd": 20},
                    {"idproduto": 1, "codproduto": "A", "qtd": 15}]
        gravados = []
        def _gravar(idproduto, codproduto, filial, qtd_fisico, qtd_contabil, data_coleta=None):
            gravados.append((idproduto, qtd_fisico, qtd_contabil))
            return {"ok": True}
        with patch("core.i9logic._paginar_estoques", side_effect=_paginar), \
             patch("core.i9logic.gravar_snapshot", side_effect=_gravar):
            resultado = i9logic.executar_coleta_filial(63)
        self.assertEqual(resultado["gravados"], 2)
        self.assertIn((1, 10, 15), gravados)
        self.assertIn((2, 20, 20), gravados)

    def test_coleta_filial_usa_mesmo_data_coleta_pra_todas_as_linhas(self):
        def _paginar(filial, tipoestoque):
            return [{"idproduto": 1, "codproduto": "A", "qtd": 10},
                    {"idproduto": 2, "codproduto": "B", "qtd": 20}]
        datas_usadas = []
        def _gravar(idproduto, codproduto, filial, qtd_fisico, qtd_contabil, data_coleta=None):
            datas_usadas.append(data_coleta)
            return {"ok": True}
        with patch("core.i9logic._paginar_estoques", side_effect=_paginar), \
             patch("core.i9logic.gravar_snapshot", side_effect=_gravar):
            i9logic.executar_coleta_filial(63)
        self.assertEqual(len(datas_usadas), 2)
        self.assertEqual(datas_usadas[0], datas_usadas[1])

    def test_coleta_filial_processa_produto_so_em_contabil_com_qtd_fisico_zero(self):
        def _paginar(filial, tipoestoque):
            if tipoestoque == 1:
                # produto 1 em fisicos, mas nao 2
                return [{"idproduto": 1, "codproduto": "A", "qtd": 10}]
            # produto 2 so em contabeis, nao em fisicos - auditoria importante
            return [{"idproduto": 1, "codproduto": "A", "qtd": 15},
                    {"idproduto": 2, "codproduto": "B", "qtd": 50}]
        gravados = []
        def _gravar(idproduto, codproduto, filial, qtd_fisico, qtd_contabil, data_coleta=None):
            gravados.append((idproduto, qtd_fisico, qtd_contabil))
            return {"ok": True}
        with patch("core.i9logic._paginar_estoques", side_effect=_paginar), \
             patch("core.i9logic.gravar_snapshot", side_effect=_gravar):
            resultado = i9logic.executar_coleta_filial(63)
        self.assertEqual(resultado["gravados"], 2)
        # produto 1: fisico 10, contabil 15
        self.assertIn((1, 10, 15), gravados)
        # produto 2: fisico 0 (nao existe em fisicos), contabil 50 (so em contabeis)
        self.assertIn((2, 0, 50), gravados)

    def test_coleta_todas_filiais_itera_mapeamentos(self):
        with patch("core.i9logic.BASE_URL", "https://fake.i9logic.test"), \
             patch("core.i9logic.listar_mapeamentos", return_value=[
                {"id_i9logic": "63", "codigo_athena": "Loja Matriz"},
                {"id_i9logic": "64", "codigo_athena": "Loja Filial"}]), \
             patch("core.i9logic.executar_coleta_filial", return_value={"ok": True, "gravados": 5}) as mock_coleta:
            resultado = i9logic.executar_coleta_todas_filiais()
        self.assertEqual(resultado["filiais_processadas"], 2)
        self.assertEqual(mock_coleta.call_count, 2)
        mock_coleta.assert_any_call(63)
        mock_coleta.assert_any_call(64)

    def test_coleta_todas_filiais_erro_numa_filial_nao_aborta_as_demais(self):
        with patch("core.i9logic.BASE_URL", "https://fake.i9logic.test"), \
             patch("core.i9logic.listar_mapeamentos", return_value=[
                {"id_i9logic": "63", "codigo_athena": "Loja Matriz"},
                {"id_i9logic": "64", "codigo_athena": "Loja Filial"}]), \
             patch("core.i9logic.executar_coleta_filial",
                   side_effect=[{"ok": True}, Exception("erro de rede")]):
            resultado = i9logic.executar_coleta_todas_filiais()
        self.assertEqual(resultado["filiais_processadas"], 2)
        self.assertEqual(resultado["resultados"][0], {"ok": True})
        self.assertIn("erro", resultado["resultados"][1])

    def test_coleta_todas_filiais_sem_base_url_retorna_erro_sem_listar_mapeamentos(self):
        with patch("core.i9logic.BASE_URL", ""), \
             patch("core.i9logic.listar_mapeamentos") as mock_listar:
            resultado = i9logic.executar_coleta_todas_filiais()
        self.assertIn("erro", resultado)
        mock_listar.assert_not_called()


class TestSeedInicial(unittest.TestCase):
    def test_sem_snapshot_retorna_erro(self):
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchrow=AsyncMock(return_value=None))
            resultado = i9logic.seed_inicial("SKU-X", "Loja Y")
        self.assertIn("erro", resultado)

    def test_quantidade_zero_ou_negativa_nao_aplica_seed(self):
        async def _fetchrow(query, *args):
            return {"qtd_fisico": 0}
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow)
            resultado = i9logic.seed_inicial("SKU-X", "Loja Y")
        self.assertIn("erro", resultado)

    def test_seed_chama_entrada_com_motivo_import_i9logic(self):
        async def _fetchrow(query, *args):
            return {"qtd_fisico": 165}
        with patch("core.i9logic.get_db") as mock_get_db, \
             patch("core.estoque.entrada", return_value={"ok": True}) as mock_entrada:
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow)
            resultado = i9logic.seed_inicial("SKU-X", "Loja Y", usuario_id=1, usuario_nome="Ana")
        mock_entrada.assert_called_once_with(
            "SKU-X", "Loja Y", 165.0, motivo="import_i9logic", usuario_id=1, usuario_nome="Ana")
        self.assertTrue(resultado["ok"])


class ThreadSincrona:
    """Substitui threading.Thread nos testes — .start() roda o target na
    hora, na mesma thread, pra nao depender de timing real."""
    def __init__(self, target, args=(), daemon=None, name=None):
        self._target = target
        self._args = args

    def start(self):
        self._target(*self._args)


class TestSnapshotMaisRecente(unittest.TestCase):
    """snapshot_mais_recente(filial_id) le a corrida mais recente do
    i9logic_estoque_snapshot, enriquecida com descricao via
    catalogo_produtos.id_i9logic."""

    def test_sem_snapshot_retorna_none_e_lista_vazia(self):
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(fetchval=AsyncMock(return_value=None))
            data_coleta, itens = i9logic.snapshot_mais_recente(63)
        self.assertIsNone(data_coleta)
        self.assertEqual(itens, [])

    def test_com_snapshot_devolve_data_coleta_e_itens(self):
        agora = datetime.now()
        async def _fetch(query, *args):
            return [{"idproduto": 1, "codproduto": "COD-1", "sku_athena": "SKU-1",
                      "qtd": 10, "descricao": "Produto 1"}]
        with patch("core.i9logic.get_db") as mock_get_db:
            mock_get_db.return_value = AsyncMock(
                fetchval=AsyncMock(return_value=agora), fetch=_fetch)
            data_coleta, itens = i9logic.snapshot_mais_recente(63)
        self.assertEqual(data_coleta, agora)
        self.assertEqual(len(itens), 1)
        self.assertEqual(itens[0]["sku_athena"], "SKU-1")


class TestColetaEmBackground(unittest.TestCase):
    """_coleta_em_background roda executar_coleta_filial fora do request,
    registrando erro (se houver) e sempre liberando o lock ao final."""

    def setUp(self):
        i9logic._coleta_em_andamento.clear()
        i9logic._coleta_erro_recente.clear()

    def test_sucesso_limpa_erro_anterior_e_libera_lock(self):
        i9logic._coleta_em_andamento.add(63)
        i9logic._coleta_erro_recente[63] = "erro antigo"
        with patch("core.i9logic.executar_coleta_filial", return_value={"ok": True}):
            i9logic._coleta_em_background(63)
        self.assertNotIn(63, i9logic._coleta_em_andamento)
        self.assertNotIn(63, i9logic._coleta_erro_recente)

    def test_falha_registra_erro_e_libera_lock(self):
        i9logic._coleta_em_andamento.add(63)
        with patch("core.i9logic.executar_coleta_filial", side_effect=Exception("timeout")):
            i9logic._coleta_em_background(63)
        self.assertNotIn(63, i9logic._coleta_em_andamento)
        self.assertEqual(i9logic._coleta_erro_recente[63], "timeout")


class TestEstoqueFisicoPorLoja(unittest.TestCase):
    """estoque_fisico_por_loja(loja) resolve o nome da loja pra filial
    i9Logic via de-para e devolve o fisico do snapshot mais recente,
    disparando coleta em background quando ausente/desatualizado — nunca
    bloqueia o request esperando a paginacao (filiais grandes estouram
    timeout de proxy). Erro claro se a loja nao tiver mapeamento de filial."""

    def setUp(self):
        i9logic._coleta_em_andamento.clear()
        i9logic._coleta_erro_recente.clear()

    def test_loja_sem_mapeamento_retorna_erro_claro(self):
        with patch("core.i9logic.buscar_id_i9logic", return_value=None):
            resultado = i9logic.estoque_fisico_por_loja("Loja Sem Mapa")
        self.assertIn("erro", resultado)
        self.assertIn("mapeamento", resultado["erro"])

    def test_sem_snapshot_dispara_coleta_e_retorna_processando(self):
        with patch("core.i9logic.buscar_id_i9logic", return_value="63"), \
             patch("core.i9logic.snapshot_mais_recente", return_value=(None, [])), \
             patch("core.i9logic.threading.Thread", ThreadSincrona), \
             patch("core.i9logic.executar_coleta_filial", return_value={"ok": True}) as mock_coleta:
            resultado = i9logic.estoque_fisico_por_loja("Loja Matriz")
        mock_coleta.assert_called_once_with(63)
        self.assertEqual(resultado["status"], "processando")
        self.assertEqual(resultado["data"], [])
        self.assertNotIn(63, i9logic._coleta_em_andamento)  # ThreadSincrona ja rodou e liberou

    def test_coleta_ja_em_andamento_nao_dispara_de_novo(self):
        i9logic._coleta_em_andamento.add(63)
        with patch("core.i9logic.buscar_id_i9logic", return_value="63"), \
             patch("core.i9logic.snapshot_mais_recente", return_value=(None, [])), \
             patch("core.i9logic.threading.Thread") as mock_thread:
            resultado = i9logic.estoque_fisico_por_loja("Loja Matriz")
        mock_thread.assert_not_called()
        self.assertEqual(resultado["status"], "processando")

    def test_snapshot_fresco_retorna_pronto_sem_disparar_coleta(self):
        agora = datetime.now()
        itens = [{"idproduto": 1, "codproduto": "COD-1", "sku_athena": "SKU-1", "qtd": 10, "descricao": "P1"}]
        with patch("core.i9logic.buscar_id_i9logic", return_value="63"), \
             patch("core.i9logic.snapshot_mais_recente", return_value=(agora, itens)), \
             patch("core.i9logic.threading.Thread") as mock_thread:
            resultado = i9logic.estoque_fisico_por_loja("Loja Matriz")
        mock_thread.assert_not_called()
        self.assertEqual(resultado["status"], "pronto")
        self.assertEqual(resultado["data"], itens)
        self.assertEqual(resultado["coletado_em"], agora.isoformat())

    def test_snapshot_velho_dispara_nova_coleta_mas_devolve_dado_stale(self):
        velho = datetime.now() - timedelta(minutes=i9logic.FRESCOR_MAXIMO_MINUTOS + 5)
        itens = [{"idproduto": 1, "codproduto": "COD-1", "sku_athena": "SKU-1", "qtd": 10, "descricao": "P1"}]
        with patch("core.i9logic.buscar_id_i9logic", return_value="63"), \
             patch("core.i9logic.snapshot_mais_recente", return_value=(velho, itens)), \
             patch("core.i9logic.threading.Thread") as mock_thread:
            resultado = i9logic.estoque_fisico_por_loja("Loja Matriz")
        mock_thread.assert_called_once()
        self.assertEqual(resultado["status"], "processando")
        self.assertEqual(resultado["data"], itens)  # stale-while-revalidate

    def test_erro_da_ultima_tentativa_aparece_mas_nao_bloqueia_retry(self):
        i9logic._coleta_erro_recente[63] = "timeout"
        with patch("core.i9logic.buscar_id_i9logic", return_value="63"), \
             patch("core.i9logic.snapshot_mais_recente", return_value=(None, [])), \
             patch("core.i9logic.threading.Thread") as mock_thread:
            resultado = i9logic.estoque_fisico_por_loja("Loja Matriz")
        mock_thread.assert_called_once()  # dispara retry mesmo com erro anterior
        self.assertEqual(resultado.get("erro_ultima_coleta"), "timeout")
        self.assertEqual(resultado["status"], "processando")


class TestClassificarDivergenciaReexport(unittest.TestCase):
    """i9logic.classificar_divergencia agora e' um re-export de
    core.estoque_divergencia — este teste confirma que o comportamento nao
    mudou apos a extracao."""
    def test_dentro_da_tolerancia_zero_e_sem_acao(self):
        self.assertEqual(i9logic.classificar_divergencia(100, 100.3), "sem_acao")

    def test_acima_do_limiar_absoluto_e_alerta(self):
        self.assertEqual(i9logic.classificar_divergencia(100, 106), "alerta")

    def test_acima_do_limiar_percentual_e_alerta(self):
        self.assertEqual(i9logic.classificar_divergencia(10, 12), "alerta")

    def test_divergencia_pequena_mas_fora_da_tolerancia_e_registrado(self):
        self.assertEqual(i9logic.classificar_divergencia(100, 102), "registrado")

    def test_constantes_reexportadas(self):
        from core.estoque_divergencia import TOLERANCIA_ZERO, LIMIAR_ALERTA_ABSOLUTO, LIMIAR_ALERTA_PERCENTUAL
        self.assertEqual(i9logic.TOLERANCIA_ZERO, TOLERANCIA_ZERO)
        self.assertEqual(i9logic.LIMIAR_ALERTA_ABSOLUTO, LIMIAR_ALERTA_ABSOLUTO)
        self.assertEqual(i9logic.LIMIAR_ALERTA_PERCENTUAL, LIMIAR_ALERTA_PERCENTUAL)


class TestListarDivergenciasAthena(unittest.TestCase):
    def test_loja_sem_mapeamento_retorna_erro(self):
        with patch("core.i9logic.buscar_id_i9logic", return_value=None):
            resultado = i9logic.listar_divergencias_athena("Loja Sem Mapeamento")
        self.assertIn("erro", resultado)
        self.assertIn("mapeamento de filial", resultado["erro"])

    def test_snapshot_vazio_retorna_lista_vazia_sem_quebrar(self):
        with patch("core.i9logic.buscar_id_i9logic", return_value="63"), \
             patch("core.i9logic.snapshot_mais_recente", return_value=(None, [])), \
             patch("core.i9logic._disparar_coleta_se_necessario", return_value=True):
            resultado = i9logic.listar_divergencias_athena("Loja Matriz")
        self.assertEqual(resultado["data"], [])
        self.assertEqual(resultado["status"], "processando")

    def test_item_sem_sku_athena_e_ignorado(self):
        itens = [{"idproduto": 1, "sku_athena": None, "qtd": 10, "descricao": "X"}]
        with patch("core.i9logic.buscar_id_i9logic", return_value="63"), \
             patch("core.i9logic.snapshot_mais_recente", return_value=(datetime.now(), itens)), \
             patch("core.i9logic._disparar_coleta_se_necessario", return_value=False):
            resultado = i9logic.listar_divergencias_athena("Loja Matriz")
        self.assertEqual(resultado["data"], [])

    def test_calcula_divergencia_e_classificacao_contra_saldo_athena(self):
        itens = [{"idproduto": 1, "sku_athena": "SKU-A", "qtd": 100, "descricao": "Produto A"}]
        with patch("core.i9logic.buscar_id_i9logic", return_value="63"), \
             patch("core.i9logic.snapshot_mais_recente", return_value=(datetime.now(), itens)), \
             patch("core.i9logic._disparar_coleta_se_necessario", return_value=False), \
             patch("core.estoque_saldos.saldos_em_lote", return_value={"SKU-A": 106.0}):
            resultado = i9logic.listar_divergencias_athena("Loja Matriz")
        self.assertEqual(len(resultado["data"]), 1)
        item = resultado["data"][0]
        self.assertEqual(item["sku"], "SKU-A")
        self.assertEqual(item["disponivel_athena"], 106.0)
        self.assertEqual(item["qtd_fisico_i9logic"], 100.0)
        self.assertEqual(item["divergencia"], 6.0)
        self.assertEqual(item["classificacao"], "alerta")
        self.assertEqual(resultado["status"], "pronto")

    def test_le_saldos_numa_unica_query_em_lote(self):
        """Regressao de performance: era um saldo() por sku (~9k round-trips
        sequenciais numa filial grande). saldos_em_lote tem que ser chamada UMA
        vez, com todos os skus de uma vez."""
        itens = [
            {"idproduto": 1, "sku_athena": "SKU-A", "qtd": 10, "descricao": "A"},
            {"idproduto": 2, "sku_athena": "SKU-B", "qtd": 20, "descricao": "B"},
            {"idproduto": 3, "sku_athena": None, "qtd": 30, "descricao": "sem de-para"},
        ]
        with patch("core.i9logic.buscar_id_i9logic", return_value="63"), \
             patch("core.i9logic.snapshot_mais_recente", return_value=(datetime.now(), itens)), \
             patch("core.i9logic._disparar_coleta_se_necessario", return_value=False), \
             patch("core.estoque_saldos.saldos_em_lote",
                   return_value={"SKU-A": 10.0, "SKU-B": 25.0}) as mock_lote:
            resultado = i9logic.listar_divergencias_athena("Loja Matriz")
        mock_lote.assert_called_once()
        self.assertEqual(mock_lote.call_args.args[0], ["SKU-A", "SKU-B"])  # item sem sku fora
        self.assertEqual(mock_lote.call_args.args[1], "Loja Matriz")
        self.assertEqual(len(resultado["data"]), 2)
        self.assertEqual(resultado["data"][0]["divergencia"], 0.0)
        self.assertEqual(resultado["data"][1]["divergencia"], 5.0)

    def test_falha_ao_ler_saldos_retorna_erro_em_vez_de_zeros(self):
        """Antes o loop usava saldo(), que e' fail-open (0.0 em qualquer
        excecao) — um erro transiente de banco virava uma lista inteira de
        'alerta' fabricados com botao de Ajustar do lado. Agora a falha e'
        visivel."""
        itens = [{"idproduto": 1, "sku_athena": "SKU-A", "qtd": 100, "descricao": "A"}]
        with patch("core.i9logic.buscar_id_i9logic", return_value="63"), \
             patch("core.i9logic.snapshot_mais_recente", return_value=(datetime.now(), itens)), \
             patch("core.i9logic._disparar_coleta_se_necessario", return_value=False), \
             patch("core.estoque_saldos.saldos_em_lote", side_effect=Exception("conexao caiu")):
            resultado = i9logic.listar_divergencias_athena("Loja Matriz")
        self.assertIn("erro", resultado)
        self.assertIn("conexao caiu", resultado["erro"])
        self.assertNotIn("data", resultado)


from flask import Flask
import core.rbac as rbac


def _app():
    from routes.i9logic import i9logic_bp
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(i9logic_bp)
    return app.test_client()


class TestRotasI9Logic(unittest.TestCase):
    def setUp(self):
        self.client = _app()

    def _headers_com_permissao(self, permissoes):
        with patch.dict(os.environ, {"ATHENA_JWT_SECRET": "test-secret-key"}):
            token = rbac.gerar_token_sessao(11, "u@x.com", "Gerente")
            return {"Authorization": f"Bearer {token}"}

    def test_listar_depara_exige_estoque_ver(self):
        headers = self._headers_com_permissao([])
        with patch("core.rbac.usuario_tem_permissao", return_value=False):
            r = self.client.get("/api/integrations/i9logic/depara", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_listar_depara_com_permissao_libera(self):
        headers = self._headers_com_permissao(["estoque.ver"])
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.i9logic.listar_mapeamentos", return_value=[{"id": 1}]) as mock_listar:
            r = self.client.get("/api/integrations/i9logic/depara", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["data"], [{"id": 1}])
        mock_listar.assert_called_once()

    def test_criar_depara_exige_estoque_editar(self):
        headers = self._headers_com_permissao([])
        with patch("core.rbac.usuario_tem_permissao", return_value=False):
            r = self.client.post("/api/integrations/i9logic/depara", headers=headers,
                                  json={"tipo": "produto", "id_i9logic": 1, "codigo_athena": "SKU-1"})
        self.assertEqual(r.status_code, 403)

    def test_criar_depara_com_permissao_libera(self):
        headers = self._headers_com_permissao(["estoque.editar"])
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.i9logic.criar_mapeamento", return_value={"id": 1}) as mock_criar:
            r = self.client.post("/api/integrations/i9logic/depara", headers=headers,
                                  json={"tipo": "produto", "id_i9logic": 1, "codigo_athena": "SKU-1"})
        self.assertEqual(r.status_code, 200)
        mock_criar.assert_called_once_with("produto", 1, "SKU-1")

    def test_matching_automatico_exige_estoque_editar(self):
        headers = self._headers_com_permissao([])
        with patch("core.rbac.usuario_tem_permissao", return_value=False):
            r = self.client.post("/api/integrations/i9logic/depara/matching", headers=headers,
                                  json={"tipo": "produto", "pares": []})
        self.assertEqual(r.status_code, 403)

    def test_listar_divergencias_exige_estoque_ver(self):
        headers = self._headers_com_permissao([])
        with patch("core.rbac.usuario_tem_permissao", return_value=False):
            r = self.client.get("/api/integrations/i9logic/divergencias", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_listar_divergencias_com_permissao_libera(self):
        headers = self._headers_com_permissao(["estoque.ver"])
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.i9logic.listar_itens_para_revisao", return_value=[{"id": 1}]) as mock_listar:
            r = self.client.get("/api/integrations/i9logic/divergencias", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_listar.assert_called_once()

    def test_coletar_exige_estoque_editar(self):
        headers = self._headers_com_permissao([])
        with patch("core.rbac.usuario_tem_permissao", return_value=False):
            r = self.client.post("/api/integrations/i9logic/coletar", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_coletar_com_permissao_dispara_job(self):
        headers = self._headers_com_permissao(["estoque.editar"])
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.i9logic.executar_coleta_todas_filiais", return_value={"ok": True}) as mock_coleta:
            r = self.client.post("/api/integrations/i9logic/coletar", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_coleta.assert_called_once()

    def test_resolver_divergencia_exige_estoque_editar(self):
        headers = self._headers_com_permissao([])
        with patch("core.rbac.usuario_tem_permissao", return_value=False):
            r = self.client.post("/api/integrations/i9logic/divergencias/1/resolver", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_resolver_divergencia_com_permissao_chama_marcar_revisado_nao_ajusta(self):
        """/resolver so' aceita a divergencia como conhecida — nunca ajusta saldo,
        entao NUNCA pode chamar aplicar_ajuste_divergencia."""
        headers = self._headers_com_permissao(["estoque.editar"])
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.i9logic.marcar_revisado", return_value={"ok": True}) as mock_marcar, \
             patch("routes.i9logic.aplicar_ajuste_divergencia") as mock_ajustar:
            r = self.client.post("/api/integrations/i9logic/divergencias/1/resolver", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_marcar.assert_called_once_with(1)
        mock_ajustar.assert_not_called()

    def test_ajustar_divergencia_exige_estoque_editar(self):
        headers = self._headers_com_permissao([])
        with patch("core.rbac.usuario_tem_permissao", return_value=False):
            r = self.client.post("/api/integrations/i9logic/divergencias/1/ajustar", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_ajustar_divergencia_com_permissao_chama_aplicar_ajuste_nao_so_marca(self):
        """/ajustar ajusta o saldo de verdade — nao pode ser satisfeita so' chamando
        marcar_revisado (que e' o comportamento da rota /resolver, diferente)."""
        headers = self._headers_com_permissao(["estoque.editar"])
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.i9logic.aplicar_ajuste_divergencia", return_value={"ok": True}) as mock_ajustar, \
             patch("routes.i9logic.marcar_revisado") as mock_marcar:
            r = self.client.post("/api/integrations/i9logic/divergencias/1/ajustar", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_ajustar.assert_called_once()
        self.assertEqual(mock_ajustar.call_args[0][0], 1)
        mock_marcar.assert_not_called()

    def test_ajustar_divergencia_repassa_confirmar_zerar_do_corpo(self):
        headers = self._headers_com_permissao(["estoque.editar"])
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.i9logic.aplicar_ajuste_divergencia", return_value={"ok": True}) as mock_ajustar:
            r = self.client.post("/api/integrations/i9logic/divergencias/1/ajustar", headers=headers,
                                  json={"confirmar_zerar": True})
        self.assertEqual(r.status_code, 200)
        mock_ajustar.assert_called_once()
        self.assertEqual(mock_ajustar.call_args.kwargs.get("confirmar_zerar"), True)

    def test_ajustar_divergencia_sem_corpo_repassa_confirmar_zerar_false(self):
        headers = self._headers_com_permissao(["estoque.editar"])
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.i9logic.aplicar_ajuste_divergencia", return_value={"ok": True}) as mock_ajustar:
            r = self.client.post("/api/integrations/i9logic/divergencias/1/ajustar", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(mock_ajustar.call_args.kwargs.get("confirmar_zerar"), False)

    def test_ajustar_divergencia_snapshot_nao_encontrado_retorna_404(self):
        headers = self._headers_com_permissao(["estoque.editar"])
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.i9logic.aplicar_ajuste_divergencia",
                   return_value={"erro": "snapshot nao encontrado"}):
            r = self.client.post("/api/integrations/i9logic/divergencias/999/ajustar", headers=headers)
        self.assertEqual(r.status_code, 404)
        self.assertIn("erro", r.get_json())

    def test_ajustar_divergencia_erro_de_negocio_retorna_400(self):
        headers = self._headers_com_permissao(["estoque.editar"])
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.i9logic.aplicar_ajuste_divergencia",
                   return_value={"erro": "snapshot sem de-para resolvido (sku_athena/loja_athena nulos) - resolva o de-para antes de ajustar"}):
            r = self.client.post("/api/integrations/i9logic/divergencias/1/ajustar", headers=headers)
        self.assertEqual(r.status_code, 400)
        self.assertIn("erro", r.get_json())

    def test_comparar_exige_estoque_ver(self):
        headers = self._headers_com_permissao([])
        with patch("core.rbac.usuario_tem_permissao", return_value=False):
            r = self.client.get("/api/integrations/i9logic/comparar?sku=SKU-1&loja=Loja1", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_comparar_com_permissao_libera(self):
        headers = self._headers_com_permissao(["estoque.ver"])
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.i9logic.comparar_com_athena", return_value={"ok": True}) as mock_comparar:
            r = self.client.get("/api/integrations/i9logic/comparar?sku=SKU-1&loja=Loja1", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_comparar.assert_called_once_with("SKU-1", "Loja1")

    def test_seed_exige_estoque_editar(self):
        headers = self._headers_com_permissao([])
        with patch("core.rbac.usuario_tem_permissao", return_value=False):
            r = self.client.post("/api/integrations/i9logic/seed", headers=headers,
                                  json={"sku": "SKU-1", "loja": "Loja1"})
        self.assertEqual(r.status_code, 403)

    def test_seed_com_permissao_libera(self):
        headers = self._headers_com_permissao(["estoque.editar"])
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.i9logic.seed_inicial", return_value={"ok": True}) as mock_seed:
            r = self.client.post("/api/integrations/i9logic/seed", headers=headers,
                                  json={"sku": "SKU-1", "loja": "Loja1"})
        self.assertEqual(r.status_code, 200)
        mock_seed.assert_called_once()
        self.assertEqual(mock_seed.call_args[0][0], "SKU-1")
        self.assertEqual(mock_seed.call_args[0][1], "Loja1")

    def test_seed_sem_snapshot_retorna_404(self):
        # Texto real de core.i9logic.seed_inicial (linha 356) — nao contem literalmente
        # "nao encontrado", entao a rota tambem reconhece "sem snapshot" como not-found.
        headers = self._headers_com_permissao(["estoque.editar"])
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.i9logic.seed_inicial",
                   return_value={"erro": "sem snapshot para este sku/loja"}):
            r = self.client.post("/api/integrations/i9logic/seed", headers=headers,
                                  json={"sku": "SKU-X", "loja": "Loja1"})
        self.assertEqual(r.status_code, 404)
        self.assertIn("erro", r.get_json())

    def test_seed_quantidade_invalida_retorna_400(self):
        headers = self._headers_com_permissao(["estoque.editar"])
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.i9logic.seed_inicial",
                   return_value={"erro": "quantidade fisica coletada e' zero ou negativa, seed nao aplicado"}):
            r = self.client.post("/api/integrations/i9logic/seed", headers=headers,
                                  json={"sku": "SKU-X", "loja": "Loja1"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("erro", r.get_json())

    def test_sincronizar_vendas_exige_vendas_editar(self):
        headers = self._headers_com_permissao([])
        with patch("core.rbac.usuario_tem_permissao", return_value=False):
            r = self.client.post("/api/integrations/i9logic/vendas/sincronizar", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_sincronizar_vendas_com_permissao_libera(self):
        headers = self._headers_com_permissao(["vendas.editar"])
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.i9logic.sincronizar_pedidos_i9logic",
                   return_value={"ok": True, "sincronizados": 2}) as mock_sync:
            r = self.client.post("/api/integrations/i9logic/vendas/sincronizar", headers=headers, json={})
        self.assertEqual(r.status_code, 200)
        mock_sync.assert_called_once_with(data_de=None, data_ate=None)

    def test_estoque_por_loja_exige_estoque_ver(self):
        headers = self._headers_com_permissao([])
        with patch("core.rbac.usuario_tem_permissao", return_value=False):
            r = self.client.get("/api/integrations/i9logic/estoque/1", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_estoque_por_loja_inexistente_retorna_404(self):
        headers = self._headers_com_permissao(["estoque.ver"])
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.i9logic.obter_loja", return_value=None):
            r = self.client.get("/api/integrations/i9logic/estoque/999", headers=headers)
        self.assertEqual(r.status_code, 404)

    def test_estoque_por_loja_virtual_retorna_400(self):
        headers = self._headers_com_permissao(["estoque.ver"])
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.i9logic.obter_loja", return_value={"id": 1, "nome": "Shopee Loja", "tipo": "virtual"}):
            r = self.client.get("/api/integrations/i9logic/estoque/1", headers=headers)
        self.assertEqual(r.status_code, 400)
        self.assertIn("fisica", r.get_json()["erro"])

    def test_estoque_por_loja_fisica_com_permissao_libera(self):
        headers = self._headers_com_permissao(["estoque.ver"])
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.i9logic.obter_loja", return_value={"id": 1, "nome": "Loja Matriz", "tipo": "fisica"}), \
             patch("routes.i9logic.estoque_fisico_por_loja",
                   return_value={"ok": True, "filial_i9logic": 63, "data": []}) as mock_estoque:
            r = self.client.get("/api/integrations/i9logic/estoque/1", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_estoque.assert_called_once_with("Loja Matriz")

    def test_estoque_por_loja_sem_mapeamento_retorna_404(self):
        headers = self._headers_com_permissao(["estoque.ver"])
        with patch("core.rbac.usuario_tem_permissao", return_value=True), \
             patch("routes.i9logic.obter_loja", return_value={"id": 1, "nome": "Loja Nova", "tipo": "fisica"}), \
             patch("routes.i9logic.estoque_fisico_por_loja",
                   return_value={"erro": "mapeamento de filial i9Logic nao encontrado para a loja 'Loja Nova'"}):
            r = self.client.get("/api/integrations/i9logic/estoque/1", headers=headers)
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
