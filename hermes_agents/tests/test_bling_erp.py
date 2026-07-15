"""Testes unitarios — Bling ERP SDK (bling_erp.py)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio

# Mock DB pool
_fake_pool = AsyncMock()
_fake_conn = AsyncMock()
_fake_conn.fetch.return_value = []
_fake_conn.fetchrow.return_value = None
_fake_conn.fetchval.return_value = 0
_fake_conn.execute.return_value = "OK"
_fake_conn.__aenter__ = AsyncMock(return_value=_fake_conn)
_fake_conn.__aexit__ = AsyncMock(return_value=None)
_fake_pool.acquire.return_value = _fake_conn

async def _mock_create_pool(*a, **kw):
    pool = AsyncMock()
    pool.acquire.return_value = _fake_conn
    return pool

patcher = patch("asyncpg.create_pool", side_effect=_mock_create_pool)
patcher.start()

import bling_erp as bling
import unittest

class TestBlingAuth(unittest.TestCase):
    def setUp(self): bling._TOKEN["access"] = ""
    def test_token_cache(self): bling.set_access_token("t"); self.assertEqual(bling.get_access_token(),"t"); bling.set_access_token(""); self.assertEqual(bling.get_access_token(),"")
    def test_status(self): self.assertFalse(bling.status()["autenticado"])
    def test_auth_url(self): self.assertIn("bling.com.br", bling.get_auth_url())

class TestBlingAPI(unittest.TestCase):
    def setUp(self): bling._TOKEN["access"] = "mock"
    @patch("bling_erp.requests.request")
    def test_sucesso(self, m): m.return_value.status_code=200; m.return_value.json.return_value={"data":[{"id":1}]}; self.assertIn("data",bling._request("p"))
    @patch("bling_erp.requests.request")
    def test_sem_token(self, m): bling._TOKEN["access"]=""; self.assertIn("error",bling._request("p"))
    @patch("bling_erp.requests.request")
    def test_timeout(self, m): import requests as r; m.side_effect=r.exceptions.Timeout(); self.assertIn("error",bling._request("p"))

class TestBlingWebhooks(unittest.TestCase):
    def test_hmac_valida(self): import hmac,hashlib; s="sec";b=b'{"x":1}';os.environ["BLING_WEBHOOK_SECRET"]=s;h=hmac.new(s.encode(),b,hashlib.sha256).hexdigest();self.assertTrue(bling.validar_assinatura_webhook(b,h))
    def test_hmac_invalida(self): self.assertFalse(bling.validar_assinatura_webhook(b"x","bad"))

class TestBlingSync(unittest.TestCase):
    def setUp(self): bling._TOKEN["access"]="mock"
    @patch("bling_erp.listar_produtos",return_value={"data":[]})
    def test_vazio(self, m): self.assertEqual(bling.sincronizar_produtos()["sincronizados"],0)

class TestBlingAgrupados(unittest.TestCase):
    def setUp(self): bling._TOKEN["access"]="mock"
    @patch("bling_erp._request",return_value={"data":[]})
    def test_vazio(self, m): self.assertEqual(bling.listar_produtos_agrupados()["total"],0)
    @patch("bling_erp._request",return_value={"data":[{"id":1,"codigo":"P"},{"id":2,"codigo":"F","idProdutoPai":1}]})
    def test_filhos(self, m): r=bling.listar_produtos_agrupados(); self.assertEqual(r["total_filhos"],1)

if __name__=="__main__": unittest.main(verbosity=2)

patcher.stop()
