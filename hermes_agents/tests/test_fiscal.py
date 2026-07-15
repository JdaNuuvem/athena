"""Testes unitarios — Fiscal / NF-e Bling."""
import sys,os,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch,MagicMock,AsyncMock
async def _mp(*a,**kw):m=AsyncMock();m.acquire.return_value=AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(fetch=AsyncMock(return_value=[]),fetchrow=AsyncMock(return_value=None),fetchval=AsyncMock(return_value=0),execute=AsyncMock(return_value="OK"))),__aexit__=AsyncMock(return_value=None));return m
patcher=patch("asyncpg.create_pool",side_effect=_mp)
patcher.start()

class TestBlingNFe(unittest.TestCase):
    @patch("bling_erp.get_access_token",return_value="token")
    @patch("bling_erp.requests.request")
    def test_listar_notas(self,mr,mt):
        mr.return_value.status_code=200;mr.return_value.json.return_value={"data":[]}
        import bling_erp as b
        r=b.listar_notas_fiscais()
        self.assertIn("data",r)

    @patch("bling_erp.get_access_token",return_value="token")
    @patch("bling_erp.requests.request")
    def test_get_nfe_detail(self,mr,mt):
        mr.return_value.status_code=200;mr.return_value.json.return_value={"data":{"chave":"x"}}
        import bling_erp as b
        r=b.get_nfe_detail(1)
        self.assertIn("data",r)

    @patch("bling_erp.get_access_token",return_value="token")
    def test_get_nfe_xml_sem_url(self,mt):
        with patch("bling_erp.get_nfe_detail",return_value={"data":{}}):
            import bling_erp as b
            xml,ct=b.get_nfe_xml(1)
            self.assertIsNone(xml)

if __name__=="__main__":unittest.main(verbosity=2)
