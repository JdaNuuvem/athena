"""Testes — ao_converter_negociacao (evento "negociacao ganha" do CRM).

Cobre os 3 bugs corrigidos: (1) faltava idempotencia, reenviar o evento
criava um vendas_pedidos novo a cada chamada; (2) a negociacao nunca era
marcada como 'ganha'; (3) cliente_id recebia crm_empresas.id onde
vendas_pedidos.cliente_id espera cad_clientes.id — tabelas diferentes."""
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
from core.entidades import ao_converter_negociacao


class TestNegociacaoGanhaIdempotente(unittest.TestCase):
    def test_ja_processada_nao_reinsere_pedido(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value="OK")
        db.fetchrow = AsyncMock(return_value={"id": 5, "status": "ganha", "pedido_id": 42, "lead_id": None, "valor": 100})

        async def _fake_get_db():
            return db

        with patch("core.entidades.get_db", _fake_get_db):
            r = ao_converter_negociacao(5)

        self.assertEqual(r, {"pedido_id": 42, "ja_processada": True})
        # so' 1 fetchrow (SELECT da negociacao) — nao buscou lead/empresa nem inseriu pedido
        self.assertEqual(db.fetchrow.call_count, 1)


class TestNegociacaoGanhaClienteId(unittest.TestCase):
    def test_cliente_id_usa_cad_clientes_nao_crm_empresas(self):
        neg = {"id": 6, "status": "aberta", "pedido_id": None, "lead_id": 10, "valor": 500.0, "titulo": "Negociação X"}
        lead = {"id": 10, "nome": "Cliente Y", "empresa_id": 20}
        empresa = {"id": 20, "cnpj": "12.345.678/0001-99"}

        async def fake_fetchrow(query, *args):
            if "FROM crm_negociacoes WHERE id" in query:
                return neg
            if "FROM crm_leads WHERE id" in query:
                return lead
            if "FROM crm_empresas WHERE id" in query:
                return empresa
            if "INSERT INTO vendas_pedidos" in query:
                # empresa.id (20) NUNCA deve ser usado como cliente_id — so' um id
                # resolvido via cad_clientes (aqui, o fetchval abaixo -> 77)
                self.assertEqual(args[1], 77)
                return {"id": 999}
            raise AssertionError(f"fetchrow inesperado: {query}")

        db = AsyncMock()
        db.execute = AsyncMock(return_value="OK")
        db.fetchrow = AsyncMock(side_effect=fake_fetchrow)
        db.fetchval = AsyncMock(return_value=77)

        async def _fake_get_db():
            return db

        with patch("core.entidades.get_db", _fake_get_db):
            r = ao_converter_negociacao(6)

        self.assertEqual(r, {"pedido_id": 999})
        # UPDATE final marca a negociacao como ganha, com o pedido_id certo
        update_call = [c for c in db.execute.call_args_list if "UPDATE crm_negociacoes" in c.args[0]]
        self.assertEqual(len(update_call), 1)
        self.assertEqual(update_call[0].args[1], 999)  # pedido_id
        self.assertEqual(update_call[0].args[2], 6)     # negociacao_id


if __name__ == "__main__":
    unittest.main(verbosity=2)
