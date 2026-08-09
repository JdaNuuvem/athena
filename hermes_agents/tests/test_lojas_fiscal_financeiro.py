"""Testes de core/lojas_fiscal_financeiro.py — financeiro/estoque-config, e
a mascara de campos sensiveis antes de auditoria (chave PIX nunca em texto
puro em audit_log)."""
import sys, os, re, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock


async def _mp(*a, **kw):
    return AsyncMock()


patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import core.lojas as lojas
import core.lojas_fiscal_financeiro as ff


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


class TestLojasFiscalFinanceiro(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fake = FakeDB()

        async def _get_db(_fake=self.fake):
            return _fake
        self._p = patch("core.lojas.get_db", side_effect=_get_db)
        self._p.start()
        lojas._table_ok = True

    def tearDown(self):
        self._p.stop()
        lojas._table_ok = False

    async def test_atualizar_financeiro(self):
        ok = ff.atualizar_financeiro(1, {
            "conta_bancaria": "Banco X ag 0001 cc 12345", "gateway_pagamento": "mercado_pago",
            "pix_chave": "loja1@charme.com",
        })
        self.assertTrue(ok)
        self.assertEqual(self.fake.rows[1]["gateway_pagamento"], "mercado_pago")

    async def test_atualizar_estoque_config(self):
        ok = ff.atualizar_estoque_config(1, {
            "deposito_principal": "CD Nilopolis", "permitir_estoque_negativo": False,
            "estoque_minimo_padrao": 10.0, "estoque_reservado": True,
        })
        self.assertTrue(ok)
        row = self.fake.rows[1]
        self.assertEqual(row["deposito_principal"], "CD Nilopolis")
        self.assertTrue(row["estoque_reservado"])

    async def test_atualizar_estoque_config_permitir_negativo_false_nao_e_ignorado(self):
        """False e' um valor valido (nao deve ser filtrado como 'ausente')."""
        ok = ff.atualizar_estoque_config(1, {"permitir_estoque_negativo": False})
        self.assertTrue(ok)
        self.assertIn("permitir_estoque_negativo", self.fake.rows[1])
        self.assertFalse(self.fake.rows[1]["permitir_estoque_negativo"])

    def test_mascarar_para_auditoria_esconde_campos_sensiveis(self):
        campos = {
            "gateway_pagamento": "mercado_pago",
            "pix_chave": "loja1@charme.com",
        }
        mascarado = ff.mascarar_para_auditoria(campos)
        self.assertEqual(mascarado["gateway_pagamento"], "mercado_pago")
        self.assertNotEqual(mascarado["pix_chave"], campos["pix_chave"])
        self.assertTrue(mascarado["pix_chave"].startswith("configurado:"))

    def test_mascarar_para_auditoria_campo_vazio_marca_configurado_false(self):
        mascarado = ff.mascarar_para_auditoria({"pix_chave": ""})
        self.assertEqual(mascarado["pix_chave"], "configurado: False")


if __name__ == "__main__":
    unittest.main(verbosity=2)
