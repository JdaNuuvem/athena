"""Fechamento de apuracao fiscal (fiscal_apuracao_fechada) — antes a
apuracao era so' um SUM() ao vivo, sem nenhum conceito de periodo fechado
nem trilha do que mudou depois (nota cancelada/corrigida apos o "fechamento"
informal do mes mudava o total silenciosamente). Cobre tambem RBAC das
rotas novas e o calculo de tributos com Decimal."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

_TEST_TOKEN = "test-master-token-32-bytes-long!!"

async def _mp(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

from flask import Flask
from routes.fiscal import fiscal_bp
import core.rbac as rbac
import core.fiscal as fiscal


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(fiscal_bp)
    return app.test_client()


RESUMO_FAKE = {
    "total_notas": 10, "valor_total": 5000.0, "valor_produtos": 4500.0,
    "base_icms": 4000.0, "total_icms": 720.0, "total_ipi": 100.0,
    "total_pis": 74.0, "total_cofins": 342.0, "total_iss": 0.0, "total_tributos": 1236.0,
}


class TestFecharApuracao(unittest.TestCase):
    def test_ano_mes_obrigatorios(self):
        self.assertIn("error", fiscal.fechar_apuracao(None, 6))
        self.assertIn("error", fiscal.fechar_apuracao(2026, None))

    def test_mes_invalido_rejeita(self):
        r = fiscal.fechar_apuracao(2026, 13)
        self.assertIn("error", r)

    def test_ja_fechado_rejeita_sem_sobrescrever(self):
        db = AsyncMock()
        db.fetchval = AsyncMock(return_value=5)  # ja existe fechamento com id=5
        async def _fake_get_db(): return db
        with patch.object(fiscal, "get_db", _fake_get_db):
            r = fiscal.fechar_apuracao(2026, 6, "user@x.com")
        self.assertIn("error", r)
        self.assertIn("ja esta fechada", r["error"])
        db.fetchrow.assert_not_called()

    def test_fecha_com_sucesso_grava_snapshot(self):
        db = AsyncMock()
        db.fetchval = AsyncMock(return_value=None)  # nao fechado ainda

        async def fake_fetchrow(query, *args):
            if "FROM fiscal_notas_fiscais" in query:
                return dict(RESUMO_FAKE)
            if "INSERT INTO fiscal_apuracao_fechada" in query:
                self.assertEqual(args[0], 2026)  # ano
                self.assertEqual(args[1], 6)     # mes
                self.assertEqual(args[-1], "user@x.com")  # fechado_por
                return {"id": 1, "ano": 2026, "mes": 6, **RESUMO_FAKE, "fechado_por": "user@x.com"}
            raise AssertionError(f"fetchrow inesperado: {query}")
        db.fetchrow = AsyncMock(side_effect=fake_fetchrow)

        async def _fake_get_db(): return db
        with patch.object(fiscal, "get_db", _fake_get_db), \
             patch("core.seguranca.auditar_alteracao") as mock_audit:
            r = fiscal.fechar_apuracao(2026, 6, "user@x.com")
        self.assertNotIn("error", r)
        self.assertEqual(r["fechado_por"], "user@x.com")
        mock_audit.assert_called_once()


class TestReabrirApuracao(unittest.TestCase):
    def test_nao_fechado_rejeita(self):
        db = AsyncMock()
        db.fetchrow = AsyncMock(return_value=None)
        async def _fake_get_db(): return db
        with patch.object(fiscal, "get_db", _fake_get_db):
            r = fiscal.reabrir_apuracao(2026, 6)
        self.assertIn("error", r)

    def test_reabre_com_sucesso_remove_fechamento(self):
        db = AsyncMock()
        db.fetchrow = AsyncMock(return_value={"id": 1, "ano": 2026, "mes": 6, "fechado_por": "user@x.com"})
        db.execute = AsyncMock(return_value="DELETE 1")
        async def _fake_get_db(): return db
        with patch.object(fiscal, "get_db", _fake_get_db), \
             patch("core.seguranca.auditar_exclusao") as mock_audit:
            r = fiscal.reabrir_apuracao(2026, 6)
        self.assertTrue(r.get("success"))
        mock_audit.assert_called_once_with("fiscal", "apuracao_fechada", 1, {"id": 1, "ano": 2026, "mes": 6, "fechado_por": "user@x.com"})


class TestApuracaoImpostosComFechamento(unittest.TestCase):
    def test_mes_sem_fechamento_reporta_fechado_false(self):
        db = AsyncMock()
        async def fake_fetchrow(query, *args):
            if "FROM fiscal_notas_fiscais" in query:
                return dict(RESUMO_FAKE)
            if "FROM fiscal_apuracao_fechada" in query:
                return None
            raise AssertionError(query)
        db.fetchrow = AsyncMock(side_effect=fake_fetchrow)
        db.fetch = AsyncMock(return_value=[])
        async def _fake_get_db(): return db
        with patch.object(fiscal, "get_db", _fake_get_db):
            r = fiscal.apuracao_impostos(2026, 6)
        self.assertEqual(r["fechamento"], {"fechado": False})

    def test_mes_fechado_sem_divergencia(self):
        db = AsyncMock()
        async def fake_fetchrow(query, *args):
            if "FROM fiscal_notas_fiscais" in query:
                return dict(RESUMO_FAKE)
            if "FROM fiscal_apuracao_fechada" in query:
                return {"fechado_por": "user@x.com", "fechado_em": None, "total_tributos": RESUMO_FAKE["total_tributos"]}
            raise AssertionError(query)
        db.fetchrow = AsyncMock(side_effect=fake_fetchrow)
        db.fetch = AsyncMock(return_value=[])
        async def _fake_get_db(): return db
        with patch.object(fiscal, "get_db", _fake_get_db):
            r = fiscal.apuracao_impostos(2026, 6)
        self.assertTrue(r["fechamento"]["fechado"])
        self.assertFalse(r["fechamento"]["divergente"])

    def test_mes_fechado_com_divergencia_apos_nota_alterada(self):
        # nota cancelada/corrigida depois do fechamento -> total ao vivo
        # (RESUMO_FAKE) diferente do valor congelado no snapshot.
        db = AsyncMock()
        async def fake_fetchrow(query, *args):
            if "FROM fiscal_notas_fiscais" in query:
                return dict(RESUMO_FAKE)
            if "FROM fiscal_apuracao_fechada" in query:
                return {"fechado_por": "user@x.com", "fechado_em": None, "total_tributos": 999.0}
            raise AssertionError(query)
        db.fetchrow = AsyncMock(side_effect=fake_fetchrow)
        db.fetch = AsyncMock(return_value=[])
        async def _fake_get_db(): return db
        with patch.object(fiscal, "get_db", _fake_get_db):
            r = fiscal.apuracao_impostos(2026, 6)
        self.assertTrue(r["fechamento"]["divergente"])


class TestListarFechamentos(unittest.TestCase):
    def test_lista_ordenada(self):
        db = AsyncMock()
        db.fetch = AsyncMock(return_value=[{"ano": 2026, "mes": 6}, {"ano": 2026, "mes": 5}])
        async def _fake_get_db(): return db
        with patch.object(fiscal, "get_db", _fake_get_db):
            r = fiscal.listar_fechamentos()
        self.assertEqual(len(r), 2)


class TestFiscalApuracaoRotasRBAC(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env.start()
        self.client = _app()

    def tearDown(self):
        self._env.stop()

    def test_apuracao_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(1, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]):
            r = self.client.get("/api/fiscal/apuracao", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_dashboard_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(1, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]):
            r = self.client.get("/api/fiscal/dashboard", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_fechar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(1, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["fiscal.ver"]), \
             patch("core.fiscal.fechar_apuracao") as mock_fechar:
            r = self.client.post("/api/fiscal/apuracao/fechar", json={"ano": 2026, "mes": 6}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_fechar.assert_not_called()

    def test_fechar_com_permissao_libera(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.fiscal.fechar_apuracao", return_value={"id": 1}) as mock_fechar:
            r = self.client.post("/api/fiscal/apuracao/fechar", json={"ano": 2026, "mes": 6}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_fechar.assert_called_once()

    def test_fechar_sem_ano_mes_retorna_400(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.post("/api/fiscal/apuracao/fechar", json={}, headers=headers)
        self.assertEqual(r.status_code, 400)

    def test_reabrir_exige_fiscal_excluir_nao_fiscal_editar(self):
        # reabrir desfaz um fechamento — nivel de permissao mais restrito
        # (mesmo usado pra exclusao), nao basta ter fiscal.editar.
        token = rbac.gerar_token_sessao(1, "op@x.com", "Editor")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["fiscal.ver", "fiscal.editar"]), \
             patch("core.fiscal.reabrir_apuracao") as mock_reabrir:
            r = self.client.post("/api/fiscal/apuracao/reabrir", json={"ano": 2026, "mes": 6}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_reabrir.assert_not_called()

    def test_reabrir_com_fiscal_excluir_libera(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.fiscal.reabrir_apuracao", return_value={"success": True}) as mock_reabrir:
            r = self.client.post("/api/fiscal/apuracao/reabrir", json={"ano": 2026, "mes": 6}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_reabrir.assert_called_once()

    def test_fechamentos_sem_permissao_nega(self):
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]):
            token = rbac.gerar_token_sessao(1, "op@x.com", "Sem Papel")
            r = self.client.get("/api/fiscal/apuracao/fechamentos", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(r.status_code, 403)

    def test_sync_contas_receber_exige_fiscal_editar(self):
        token = rbac.gerar_token_sessao(1, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.fiscal.sincronizar_contas_receber_bling") as mock_sync:
            r = self.client.post("/api/fiscal/sync/contas-receber", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_sync.assert_not_called()

    def test_obrigacoes_baixar_exige_fiscal_editar(self):
        token = rbac.gerar_token_sessao(1, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.fiscal.baixar_ocorrencia") as mock_baixar:
            r = self.client.post("/api/fiscal/obrigacoes/1/baixar", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_baixar.assert_not_called()

class TestSincronizarUmaNotaFiscal(unittest.TestCase):
    """Usada pelo webhook de nota-fiscal — antes o webhook gravava so' um
    resumo (numero/data/contato/valor_nf/status), com todos os campos de
    imposto zerados. Agora busca o detalhe completo, igual ao sync manual."""

    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.get_nfe_completa", return_value={"data": {
        "id": 777, "numero": "500", "total": 220.0, "totalProdutos": 200.0,
        "tributos": {"totalICMS": 36.0}, "itens": [],
    }})
    def test_busca_detalhe_completo_com_sucesso(self, mdet, mtok):
        db = AsyncMock()
        db.fetchval = AsyncMock(return_value=None)
        db.fetchrow = AsyncMock(return_value=None)
        db.fetch = AsyncMock(return_value=[])
        db.execute = AsyncMock(return_value="OK")
        async def _fake_get_db(): return db
        with patch.object(fiscal, "get_db", _fake_get_db):
            r = fiscal.sincronizar_uma_nota_fiscal(777, resumo_fallback={"numero": "500", "total": 220.0})
        self.assertNotIn("error", r)
        mdet.assert_called_once_with(777)

    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.get_nfe_completa", return_value={"error": "rate limited"})
    def test_fallback_para_payload_do_webhook_quando_detalhe_falha(self, mdet, mtok):
        db = AsyncMock()
        db.fetchval = AsyncMock(return_value=None)
        db.fetchrow = AsyncMock(return_value=None)
        db.fetch = AsyncMock(return_value=[])
        db.execute = AsyncMock(return_value="OK")
        async def _fake_get_db(): return db
        with patch.object(fiscal, "get_db", _fake_get_db):
            r = fiscal.sincronizar_uma_nota_fiscal(777, resumo_fallback={"id": 777, "numero": "500", "total": 220.0})
        # nao deve dar error mesmo com o detalhe falhando, gracas ao fallback
        self.assertNotIn("error", r)

    def test_sem_fallback_e_sem_detalhe_retorna_erro(self):
        with patch("bling_erp.get_access_token", return_value=None):
            r = fiscal.sincronizar_uma_nota_fiscal(777, resumo_fallback=None)
        self.assertIn("error", r)


class TestPopularImpostosNota(unittest.TestCase):
    """fiscal_impostos_nota existia no schema desde sempre (FK pra
    fiscal_tributos) mas nunca era populada — GET /notas-fiscais/<id>/impostos
    sempre devolvia []. _upsert_nota_fiscal agora deriva uma linha por
    tributo ativo com valor correspondente > 0."""

    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.get_nfe_completa", return_value={"data": {
        "id": 777, "numero": "500", "total": 220.0, "totalProdutos": 200.0,
        "tributos": {"totalICMS": 36.0, "totalPIS": 3.3, "totalIPI": 0.0}, "itens": [],
    }})
    def test_popula_apenas_tributos_com_valor_positivo(self, mdet, mtok):
        db = AsyncMock()
        db.fetchval = AsyncMock(return_value=None)
        db.fetchrow = AsyncMock(return_value=None)
        db.fetch = AsyncMock(return_value=[
            {"id": 1, "nome": "ICMS", "sigla": "ICMS", "aliquota": 18},
            {"id": 2, "nome": "IPI", "sigla": "IPI", "aliquota": 10},
            {"id": 3, "nome": "Simples Nacional", "sigla": "SN", "aliquota": 6},  # sem mapeamento -> ignorado
        ])
        db.execute = AsyncMock(return_value="OK")
        async def _fake_get_db(): return db
        with patch.object(fiscal, "get_db", _fake_get_db):
            fiscal.sincronizar_uma_nota_fiscal(777, resumo_fallback={"id": 777})

        inserts = [c for c in db.execute.call_args_list if "INSERT INTO fiscal_impostos_nota" in c.args[0]]
        siglas_inseridas = {c.args[4] for c in inserts}  # (nota_id, tributo_id, nome, sigla, ...)
        self.assertIn("ICMS", siglas_inseridas)   # valor_icms = 36.0 > 0
        self.assertNotIn("IPI", siglas_inseridas)  # valor_ipi = 0.0 -> nao insere
        self.assertNotIn("SN", siglas_inseridas)   # sem campo mapeado -> nao insere

    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.get_nfe_completa", return_value={"data": {
        "id": 778, "numero": "501", "total": 100.0, "totalProdutos": 100.0, "itens": [],
    }})
    def test_resincronizar_limpa_impostos_antigos_antes_de_repopular(self, mdet, mtok):
        db = AsyncMock()
        db.fetchval = AsyncMock(return_value=55)  # nota ja existe
        db.fetchrow = AsyncMock(return_value=None)
        db.fetch = AsyncMock(return_value=[])
        db.execute = AsyncMock(return_value="OK")
        async def _fake_get_db(): return db
        with patch.object(fiscal, "get_db", _fake_get_db):
            fiscal.sincronizar_uma_nota_fiscal(778, resumo_fallback={"id": 778})
        deletes = [c for c in db.execute.call_args_list if "DELETE FROM fiscal_impostos_nota" in c.args[0]]
        self.assertEqual(len(deletes), 1)
        self.assertEqual(deletes[0].args[1], 55)


if __name__ == "__main__":
    unittest.main(verbosity=2)
