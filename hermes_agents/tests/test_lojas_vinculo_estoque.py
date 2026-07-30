"""Testes de core/lojas.py — resolver de vinculo de estoque fisica x virtual
e vincular_estoque()/desvincular_estoque()."""
import sys, os, unittest
from unittest.mock import patch, AsyncMock, MagicMock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.lojas as lojas


class TestLojaEfetivaAsync(unittest.TestCase):
    def setUp(self):
        lojas.invalidar_cache_loja_efetiva()

    def test_loja_sem_vinculo_retorna_o_proprio_nome(self):
        db = AsyncMock()
        db.fetchrow.return_value = None
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas._sync_run(lojas._loja_efetiva_async("Loja X"))
        self.assertEqual(resultado, "Loja X")

    def test_loja_virtual_vinculada_resolve_para_fisica(self):
        db = AsyncMock()
        db.fetchrow.return_value = {"nome": "Loja Fisica Central"}
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas._sync_run(lojas._loja_efetiva_async("Loja Virtual A"))
        self.assertEqual(resultado, "Loja Fisica Central")

    def test_loja_vazia_nao_consulta_banco(self):
        db = AsyncMock()
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas._sync_run(lojas._loja_efetiva_async(""))
        self.assertEqual(resultado, "")
        db.fetchrow.assert_not_called()

    def test_id_com_vinculo_resolve_para_nome_da_fisica(self):
        db = AsyncMock()
        db.fetchrow.return_value = {"nome": "Loja Virtual A", "nome_fisica": "Loja Fisica Central"}
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas._sync_run(lojas._loja_efetiva_async("42"))
        self.assertEqual(resultado, "Loja Fisica Central")

    def test_id_sem_vinculo_resolve_para_o_proprio_nome(self):
        db = AsyncMock()
        db.fetchrow.return_value = {"nome": "Loja Y", "nome_fisica": None}
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas._sync_run(lojas._loja_efetiva_async("7"))
        self.assertEqual(resultado, "Loja Y")

    def test_cache_evita_segunda_consulta(self):
        db = AsyncMock()
        db.fetchrow.return_value = {"nome": "Loja Fisica Central"}
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            lojas._sync_run(lojas._loja_efetiva_async("Loja Virtual A"))
            lojas._sync_run(lojas._loja_efetiva_async("Loja Virtual A"))
        self.assertEqual(db.fetchrow.call_count, 1)


class TestLojaEfetivaSync(unittest.TestCase):
    def setUp(self):
        lojas.invalidar_cache_loja_efetiva()

    def test_cursor_sync_resolve_vinculo(self):
        cur = MagicMock()
        cur.fetchone.return_value = ("Loja Fisica Central",)
        resultado = lojas.loja_efetiva_sync(cur, "Loja Virtual A")
        self.assertEqual(resultado, "Loja Fisica Central")

    def test_cursor_sync_sem_vinculo_retorna_proprio_nome(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        resultado = lojas.loja_efetiva_sync(cur, "Loja X")
        self.assertEqual(resultado, "Loja X")
