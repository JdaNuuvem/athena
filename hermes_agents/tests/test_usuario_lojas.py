"""Testes de core/usuario_lojas.py — vinculo usuario<->loja que CONTROLA
ACESSO (diferente de loja_responsaveis, que e' so' registro informativo)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock


async def _mp(*a, **kw):
    return AsyncMock()


patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import core.usuario_lojas as usuario_lojas


class FakeDB:
    def __init__(self):
        self.vinculos = []  # [(usuario_id, loja_id)]
        self.executed = []
        self._in_tx = False

    async def fetch(self, query, *params):
        q = " ".join(query.split())
        self.executed.append((q, params))
        if "SELECT loja_id FROM usuario_lojas WHERE usuario_id" in q:
            (usuario_id,) = params
            return [{"loja_id": lid} for (uid, lid) in self.vinculos if uid == usuario_id]
        if "JOIN lojas l ON l.id = ul.loja_id" in q:
            (usuario_id,) = params
            return [{"id": lid, "nome": f"Loja {lid}"} for (uid, lid) in self.vinculos if uid == usuario_id]
        return []

    async def fetchrow(self, query, *params):
        self.executed.append((query, params))
        if "INSERT INTO usuario_lojas" in query and "RETURNING" in query:
            usuario_id, loja_id = params
            if (usuario_id, loja_id) in self.vinculos:
                return None  # ON CONFLICT DO NOTHING -> sem RETURNING
            self.vinculos.append((usuario_id, loja_id))
            return {"id": len(self.vinculos), "usuario_id": usuario_id, "loja_id": loja_id}
        return None

    async def execute(self, query, *params):
        self.executed.append((query, params))
        if "DELETE FROM usuario_lojas WHERE usuario_id = $1 AND loja_id" in query:
            usuario_id, loja_id = params
            before = len(self.vinculos)
            self.vinculos = [v for v in self.vinculos if v != (usuario_id, loja_id)]
            return "DELETE 1" if len(self.vinculos) < before else "DELETE 0"
        if "DELETE FROM usuario_lojas WHERE usuario_id = $1" in query:
            (usuario_id,) = params
            self.vinculos = [v for v in self.vinculos if v[0] != usuario_id]
            return "DELETE"
        if "INSERT INTO usuario_lojas" in query:
            usuario_id, loja_id = params
            if (usuario_id, loja_id) not in self.vinculos:
                self.vinculos.append((usuario_id, loja_id))
            return "INSERT 1"
        return "OK"

    def transaction(self):
        return _FakeTx()


class _FakeTx:
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False


class TestUsuarioLojas(unittest.TestCase):
    def setUp(self):
        self.fake = FakeDB()
        async def _get_db(_fake=self.fake): return _fake
        self._p = patch("core.usuario_lojas.get_db", side_effect=_get_db)
        self._p.start()
        usuario_lojas._table_ok = True  # pula CREATE TABLE (ja coberto por _ensure_table isolado)

    def tearDown(self):
        self._p.stop()

    def test_vincular_grava_e_lista(self):
        usuario_lojas.vincular(7, 3)
        self.assertEqual(usuario_lojas.listar_ids_lojas_do_usuario(7), [3])

    def test_vincular_duplicado_nao_quebra(self):
        usuario_lojas.vincular(7, 3)
        r = usuario_lojas.vincular(7, 3)
        self.assertNotIn("error", r)
        self.assertEqual(usuario_lojas.listar_ids_lojas_do_usuario(7), [3])

    def test_desvincular_remove(self):
        usuario_lojas.vincular(7, 3)
        ok = usuario_lojas.desvincular(7, 3)
        self.assertTrue(ok)
        self.assertEqual(usuario_lojas.listar_ids_lojas_do_usuario(7), [])

    def test_desvincular_inexistente_retorna_false(self):
        self.assertFalse(usuario_lojas.desvincular(7, 999))

    def test_substituir_vinculos_troca_conjunto_completo(self):
        usuario_lojas.vincular(7, 3)
        usuario_lojas.vincular(7, 4)
        usuario_lojas.substituir_vinculos(7, [5, 6])
        self.assertEqual(sorted(usuario_lojas.listar_ids_lojas_do_usuario(7)), [5, 6])

    def test_substituir_vinculos_lista_vazia_remove_tudo(self):
        usuario_lojas.vincular(7, 3)
        usuario_lojas.substituir_vinculos(7, [])
        self.assertEqual(usuario_lojas.listar_ids_lojas_do_usuario(7), [])

    def test_vinculo_de_outro_usuario_nao_interfere(self):
        usuario_lojas.vincular(99, 3)
        self.assertEqual(usuario_lojas.listar_ids_lojas_do_usuario(7), [])

    def test_listar_lojas_do_usuario_traz_nome(self):
        usuario_lojas.vincular(7, 3)
        r = usuario_lojas.listar_lojas_do_usuario(7)
        self.assertEqual(r, [{"id": 3, "nome": "Loja 3"}])


if __name__ == "__main__":
    unittest.main(verbosity=2)
