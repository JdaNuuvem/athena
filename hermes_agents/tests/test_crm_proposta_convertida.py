"""Testes — ao_converter_proposta_em_contrato (evento "proposta aceita -> gera
contrato" do CRM). Antes desse evento, uma proposta aceita nao tinha nenhum
caminho pra virar contrato — crm_contratos.proposta_id existia no schema mas
nada preenchia. Mesmo padrao de test_crm_negociacao_ganha.py (idempotencia,
FK correta entre tabelas diferentes)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

_fake_conn = AsyncMock()
_fake_conn.__aenter__ = AsyncMock(return_value=AsyncMock())
_fake_conn.__aexit__ = AsyncMock(return_value=None)
async def _mock_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = _fake_conn
    return m
patcher = patch("asyncpg.create_pool", side_effect=_mock_pool)
patcher.start()

import core  # noqa
from core.entidades import ao_converter_proposta_em_contrato


class TestConverterPropostaEmContrato(unittest.TestCase):
    def test_proposta_nao_encontrada(self):
        db = AsyncMock()
        db.fetchrow = AsyncMock(return_value=None)

        async def _fake_get_db(): return db

        with patch("core.entidades.get_db", _fake_get_db):
            r = ao_converter_proposta_em_contrato(999)
        self.assertEqual(r, {"error": "proposta nao encontrada"})

    def test_ja_convertida_e_idempotente(self):
        db = AsyncMock()
        db.fetchrow = AsyncMock(return_value={"id": 5, "negociacao_id": 1, "valor": 1000.0, "status": "aceita"})
        db.fetchval = AsyncMock(return_value=77)  # ja existe contrato com proposta_id=5

        async def _fake_get_db(): return db

        with patch("core.entidades.get_db", _fake_get_db):
            r = ao_converter_proposta_em_contrato(5)
        self.assertEqual(r, {"contrato_id": 77, "ja_processada": True})
        db.execute.assert_not_called()

    def test_cria_contrato_com_negociacao_e_valor_da_proposta(self):
        proposta = {"id": 6, "negociacao_id": 3, "valor": 2500.0, "status": "aceita"}

        async def fake_fetchrow(query, *args):
            if "FROM crm_propostas WHERE id" in query:
                return proposta
            if "INSERT INTO crm_contratos" in query:
                self.assertEqual(args[0], 3)      # negociacao_id
                self.assertEqual(args[1], 6)       # proposta_id
                self.assertEqual(args[2], 2500.0)  # valor
                return {"id": 42}
            raise AssertionError(f"fetchrow inesperado: {query}")

        db = AsyncMock()
        db.fetchrow = AsyncMock(side_effect=fake_fetchrow)
        db.fetchval = AsyncMock(return_value=None)  # nenhum contrato existente ainda
        db.execute = AsyncMock(return_value="OK")

        async def _fake_get_db(): return db

        with patch("core.entidades.get_db", _fake_get_db):
            r = ao_converter_proposta_em_contrato(6)

        self.assertEqual(r, {"contrato_id": 42})
        numero_call = [c for c in db.execute.call_args_list if "UPDATE crm_contratos" in c.args[0] and "numero" in c.args[0]]
        self.assertEqual(len(numero_call), 1)
        self.assertEqual(numero_call[0].args[1], "CONT-0042")

    def test_proposta_nao_aceita_ainda_rejeita_conversao(self):
        # so' faz sentido gerar contrato de uma proposta que o cliente aceitou
        # — converter uma "rascunho"/"enviada" sem resposta seria criar um
        # contrato de algo que ainda nao foi fechado.
        db = AsyncMock()
        db.fetchrow = AsyncMock(return_value={"id": 7, "negociacao_id": 1, "valor": 100.0, "status": "enviada"})
        db.fetchval = AsyncMock(return_value=None)  # nenhum contrato existente ainda

        async def _fake_get_db(): return db

        with patch("core.entidades.get_db", _fake_get_db):
            r = ao_converter_proposta_em_contrato(7)
        self.assertIn("error", r)
        db.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
