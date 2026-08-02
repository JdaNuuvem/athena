"""Testes de integracao — CRUD generico de CRM (leads, contatos, negociacoes,
propostas, contratos) antes nao checava nenhuma permissao."""
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
from routes.crm import crm_bp
import core.rbac as rbac
import core.crm as crm


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(crm_bp)
    return app.test_client()


class TestCRMCRUDExigePermissao(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_criar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.crm.create") as mock_create:
            r = self.client.post("/api/crm/leads", json={"nome": "X"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_create.assert_not_called()

    def test_criar_com_permissao_libera(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["crm.criar"]), \
             patch("core.crm.create", return_value={"id": 1}) as mock_create:
            r = self.client.post("/api/crm/leads", json={"nome": "X"}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_create.assert_called_once()

    def test_editar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["crm.criar"]), \
             patch("core.crm.update") as mock_update:
            r = self.client.put("/api/crm/leads/1", json={"nome": "Y"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_update.assert_not_called()

    def test_excluir_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["crm.criar", "crm.editar"]), \
             patch("core.crm.delete") as mock_delete:
            r = self.client.delete("/api/crm/leads/1", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_delete.assert_not_called()

    def test_excluir_com_permissao_libera_e_audita(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.crm.get", return_value={"id": 1, "nome": "X"}), \
             patch("core.crm.delete", return_value={"success": True}) as mock_delete, \
             patch("core.seguranca.auditar_exclusao") as mock_audit:
            r = self.client.delete("/api/crm/leads/1", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_delete.assert_called_once()
        mock_audit.assert_called_once_with("crm", "leads", 1, {"id": 1, "nome": "X"})

    def test_importar_bling_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.crm.importar_contatos_bling") as mock_importar:
            r = self.client.post("/api/crm/importar-bling", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_importar.assert_not_called()

    # ── GET (list/get/funil) tambem exigem crm.ver — antes eram abertos a
    # qualquer usuario autenticado, independente de permissao/papel ──

    def test_listar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.crm.list") as mock_list:
            r = self.client.get("/api/crm/leads", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_list.assert_not_called()

    def test_listar_com_permissao_libera(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["crm.ver"]), \
             patch("core.crm.list", return_value=[{"id": 1}]) as mock_list:
            r = self.client.get("/api/crm/leads", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_list.assert_called_once()

    def test_get_um_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.crm.get") as mock_get:
            r = self.client.get("/api/crm/leads/1", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_get.assert_not_called()

    def test_funil_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.crm.funil") as mock_funil:
            r = self.client.get("/api/crm/funil", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_funil.assert_not_called()

    def test_criar_com_payload_invalido_retorna_400(self):
        # antes, um {"error": ...} do core.crm sempre virava HTTP 200 —
        # o frontend nao tinha como saber que a operacao falhou.
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["crm.criar"]), \
             patch("core.crm.create", return_value={"error": "Nenhum campo valido informado"}):
            r = self.client.post("/api/crm/leads", json={"campo_inexistente": "y"}, headers=headers)
        self.assertEqual(r.status_code, 400)


class TestCRMColunaWhitelist(unittest.TestCase):
    """_create/_update concatenam as CHAVES do dict recebido direto na
    string SQL — sem whitelist, uma chave de JSON maliciosa vira SQL
    injection. create()/update() devem filtrar antes de chegar la."""

    def test_create_filtra_colunas_nao_whitelisted(self):
        payload = {
            "nome": "Lead X",
            "email": "x@x.com",
            "id, extra) VALUES (999, 'x'); DROP TABLE crm_leads;--": "malicioso",
        }
        with patch("core.crm._create", return_value={"id": 1}) as mock_create:
            crm.create("leads", payload)
        mock_create.assert_called_once_with("crm_leads", {"nome": "Lead X", "email": "x@x.com"})

    def test_create_todas_colunas_invalidas_nao_toca_banco(self):
        with patch("core.crm._create") as mock_create:
            resultado = crm.create("leads", {"campo_inexistente": "y"})
        mock_create.assert_not_called()
        self.assertEqual(resultado, {"error": "Nenhum campo valido informado"})

    def test_update_filtra_colunas_nao_whitelisted(self):
        with patch("core.crm._update", return_value={"id": 1}) as mock_update:
            crm.update("leads", 1, {"status": "qualificado", "outra_coluna_invasora": "x"})
        mock_update.assert_called_once_with("crm_leads", 1, {"status": "qualificado"})

    def test_create_tabela_invalida(self):
        resultado = crm.create("nao_existe", {"nome": "x"})
        self.assertEqual(resultado, {"error": "Tabela invalida"})


class TestImportarBlingDedupe(unittest.TestCase):
    """Contatos sem email sempre caiam no ramo `if email:` como False e
    duplicavam lead+contato a cada resync — precisa de fallback por
    nome+telefone (ou so' nome) quando nao ha email."""

    def test_dedupe_sem_email_usa_nome_e_telefone(self):
        contato_sem_email = {
            "nome": "Fulano de Tal", "email": "", "telefone": "11999998888",
            "tipo": "C", "numeroDocumento": "",
        }
        db_mock = AsyncMock()
        db_mock.fetchval = AsyncMock(return_value=42)  # contato ja existe -> deve pular
        db_mock.fetchrow = AsyncMock(return_value=None)
        db_mock.execute = AsyncMock(return_value="OK")

        async def _fake_get_db():
            return db_mock

        with patch("bling_erp.get_access_token", return_value="tok"), \
             patch("bling_erp.get_auth_url", return_value="http://auth"), \
             patch("bling_erp.listar_contatos", return_value={"data": [contato_sem_email]}), \
             patch("core.crm.get_db", _fake_get_db):
            resultado = crm.importar_contatos_bling()

        self.assertEqual(resultado["leads"], 0)
        self.assertEqual(resultado["total"], 1)
        query_usada = db_mock.fetchval.call_args_list[0].args[0]
        self.assertIn("telefone", query_usada)
        self.assertIn("nome", query_usada)
        self.assertNotIn("email", query_usada)


class TestCRMEmpresasValidacao(unittest.TestCase):
    """create()/update() de 'empresas' validam nome/cnpj/email no boundary
    antes de tocar o banco — sem isso, um CNPJ invalido so' estourava como
    erro cru de constraint/tipo do Postgres, sem mensagem util."""

    def test_create_sem_nome_rejeita(self):
        with patch("core.crm._create") as mock_create:
            resultado = crm.create("empresas", {"cnpj": "11222333000181"})
        mock_create.assert_not_called()
        self.assertEqual(resultado, {"error": "Nome e obrigatorio"})

    def test_create_com_cnpj_invalido_rejeita(self):
        with patch("core.crm._create") as mock_create:
            resultado = crm.create("empresas", {"nome": "Acme", "cnpj": "11111111111111"})
        mock_create.assert_not_called()
        self.assertEqual(resultado, {"error": "CNPJ invalido"})

    def test_create_com_email_invalido_rejeita(self):
        with patch("core.crm._create") as mock_create:
            resultado = crm.create("empresas", {"nome": "Acme", "email": "nao-e-email"})
        mock_create.assert_not_called()
        self.assertEqual(resultado, {"error": "E-mail invalido"})

    def test_create_com_dados_validos_libera(self):
        with patch("core.crm._create", return_value={"id": 1}) as mock_create:
            resultado = crm.create("empresas", {"nome": "Acme", "cnpj": "11222333000181", "email": "contato@acme.com"})
        mock_create.assert_called_once()
        self.assertEqual(resultado, {"id": 1})

    def test_create_cnpj_com_mascara_valido_libera(self):
        with patch("core.crm._create", return_value={"id": 1}):
            resultado = crm.create("empresas", {"nome": "Acme", "cnpj": "11.222.333/0001-81"})
        self.assertEqual(resultado, {"id": 1})

    def test_update_esvaziando_nome_rejeita(self):
        with patch("core.crm._update") as mock_update:
            resultado = crm.update("empresas", 1, {"nome": "  "})
        mock_update.assert_not_called()
        self.assertEqual(resultado, {"error": "Nome nao pode ser vazio"})

    def test_update_parcial_sem_nome_nao_exige_nome(self):
        # update parcial (so' status/telefone, por exemplo) nao deve exigir
        # reenvio do nome — so' 'criando=True' (POST) exige.
        with patch("core.crm._update", return_value={"id": 1, "telefone": "11999999999"}) as mock_update:
            resultado = crm.update("empresas", 1, {"telefone": "11999999999"})
        mock_update.assert_called_once()
        self.assertEqual(resultado, {"id": 1, "telefone": "11999999999"})

    def test_update_com_cnpj_invalido_rejeita(self):
        with patch("core.crm._update") as mock_update:
            resultado = crm.update("empresas", 1, {"cnpj": "123"})
        mock_update.assert_not_called()
        self.assertEqual(resultado, {"error": "CNPJ invalido"})

    def test_validacao_nao_se_aplica_a_outras_tabelas(self):
        # leads nao tem coluna cnpj — nao faz sentido validar CNPJ nela, e
        # nome vazio em leads segue o comportamento pre-existente (a
        # constraint NOT NULL do Postgres e' quem barra, no delete real).
        with patch("core.crm._create", return_value={"id": 1}) as mock_create:
            resultado = crm.create("leads", {"nome": "Lead sem validacao extra"})
        mock_create.assert_called_once()
        self.assertEqual(resultado, {"id": 1})


class TestCRMPropostasValidacao(unittest.TestCase):
    """create()/update() de 'propostas' — a UI antiga so' tinha os campos
    numero/valor/status/data_envio como texto livre, sem negociacao_id (a FK
    obrigatoria da tabela), sem enum de status, aceitando valor negativo e
    data_validade anterior a data_envio."""

    def test_create_sem_negociacao_id_rejeita(self):
        with patch("core.crm._create") as mock_create:
            resultado = crm.create("propostas", {"valor": "100"})
        mock_create.assert_not_called()
        self.assertEqual(resultado, {"error": "Negociação é obrigatória"})

    def test_create_com_negociacao_id_invalido_rejeita(self):
        with patch("core.crm._create") as mock_create:
            resultado = crm.create("propostas", {"negociacao_id": "abc"})
        mock_create.assert_not_called()
        self.assertEqual(resultado, {"error": "Negociação inválida"})

    def test_create_com_status_fora_do_enum_rejeita(self):
        with patch("core.crm._create") as mock_create:
            resultado = crm.create("propostas", {"negociacao_id": 1, "status": "em_analise_juridica"})
        mock_create.assert_not_called()
        self.assertIn("Status inválido", resultado["error"])

    def test_create_com_valor_negativo_rejeita(self):
        with patch("core.crm._create") as mock_create:
            resultado = crm.create("propostas", {"negociacao_id": 1, "valor": -50})
        mock_create.assert_not_called()
        self.assertEqual(resultado, {"error": "Valor não pode ser negativo"})

    def test_create_com_validade_antes_do_envio_rejeita(self):
        with patch("core.crm._create") as mock_create:
            resultado = crm.create("propostas", {
                "negociacao_id": 1, "data_envio": "2026-08-10", "data_validade": "2026-08-01",
            })
        mock_create.assert_not_called()
        self.assertIn("validade", resultado["error"])

    def test_create_com_dados_validos_gera_numero_automatico(self):
        with patch("core.crm._create", return_value={"id": 42, "negociacao_id": 1}) as mock_create, \
             patch("core.crm._update", return_value={"id": 42, "numero": "PROP-0042", "negociacao_id": 1}) as mock_update:
            resultado = crm.create("propostas", {"negociacao_id": 1, "valor": 1500.0, "status": "rascunho"})
        mock_create.assert_called_once()
        mock_update.assert_called_once_with("crm_propostas", 42, {"numero": "PROP-0042"})
        self.assertEqual(resultado["numero"], "PROP-0042")

    def test_create_com_numero_explicito_nao_sobrescreve(self):
        # se o caller ja mandou numero (ex: importacao de dados antigos),
        # nao gera outro por cima.
        with patch("core.crm._create", return_value={"id": 7, "numero": "PROP-LEGADO-1"}) as mock_create, \
             patch("core.crm._update") as mock_update:
            resultado = crm.create("propostas", {"negociacao_id": 1, "numero": "PROP-LEGADO-1"})
        mock_create.assert_called_once()
        mock_update.assert_not_called()
        self.assertEqual(resultado["numero"], "PROP-LEGADO-1")

    def test_update_parcial_nao_exige_negociacao_id(self):
        # so' mudar o status (ex: rascunho -> enviada) nao deve exigir
        # reenviar negociacao_id — mesmo padrao de update parcial de empresas.
        with patch("core.crm._update", return_value={"id": 1, "status": "enviada"}) as mock_update:
            resultado = crm.update("propostas", 1, {"status": "enviada"})
        mock_update.assert_called_once()
        self.assertEqual(resultado, {"id": 1, "status": "enviada"})

    def test_validacao_nao_se_aplica_a_outras_tabelas(self):
        # leads nao tem negociacao_id/status-de-proposta — a validacao de
        # propostas (enum de status, valor negativo etc.) nao deve disparar.
        with patch("core.crm._create", return_value={"id": 1}) as mock_create:
            resultado = crm.create("leads", {"nome": "Lead sem validacao de proposta"})
        mock_create.assert_called_once()
        self.assertEqual(resultado, {"id": 1})


class TestCRMContratosValidacao(unittest.TestCase):
    """create()/update() de 'contratos' — o CRUD generico aceitava um
    contrato sem negociacao_id, com status fora do enum (pendente/assinado/
    cancelado) ou valor negativo; a unica validacao existia no evento
    automatico (ao_converter_proposta_em_contrato), nao no CRUD manual."""

    def test_create_sem_negociacao_id_rejeita(self):
        with patch("core.crm._create") as mock_create:
            resultado = crm.create("contratos", {"valor": "100"})
        mock_create.assert_not_called()
        self.assertEqual(resultado, {"error": "Negociação é obrigatória"})

    def test_create_com_negociacao_id_invalido_rejeita(self):
        with patch("core.crm._create") as mock_create:
            resultado = crm.create("contratos", {"negociacao_id": "abc"})
        mock_create.assert_not_called()
        self.assertEqual(resultado, {"error": "Negociação inválida"})

    def test_create_com_proposta_id_invalido_rejeita(self):
        with patch("core.crm._create") as mock_create:
            resultado = crm.create("contratos", {"negociacao_id": 1, "proposta_id": "abc"})
        mock_create.assert_not_called()
        self.assertEqual(resultado, {"error": "Proposta inválida"})

    def test_create_com_status_fora_do_enum_rejeita(self):
        with patch("core.crm._create") as mock_create:
            resultado = crm.create("contratos", {"negociacao_id": 1, "status": "em_revisao"})
        mock_create.assert_not_called()
        self.assertIn("Status inválido", resultado["error"])

    def test_create_com_valor_negativo_rejeita(self):
        with patch("core.crm._create") as mock_create:
            resultado = crm.create("contratos", {"negociacao_id": 1, "valor": -10})
        mock_create.assert_not_called()
        self.assertEqual(resultado, {"error": "Valor não pode ser negativo"})

    def test_create_com_dados_validos_gera_numero_automatico(self):
        with patch("core.crm._create", return_value={"id": 42, "negociacao_id": 1}) as mock_create, \
             patch("core.crm._update", return_value={"id": 42, "numero": "CONT-0042", "negociacao_id": 1}) as mock_update:
            resultado = crm.create("contratos", {"negociacao_id": 1, "valor": 1500.0, "status": "pendente"})
        mock_create.assert_called_once()
        mock_update.assert_called_once_with("crm_contratos", 42, {"numero": "CONT-0042"})
        self.assertEqual(resultado["numero"], "CONT-0042")

    def test_create_com_numero_explicito_nao_sobrescreve(self):
        with patch("core.crm._create", return_value={"id": 7, "numero": "CONT-LEGADO-1"}) as mock_create, \
             patch("core.crm._update") as mock_update:
            resultado = crm.create("contratos", {"negociacao_id": 1, "numero": "CONT-LEGADO-1"})
        mock_create.assert_called_once()
        mock_update.assert_not_called()
        self.assertEqual(resultado["numero"], "CONT-LEGADO-1")

    def test_update_parcial_nao_exige_negociacao_id(self):
        # marcar como assinado (so' status + data_assinatura) nao deve exigir
        # reenviar negociacao_id — mesmo padrao de update parcial de propostas.
        with patch("core.crm._update", return_value={"id": 1, "status": "assinado"}) as mock_update:
            resultado = crm.update("contratos", 1, {"status": "assinado", "data_assinatura": "2026-08-02"})
        mock_update.assert_called_once()
        self.assertEqual(resultado, {"id": 1, "status": "assinado"})


class TestCRMDeleteComVinculo(unittest.TestCase):
    """Excluir uma empresa/lead com filhos vinculados (leads, contatos,
    negociacoes apontando pra ela via FK) deve retornar erro amigavel em
    vez do erro cru do Postgres (violates foreign key constraint...)."""

    def test_delete_com_fk_violation_retorna_mensagem_amigavel(self):
        import asyncpg

        db_mock = AsyncMock()
        db_mock.execute = AsyncMock(side_effect=asyncpg.ForeignKeyViolationError("violates foreign key constraint"))

        async def _fake_get_db():
            return db_mock

        with patch("core.crm.get_db", _fake_get_db):
            resultado = crm.delete("empresas", 1)
        self.assertIn("error", resultado)
        self.assertIn("vinculados", resultado["error"])

    def test_delete_sem_vinculo_funciona_normalmente(self):
        db_mock = AsyncMock()
        db_mock.execute = AsyncMock(return_value="DELETE 1")

        async def _fake_get_db():
            return db_mock

        with patch("core.crm.get_db", _fake_get_db):
            resultado = crm.delete("empresas", 1)
        self.assertEqual(resultado, {"success": True})


class TestCRMAgendaAlias(unittest.TestCase):
    """'agenda' e' alias de 'atividades' — nunca existiu tabela crm_agenda;
    sem o alias, list/create/get/update/delete('agenda', ...) sempre caiam
    em 404 'Tabela invalida' (web/src/app/crm/agenda chama /api/crm/agenda)."""

    def test_agenda_esta_em_crm_tables(self):
        self.assertIn("agenda", crm.CRM_TABLES)

    def test_list_agenda_usa_tabela_atividades(self):
        with patch("core.crm._list", return_value=[{"id": 1}]) as mock_list:
            resultado = crm.list("agenda")
        mock_list.assert_called_once_with("crm_atividades")
        self.assertEqual(resultado, [{"id": 1}])

    def test_create_agenda_usa_colunas_de_atividades(self):
        with patch("core.crm._create", return_value={"id": 1}) as mock_create:
            crm.create("agenda", {"tipo": "ligacao", "descricao": "Follow-up", "campo_invalido": "x"})
        mock_create.assert_called_once_with("crm_atividades", {"tipo": "ligacao", "descricao": "Follow-up"})

    def test_delete_agenda_usa_tabela_atividades(self):
        with patch("core.crm._delete", return_value={"success": True}) as mock_delete:
            crm.delete("agenda", 1)
        mock_delete.assert_called_once_with("crm_atividades", 1)

    def test_leads_nao_sao_afetados_pelo_alias(self):
        with patch("core.crm._list", return_value=[]) as mock_list:
            crm.list("leads")
        mock_list.assert_called_once_with("crm_leads")


if __name__ == "__main__":
    unittest.main(verbosity=2)
