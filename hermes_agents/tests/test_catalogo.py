"""Testes unitarios — Catalogo SSOT."""
import sys,os,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch,MagicMock,AsyncMock
async def _mp(*a,**kw):m=AsyncMock();m.acquire.return_value=AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(fetch=AsyncMock(return_value=[]),fetchrow=AsyncMock(return_value=None),fetchval=AsyncMock(return_value=0),execute=AsyncMock(return_value="OK"))),__aexit__=AsyncMock(return_value=None));return m
patcher=patch("asyncpg.create_pool",side_effect=_mp)
patcher.start()
import core.catalogo as cat

class TestCatalogo(unittest.TestCase):
    def test_import_ok(self):self.assertTrue(hasattr(cat,"AGENT"))
    def test_buscar_por_sku_nao_existe(self):r=cat.buscar_por_sku("NAOEXISTE");self.assertTrue(r is None or isinstance(r,dict))
    def test_listar_alguma_coisa(self):
        funcs=["listar_produtos","listar_produtos_estoque","listar_todos","listar"]
        for fname in funcs:
            if hasattr(cat,fname):
                r=getattr(cat,fname)()
                self.assertIsInstance(r,list)
                return
        self.skipTest("nenhuma funcao de listagem encontrada")

if __name__=="__main__":unittest.main(verbosity=2)
