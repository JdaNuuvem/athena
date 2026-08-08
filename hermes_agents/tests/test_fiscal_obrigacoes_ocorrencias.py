"""Fase 1 do redesenho Fiscal — Obrigacoes vira cadastro (fiscal_obrigacoes,
com dia_vencimento fixo + ativo) e ocorrencia por competencia
(fiscal_obrigacoes_ocorrencias, uma linha por mes, vencimento calculado de
verdade). Antes a "obrigacao" tinha uma unica data_vencimento congelada
desde o primeiro boot — nunca mais recalculada."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock, MagicMock

# Mock asyncpg BEFORE any imports
with patch("asyncpg.create_pool", new_callable=AsyncMock):
    import core.fiscal as fiscal


class _FakeDB:
    """Fake minimo o suficiente pra exercitar _garantir_ocorrencias sem
    depender de Postgres real — grava as ocorrencias inseridas num set em
    memoria e simula ON CONFLICT DO NOTHING checando esse set."""

    def __init__(self, obrigacoes_ativas, hoje):
        self._obrigacoes = obrigacoes_ativas
        self._hoje = hoje
        self.existentes = set()  # {(obrigacao_id, competencia)}
        self.inseridas = []

    async def fetchval(self, query, *params):
        if "CURRENT_DATE" in query:
            return self._hoje
        return 0

    async def fetch(self, query, *params):
        if "fiscal_obrigacoes WHERE ativo" in query:
            return self._obrigacoes
        return []

    async def execute(self, query, *params):
        if "INSERT INTO fiscal_obrigacoes_ocorrencias" in query:
            obrigacao_id, competencia, venc = params
            chave = (obrigacao_id, competencia)
            if chave in self.existentes:
                return "INSERT 0 0"
            self.existentes.add(chave)
            self.inseridas.append({"obrigacao_id": obrigacao_id, "competencia": competencia, "data_vencimento": venc})
            return "INSERT 0 1"
        return "OK"


class TestCalcularVencimento(unittest.TestCase):
    def test_dia_normal(self):
        import datetime
        self.assertEqual(fiscal._calcular_vencimento(2026, 8, 15), datetime.date(2026, 8, 15))

    def test_dia_alem_do_ultimo_dia_do_mes_e_ajustado(self):
        """Fevereiro nao tem dia 31 — clampa pro ultimo dia real do mes."""
        import datetime
        self.assertEqual(fiscal._calcular_vencimento(2026, 2, 31), datetime.date(2026, 2, 28))

    def test_ano_bissexto(self):
        import datetime
        self.assertEqual(fiscal._calcular_vencimento(2028, 2, 31), datetime.date(2028, 2, 29))


class TestGarantirOcorrencias(unittest.TestCase):
    def test_cria_ocorrencia_para_cada_obrigacao_ativa(self):
        import datetime
        db = _FakeDB(
            obrigacoes_ativas=[{"id": 1, "dia_vencimento": 15}, {"id": 2, "dia_vencimento": 10}],
            hoje=datetime.date(2026, 8, 8),
        )
        with patch.object(fiscal, "get_db", AsyncMock(return_value=db)):
            resultado = fiscal.garantir_ocorrencias_mes_atual()
        self.assertEqual(resultado["criadas"], 2)
        competencias = {i["competencia"] for i in db.inseridas}
        self.assertEqual(competencias, {"2026-08"})

    def test_idempotente_nao_duplica_na_segunda_chamada(self):
        import datetime
        db = _FakeDB(
            obrigacoes_ativas=[{"id": 1, "dia_vencimento": 15}],
            hoje=datetime.date(2026, 8, 8),
        )
        with patch.object(fiscal, "get_db", AsyncMock(return_value=db)):
            fiscal.garantir_ocorrencias_mes_atual()
            resultado2 = fiscal.garantir_ocorrencias_mes_atual()
        self.assertEqual(resultado2["criadas"], 0)
        self.assertEqual(len(db.inseridas), 1)

    def test_sem_dia_vencimento_usa_dia_1_como_fallback(self):
        import datetime
        db = _FakeDB(
            obrigacoes_ativas=[{"id": 1, "dia_vencimento": None}],
            hoje=datetime.date(2026, 8, 8),
        )
        with patch.object(fiscal, "get_db", AsyncMock(return_value=db)):
            fiscal.garantir_ocorrencias_mes_atual()
        self.assertEqual(db.inseridas[0]["data_vencimento"], datetime.date(2026, 8, 1))


class TestBaixarOcorrencia(unittest.TestCase):
    def test_marca_entregue_com_responsavel(self):
        db = AsyncMock()
        db.fetchrow = AsyncMock(return_value={"id": 5, "obrigacao_id": 1, "status": "entregue", "responsavel": "joao@x.com"})
        with patch.object(fiscal, "get_db", AsyncMock(return_value=db)):
            r = fiscal.baixar_ocorrencia(5, "joao@x.com")
        self.assertNotIn("error", r)
        self.assertEqual(r["status"], "entregue")
        db.fetchrow.assert_called_once()
        query = db.fetchrow.call_args.args[0]
        self.assertIn("UPDATE fiscal_obrigacoes_ocorrencias", query)
        self.assertIn("status='entregue'", query)

    def test_ocorrencia_inexistente(self):
        db = AsyncMock()
        db.fetchrow = AsyncMock(return_value=None)
        with patch.object(fiscal, "get_db", AsyncMock(return_value=db)):
            r = fiscal.baixar_ocorrencia(999)
        self.assertEqual(r, {"error": "ocorrencia nao encontrada"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
