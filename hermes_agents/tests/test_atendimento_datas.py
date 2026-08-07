"""Testes — bind de TIMESTAMP/DATE em Atendimento (revisao final do plano
2026-08-01-atendimento-tickets-estruturado).

asyncpg NAO aceita str como parametro ligado a coluna TIMESTAMP/DATE — exige
um objeto datetime.date/datetime.datetime nativo (mesmo precedente ja
documentado em core/fiscal.py._data, core/i9logic_vendas.py._gravar_pedido e
coberto por regressao em tests/test_pdv_estoque.py). Este arquivo cobre dois
achados da revisao final que reintroduziam essa classe de bug:

- listar_tickets_filtrado(de=..., ate=...) bindava as strings de query param
  direto, sem converter — filtro de data silenciosamente nao retornava nada
  (excecao do asyncpg engolida pelo except/log/return [] da funcao).
- criar_ticket / adicionar_mensagem / mudar_status_ticket usavam hoje()
  (que retorna str) pros campos data_abertura/enviado_em/data_fechamento,
  todos TIMESTAMP — o fluxo NOVO de criacao de ticket (unico caminho que a
  UI usa hoje) nunca foi exercitado contra Postgres real durante o plano
  (todos os testes mockam a camada de banco)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import date, datetime
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


class TestListarTicketsFiltradoCoercaoData(unittest.TestCase):
    """C2 — filtro de data (de/ate) precisa virar date real antes do bind."""

    @patch("core.atendimento.get_db", return_value=_fake_db)
    def test_de_ate_viram_date_nativo_nao_string(self, mock_db):
        _fake_db.fetch.reset_mock()
        _fake_db.fetch.return_value = []
        atend.listar_tickets_filtrado(de="2026-01-01", ate="2026-01-31")
        sql, *params = _fake_db.fetch.call_args[0]
        self.assertIn("data_abertura >= $1", sql)
        self.assertIn("data_abertura <= $2", sql)
        self.assertEqual(len(params), 2)
        for p in params:
            self.assertIsInstance(p, date)
            self.assertNotIsInstance(p, str)
        self.assertEqual(params[0], date(2026, 1, 1))
        self.assertEqual(params[1], date(2026, 1, 31))

    @patch("core.atendimento.get_db", return_value=_fake_db)
    def test_data_invalida_e_ignorada_sem_quebrar(self, mock_db):
        """Formato invalido nao deve virar bind de string crua nem estourar
        excecao — o filtro e' simplesmente descartado (e logado)."""
        _fake_db.fetch.reset_mock()
        _fake_db.fetch.return_value = []
        resultado = atend.listar_tickets_filtrado(de="nao-e-uma-data")
        self.assertEqual(resultado, [])
        sql, *params = _fake_db.fetch.call_args[0]
        self.assertNotIn("data_abertura", sql)
        self.assertEqual(params, [])


class TestTimestampsUsamDatetimeNativo(unittest.TestCase):
    """C3 — hoje() (string) nao pode ser bindado em coluna TIMESTAMP."""

    @patch("core.atendimento.get_db", return_value=_fake_db)
    def test_criar_ticket_data_abertura_e_datetime(self, mock_db):
        _fake_db.fetchrow.return_value = None
        with patch.object(atend, "create", return_value={"id": 1, "status": "aberto"}) as mock_create:
            atend.criar_ticket("Cliente", "Assunto")
        campos = mock_create.call_args[0][1]
        self.assertIsInstance(campos["data_abertura"], datetime)
        self.assertNotIsInstance(campos["data_abertura"], str)

    def test_adicionar_mensagem_enviado_em_e_datetime(self):
        with patch.object(atend, "create", return_value={"error": "skip-broadcast"}) as mock_create:
            atend.adicionar_mensagem(1, "atendente", "ola")
        campos = mock_create.call_args[0][1]
        self.assertIsInstance(campos["enviado_em"], datetime)
        self.assertNotIsInstance(campos["enviado_em"], str)

    def test_mudar_status_fechado_data_fechamento_e_datetime(self):
        with patch.object(atend, "get", return_value={"id": 1, "status": "aberto"}), \
             patch.object(atend, "update", return_value={"error": "skip-broadcast"}) as mock_update:
            atend.mudar_status_ticket(1, "fechado")
        campos = mock_update.call_args[0][2]
        self.assertIsInstance(campos["data_fechamento"], datetime)
        self.assertNotIsInstance(campos["data_fechamento"], str)


if __name__ == "__main__":
    unittest.main(verbosity=2)
