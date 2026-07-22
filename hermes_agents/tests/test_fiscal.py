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


class _FakeDBNotas:
    """Fake DB minimo para testar sincronizar_notas_fiscais_bling sem banco real."""
    def __init__(self, existing_id=None):
        self.existing_id = existing_id
        self.executed = []
        self.deleted_itens_nota_id = None

    async def fetchval(self, q, *a):
        if "SELECT id FROM fiscal_notas_fiscais" in q:
            return self.existing_id
        if "INSERT INTO fiscal_notas_fiscais" in q:
            return 99
        return 1

    async def fetchrow(self, q, *a):
        return None

    async def execute(self, q, *a):
        self.executed.append((q, a))
        if "DELETE FROM fiscal_nfe_itens" in q:
            self.deleted_itens_nota_id = a[0]


_NFE_DETALHE_MOCK = {
    "id": 777, "numero": "500", "chaveAcesso": "CHV500", "tipo": 0,
    "dataEmissao": "2026-07-20 09:00:00",
    "contato": {"nome": "Cliente Fiscal", "numeroDocumento": "99988877766"},
    "naturezaOperacao": {"descricao": "Venda de mercadoria", "cfop": "5102"},
    "loja": {"id": 3}, "situacao": 1,
    "total": 220.0, "totalProdutos": 200.0, "valorFrete": 20.0,
    "xml": "https://bling.com.br/nfe/777.xml", "danfe": "https://bling.com.br/nfe/777/danfe",
    "itens": [{"codigo": "SKU-X", "descricao": "Item X", "ncm": "11223344",
               "cfop": "5102", "unidade": "UN", "quantidade": 2,
               "valorUnitario": 100.0, "valor": 200.0}],
    "tributos": {"totalICMS": 36.0, "totalIPI": 0.0, "totalPIS": 3.3, "totalCOFINS": 15.2},
}


class TestSincronizarNotasFiscaisBling(unittest.TestCase):
    def setUp(self):
        import core.fiscal as fiscal
        self.fiscal = fiscal

    @patch("bling_erp.get_access_token", return_value="")
    def test_sem_token(self, mt):
        r = self.fiscal.sincronizar_notas_fiscais_bling()
        self.assertIn("error", r)

    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.listar_notas_fiscais", return_value={"data": []})
    def test_sem_notas(self, ml, mt):
        r = self.fiscal.sincronizar_notas_fiscais_bling()
        self.assertEqual(r["sync"], 0)

    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.listar_notas_fiscais", return_value={"data": [{"id": 777}]})
    @patch("bling_erp.get_nfe_completa", return_value={"data": _NFE_DETALHE_MOCK})
    def test_cria_nota_com_detalhe_completo(self, mdet, ml, mt):
        db = _FakeDBNotas(existing_id=None)
        async def fake_get_db(): return db
        with patch.object(self.fiscal, "get_db", fake_get_db):
            r = self.fiscal.sincronizar_notas_fiscais_bling()
        self.assertEqual(r["sync"], 1)
        insert_itens = [e for e in db.executed if "INSERT INTO fiscal_nfe_itens" in e[0]]
        self.assertEqual(len(insert_itens), 1)
        self.assertEqual(insert_itens[0][1][2], "SKU-X")  # codigo do item

    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.listar_notas_fiscais", return_value={"data": [{"id": 777}]})
    @patch("bling_erp.get_nfe_completa", return_value={"data": _NFE_DETALHE_MOCK})
    def test_atualiza_nota_existente_refaz_itens(self, mdet, ml, mt):
        db = _FakeDBNotas(existing_id=55)
        async def fake_get_db(): return db
        with patch.object(self.fiscal, "get_db", fake_get_db):
            r = self.fiscal.sincronizar_notas_fiscais_bling()
        self.assertEqual(r["sync"], 1)
        self.assertEqual(db.deleted_itens_nota_id, 55)

    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.listar_notas_fiscais", return_value={"data": [{"id": 777}]})
    @patch("bling_erp.get_nfe_completa", return_value={"error": "falhou"})
    def test_fallback_para_resumo_quando_detalhe_falha(self, mdet, ml, mt):
        db = _FakeDBNotas(existing_id=None)
        async def fake_get_db(): return db
        with patch.object(self.fiscal, "get_db", fake_get_db):
            r = self.fiscal.sincronizar_notas_fiscais_bling()
        self.assertEqual(r["sync"], 1)
        self.assertTrue(any("777" in e for e in r["erros"]))


if __name__=="__main__":unittest.main(verbosity=2)
