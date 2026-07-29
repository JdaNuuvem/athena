"""Tabelas normalizadas de marca/fabricante/categoria/tag (Fase 1 PIM Core) e
o CRUD basico sobre elas."""
import sys, os, unittest, importlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock, MagicMock


def _fake_db(fetchval_return=1):
    db = MagicMock()
    db.execute = AsyncMock(return_value="OK")
    db.fetchval = AsyncMock(return_value=fetchval_return)
    db.fetch = AsyncMock(return_value=[])
    db.fetchrow = AsyncMock(return_value=None)
    return db


class TestTabelasOrganizacao(unittest.TestCase):
    def test_ensure_tables_cria_tabelas_normalizadas(self):
        fake_db = _fake_db(fetchval_return=1)  # >0 => pula migracao de dedup
        with patch("core.get_db", new=AsyncMock(return_value=fake_db)):
            import core.catalogo as catalogo
            importlib.reload(catalogo)
        sql_executado = " ".join(str(c.args[0]) for c in fake_db.execute.call_args_list if c.args)
        for tabela in ("catalogo_marcas", "catalogo_fabricantes", "catalogo_categorias",
                       "catalogo_tags", "catalogo_produto_tags"):
            self.assertIn(tabela, sql_executado, f"tabela {tabela} nao foi criada")


class TestCrudMarcas(unittest.TestCase):
    def test_criar_marca_retorna_id_e_nome(self):
        fake_db = _fake_db()
        fake_db.fetchrow = AsyncMock(return_value={"id": 1, "nome": "Nike"})
        with patch("core.catalogo.get_db", new=AsyncMock(return_value=fake_db)):
            import core.catalogo as catalogo
            resultado = catalogo.criar_marca("Nike")
        self.assertEqual(resultado, {"id": 1, "nome": "Nike"})

    def test_listar_marcas_retorna_lista(self):
        fake_db = _fake_db()
        fake_db.fetch = AsyncMock(return_value=[{"id": 1, "nome": "Nike"}, {"id": 2, "nome": "Adidas"}])
        with patch("core.catalogo.get_db", new=AsyncMock(return_value=fake_db)):
            import core.catalogo as catalogo
            resultado = catalogo.listar_marcas()
        self.assertEqual(len(resultado), 2)


class TestVinculoTags(unittest.TestCase):
    def test_vincular_tag_produto(self):
        fake_db = _fake_db()
        fake_db.execute = AsyncMock(return_value="INSERT 0 1")
        with patch("core.catalogo.get_db", new=AsyncMock(return_value=fake_db)):
            import core.catalogo as catalogo
            resultado = catalogo.vincular_tag(10, 3)
        self.assertEqual(resultado, {"success": True})
        fake_db.execute.assert_called_once()
        self.assertIn("catalogo_produto_tags", str(fake_db.execute.call_args.args[0]))


class TestMigracaoDedupMarca(unittest.TestCase):
    def test_migracao_so_roda_quando_tabela_vazia(self):
        """Se catalogo_marcas ja tem registros, a migracao de dedup nao deve
        rodar de novo (evita duplicar em todo boot)."""
        # Test 1: When table already has data (fetchval_return=5), migration should NOT run
        fake_db = _fake_db(fetchval_return=5)  # tabela ja populada
        with patch("core.get_db", new=AsyncMock(return_value=fake_db)):
            import core.catalogo as catalogo
            importlib.reload(catalogo)

        # Count how many times "INSERT INTO catalogo_marcas" was called
        insert_calls = [c for c in fake_db.execute.call_args_list if c.args and "INSERT INTO catalogo_marcas" in str(c.args[0])]
        self.assertEqual(len(insert_calls), 0, "Migration should NOT run when catalogo_marcas is already populated")

    def test_migracao_roda_quando_tabela_vazia(self):
        """Quando catalogo_marcas esta vazia, a migracao deve rodar uma vez."""
        # Test 2: When table is empty (fetchval_return=0), migration SHOULD run
        fake_db = _fake_db(fetchval_return=0)  # tabela vazia
        with patch("core.get_db", new=AsyncMock(return_value=fake_db)):
            import core.catalogo as catalogo
            importlib.reload(catalogo)

        # Count how many times "INSERT INTO catalogo_marcas" was called
        insert_calls = [c for c in fake_db.execute.call_args_list if c.args and "INSERT INTO catalogo_marcas" in str(c.args[0])]
        self.assertGreater(len(insert_calls), 0, "Migration SHOULD run when catalogo_marcas is empty")


if __name__ == "__main__":
    unittest.main(verbosity=2)
