"""Testes — feature CRM Agenda.

Cobre os bugs corrigidos: (1) tabela "agenda" ausente de CRM_TABLES fazia
toda operacao em /api/crm/agenda cair em 404 "Tabela invalida" — resolvido
com alias agenda->atividades; (2) _coerce_datas so' convertia string DATE
("YYYY-MM-DD"), mas data_agendada/data_realizada sao TIMESTAMP e chegam do
frontend como "YYYY-MM-DDTHH:MM" — sem conversao pra datetime.datetime,
asyncpg estourava erro de tipo ao gravar; (3) tipo vazio/ausente so' falhava
na constraint NOT NULL do Postgres sem mensagem util; (4) FK invalida
(lead_id/negociacao_id/contato_id apontando pra registro inexistente)
tambem so' devolvia o erro cru do Postgres; (5) o JSONProvider padrao do
Flask serializa date/datetime em RFC 822 (formato de header HTTP), nao ISO
8601 — o frontend inteiro assume ISO, entao editar qualquer registro com
data preenchida mostrava o campo vazio e podia apagar a data ao salvar.
"""
import sys, os, unittest, datetime
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
import asyncpg


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(crm_bp)
    return app.test_client()


class TestAliasAgendaAtividades(unittest.TestCase):
    def test_tabela_real_resolve_alias(self):
        self.assertEqual(crm._tabela_real("agenda"), "atividades")

    def test_tabela_real_passthrough_outras_tabelas(self):
        self.assertEqual(crm._tabela_real("leads"), "leads")
        self.assertEqual(crm._tabela_real("atividades"), "atividades")

    def test_list_agenda_consulta_crm_atividades(self):
        with patch("core.crm._list", return_value=[{"id": 1}]) as mock_list:
            crm.list("agenda")
        mock_list.assert_called_once_with("crm_atividades")

    def test_get_agenda_consulta_crm_atividades(self):
        with patch("core.crm._get", return_value={"id": 1}) as mock_get:
            crm.get("agenda", 1)
        mock_get.assert_called_once_with("crm_atividades", 1)

    def test_create_agenda_filtra_e_grava_em_crm_atividades(self):
        with patch("core.crm._create", return_value={"id": 1}) as mock_create:
            crm.create("agenda", {"tipo": "ligacao", "campo_invalido": "x"})
        mock_create.assert_called_once_with("crm_atividades", {"tipo": "ligacao"})

    def test_update_agenda_filtra_e_grava_em_crm_atividades(self):
        with patch("core.crm._update", return_value={"id": 1}) as mock_update:
            crm.update("agenda", 1, {"status": "concluida", "campo_invalido": "x"})
        mock_update.assert_called_once_with("crm_atividades", 1, {"status": "concluida"})

    def test_delete_agenda_apaga_em_crm_atividades(self):
        with patch("core.crm._delete", return_value={"success": True}) as mock_delete:
            crm.delete("agenda", 1)
        mock_delete.assert_called_once_with("crm_atividades", 1)


class TestCoercaoDatetimeAgenda(unittest.TestCase):
    def test_data_agendada_com_espaco_vira_datetime(self):
        out = crm._coerce_datas({"data_agendada": "2026-08-05 14:30"})
        self.assertIsInstance(out["data_agendada"], datetime.datetime)
        self.assertEqual(out["data_agendada"], datetime.datetime(2026, 8, 5, 14, 30))

    def test_data_agendada_formato_input_datetime_local(self):
        out = crm._coerce_datas({"data_agendada": "2026-08-05T14:30"})
        self.assertEqual(out["data_agendada"], datetime.datetime(2026, 8, 5, 14, 30))

    def test_data_com_segundos(self):
        out = crm._coerce_datas({"data_realizada": "2026-08-05T14:30:45"})
        self.assertEqual(out["data_realizada"], datetime.datetime(2026, 8, 5, 14, 30, 45))

    def test_data_pura_continua_virando_date_nao_datetime(self):
        # regressao: campos DATE (data_fechamento, data_envio...) nao podem
        # ser afetados pela nova conversao de datetime.
        out = crm._coerce_datas({"data_fechamento": "2026-08-05"})
        self.assertIsInstance(out["data_fechamento"], datetime.date)
        self.assertNotIsInstance(out["data_fechamento"], datetime.datetime)

    def test_data_vazia_vira_none(self):
        out = crm._coerce_datas({"data_realizada": ""})
        self.assertIsNone(out["data_realizada"])

    def test_string_nao_data_passa_intacta(self):
        out = crm._coerce_datas({"tipo": "ligacao"})
        self.assertEqual(out["tipo"], "ligacao")


class TestValidacaoAtividades(unittest.TestCase):
    def test_criar_sem_tipo_bloqueia(self):
        r = crm.create("agenda", {"descricao": "sem tipo"})
        self.assertEqual(r, {"error": "Tipo e obrigatorio"})

    def test_criar_com_tipo_so_espacos_bloqueia(self):
        r = crm.create("agenda", {"tipo": "   "})
        self.assertEqual(r, {"error": "Tipo e obrigatorio"})

    def test_editar_tipo_vazio_bloqueia(self):
        r = crm.update("agenda", 1, {"tipo": ""})
        self.assertEqual(r, {"error": "Tipo nao pode ser vazio"})

    def test_editar_sem_mexer_no_tipo_nao_bloqueia(self):
        with patch("core.crm._update", return_value={"id": 1, "status": "concluida"}) as mock_update:
            r = crm.update("agenda", 1, {"status": "concluida"})
        mock_update.assert_called_once()
        self.assertNotIn("error", r)


class TestFKInvalidaMensagemAmigavel(unittest.TestCase):
    def test_create_fk_invalida_retorna_mensagem_amigavel(self):
        db_mock = AsyncMock()
        db_mock.fetchrow = AsyncMock(side_effect=asyncpg.ForeignKeyViolationError("fk violation"))

        async def _fake_get_db():
            return db_mock

        with patch("core.crm.get_db", _fake_get_db):
            r = crm._create("crm_atividades", {"tipo": "ligacao", "lead_id": 999999})
        self.assertEqual(r, {"error": crm._ERRO_FK_INVALIDA})

    def test_update_fk_invalida_retorna_mensagem_amigavel(self):
        db_mock = AsyncMock()
        db_mock.fetchrow = AsyncMock(side_effect=asyncpg.ForeignKeyViolationError("fk violation"))

        async def _fake_get_db():
            return db_mock

        with patch("core.crm.get_db", _fake_get_db):
            r = crm._update("crm_atividades", 1, {"lead_id": 999999})
        self.assertEqual(r, {"error": crm._ERRO_FK_INVALIDA})


class TestRotasAgendaExigemPermissao(unittest.TestCase):
    """Mesma cobertura de RBAC ja aplicada a /api/crm/leads (test_crm_seguranca.py),
    replicada para o alias /api/crm/agenda — garante que o alias nao virou um
    atalho que escapa da checagem de permissao."""

    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_listar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.crm.list") as mock_list:
            r = self.client.get("/api/crm/agenda", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_list.assert_not_called()

    def test_listar_com_permissao_libera(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["crm.ver"]), \
             patch("core.crm.list", return_value=[{"id": 1, "tipo": "ligacao"}]) as mock_list:
            r = self.client.get("/api/crm/agenda", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_list.assert_called_once_with("agenda")

    def test_criar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.crm.create") as mock_create:
            r = self.client.post("/api/crm/agenda", json={"tipo": "ligacao"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_create.assert_not_called()

    def test_criar_com_permissao_libera(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["crm.criar"]), \
             patch("core.crm.create", return_value={"id": 1}) as mock_create:
            r = self.client.post("/api/crm/agenda", json={"tipo": "ligacao"}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_create.assert_called_once_with("agenda", {"tipo": "ligacao"})

    def test_excluir_com_permissao_libera_e_audita(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.crm.get", return_value={"id": 1, "tipo": "ligacao"}), \
             patch("core.crm.delete", return_value={"success": True}) as mock_delete, \
             patch("core.seguranca.auditar_exclusao") as mock_audit:
            r = self.client.delete("/api/crm/agenda/1", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_delete.assert_called_once()
        mock_audit.assert_called_once_with("crm", "agenda", 1, {"id": 1, "tipo": "ligacao"})

    def test_tabela_invalida_continua_404(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.get("/api/crm/nao_existe", headers=headers)
        self.assertEqual(r.status_code, 404)


class TestJSONProviderISO(unittest.TestCase):
    """athena_bridge sobrescreve o JSONProvider padrao do Flask (que
    serializa date/datetime em RFC 822, formato de header HTTP) para ISO
    8601 — formato que o frontend inteiro assume."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("ATHENA_TOKEN", _TEST_TOKEN)
        # ponytail: sem autospec — se outro modulo de teste ja mockou
        # psycopg2.connect (com ou sem autospec) e nunca chamou .stop(),
        # empilhar outro patch com autospec=True quebra com InvalidSpecError
        # (autospec precisa inspecionar o alvo real, nao um Mock).
        patch("psycopg2.connect").start()
        import athena_bridge
        cls.provider = athena_bridge._ISODateJSONProvider

    def test_date_serializa_iso(self):
        self.assertEqual(self.provider.default(datetime.date(2026, 8, 5)), "2026-08-05")

    def test_datetime_serializa_iso(self):
        self.assertEqual(
            self.provider.default(datetime.datetime(2026, 8, 5, 14, 30)),
            "2026-08-05T14:30:00",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
