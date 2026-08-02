"""Testes de integracao — CRUD financeiro exige permissao RBAC e pagamentos
de valor alto exigem financeiro.aprovar (alcada), nao so' financeiro.editar."""
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
from routes.financeiro import financeiro_bp
import core.rbac as rbac


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(financeiro_bp)
    return app.test_client()


class TestFinanceiroCRUDExigePermissao(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_criar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["pdv.operar"]):
            r = self.client.post("/api/financeiro/contas_pagar", json={"fornecedor": "X", "valor": 100}, headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_excluir_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["pdv.operar"]):
            r = self.client.delete("/api/financeiro/bancos/1", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_criar_com_permissao_editar_baixo_valor_ok(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Financeiro")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["financeiro.criar"]), \
             patch("core.financeiro.create", return_value={"id": 1}) as mock_create:
            r = self.client.post("/api/financeiro/contas_pagar", json={"fornecedor": "X", "valor": 100, "status": "pago"}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_create.assert_called_once()


class TestFinanceiroAlcadaPagamento(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_criar_pagamento_alto_sem_aprovar_e_bloqueado(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Financeiro")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["financeiro.criar"]), \
             patch("core.financeiro.create") as mock_create:
            r = self.client.post(
                "/api/financeiro/contas_pagar",
                json={"fornecedor": "X", "valor": 9000, "status": "pago"},
                headers=headers,
            )
        self.assertEqual(r.status_code, 400)
        data = r.get_json()
        self.assertIn("error", data)
        mock_create.assert_not_called()

    def test_criar_pagamento_alto_com_aprovar_libera_e_grava_aprovador(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Financeiro")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["financeiro.criar", "financeiro.aprovar"]), \
             patch("core.financeiro.create", return_value={"id": 1}) as mock_create:
            r = self.client.post(
                "/api/financeiro/contas_pagar",
                json={"fornecedor": "X", "valor": 9000, "status": "pago"},
                headers=headers,
            )
        self.assertEqual(r.status_code, 200)
        mock_create.assert_called_once()
        tabela, dados_enviados = mock_create.call_args[0]
        self.assertEqual(tabela, "contas_pagar")
        self.assertEqual(dados_enviados["aprovado_por"], "gerente")
        self.assertEqual(dados_enviados["aprovado_por_id"], 9)

    def test_pix_sem_status_explicito_assume_default_concluido_e_e_bloqueado(self):
        """fin_pix tem status default 'concluido' na tabela — se o payload nao
        manda status, o valor ainda deve ser tratado como executado na hora
        de checar a alcada (senao seria uma porta lateral facil)."""
        token = rbac.gerar_token_sessao(7, "op@x.com", "Financeiro")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["financeiro.criar"]), \
             patch("core.financeiro.create") as mock_create:
            r = self.client.post(
                "/api/financeiro/pix",
                json={"chave": "x@x.com", "valor": 9000},
                headers=headers,
            )
        data = r.get_json()
        self.assertIn("error", data)
        mock_create.assert_not_called()

    def test_atualizar_para_pago_valor_alto_sem_aprovar_bloqueado(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Financeiro")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["financeiro.editar"]), \
             patch("core.financeiro.get", return_value={"id": 5, "valor": 9000, "status": "pendente"}), \
             patch("core.financeiro.update") as mock_update:
            r = self.client.put(
                "/api/financeiro/contas_pagar/5",
                json={"status": "pago"},
                headers=headers,
            )
        data = r.get_json()
        self.assertIn("error", data)
        mock_update.assert_not_called()

    def test_atualizar_valor_baixo_nao_exige_aprovar(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Financeiro")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["financeiro.editar"]), \
             patch("core.financeiro.get", return_value={"id": 5, "valor": 100, "status": "pendente"}), \
             patch("core.financeiro.update", return_value={"id": 5, "status": "pago"}) as mock_update:
            r = self.client.put(
                "/api/financeiro/contas_pagar/5",
                json={"status": "pago"},
                headers=headers,
            )
        self.assertEqual(r.status_code, 200)
        mock_update.assert_called_once()


class TestFinanceiroAlcadaPorPinOuCracha(unittest.TestCase):
    """Quem esta logado nao precisa ter financeiro.aprovar — um gerente pode
    autorizar via PIN ou cracha, igual ja acontece no PDV."""

    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_pin_de_gerente_com_aprovar_libera_pagamento_alto(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Financeiro")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["financeiro.criar"]), \
             patch("core.rbac.verificar_pin_usuario", return_value={"ok": True, "id": 9, "nome": "Gerente Fulano"}), \
             patch("core.financeiro.create", return_value={"id": 1}) as mock_create:
            r = self.client.post(
                "/api/financeiro/contas_pagar",
                json={"fornecedor": "X", "valor": 9000, "status": "pago", "usuario_pin_id": 9, "pin": "1234"},
                headers=headers,
            )
        self.assertEqual(r.status_code, 200)
        mock_create.assert_called_once()
        _, dados_enviados = mock_create.call_args[0]
        self.assertEqual(dados_enviados["aprovado_por"], "Gerente Fulano")
        self.assertEqual(dados_enviados["aprovado_por_id"], 9)

    def test_pin_incorreto_nao_libera(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Financeiro")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["financeiro.criar"]), \
             patch("core.rbac.verificar_pin_usuario", return_value={"error": "PIN incorreto"}), \
             patch("core.financeiro.create") as mock_create:
            r = self.client.post(
                "/api/financeiro/contas_pagar",
                json={"fornecedor": "X", "valor": 9000, "status": "pago", "usuario_pin_id": 9, "pin": "0000"},
                headers=headers,
            )
        data = r.get_json()
        self.assertIn("error", data)
        mock_create.assert_not_called()

    def test_cracha_identifica_gerente_automaticamente(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Financeiro")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["financeiro.criar"]), \
             patch("core.rbac.verificar_codigo_barras_usuario", return_value={"ok": True, "id": 12, "nome": "Diretora X"}), \
             patch("core.financeiro.create", return_value={"id": 1}) as mock_create:
            r = self.client.post(
                "/api/financeiro/contas_pagar",
                json={"fornecedor": "X", "valor": 9000, "status": "pago", "codigo_barras": "ABC123"},
                headers=headers,
            )
        self.assertEqual(r.status_code, 200)
        _, dados_enviados = mock_create.call_args[0]
        self.assertEqual(dados_enviados["aprovado_por"], "Diretora X")


class TestFinanceiroWhitelistColunas(unittest.TestCase):
    """core.financeiro._create/_update concatenam as CHAVES do dict recebido
    direto na string SQL (so' os valores sao parametrizados) — sem whitelist,
    um nome de campo malicioso no JSON vira SQL injection. FIN_COLUNAS filtra
    antes de chegar em _create/_update."""

    def test_create_filtra_coluna_desconhecida(self):
        import core.financeiro as fin
        with patch("core.financeiro._create", return_value={"id": 1}) as mock_create:
            fin.create("contas_pagar", {"fornecedor": "X", "valor); DROP TABLE fin_bancos;--": "1"})
        tabela, dados_enviados = mock_create.call_args[0]
        self.assertEqual(tabela, "fin_contas_pagar")
        self.assertEqual(set(dados_enviados.keys()), {"fornecedor"})

    def test_update_filtra_coluna_desconhecida(self):
        import core.financeiro as fin
        with patch("core.financeiro._update", return_value={"id": 1}) as mock_update:
            fin.update("bancos", 1, {"nome": "Y", "id = 0 OR 1=1; --": "x"})
        tabela, id_, dados_enviados = mock_update.call_args[0]
        self.assertEqual(tabela, "fin_bancos")
        self.assertEqual(set(dados_enviados.keys()), {"nome"})

    def test_create_sem_campo_valido_retorna_erro_sem_tocar_banco(self):
        import core.financeiro as fin
        with patch("core.financeiro._create") as mock_create:
            r = fin.create("contas_pagar", {"campo_inexistente": "x"})
        self.assertIn("error", r)
        mock_create.assert_not_called()

    def test_tabela_invalida_retorna_erro_sem_tocar_banco(self):
        import core.financeiro as fin
        with patch("core.financeiro._create") as mock_create:
            r = fin.create("tabela_que_nao_existe", {"x": "y"})
        self.assertIn("error", r)
        mock_create.assert_not_called()

    def test_contas_receber_e_pagar_aceitam_bling_id_e_origem(self):
        """Schema bling_id/origem foi adicionado para os 3 fluxos que gravam
        contas vindas do Bling (webhook, sync manual, migracao) — a whitelist
        precisa deixar esses 2 campos passarem, senao o INSERT do webhook
        falha calado (campo filtrado vira dict vazio ou incompleto)."""
        import core.financeiro as fin
        self.assertIn("bling_id", fin.FIN_COLUNAS["contas_receber"])
        self.assertIn("origem", fin.FIN_COLUNAS["contas_pagar"])
        with patch("core.financeiro._create", return_value={"id": 1}) as mock_create:
            fin.create("contas_receber", {"cliente": "X", "bling_id": 999, "origem": "bling"})
        _, dados_enviados = mock_create.call_args[0]
        self.assertEqual(dados_enviados["bling_id"], 999)
        self.assertEqual(dados_enviados["origem"], "bling")


class TestFinanceiroRBACLeitura(unittest.TestCase):
    """financeiro.ver deve ser exigido em toda rota GET — antes da correcao
    qualquer usuario autenticado (mesmo sem nenhuma permissao financeira)
    conseguia ler contas a pagar/receber, saldo bancario, DRE etc."""

    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def _headers_sem_permissao_financeira(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        return {"Authorization": f"Bearer {token}"}

    def test_listar_sem_permissao_nega(self):
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["pdv.operar"]):
            r = self.client.get("/api/financeiro/contas_pagar", headers=self._headers_sem_permissao_financeira())
        self.assertEqual(r.status_code, 403)

    def test_obter_por_id_sem_permissao_nega(self):
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["pdv.operar"]):
            r = self.client.get("/api/financeiro/contas_pagar/1", headers=self._headers_sem_permissao_financeira())
        self.assertEqual(r.status_code, 403)

    def test_fluxo_caixa_resumo_sem_permissao_nega(self):
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["pdv.operar"]):
            r = self.client.get("/api/financeiro/fluxo_caixa/resumo", headers=self._headers_sem_permissao_financeira())
        self.assertEqual(r.status_code, 403)

    def test_dre_resumo_sem_permissao_nega(self):
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["pdv.operar"]):
            r = self.client.get("/api/financeiro/dre/resumo", headers=self._headers_sem_permissao_financeira())
        self.assertEqual(r.status_code, 403)

    def test_listar_com_permissao_ver_ok(self):
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["financeiro.ver"]), \
             patch("core.financeiro.list", return_value=[]):
            r = self.client.get("/api/financeiro/contas_pagar", headers=self._headers_sem_permissao_financeira())
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
