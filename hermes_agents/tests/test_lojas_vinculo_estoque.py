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
        db.fetchrow.return_value = {"nome": "Loja Virtual A", "tipo": "virtual", "nome_fisica": "Loja Fisica Central"}
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas._sync_run(lojas._loja_efetiva_async("42"))
        self.assertEqual(resultado, "Loja Fisica Central")

    def test_id_sem_vinculo_resolve_para_o_proprio_nome(self):
        db = AsyncMock()
        db.fetchrow.return_value = {"nome": "Loja Y", "nome_fisica": None}
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas._sync_run(lojas._loja_efetiva_async("7"))
        self.assertEqual(resultado, "Loja Y")

    def test_id_fisica_com_loja_vinculada_id_setado_ignora_e_resolve_proprio_nome(self):
        """Regressao: loja fisica (tipo != 'virtual') com loja_vinculada_id
        setado (nao deveria acontecer, mas o resolver nao pode confiar so' na
        escrita) deve resolver pro proprio nome, nunca pro nome "vinculado"."""
        db = AsyncMock()
        db.fetchrow.return_value = {"nome": "Loja Fisica Y", "tipo": "fisica", "nome_fisica": "Loja Vinculada Errada"}
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas._sync_run(lojas._loja_efetiva_async("99"))
        self.assertEqual(resultado, "Loja Fisica Y")

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

    def test_cursor_sync_id_virtual_com_vinculo_resolve_para_fisica(self):
        cur = MagicMock()
        cur.fetchone.return_value = ("Loja Virtual A", "virtual", "Loja Fisica Central")
        resultado = lojas.loja_efetiva_sync(cur, "42")
        self.assertEqual(resultado, "Loja Fisica Central")

    def test_cursor_sync_id_sem_vinculo_resolve_proprio_nome(self):
        cur = MagicMock()
        cur.fetchone.return_value = ("Loja Y", "fisica", None)
        resultado = lojas.loja_efetiva_sync(cur, "7")
        self.assertEqual(resultado, "Loja Y")

    def test_cursor_sync_id_fisica_com_loja_vinculada_id_setado_ignora_e_resolve_proprio_nome(self):
        """Regressao (mesmo caso do async acima): loja fisica com
        loja_vinculada_id setado nao deve resolver pro nome "vinculado"."""
        cur = MagicMock()
        cur.fetchone.return_value = ("Loja Fisica Y", "fisica", "Loja Vinculada Errada")
        resultado = lojas.loja_efetiva_sync(cur, "99")
        self.assertEqual(resultado, "Loja Fisica Y")


class TestVincularDesvincularEstoque(unittest.TestCase):
    def setUp(self):
        lojas.invalidar_cache_loja_efetiva()

    def test_vincular_rejeita_se_virtual_nao_e_tipo_virtual(self):
        db = AsyncMock()
        db.fetchrow.side_effect = [
            {"id": 1, "tipo": "fisica", "nome": "Loja A"},  # loja "virtual" informada
            {"id": 2, "tipo": "fisica", "nome": "Loja B"},
        ]
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.vincular_estoque(1, 2)
        self.assertIn("erro", resultado)

    def test_vincular_rejeita_se_fisica_nao_e_tipo_fisica(self):
        db = AsyncMock()
        db.fetchrow.side_effect = [
            {"id": 1, "tipo": "virtual", "nome": "Loja Virtual A"},
            {"id": 2, "tipo": "virtual", "nome": "Loja Virtual B"},
        ]
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.vincular_estoque(1, 2)
        self.assertIn("erro", resultado)

    def test_desvincular_sem_vinculo_ativo_retorna_erro(self):
        db = AsyncMock()
        db.fetchrow.return_value = {"id": 1, "tipo": "virtual", "nome": "Loja Virtual A", "loja_vinculada_id": None}
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.desvincular_estoque(1)
        self.assertIn("erro", resultado)

    def test_vincular_sucesso_grava_vinculo_e_invalida_cache(self):
        db = AsyncMock()
        db.fetchrow.side_effect = [
            {"id": 1, "tipo": "virtual", "nome": "Loja Virtual A"},
            {"id": 2, "tipo": "fisica", "nome": "Loja Fisica B"},
        ]
        lojas._cache_loja_efetiva["algo"] = "valor_stale"
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.vincular_estoque(1, 2)
        self.assertTrue(resultado.get("ok"))
        self.assertEqual(resultado["loja_virtual"], "Loja Virtual A")
        self.assertEqual(resultado["loja_fisica"], "Loja Fisica B")
        db.execute.assert_called_once_with(
            "UPDATE lojas SET loja_vinculada_id = $1 WHERE id = $2", 2, 1)
        self.assertEqual(lojas._cache_loja_efetiva, {})

    def test_desvincular_sucesso_copia_saldos_por_sku_e_limpa_vinculo(self):
        db = AsyncMock()
        db.fetchrow.side_effect = [
            {"id": 1, "tipo": "virtual", "nome": "Loja Virtual A", "loja_vinculada_id": 2},
            {"nome": "Loja Fisica B"},
        ]
        db.fetch.return_value = [
            {"sku": "SKU1", "quantidade": 10},
            {"sku": "SKU2", "quantidade": 5},
        ]
        lojas._cache_loja_efetiva["algo"] = "valor_stale"
        with patch("core.lojas.get_db", AsyncMock(return_value=db)), \
             patch("core.estoque.entrada", return_value={"ok": True}) as mock_entrada:
            resultado = lojas.desvincular_estoque(1)
        self.assertTrue(resultado.get("ok"))
        self.assertEqual(resultado["loja_virtual"], "Loja Virtual A")
        self.assertEqual(resultado["loja_fisica"], "Loja Fisica B")
        self.assertEqual(resultado["skus_copiados"], 2)
        mock_entrada.assert_any_call("SKU1", "Loja Virtual A", 10.0, "ajuste_inventario")
        mock_entrada.assert_any_call("SKU2", "Loja Virtual A", 5.0, "ajuste_inventario")
        limpa_calls = [c for c in db.execute.call_args_list
                       if "loja_vinculada_id = NULL" in c.args[0]]
        self.assertEqual(len(limpa_calls), 1)
        self.assertEqual(limpa_calls[0].args[1], 1)
        self.assertEqual(lojas._cache_loja_efetiva, {})

    def test_desvincular_nao_copia_skus_com_erro_na_entrada(self):
        """Se entrada() falhar pra um sku (ex.: motivo invalido), esse sku nao
        conta em skus_copiados mas nao interrompe os demais."""
        db = AsyncMock()
        db.fetchrow.side_effect = [
            {"id": 1, "tipo": "virtual", "nome": "Loja Virtual A", "loja_vinculada_id": 2},
            {"nome": "Loja Fisica B"},
        ]
        db.fetch.return_value = [
            {"sku": "SKU1", "quantidade": 10},
            {"sku": "SKU2", "quantidade": 5},
        ]
        with patch("core.lojas.get_db", AsyncMock(return_value=db)), \
             patch("core.estoque.entrada", side_effect=[{"erro": "falhou"}, {"ok": True}]):
            resultado = lojas.desvincular_estoque(1)
        self.assertTrue(resultado.get("ok"))
        self.assertEqual(resultado["skus_copiados"], 1)
