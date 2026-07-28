"""Testes de core/lojas_operacional.py — config operacional (horario/matriz-
filial/codigos) e comercial (politica de precos/desconto/metas) da loja.
atualizar_operacional/atualizar_comercial delegam pro _update_campos
generico ja definido em core/lojas.py, entao o patch de get_db acontece em
core.lojas (nao em core.lojas_operacional)."""
import sys, os, re, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock


async def _mp(*a, **kw):
    return AsyncMock()


patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import core.lojas as lojas
import core.lojas_operacional as lojas_op


class FakeDB:
    def __init__(self):
        self.rows = {1: {"id": 1, "nome": "Loja Teste"}}

    async def execute(self, query, *params):
        q = " ".join(query.split())
        if "CREATE TABLE" in q or "ALTER TABLE" in q or "CREATE INDEX" in q:
            return "OK"
        m = re.match(r"UPDATE lojas SET (.+) WHERE id = \$(\d+)$", q)
        if m:
            id_loja = params[int(m.group(2)) - 1]
            if id_loja not in self.rows:
                return "UPDATE 0"
            for atrib in m.group(1).split(","):
                col, ph = [p.strip() for p in atrib.split("=")]
                self.rows[id_loja][col] = params[int(ph.lstrip("$")) - 1]
            return "UPDATE 1"
        return "OK"

    async def fetchval(self, query, *params):
        return 0

    async def fetchrow(self, query, *params):
        return None

    async def fetch(self, query, *params):
        return []


class TestLojasOperacionalComercial(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fake = FakeDB()

        async def _get_db(_fake=self.fake):
            return _fake
        # atualizar_operacional/atualizar_comercial chamam _update_campos,
        # definido em core.lojas — o get_db resolvido em runtime e' o de
        # core.lojas, nao o de core.lojas_operacional.
        self._p = patch("core.lojas.get_db", side_effect=_get_db)
        self._p.start()
        lojas._table_ok = True

    def tearDown(self):
        self._p.stop()
        lojas._table_ok = False

    async def test_atualizar_operacional_matriz_filial_e_codigos(self):
        ok = lojas_op.atualizar_operacional(1, {
            "codigo_interno": "LJ001", "codigo_erp": "ERP-001",
            "fuso_horario": "America/Sao_Paulo", "regiao": "Baixada Fluminense",
        })
        self.assertTrue(ok)
        row = self.fake.rows[1]
        self.assertEqual(row["codigo_interno"], "LJ001")
        self.assertEqual(row["regiao"], "Baixada Fluminense")

    async def test_atualizar_operacional_horario_funcionamento_vira_json(self):
        ok = lojas_op.atualizar_operacional(1, {
            "horario_funcionamento": {"seg": "08:00-18:00", "dom": "fechado"},
        })
        self.assertTrue(ok)
        salvo = self.fake.rows[1]["horario_funcionamento"]
        self.assertIsInstance(salvo, str)
        self.assertIn("08:00-18:00", salvo)

    async def test_atualizar_operacional_ignora_campo_comercial(self):
        ok = lojas_op.atualizar_operacional(1, {"meta_mensal": 50000})
        self.assertTrue(ok)
        self.assertNotIn("meta_mensal", self.fake.rows[1])

    async def test_atualizar_operacional_loja_inexistente_retorna_false(self):
        ok = lojas_op.atualizar_operacional(9999, {"codigo_interno": "X"})
        self.assertFalse(ok)

    async def test_atualizar_comercial_metas_e_desconto(self):
        ok = lojas_op.atualizar_comercial(1, {
            "desconto_maximo_pct": 15.0, "comissao_padrao_pct": 3.5,
            "meta_mensal": 80000.0, "meta_anual": 960000.0,
        })
        self.assertTrue(ok)
        row = self.fake.rows[1]
        self.assertEqual(row["desconto_maximo_pct"], 15.0)
        self.assertEqual(row["meta_anual"], 960000.0)

    async def test_atualizar_comercial_ignora_campo_operacional(self):
        ok = lojas_op.atualizar_comercial(1, {"codigo_interno": "NAO-DEVE-ENTRAR"})
        self.assertTrue(ok)  # dict vazio apos filtro -> _update_campos retorna True sem UPDATE
        self.assertNotIn("codigo_interno", self.fake.rows[1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
