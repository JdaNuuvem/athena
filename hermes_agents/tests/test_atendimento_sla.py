"""Testes — SLA no Atendimento + Webhook Dispatcher (Fase 2)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

async def _mock_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(
        __aenter__=AsyncMock(return_value=AsyncMock(
            fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
            fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"),
        )),
        __aexit__=AsyncMock(return_value=None),
    )
    return m
patcher = patch("asyncpg.create_pool", side_effect=_mock_pool)
patcher.start()
_fake_db = AsyncMock()
_fake_db.fetchval = AsyncMock(return_value=0)
_fake_db.fetchrow = AsyncMock(return_value=None)
_fake_db.fetch = AsyncMock(return_value=[])
_fake_db.execute = AsyncMock(return_value="OK")

import core.atendimento as atend

class TestSLAEnforcement(unittest.TestCase):
    """Fase 2 — SLA aplicado ao criar ticket."""

    @patch("core.atendimento.get_db", return_value=_fake_db)
    def test_criar_ticket_com_sla_urgente(self, mock_db):
        """Ticket urgente deve ter sla_vencimento = agora + 1h."""
        _fake_db.fetchrow.return_value = {"tempo_resposta_min": 60, "tempo_resolucao_h": 2}
        # mock _create to return a fake dict
        with patch.object(atend, "create", return_value={"id": 1, "status": "aberto"}) as mock_create:
            r = atend.criar_ticket("Cliente", "Assunto", canal="chat", prioridade="urgente")
        self.assertEqual(r["id"], 1)
        # verifica que create foi chamado com sla_vencimento e tempo_resposta_min
        args = mock_create.call_args[0][1]
        self.assertIsNotNone(args.get("sla_vencimento"))
        self.assertEqual(args["tempo_resposta_min"], 60)

    @patch("core.atendimento.get_db", return_value=_fake_db)
    def test_criar_ticket_sem_sla_configurado(self, mock_db):
        """Se SLA nao existe na tabela, cria sem sla_vencimento."""
        _fake_db.fetchrow.return_value = None
        with patch.object(atend, "create", return_value={"id": 2, "status": "aberto"}) as mock_create:
            r = atend.criar_ticket("Cliente", "Assunto", canal="email", prioridade="normal")
        self.assertEqual(r["id"], 2)
        args = mock_create.call_args[0][1]
        self.assertIsNone(args.get("sla_vencimento"))


class TestNumeroTicket(unittest.TestCase):
    @patch("core.atendimento.get_db", return_value=_fake_db)
    def test_criar_ticket_preenche_numero_sequencial(self, mock_db):
        _fake_db.fetchrow.return_value = {"tempo_resposta_min": 60, "tempo_resolucao_h": 2}
        _fake_db.fetchval.return_value = 7
        with patch.object(atend, "create") as mock_create:
            mock_create.return_value = {"id": 1, "numero": "#0007", "status": "aberto"}
            atend.criar_ticket("Cliente", "Assunto", canal="chat", prioridade="urgente")
        args = mock_create.call_args[0][1]
        self.assertEqual(args["numero"], "#0007")


class TestSLAValidacao(unittest.TestCase):
    """create()/update() de 'sla' — a UI antiga aceitava prioridade texto
    livre (nunca casava com criar_ticket, que so' consulta baixa/normal/
    alta/urgente) e tempo_resposta_min/tempo_resolucao_h zero ou negativo."""

    def test_create_sem_prioridade_rejeita(self):
        with patch.object(atend, "_create") as mock_create:
            resultado = atend.create("sla", {"tempo_resposta_min": 30, "tempo_resolucao_h": 4})
        mock_create.assert_not_called()
        self.assertEqual(resultado, {"error": "Prioridade e obrigatoria"})

    def test_create_com_prioridade_fora_do_enum_rejeita(self):
        with patch.object(atend, "_create") as mock_create:
            resultado = atend.create("sla", {"prioridade": "criticassima", "tempo_resposta_min": 10, "tempo_resolucao_h": 1})
        mock_create.assert_not_called()
        self.assertIn("error", resultado)

    def test_create_com_tempo_resposta_zero_rejeita(self):
        with patch.object(atend, "_create") as mock_create:
            resultado = atend.create("sla", {"prioridade": "baixa", "tempo_resposta_min": 0, "tempo_resolucao_h": 4})
        mock_create.assert_not_called()
        self.assertIn("error", resultado)

    def test_create_com_tempo_resolucao_negativo_rejeita(self):
        with patch.object(atend, "_create") as mock_create:
            resultado = atend.create("sla", {"prioridade": "baixa", "tempo_resposta_min": 10, "tempo_resolucao_h": -2})
        mock_create.assert_not_called()
        self.assertIn("error", resultado)

    def test_create_com_dados_validos_libera(self):
        with patch.object(atend, "_create", return_value={"id": 1, "prioridade": "alta"}) as mock_create:
            resultado = atend.create("sla", {"prioridade": "alta", "tempo_resposta_min": 15, "tempo_resolucao_h": 4})
        mock_create.assert_called_once()
        self.assertEqual(resultado, {"id": 1, "prioridade": "alta"})

    def test_update_parcial_sem_prioridade_nao_exige_prioridade(self):
        # so' mudar tempo_resposta_min (ex: ajustar regra existente) nao deve
        # exigir reenviar prioridade — mesmo padrao de update parcial do CRM.
        with patch.object(atend, "_update", return_value={"id": 1, "tempo_resposta_min": 20}) as mock_update:
            resultado = atend.update("sla", 1, {"tempo_resposta_min": 20})
        mock_update.assert_called_once()
        self.assertEqual(resultado, {"id": 1, "tempo_resposta_min": 20})

    def test_update_com_prioridade_fora_do_enum_rejeita(self):
        with patch.object(atend, "_update") as mock_update:
            resultado = atend.update("sla", 1, {"prioridade": "nao-existe"})
        mock_update.assert_not_called()
        self.assertIn("error", resultado)

    def test_validacao_nao_se_aplica_a_outras_tabelas(self):
        with patch.object(atend, "_create", return_value={"id": 1}) as mock_create:
            resultado = atend.create("kb_artigos", {"titulo": "Artigo sem validacao de SLA"})
        mock_create.assert_called_once()
        self.assertEqual(resultado, {"id": 1})


if __name__ == "__main__":
    unittest.main(verbosity=2)
