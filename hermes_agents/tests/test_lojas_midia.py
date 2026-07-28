"""Testes de core/lojas_midia.py — wrapper de midia da loja sobre o upload
generico ja existente em core/documentos.py (sem tabela nova: "tipo" e'
guardado na coluna "tags" ja existente, filtrando por entidade_tipo="loja")."""
import sys, os, shutil, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock


async def _mp(*a, **kw):
    return AsyncMock()


patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import core.documentos as documentos
import core.lojas_midia as midia


class FakeDB:
    def __init__(self):
        self.docs = {}
        self._next_id = 1

    def _norm(self, q):
        return " ".join(q.split())

    async def fetchrow(self, query, *params):
        q = self._norm(query)
        if q.startswith("INSERT INTO documentos"):
            nome_original, nome_armazenado, entidade_tipo, entidade_id, mime_type, tamanho, criado_por, tags = params
            did = self._next_id; self._next_id += 1
            row = {"id": did, "nome_original": nome_original, "nome_armazenado": nome_armazenado,
                   "entidade_tipo": entidade_tipo, "entidade_id": entidade_id, "mime_type": mime_type,
                   "tamanho_bytes": tamanho, "criado_por": criado_por, "tags": tags}
            self.docs[did] = row
            return dict(row)
        if q.startswith("SELECT nome_armazenado FROM documentos"):
            row = self.docs.get(params[0])
            return {"nome_armazenado": row["nome_armazenado"]} if row else None
        return None

    async def execute(self, query, *params):
        q = self._norm(query)
        if q.startswith("DELETE FROM documentos"):
            self.docs.pop(params[0], None)
        return "OK"

    async def fetch(self, query, *params):
        q = self._norm(query)
        if q.startswith("SELECT * FROM documentos WHERE entidade_tipo = $1 AND entidade_id = $2"):
            entidade_tipo, entidade_id, limit = params
            return [dict(r) for r in self.docs.values()
                    if r["entidade_tipo"] == entidade_tipo and r["entidade_id"] == entidade_id][:limit]
        return []


class TestLojasMidia(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.fake = FakeDB()

        async def _get_db(_fake=self.fake):
            return _fake
        self._p_db = patch("core.documentos.get_db", side_effect=_get_db)
        self._p_db.start()
        self._p_dir = patch.object(documentos, "STORAGE_DIR", self.tmpdir)
        self._p_dir.start()

    def tearDown(self):
        self._p_db.stop()
        self._p_dir.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    async def test_vincular_logo_grava_arquivo_real_e_registra(self):
        r = midia.vincular(1, "logo", b"conteudo-fake-do-logo", "logo.png", mime_type="image/png")
        self.assertNotIn("error", r)
        self.assertEqual(r["tags"], "logo")
        caminho = os.path.join(self.tmpdir, r["nome_armazenado"])
        self.assertTrue(os.path.exists(caminho))
        with open(caminho, "rb") as f:
            self.assertEqual(f.read(), b"conteudo-fake-do-logo")

    async def test_vincular_tipo_invalido_rejeitado(self):
        r = midia.vincular(1, "fachada-tipo-errado", b"x", "x.png")
        self.assertIn("error", r)

    async def test_listar_filtra_por_tipo(self):
        midia.vincular(1, "logo", b"a", "a.png")
        midia.vincular(1, "banner", b"b", "b.png")
        so_logo = midia.listar(1, tipo="logo")
        self.assertEqual(len(so_logo), 1)
        self.assertEqual(so_logo[0]["tags"], "logo")
        todos = midia.listar(1)
        self.assertEqual(len(todos), 2)

    async def test_remover_apaga_arquivo_e_registro(self):
        r = midia.vincular(1, "video", b"video-bytes", "v.mp4")
        caminho = os.path.join(self.tmpdir, r["nome_armazenado"])
        self.assertTrue(os.path.exists(caminho))
        midia.remover(r["id"])
        self.assertFalse(os.path.exists(caminho))
        self.assertNotIn(r["id"], self.fake.docs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
