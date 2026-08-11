"""Testes de core/lojas.py::impacto_exclusao() — dry-run de contagem por
tabela antes de uma exclusao forcada, sem apagar nada. Ver
docs/superpowers/specs/2026-08-09-exclusao-forcada-loja-design.md."""
import sys, os, unittest
from unittest.mock import patch, AsyncMock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def _mp(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import core.lojas as lojas


class TestImpactoExclusao(unittest.TestCase):
    def test_loja_inexistente_retorna_erro(self):
        db = AsyncMock()
        db.fetchrow.return_value = None
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.impacto_exclusao(999)
        self.assertEqual(resultado, {"erro": "Loja nao encontrada"})

    def test_loja_ativa_retorna_erro_pedindo_desativacao(self):
        db = AsyncMock()
        db.fetchrow.return_value = {"id": 1, "nome": "Loja Ativa", "status": "ativa"}
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.impacto_exclusao(1)
        self.assertEqual(resultado, {"erro": "Loja precisa estar inativa antes de avaliar exclusao forcada"})
        db.fetchval.assert_not_called()

    def test_loja_inativa_sem_dado_vinculado_retorna_contagens_zeradas(self):
        db = AsyncMock()
        db.fetchrow.return_value = {"id": 1, "nome": "Loja Teste", "status": "inativa"}
        db.fetchval.return_value = 0
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.impacto_exclusao(1)
        self.assertNotIn("erro", resultado)
        self.assertEqual(resultado["total_linhas"], 0)
        self.assertEqual(resultado["negociacoes_crm_desvinculadas"], 0)
        self.assertEqual(len(resultado["impacto"]), len(lojas._CASCATA_EXCLUSAO_FORCADA))
        self.assertTrue(all(n == 0 for n in resultado["impacto"].values()))

    def test_loja_inativa_com_dado_retorna_contagem_por_tabela(self):
        db = AsyncMock()
        db.fetchrow.return_value = {"id": 1, "nome": "Loja Teste", "status": "inativa"}
        def _fetchval(sql, *params):
            if sql.startswith("SELECT COUNT(*) FROM pdv_caixas WHERE"):
                return 3
            if sql.startswith("SELECT COUNT(*) FROM vendas_pedidos WHERE"):
                return 7
            return 0
        db.fetchval = AsyncMock(side_effect=_fetchval)
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.impacto_exclusao(1)
        self.assertEqual(resultado["impacto"]["pdv_caixas"], 3)
        self.assertEqual(resultado["impacto"]["vendas_pedidos"], 7)
        self.assertEqual(resultado["total_linhas"], 10)

    def test_loja_devolve_apenas_campos_minimos(self):
        """A rota lojas_impacto_exclusao faz jsonify(resultado) direto pro
        browser — resultado["loja"] precisa ser so' id/nome/status, nunca a
        linha completa da tabela (ver test_loja_nao_vaza_campos_sensiveis)."""
        db = AsyncMock()
        db.fetchrow.return_value = {"id": 5, "nome": "Loja Charme", "status": "inativa", "tipo": "fisica"}
        db.fetchval.return_value = 0
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.impacto_exclusao(5)
        self.assertEqual(resultado["loja"], {"id": 5, "nome": "Loja Charme", "status": "inativa"})

    def test_loja_nao_vaza_campos_sensiveis(self):
        """Achado do review final da branch: impacto_exclusao() fazia SELECT *
        e devolvia a linha inteira de "lojas" — incluindo pix_chave (nunca
        deve voltar em texto puro) e os tokens Shopee — pro cliente via
        jsonify. Mesmo com a linha mockada trazendo esses campos, o dict
        "loja" devolvido nao pode conte-los."""
        db = AsyncMock()
        db.fetchrow.return_value = {
            "id": 5, "nome": "Loja Charme", "status": "inativa", "tipo": "fisica",
            "pix_chave": "12345678900", "shopee_access_token": "token-secreto",
            "shopee_refresh_token": "refresh-secreto",
        }
        db.fetchval.return_value = 0
        with patch("core.lojas.get_db", AsyncMock(return_value=db)):
            resultado = lojas.impacto_exclusao(5)
        self.assertNotIn("pix_chave", resultado["loja"])
        self.assertNotIn("shopee_access_token", resultado["loja"])
        self.assertNotIn("shopee_refresh_token", resultado["loja"])
        self.assertEqual(resultado["loja"], {"id": 5, "nome": "Loja Charme", "status": "inativa"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
