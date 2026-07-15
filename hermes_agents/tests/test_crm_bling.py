"""Testes unitarios — CRM + Bling Contatos."""
import sys,os,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch,MagicMock

class TestBlingContatos(unittest.TestCase):
    @patch("bling_erp.get_access_token",return_value="token")
    @patch("bling_erp.requests.request")
    def test_listar_contatos(self,mr,mt):
        mr.return_value.status_code=200;mr.return_value.json.return_value={"data":[{"id":1,"nome":"Cliente A"}]}
        import bling_erp as b
        r=b.listar_contatos()
        self.assertIn("data",r)
        self.assertEqual(len(r["data"]),1)

    @patch("bling_erp.get_access_token",return_value="token")
    @patch("bling_erp.requests.request")
    def test_listar_contatos_tipo_cliente(self,mr,mt):
        mr.return_value.status_code=200;mr.return_value.json.return_value={"data":[{"tipo":"C"}]}
        import bling_erp as b
        r=b.listar_contatos(tipo="C")
        self.assertIn("data",r)

if __name__=="__main__":unittest.main(verbosity=2)
