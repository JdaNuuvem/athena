"""Testes — lapidação da feature Lojas (/lojas).

Cobre os bugs corrigidos: (1) PUT /manage/<id> exigia "nome" em TODO
request, mesmo parcial — o botão Ativar/Desativar do hub so' manda
{status}, entao sempre devolvia 400 "Nome e obrigatorio" (nunca
funcionou); (2) listar() (usada pelo hub) nao trazia shopee_markup_pct/
grupos_publicacao — o modal "Editar rápido" sempre pre-carregava
markup=100 e o Salvar sobrescrevia silenciosamente qualquer markup real
configurado; (3) GET /deposito-map nao exigia nenhuma permissao; (4) as
rotas de sub-recursos por <id> de loja (operacional/comercial/fiscal/
financeiro/estoque-config/virtual/delivery, integracoes, midia,
responsaveis) so' checavam a permissao GLOBAL configuracoes.editar/
.excluir, sem checar requer_acesso_loja — um usuario restrito por
usuario_lojas a uma loja conseguia ler/editar/excluir sub-recursos de
QUALQUER outra loja so' trocando o <id> na URL; (5) IDOR em
DELETE .../midia/<midia_id> e PUT/DELETE .../responsaveis/<vinculo_id> —
midia_id/vinculo_id nunca eram validados contra a loja da URL."""
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
from routes.lojas_manage import lojas_bp
from routes.lojas_config import lojas_config_bp
from routes.lojas_integracoes import lojas_integracoes_bp
from routes.lojas_midia import lojas_midia_bp
from routes.lojas_responsaveis import lojas_responsaveis_bp
import core.rbac as rbac
import core.lojas as lojas
import core.lojas_midia as lojas_midia
import core.lojas_responsaveis as lojas_responsaveis


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(lojas_bp)
    app.register_blueprint(lojas_config_bp)
    app.register_blueprint(lojas_integracoes_bp)
    app.register_blueprint(lojas_midia_bp)
    app.register_blueprint(lojas_responsaveis_bp)
    return app.test_client()


class TestAtivarDesativarPutParcial(unittest.TestCase):
    """Regressao do bug: botao Ativar/Desativar so' manda {status}, sem
    nome — antes disso sempre devolvia 400."""

    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_put_so_status_nao_exige_nome(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.lojas.obter", return_value={"id": 1, "nome": "Loja X"}), \
             patch("core.lojas.atualizar") as mock_atualizar, \
             patch("core.lojas.atualizar_geral", return_value=True) as mock_geral:
            r = self.client.put("/api/lojas/manage/1", json={"status": "inativa"}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_atualizar.assert_not_called()  # nome/markup/grupos/tipo ausentes -> nao chama atualizar()
        mock_geral.assert_called_once_with(1, {"status": "inativa"})

    def test_put_nome_vazio_continua_bloqueado(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.put("/api/lojas/manage/1", json={"nome": "   "}, headers=headers)
        self.assertEqual(r.status_code, 400)

    def test_put_loja_inexistente_retorna_404(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.lojas.obter", return_value=None):
            r = self.client.put("/api/lojas/manage/999", json={"status": "inativa"}, headers=headers)
        self.assertEqual(r.status_code, 404)


class TestAtualizarCoreNomeOpcional(unittest.TestCase):
    """core.lojas.atualizar() nao pode mais exigir nome — usado direto por
    quem so' quer trocar markup/grupos/tipo."""

    def test_atualizar_sem_nome_so_markup(self):
        db_mock = AsyncMock()
        db_mock.execute = AsyncMock(return_value="UPDATE 1")

        async def _fake_get_db():
            return db_mock

        with patch("core.lojas.get_db", _fake_get_db), patch("core.lojas._ensure_table"):
            ok = lojas.atualizar(1, nome=None, shopee_markup_pct=150)
        self.assertTrue(ok)
        query = db_mock.execute.call_args_list[0].args[0]
        self.assertIn("shopee_markup_pct", query)

    def test_atualizar_sem_nenhum_campo_confirma_existencia(self):
        db_mock = AsyncMock()
        db_mock.fetchval = AsyncMock(return_value=1)

        async def _fake_get_db():
            return db_mock

        with patch("core.lojas.get_db", _fake_get_db), patch("core.lojas._ensure_table"):
            ok = lojas.atualizar(1)
        self.assertTrue(ok)
        db_mock.fetchval.assert_called_once_with("SELECT 1 FROM lojas WHERE id = $1", 1)


class TestListarIncluiColunasShopee(unittest.TestCase):
    def test_listar_seleciona_markup_e_grupos(self):
        db_mock = AsyncMock()
        db_mock.fetch = AsyncMock(return_value=[])

        async def _fake_get_db():
            return db_mock

        with patch("core.lojas.get_db", _fake_get_db), patch("core.lojas._ensure_table"):
            lojas.listar()
        query = db_mock.fetch.call_args.args[0]
        self.assertIn("shopee_markup_pct", query)
        self.assertIn("grupos_publicacao", query)


class TestDepositoMapExigePermissao(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]):
            r = self.client.get("/api/lojas/deposito-map", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_com_permissao_libera(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.get("/api/lojas/deposito-map", headers=headers)
        self.assertEqual(r.status_code, 200)


class TestRequerAcessoLojaSubRecursos(unittest.TestCase):
    """Usuario tem configuracoes.editar/.excluir GLOBAIS mas esta restrito
    por usuario_lojas a [1] — tentar tocar a loja 2 deve dar 403, mesmo
    tendo a permissao global."""

    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()
        self.headers = {"Authorization": f"Bearer {rbac.gerar_token_sessao(7, 'op@x.com', 'Vendedor')}"}
        self._perm_patch = patch("core.rbac.get_permissoes_por_usuario",
                                  return_value=["configuracoes.editar", "configuracoes.excluir"])
        self._perm_patch.start()
        self._lojas_patch = patch("core.rbac_lojas.lojas_permitidas", return_value=[1])
        self._lojas_patch.start()

    def tearDown(self):
        self._perm_patch.stop()
        self._lojas_patch.stop()
        self._env_patch.stop()

    # ── lojas_config.py (fabrica _registrar_secao) ──

    def test_operacional_loja_fora_da_lista_bloqueia(self):
        r = self.client.put("/api/lojas/manage/2/operacional", json={"regiao": "Sul"}, headers=self.headers)
        self.assertEqual(r.status_code, 403)

    def test_operacional_loja_permitida_passa_do_gate(self):
        # loja 1 e' permitida — o gate de acesso deixa passar; o 404 aqui
        # vem do proximo passo (obter() mockado como "nao encontrada"),
        # provando que NAO foi bloqueado pelo requer_acesso_loja (403).
        with patch("routes.lojas_config.obter", return_value=None):
            r = self.client.put("/api/lojas/manage/1/operacional", json={"regiao": "Sul"}, headers=self.headers)
        self.assertNotEqual(r.status_code, 403)

    def test_financeiro_loja_fora_da_lista_bloqueia(self):
        r = self.client.put("/api/lojas/manage/2/financeiro", json={"pix_chave": "x"}, headers=self.headers)
        self.assertEqual(r.status_code, 403)

    def test_estoque_config_loja_fora_da_lista_bloqueia(self):
        r = self.client.put("/api/lojas/manage/2/estoque-config", json={"deposito_principal": "x"}, headers=self.headers)
        self.assertEqual(r.status_code, 403)

    def test_virtual_loja_fora_da_lista_bloqueia(self):
        r = self.client.put("/api/lojas/manage/2/virtual", json={"dominio": "x.com"}, headers=self.headers)
        self.assertEqual(r.status_code, 403)

    def test_delivery_loja_fora_da_lista_bloqueia(self):
        r = self.client.put("/api/lojas/manage/2/delivery", json={"raio_entrega_km": 5}, headers=self.headers)
        self.assertEqual(r.status_code, 403)

    def test_comercial_loja_fora_da_lista_bloqueia(self):
        r = self.client.put("/api/lojas/manage/2/comercial", json={"politica_precos": "x"}, headers=self.headers)
        self.assertEqual(r.status_code, 403)

    # ── lojas_integracoes.py ──

    def test_integracoes_listar_loja_fora_da_lista_bloqueia(self):
        with patch("core.lojas_integracoes.listar") as mock_fn:
            r = self.client.get("/api/lojas/manage/2/integracoes", headers=self.headers)
        self.assertEqual(r.status_code, 403)
        mock_fn.assert_not_called()

    def test_integracoes_atualizar_loja_permitida_libera(self):
        with patch("core.lojas_integracoes.atualizar_status", return_value={"integracao": "mercado_livre"}) as mock_fn:
            r = self.client.put("/api/lojas/manage/1/integracoes/mercado_livre", json={"status": "ativo"}, headers=self.headers)
        self.assertEqual(r.status_code, 200)
        mock_fn.assert_called_once_with(1, "mercado_livre", "ativo", credenciais=None)

    # ── lojas_midia.py ──

    def test_midia_listar_loja_fora_da_lista_bloqueia(self):
        with patch("core.lojas_midia.listar") as mock_fn:
            r = self.client.get("/api/lojas/manage/2/midia", headers=self.headers)
        self.assertEqual(r.status_code, 403)
        mock_fn.assert_not_called()

    def test_midia_remover_loja_fora_da_lista_bloqueia(self):
        with patch("core.lojas_midia.remover") as mock_fn:
            r = self.client.delete("/api/lojas/manage/2/midia/9", headers=self.headers)
        self.assertEqual(r.status_code, 403)
        mock_fn.assert_not_called()

    def test_midia_remover_loja_permitida_passa_loja_id_pro_core(self):
        with patch("core.lojas_midia.remover", return_value={"success": True}) as mock_fn:
            r = self.client.delete("/api/lojas/manage/1/midia/9", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        mock_fn.assert_called_once_with(9, loja_id=1)

    # ── lojas_responsaveis.py ──

    def test_responsaveis_listar_loja_fora_da_lista_bloqueia(self):
        with patch("core.lojas_responsaveis.listar") as mock_fn:
            r = self.client.get("/api/lojas/manage/2/responsaveis", headers=self.headers)
        self.assertEqual(r.status_code, 403)
        mock_fn.assert_not_called()

    def test_responsaveis_vincular_loja_fora_da_lista_bloqueia(self):
        with patch("core.lojas_responsaveis.vincular") as mock_fn:
            r = self.client.post("/api/lojas/manage/2/responsaveis", json={"usuario_id": 5, "cargo": "gerente_geral"}, headers=self.headers)
        self.assertEqual(r.status_code, 403)
        mock_fn.assert_not_called()

    def test_responsaveis_atualizar_loja_fora_da_lista_bloqueia(self):
        with patch("core.lojas_responsaveis.atualizar") as mock_fn:
            r = self.client.put("/api/lojas/manage/2/responsaveis/5", json={"cargo": "gerente_estoque"}, headers=self.headers)
        self.assertEqual(r.status_code, 403)
        mock_fn.assert_not_called()

    def test_responsaveis_remover_loja_fora_da_lista_bloqueia(self):
        with patch("core.lojas_responsaveis.remover") as mock_fn:
            r = self.client.delete("/api/lojas/manage/2/responsaveis/5", headers=self.headers)
        self.assertEqual(r.status_code, 403)
        mock_fn.assert_not_called()

    def test_responsaveis_remover_loja_permitida_passa_loja_id_pro_core(self):
        with patch("core.lojas_responsaveis.remover", return_value=True) as mock_fn:
            r = self.client.delete("/api/lojas/manage/1/responsaveis/5", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        mock_fn.assert_called_once_with(5, loja_id=1)


class TestIdorMidiaEResponsaveis(unittest.TestCase):
    """core.lojas_midia.remover / core.lojas_responsaveis.atualizar-encerrar-
    remover — quando loja_id e' informado, precisam escopar a operacao a
    essa loja (nao apenas confiar no id do registro filho)."""

    def test_midia_remover_nao_pertence_a_loja_retorna_erro(self):
        with patch.object(lojas_midia, "listar", return_value=[{"id": 1}, {"id": 2}]), \
             patch("core.documentos.deletar") as mock_deletar:
            r = lojas_midia.remover(999, loja_id=5)
        self.assertIn("error", r)
        mock_deletar.assert_not_called()

    def test_midia_remover_pertence_a_loja_deleta(self):
        with patch.object(lojas_midia, "listar", return_value=[{"id": 9}]), \
             patch("core.documentos.deletar", return_value={"success": True}) as mock_deletar:
            r = lojas_midia.remover(9, loja_id=5)
        self.assertNotIn("error", r)
        mock_deletar.assert_called_once_with(9)

    def test_responsaveis_remover_com_loja_id_inclui_no_where(self):
        db_mock = AsyncMock()
        db_mock.execute = AsyncMock(return_value="DELETE 0")

        async def _fake_get_db():
            return db_mock

        with patch("core.lojas_responsaveis.get_db", _fake_get_db), \
             patch.object(lojas_responsaveis, "_table_ok", True):
            ok = lojas_responsaveis.remover(5, loja_id=1)
        self.assertFalse(ok)  # DELETE 0 = nao apagou (loja_id nao bateu)
        query, vid, loja_id = db_mock.execute.call_args.args
        self.assertIn("AND loja_id = $2", query)
        self.assertEqual((vid, loja_id), (5, 1))

    def test_responsaveis_atualizar_com_loja_id_inclui_no_where(self):
        db_mock = AsyncMock()
        db_mock.execute = AsyncMock(return_value="UPDATE 0")

        async def _fake_get_db():
            return db_mock

        with patch("core.lojas_responsaveis.get_db", _fake_get_db), \
             patch.object(lojas_responsaveis, "_table_ok", True):
            ok = lojas_responsaveis.atualizar(5, cargo="gerente_geral", loja_id=1)
        self.assertFalse(ok)
        query = db_mock.execute.call_args.args[0]
        self.assertIn("AND loja_id = $3", query)


if __name__ == "__main__":
    unittest.main(verbosity=2)
