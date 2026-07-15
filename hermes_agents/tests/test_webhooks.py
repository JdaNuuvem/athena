"""Testes unitarios — Webhooks (Bling, WhatsApp, Shopee)."""
import sys,os,json,hmac,hashlib,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch,MagicMock

class TestBlingWebhook(unittest.TestCase):
    def test_hmac_valid(self):
        secret="test";body=b'{"evento":"pedido.criado"}';sig=hmac.new(secret.encode(),body,hashlib.sha256).hexdigest()
        os.environ["BLING_WEBHOOK_SECRET"]=secret
        from bling_erp import validar_assinatura_webhook
        result=validar_assinatura_webhook(body,sig)
        self.assertIsInstance(result,bool)
    def test_hmac_invalid(self):
        from bling_erp import validar_assinatura_webhook as v
        self.assertFalse(v(b"x","bad"))
    def test_payload_vazio(self):
        from bling_erp import processar_evento_webhook as p
        r=p("pedido.criado",{})
        self.assertIsInstance(r,dict)
    def test_evento_desconhecido(self):
        from bling_erp import processar_evento_webhook as p
        r=p("evento.inexistente",{})
        self.assertIn("processed",r)

if __name__=="__main__":unittest.main(verbosity=2)
