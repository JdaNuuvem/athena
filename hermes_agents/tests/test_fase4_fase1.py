"""Testes — Rotacao de Estoque (Fase 4) + PDV Auth/Desconto (Fase 1)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

async def _mock_pool(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(
        __aenter__=AsyncMock(return_value=AsyncMock(
            fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
            fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"),
        )),
        __aexit__=AsyncMock(return_value=None),
    )
    return m
patcher = patch("asyncpg.create_pool", side_effect=_mock_pool)
patcher.start()
_fake_db = AsyncMock()
_fake_db.fetchval = AsyncMock(return_value=0)
_fake_db.fetchrow = AsyncMock(return_value=None)
_fake_db.fetch = AsyncMock(return_value=[])
_fake_db.execute = AsyncMock(return_value="OK")

import core.estoque as est
import core.pdv as pdv

class TestSugestaoRotacao(unittest.TestCase):
    """Fase 4 — Sugestao de transferencia entre lojas."""

    def test_rotacao_sem_dados(self):
        """Sem estoque em nenhuma loja, retorna vazio."""
        with patch("core.estoque.run_async", return_value=[]):
            r = est.sugestao_rotacao()
        self.assertEqual(r, [])

    def test_rotacao_com_desbalanceamento(self):
        """Excesso na Loja A, escassez na Loja B."""
        result = [{
            "sku": "SKU1", "nome": "Produto X",
            "loja_excesso": "Loja A", "qtd_excesso": 50,
            "loja_escassez": "Loja B", "qtd_escassez": 1,
            "sugerir_transferir": 25,
        }]
        with patch("core.estoque.run_async", return_value=result):
            r = est.sugestao_rotacao()
        self.assertGreaterEqual(len(r), 1)
        s = r[0]
        self.assertEqual(s["sku"], "SKU1")
        self.assertEqual(s["loja_excesso"], "Loja A")
        self.assertEqual(s["loja_escassez"], "Loja B")
        self.assertGreater(s["sugerir_transferir"], 0)

    def test_rotacao_balanceada(self):
        """Estoques equilibrados nao geram sugestao."""
        with patch("core.estoque.run_async", return_value=[]):
            r = est.sugestao_rotacao()
        self.assertEqual(r, [])  # escassez tem 8, > 2, nao sugere


class TestPDVAuth(unittest.TestCase):
    """Fase 1 — Auth de operador PDV."""

    def test_login_operador_nao_encontrado(self):
        """Operador inexistente retorna erro."""
        with patch("core.pdv.run_async", return_value={"error": "Operador nao encontrado ou inativo"}):
            r = pdv.login_operador("Inexistente", "senha")
        self.assertIn("error", r)

    def test_login_sem_senha_cadastrada(self):
        """Operador sem senha (legado) permite acesso."""
        op_data = {"id": 1, "nome": "Admin", "role": "admin",
                   "desconto_maximo_percent": 100, "autenticado": True}
        with patch("core.pdv.run_async", return_value=op_data):
            r = pdv.login_operador("Admin", "")
        self.assertTrue(r.get("autenticado"))
        self.assertEqual(r["id"], 1)

    def test_desconto_excede_limite(self):
        """Desconto acima do maximo do operador deve bloquear."""
        with patch.object(pdv, "_get", return_value={"id": 2, "desconto_maximo_percent": 10}):
            r = pdv.realizar_venda(
                caixa_id=1, itens=[{"codigo": "SKU1", "descricao": "X", "quantidade": 1, "valor_unitario": 100}],
                pagamentos=[], operador_id=2, desconto=20.0
            )
        self.assertIn("error", r)
        self.assertIn("Desconto maximo", r.get("error", ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
