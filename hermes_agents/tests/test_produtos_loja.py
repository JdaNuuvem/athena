"""Testes de core/produtos_loja.py — CRUD isolado com FakeDB."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch


class FakeDBProdutosLoja:
    def __init__(self):
        self.linhas = {}  # (loja, sku) -> dict
        self._next_id = 1
        self.auditorias = []

    async def execute(self, query, *params):
        return "OK"

    async def fetchval(self, query, *params):
        q = " ".join(query.split())
        if "SELECT id FROM produtos_loja WHERE loja" in q:
            loja, sku = params
            row = self.linhas.get((loja, sku))
            return row["id"] if row else None
        if "SELECT COUNT(*) FROM produtos_loja" in q:
            loja = params[0]
            return sum(1 for (l, _), r in self.linhas.items() if l == loja)
        return None

    async def fetchrow(self, query, *params):
        q = " ".join(query.split())
        if q.startswith("INSERT INTO produtos_loja"):
            loja, sku, mestre = params[0], params[1], params[2]
            row = {"id": self._next_id, "loja": loja, "sku": sku, "produto_mestre_sku": mestre}
            self.linhas[(loja, sku)] = row
            self._next_id += 1
            return row
        if q.startswith("SELECT * FROM produtos_loja WHERE loja"):
            loja, sku = params
            return self.linhas.get((loja, sku))
        if q.startswith("UPDATE produtos_loja SET"):
            loja, sku = params[0], params[1]
            row = self.linhas.get((loja, sku))
            if not row:
                return None
            # Apply all editable field updates from params[2:]
            campo_nomes = ["preco_custo", "preco_venda", "promocao_ativa", "promocao_preco",
                          "promocao_inicio", "promocao_fim", "comissao_pct", "fornecedor_id",
                          "deposito", "localizacao_fisica", "estoque_minimo", "estoque_maximo",
                          "observacoes_internas", "produto_mestre_sku", "codigo_interno",
                          "codigo_barras_override", "nome_override", "status"]
            for i, val in enumerate(params[2:]):
                if i < len(campo_nomes):
                    row[campo_nomes[i]] = val
            return row
        if q.startswith("DELETE FROM produtos_loja"):
            loja, sku = params
            row = self.linhas.pop((loja, sku), None)
            return row
        return None

    async def fetch(self, query, *params):
        loja = params[0]
        return [r for (l, _), r in self.linhas.items() if l == loja]


class TestProdutosLoja(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.fake = FakeDBProdutosLoja()
        async def _get_db(_fake=self.fake):
            return _fake
        self.patch_db = patch("core.produtos_loja.get_db", side_effect=_get_db)
        self.patch_db.start()
        self.patch_audit = patch("core.produtos_loja.auditar_alteracao", return_value=None)
        self.patch_audit.start()
        self.patch_audit_del = patch("core.produtos_loja.auditar_exclusao", return_value=None)
        self.patch_audit_del.start()
        import core.produtos_loja as m
        m._ok = True

    def tearDown(self):
        self.patch_db.stop()
        self.patch_audit.stop()
        self.patch_audit_del.stop()

    async def test_criar_produto_loja(self):
        from core.produtos_loja import criar
        r = criar("Loja A", "SKU1", produto_mestre_sku="SKU1")
        self.assertTrue(r.get("ok"))
        self.assertEqual(r["sku"], "SKU1")

    async def test_criar_duplicado_erro(self):
        from core.produtos_loja import criar
        criar("Loja A", "SKU1")
        r = criar("Loja A", "SKU1")
        self.assertIn("erro", r)

    async def test_criar_sem_loja_ou_sku_erro(self):
        from core.produtos_loja import criar
        self.assertIn("erro", criar("", "SKU1"))
        self.assertIn("erro", criar("Loja A", ""))

    async def test_obter_existente(self):
        from core.produtos_loja import criar, obter
        criar("Loja A", "SKU1")
        r = obter("Loja A", "SKU1")
        self.assertIsNotNone(r)
        self.assertEqual(r["sku"], "SKU1")

    async def test_obter_inexistente_retorna_none(self):
        from core.produtos_loja import obter
        self.assertIsNone(obter("Loja A", "SKU_NAO_EXISTE"))

    async def test_excluir_existente(self):
        from core.produtos_loja import criar, excluir, obter
        criar("Loja A", "SKU1")
        r = excluir("Loja A", "SKU1")
        self.assertTrue(r.get("ok"))
        self.assertIsNone(obter("Loja A", "SKU1"))

    async def test_excluir_inexistente_erro(self):
        from core.produtos_loja import excluir
        self.assertIn("erro", excluir("Loja A", "SKU_NAO_EXISTE"))

    async def test_atualizar_sem_campos_editaveis_erro(self):
        from core.produtos_loja import criar, atualizar
        criar("Loja A", "SKU1")
        r = atualizar("Loja A", "SKU1", campo_invalido="x")
        self.assertIn("erro", r)

    async def test_listar_por_loja(self):
        from core.produtos_loja import criar, listar_por_loja
        criar("Loja A", "SKU1", produto_mestre_sku="SKU1")
        criar("Loja A", "SKU2", produto_mestre_sku="SKU2")
        criar("Loja B", "SKU1", produto_mestre_sku="SKU1")
        r = listar_por_loja("Loja A")
        self.assertEqual(r["total"], 2)
        self.assertEqual(len(r["produtos"]), 2)
        self.assertEqual(r["pagina"], 1)
        skus = [p["sku"] for p in r["produtos"]]
        self.assertIn("SKU1", skus)
        self.assertIn("SKU2", skus)

    async def test_atualizar_sucesso(self):
        from core.produtos_loja import criar, atualizar
        criar("Loja A", "SKU1", preco_custo=50.00)
        r = atualizar("Loja A", "SKU1", preco_custo=99.90, preco_venda=150.00)
        self.assertTrue(r.get("ok"))
        self.assertEqual(r["preco_custo"], 99.90)
        self.assertEqual(r["preco_venda"], 150.00)
        self.assertEqual(r["sku"], "SKU1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
