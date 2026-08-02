"""Testes de integracao — tickets de atendimento e CRUD generico
(mensagens, sessoes, canais, sla, kb) antes nao checavam nenhuma permissao."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock, MagicMock

# Import core.chat so it's available for patching
try:
    import core.chat
except Exception:
    pass

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
from routes.atendimento import atendimento_bp
import core.rbac as rbac


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(atendimento_bp)
    return app.test_client()


class TestAtendimentoExigePermissao(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_criar_ticket_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.atendimento.criar_ticket") as mock_criar:
            r = self.client.post("/api/atendimento/tickets/criar", json={"cliente": "X"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_criar.assert_not_called()

    def test_criar_ticket_com_permissao_libera(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["atendimento.criar"]), \
             patch("core.atendimento.criar_ticket", return_value={"id": 1}) as mock_criar:
            r = self.client.post("/api/atendimento/tickets/criar", json={"cliente": "X"}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_criar.assert_called_once()

    def test_fechar_ticket_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["atendimento.criar"]), \
             patch("core.atendimento.fechar_ticket") as mock_fechar:
            r = self.client.post("/api/atendimento/tickets/1/fechar", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_fechar.assert_not_called()

    def test_excluir_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["atendimento.criar", "atendimento.editar"]), \
             patch("core.atendimento.delete") as mock_delete:
            r = self.client.delete("/api/atendimento/tickets/1", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_delete.assert_not_called()

    def test_excluir_com_permissao_libera_e_audita(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.atendimento.get", return_value={"id": 1, "cliente": "X"}), \
             patch("core.atendimento.delete", return_value={"success": True}) as mock_delete, \
             patch("core.seguranca.auditar_exclusao") as mock_audit:
            r = self.client.delete("/api/atendimento/tickets/1", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_delete.assert_called_once()
        mock_audit.assert_called_once_with("atendimento", "tickets", 1, {"id": 1, "cliente": "X"})

    def test_criar_ticket_cria_conversa_ponte_no_chat(self):
        with patch("core.atendimento.create", return_value={"id": 55}), \
             patch("core.atendimento.run_async", return_value={"sla_vencimento": None, "tempo_resposta_min": None}), \
             patch("core.chat.criar_conversa_ticket") as mock_ponte:
            from core.atendimento import criar_ticket
            resultado = criar_ticket("Cliente X", "Duvida sobre pedido")
            assert resultado == {"id": 55}
        mock_ponte.assert_called_once_with(55)

    # ── GET generico (/<tabela>, /<tabela>/<id>) nao exigia NENHUMA
    # permissao — nem autenticacao. Qualquer request anonima conseguia ler
    # atend_canais (que guarda o token de integracao do canal!). ──

    def test_listar_sla_sem_permissao_nega(self):
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.atendimento.list") as mock_list:
            r = self.client.get("/api/atendimento/sla")
        self.assertEqual(r.status_code, 403)
        mock_list.assert_not_called()

    def test_listar_sla_com_permissao_libera(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.atendimento.list", return_value=[{"id": 1, "prioridade": "urgente"}]) as mock_list:
            r = self.client.get("/api/atendimento/sla", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_list.assert_called_once_with("sla")

    def test_listar_canais_sem_permissao_nega(self):
        # atend_canais guarda token de integracao — o mais sensivel das
        # tabelas genericas do modulo.
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.atendimento.list") as mock_list:
            r = self.client.get("/api/atendimento/canais")
        self.assertEqual(r.status_code, 403)
        mock_list.assert_not_called()

    def test_get_um_sla_sem_permissao_nega(self):
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.atendimento.get") as mock_get:
            r = self.client.get("/api/atendimento/sla/1")
        self.assertEqual(r.status_code, 403)
        mock_get.assert_not_called()

    def test_get_um_sla_com_permissao_libera(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.atendimento.get", return_value={"id": 1, "prioridade": "urgente"}) as mock_get:
            r = self.client.get("/api/atendimento/sla/1", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_get.assert_called_once_with("sla", 1)

    def test_criar_sla_com_payload_invalido_retorna_400(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.atendimento.create", return_value={"error": "Prioridade invalida — use uma de: baixa, normal, alta, urgente"}):
            r = self.client.post("/api/atendimento/sla", json={"prioridade": "critica"}, headers=headers)
        self.assertEqual(r.status_code, 400)


class TestAtendimentoColunaWhitelist(unittest.TestCase):
    """create()/update() genericos concatenam as CHAVES do dict recebido
    direto na string SQL — sem whitelist, uma chave de JSON maliciosa vira
    SQL injection (mesma classe de bug ja corrigida em core/crm.py)."""

    def test_create_filtra_colunas_nao_whitelisted(self):
        from core import atendimento as atend
        payload = {
            "prioridade": "alta", "tempo_resposta_min": 30, "tempo_resolucao_h": 4,
            "id, extra) VALUES (999, 'x'); DROP TABLE atend_sla;--": "malicioso",
        }
        with patch.object(atend, "_create", return_value={"id": 1}) as mock_create:
            atend.create("sla", payload)
        mock_create.assert_called_once_with(
            "atend_sla", {"prioridade": "alta", "tempo_resposta_min": 30, "tempo_resolucao_h": 4})

    def test_create_todas_colunas_invalidas_nao_toca_banco(self):
        from core import atendimento as atend
        with patch.object(atend, "_create") as mock_create:
            resultado = atend.create("sla", {"campo_inexistente": "y"})
        mock_create.assert_not_called()
        self.assertEqual(resultado, {"error": "Nenhum campo valido informado"})

    def test_update_filtra_colunas_nao_whitelisted(self):
        from core import atendimento as atend
        with patch.object(atend, "_update", return_value={"id": 1}) as mock_update:
            atend.update("sla", 1, {"tempo_resposta_min": 15, "outra_coluna_invasora": "x"})
        mock_update.assert_called_once_with("atend_sla", 1, {"tempo_resposta_min": 15})

    def test_create_tabela_invalida(self):
        from core import atendimento as atend
        resultado = atend.create("nao_existe", {"nome": "x"})
        self.assertEqual(resultado, {"error": "Tabela invalida"})


class TestAtendimentoCanaisValidacao(unittest.TestCase):
    """create()/update() de 'canais' — o CRUD generico aceitava um canal sem
    nome (violava a constraint NOT NULL do Postgres com erro cru) e uma
    url_webhook em qualquer formato."""

    def test_create_sem_nome_rejeita(self):
        from core import atendimento as atend
        with patch.object(atend, "_create") as mock_create:
            resultado = atend.create("canais", {"url_webhook": "https://x.com/hook"})
        mock_create.assert_not_called()
        self.assertEqual(resultado, {"error": "Nome e obrigatorio"})

    def test_create_com_url_webhook_invalida_rejeita(self):
        from core import atendimento as atend
        with patch.object(atend, "_create") as mock_create:
            resultado = atend.create("canais", {"nome": "whatsapp", "url_webhook": "nao-e-url"})
        mock_create.assert_not_called()
        self.assertIn("URL do webhook invalida", resultado["error"])

    def test_create_com_dados_validos_libera(self):
        from core import atendimento as atend
        with patch.object(atend, "_create", return_value={"id": 1, "nome": "whatsapp", "token": "segredo"}):
            resultado = atend.create("canais", {"nome": "whatsapp", "url_webhook": "https://evolution.exemplo.com/hook", "token": "segredo"})
        # token nao deve voltar na resposta, mesmo tendo sido salvo
        self.assertNotIn("token", resultado)
        self.assertEqual(resultado["nome"], "whatsapp")

    def test_update_esvaziando_nome_rejeita(self):
        from core import atendimento as atend
        with patch.object(atend, "_update") as mock_update:
            resultado = atend.update("canais", 1, {"nome": "  "})
        mock_update.assert_not_called()
        self.assertEqual(resultado, {"error": "Nome nao pode ser vazio"})

    def test_update_parcial_sem_nome_nao_exige_nome(self):
        from core import atendimento as atend
        with patch.object(atend, "_update", return_value={"id": 1, "ativo": False}) as mock_update:
            resultado = atend.update("canais", 1, {"ativo": False})
        mock_update.assert_called_once()
        self.assertEqual(resultado, {"id": 1, "ativo": False})


class TestAtendimentoCanaisTokenSensivel(unittest.TestCase):
    """token de canal e' credencial de integracao externa (ex.: API key do
    WhatsApp/Evolution) — list()/get() nao devem devolve-lo pra quem tem
    apenas atendimento.ver, mesmo endpoint generico usado por outras 5
    tabelas do modulo."""

    def test_list_filtra_token(self):
        from core import atendimento as atend
        with patch.object(atend, "_list", return_value=[{"id": 1, "nome": "whatsapp", "token": "segredo-123", "ativo": True}]):
            resultado = atend.list("canais")
        self.assertNotIn("token", resultado[0])
        self.assertEqual(resultado[0]["nome"], "whatsapp")

    def test_get_filtra_token(self):
        from core import atendimento as atend
        with patch.object(atend, "_get", return_value={"id": 1, "nome": "whatsapp", "token": "segredo-123"}):
            resultado = atend.get("canais", 1)
        self.assertNotIn("token", resultado)

    def test_filtro_nao_afeta_outras_tabelas(self):
        from core import atendimento as atend
        with patch.object(atend, "_list", return_value=[{"id": 1, "prioridade": "alta", "tempo_resposta_min": 30}]):
            resultado = atend.list("sla")
        self.assertEqual(resultado, [{"id": 1, "prioridade": "alta", "tempo_resposta_min": 30}])


if __name__ == "__main__":
    unittest.main(verbosity=2)
