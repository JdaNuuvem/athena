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

if __name__=="__main__":unittest.main(verbosity=2)
