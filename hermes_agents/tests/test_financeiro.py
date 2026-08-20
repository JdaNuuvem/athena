"""Testes unitarios — Financeiro + Bling (contas pagar/receber, fluxo caixa, DRE)."""
import sys,os,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch,MagicMock,AsyncMock
async def _mp(*a,**kw):m=AsyncMock();m.acquire.return_value=AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(fetch=AsyncMock(return_value=[]),fetchrow=AsyncMock(return_value=None),fetchval=AsyncMock(return_value=0),execute=AsyncMock(return_value="OK"))),__aexit__=AsyncMock(return_value=None));return m
patcher=patch("asyncpg.create_pool",side_effect=_mp)
patcher.start()
import core.financeiro as fin

class TestFinanceiro(unittest.TestCase):
    def test_list_fluxo(self):r=fin.list("fluxo_caixa");self.assertIsInstance(r,list)
    def test_list_contas(self):r=fin.list("contas_receber");self.assertIsInstance(r,list)
    def test_fluxo_resumo(self):r=fin.fluxo_caixa_resumo();self.assertIn("resumo",r)
    def test_dre_resumo(self):r=fin.dre_resumo();self.assertIn("resultado",r)

class TestBlingFinanceiro(unittest.TestCase):
    @patch("bling_erp.get_access_token",return_value="token")
    @patch("bling_erp.requests.request")
    def test_listar_contas_pagar(self,mr,mt):
        mr.return_value.status_code=200;mr.return_value.json.return_value={"data":[]}
        import bling_erp as b
        r=b.listar_contas_pagar()
        self.assertIn("data",r)

    def test_sincronizar_plano_contas_bling_faz_upsert_por_bling_id(self):
        fake_db = AsyncMock()
        fake_db.fetchval.side_effect = [None, None]  # 1a chamada: checa coluna; 2a: checa conta existente
        with patch("bling_erp.get_access_token", return_value="tok"), \
             patch("core.financeiro.get_db", new=AsyncMock(return_value=fake_db)), \
             patch("bling_erp.listar_contas_contabeis", return_value={"data": [
                 {"id": 999, "descricao": "Receita de Vendas Online", "tipo": "R"},
             ]}):
            resultado = fin.sincronizar_plano_contas_bling()
        self.assertEqual(resultado["sync"], 1)
        sqls_executados = [c.args[0] for c in fake_db.execute.call_args_list]
        self.assertTrue(any("ALTER TABLE fin_plano_contas ADD COLUMN" in s for s in sqls_executados))
        self.assertTrue(any("INSERT INTO fin_plano_contas" in s for s in sqls_executados))
        # migracao de coluna nunca pode apagar/truncar o seed de 11 linhas ja
        # existente em fin_plano_contas — ADD COLUMN IF NOT EXISTS e' a unica
        # operacao de schema permitida contra essa tabela no sync.
        self.assertFalse(any("DROP" in s.upper() or "TRUNCATE" in s.upper() or "DELETE FROM fin_plano_contas" in s.upper() for s in sqls_executados))

if __name__=="__main__":unittest.main(verbosity=2)
