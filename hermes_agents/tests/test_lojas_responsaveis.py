"""Testes de core/lojas_responsaveis.py — vinculo informativo usuario<->loja
com cargo/permissoes/vigencia (nao controla acesso, so' registra "quem
responde por essa loja")."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock


async def _mp(*a, **kw):
    return AsyncMock()


patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import core.lojas_responsaveis as resp


class FakeDB:
    def __init__(self):
        self.vinculos = {}
        self._next_id = 1
        self.usuarios = {7: {"nome": "Joao Gerente", "email": "joao@charme.com"}}

    def _norm(self, q):
        return " ".join(q.split())

    async def execute(self, query, *params):
        q = self._norm(query)
        if "CREATE TABLE" in q or "CREATE INDEX" in q:
            return "OK"
        if q.startswith("UPDATE loja_responsaveis SET cargo"):
            cargo, vid = params
            if vid not in self.vinculos:
                return "UPDATE 0"
            self.vinculos[vid]["cargo"] = cargo
            return "UPDATE 1"
        if q.startswith("UPDATE loja_responsaveis SET permissoes"):
            permissoes, vid = params
            if vid not in self.vinculos:
                return "UPDATE 0"
            self.vinculos[vid]["permissoes"] = permissoes
            return "UPDATE 1"
        if q.startswith("UPDATE loja_responsaveis SET data_fim"):
            data_fim, vid = params
            if vid not in self.vinculos:
                return "UPDATE 0"
            self.vinculos[vid]["data_fim"] = data_fim or "2026-07-28"
            return "UPDATE 1"
        if q.startswith("DELETE FROM loja_responsaveis"):
            vid = params[0]
            if vid not in self.vinculos:
                return "DELETE 0"
            del self.vinculos[vid]
            return "DELETE 1"
        return "OK"

    async def fetchrow(self, query, *params):
        q = self._norm(query)
        if q.startswith("INSERT INTO loja_responsaveis"):
            loja_id, usuario_id, cargo, permissoes, data_inicio, data_fim = params
            vid = self._next_id; self._next_id += 1
            row = {"id": vid, "loja_id": loja_id, "usuario_id": usuario_id, "cargo": cargo,
                   "permissoes": permissoes, "data_inicio": data_inicio or "2026-01-01", "data_fim": data_fim}
            self.vinculos[vid] = row
            return dict(row)
        return None

    async def fetch(self, query, *params):
        q = self._norm(query)
        if "FROM loja_responsaveis r JOIN rbac_usuarios" in q:
            loja_id = params[0]
            result = []
            for v in self.vinculos.values():
                if v["loja_id"] == loja_id:
                    u = self.usuarios.get(v["usuario_id"], {"nome": "?", "email": "?"})
                    result.append({**v, "usuario_nome": u["nome"], "usuario_email": u["email"]})
            return result
        return []


class TestLojasResponsaveis(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fake = FakeDB()

        async def _get_db(_fake=self.fake):
            return _fake
        self._p = patch("core.lojas_responsaveis.get_db", side_effect=_get_db)
        self._p.start()
        resp._table_ok = True

    def tearDown(self):
        self._p.stop()
        resp._table_ok = False

    async def test_vincular_gerente_geral_sucesso(self):
        r = resp.vincular(1, 7, "gerente_geral", data_inicio="2026-01-01")
        self.assertNotIn("error", r)
        self.assertEqual(r["cargo"], "gerente_geral")
        self.assertEqual(r["loja_id"], 1)

    async def test_vincular_cargo_invalido_retorna_error(self):
        r = resp.vincular(1, 7, "faxineiro")
        self.assertIn("error", r)

    async def test_listar_traz_nome_e_email_do_usuario(self):
        resp.vincular(1, 7, "proprietario")
        result = resp.listar(1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["usuario_nome"], "Joao Gerente")

    async def test_atualizar_cargo(self):
        r = resp.vincular(1, 7, "responsavel_pdv")
        ok = resp.atualizar(r["id"], cargo="gerente_estoque")
        self.assertTrue(ok)
        self.assertEqual(self.fake.vinculos[r["id"]]["cargo"], "gerente_estoque")

    async def test_atualizar_cargo_invalido_retorna_false(self):
        r = resp.vincular(1, 7, "responsavel_fiscal")
        ok = resp.atualizar(r["id"], cargo="rei-da-loja")
        self.assertFalse(ok)

    async def test_encerrar_marca_data_fim(self):
        r = resp.vincular(1, 7, "administrador")
        ok = resp.encerrar(r["id"], data_fim="2026-12-31")
        self.assertTrue(ok)
        self.assertEqual(self.fake.vinculos[r["id"]]["data_fim"], "2026-12-31")

    async def test_remover_apaga_vinculo(self):
        r = resp.vincular(1, 7, "gerente_financeiro")
        ok = resp.remover(r["id"])
        self.assertTrue(ok)
        self.assertNotIn(r["id"], self.fake.vinculos)

    async def test_remover_inexistente_retorna_false(self):
        self.assertFalse(resp.remover(9999))


if __name__ == "__main__":
    unittest.main(verbosity=2)
