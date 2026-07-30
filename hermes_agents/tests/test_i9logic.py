"""Testes de integracao — reconciliacao i9Logic."""
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

import core.i9logic as i9logic


class TestDeParaCRUD(unittest.TestCase):
    def test_criar_mapeamento_tipo_invalido_retorna_erro(self):
        resultado = i9logic.criar_mapeamento("invalido", "1", "SKU-1")
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
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow)
            resultado = i9logic.aplicar_ajuste_divergencia(1, usuario_id=1, usuario_nome="Ana")
        mock_ajustar.assert_called_once_with(
            "SKU-29098", "Loja Matriz", 165.0, motivo="ajuste_inventario", usuario_id=1, usuario_nome="Ana")
        self.assertTrue(resultado["ok"])

    def test_ajustar_absoluto_com_erro_nao_marca_revisado(self):
        async def _fetchrow(query, *args):
            return {"id": 1, "sku_athena": "SKU-X", "loja_athena": "Loja Y", "qtd_fisico": 165}
        with patch("core.i9logic.get_db") as mock_get_db, \
             patch("core.estoque.ajustar_absoluto", return_value={"erro": "falha simulada"}):
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow)
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
            mock_get_db.return_value = AsyncMock(fetchrow=_fetchrow)
            resultado = i9logic.aplicar_ajuste_divergencia(1)
        self.assertIn("erro", resultado)
        self.assertNotIn("ok", resultado)


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
            return [{"idproduto": 1, "codproduto": "A", "qtd": 15},
                    {"idproduto": 2, "codproduto": "B", "qtd": 20}]
        gravados = []
        def _gravar(idproduto, codproduto, filial, qtd_fisico, qtd_contabil, data_coleta=None):
            gravados.append((idproduto, qtd_fisico, qtd_contabil))
            return {"ok": True}
        with patch("core.i9logic._paginar_estoques", side_effect=_paginar), \
             patch("core.i9logic.gravar_snapshot", side_effect=_gravar):
            resultado = i9logic.executar_coleta_filial(63)
        self.assertEqual(resultado["fisicos"], 2)
        self.assertEqual(resultado["gravados"], 2)
        self.assertIn((1, 10, 15), gravados)
        self.assertIn((2, 20, 20), gravados)

    def test_coleta_filial_usa_mesmo_data_coleta_pra_todas_as_linhas(self):
        def _paginar(filial, tipoestoque):
            return [{"idproduto": 1, "codproduto": "A", "qtd": 10}]
        datas_usadas = []
        def _gravar(idproduto, codproduto, filial, qtd_fisico, qtd_contabil, data_coleta=None):
            datas_usadas.append(data_coleta)
            return {"ok": True}
        with patch("core.i9logic._paginar_estoques", side_effect=_paginar), \
             patch("core.i9logic.gravar_snapshot", side_effect=_gravar):
            i9logic.executar_coleta_filial(63)
        self.assertIsNotNone(datas_usadas[0])

    def test_coleta_todas_filiais_itera_mapeamentos(self):
        with patch("core.i9logic.listar_mapeamentos", return_value=[
                {"id_i9logic": "63", "codigo_athena": "Loja Matriz"},
                {"id_i9logic": "64", "codigo_athena": "Loja Filial"}]), \
             patch("core.i9logic.executar_coleta_filial", return_value={"ok": True, "gravados": 5}) as mock_coleta:
            resultado = i9logic.executar_coleta_todas_filiais()
        self.assertEqual(resultado["filiais_processadas"], 2)
        self.assertEqual(mock_coleta.call_count, 2)
        mock_coleta.assert_any_call(63)
        mock_coleta.assert_any_call(64)
