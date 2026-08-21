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
        self.fetchvals = []
        self.deleted_itens_nota_id = None

    async def fetchval(self, q, *a):
        self.fetchvals.append((q, a))
        if "SELECT id FROM fiscal_notas_fiscais" in q:
            return self.existing_id
        if "INSERT INTO fiscal_notas_fiscais" in q:
            return 99
        return 1

    async def fetchrow(self, q, *a):
        return None

    async def fetch(self, q, *a):
        # fiscal_tributos ativos, usados pra popular fiscal_impostos_nota —
        # lista vazia = nenhum tributo cadastrado, comportamento seguro (so'
        # nao popula a tabela derivada, nao quebra o upsert da nota/itens).
        return []

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

    def test_mapear_nfe_detalhe_datas_sao_date_reais(self):
        """asyncpg exige datetime.date nos parametros ligados a colunas DATE — passar
        string (mesmo com ::date no SQL) falha com 'str' object has no attribute 'toordinal'."""
        from datetime import date
        campos = self.fiscal._mapear_nfe_detalhe(_NFE_DETALHE_MOCK)
        self.assertEqual(campos["data_emissao"], date(2026, 7, 20))
        self.assertIsInstance(campos["data_emissao"], date)
        self.assertNotIsInstance(campos["data_emissao"], str)

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

    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.listar_notas_fiscais", return_value={"data": [{"id": 777}]})
    def test_erro_fora_do_loop_nao_propaga(self, ml, mt):
        """ponytail: get_db() (ou qualquer coisa fora do try/except por-nota)
        falhando nao pode subir como excecao crua ate o Flask — tem que virar
        {"error":..., "sync":0}, igual toda outra funcao deste arquivo."""
        async def fake_get_db(): raise RuntimeError("conexao recusada")
        with patch.object(self.fiscal, "get_db", fake_get_db):
            r = self.fiscal.sincronizar_notas_fiscais_bling()
        self.assertIn("error", r)
        self.assertEqual(r["sync"], 0)
        self.assertIn("conexao recusada", r["error"])

    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.listar_notas_fiscais", return_value={"data": [{"id": i} for i in range(1, 61)]})
    @patch("bling_erp.get_nfe_completa", return_value={"data": _NFE_DETALHE_MOCK})
    def test_processa_em_lote_com_continuacao(self, mdet, ml, mt):
        """ponytail: processar o detalhe de todas as notas numa chamada so'
        estourava o timeout de 100s do proxy Cloudflare com contas reais
        (centenas de notas). Cap de 50 por chamada + mais_notas/proximo_pular
        pro chamador continuar em lotes."""
        db = _FakeDBNotas(existing_id=None)
        async def fake_get_db(): return db
        with patch.object(self.fiscal, "get_db", fake_get_db):
            r1 = self.fiscal.sincronizar_notas_fiscais_bling()
        self.assertEqual(r1["sync"], 50)
        self.assertTrue(r1["mais_notas"])
        self.assertEqual(r1["proximo_pular"], 50)
        self.assertEqual(r1["total_notas"], 60)

        with patch.object(self.fiscal, "get_db", fake_get_db):
            r2 = self.fiscal.sincronizar_notas_fiscais_bling(pular=50)
        self.assertEqual(r2["sync"], 10)
        self.assertFalse(r2["mais_notas"])
        self.assertEqual(r2["proximo_pular"], 0)


class TestUpsertNotaFiscalTipoDocumento(unittest.TestCase):
    """tipo_documento distingue NF-e / NFC-e / NFS-e dentro da MESMA tabela
    fiscal_notas_fiscais. O parametro e' o ULTIMO da assinatura e tem default
    'nfe' — nenhum caller existente muda de comportamento."""
    def setUp(self):
        import core.fiscal as fiscal
        from core import run_async
        self.fiscal = fiscal
        self.run_async = run_async

    def _insert_call(self, db):
        return next(c for c in db.fetchvals if "INSERT INTO fiscal_notas_fiscais" in c[0])

    def _update_call(self, db):
        return next(c for c in db.executed if "UPDATE fiscal_notas_fiscais" in c[0])

    def test_upsert_grava_tipo_documento_nfce_quando_informado(self):
        db = _FakeDBNotas(existing_id=None)
        self.run_async(self.fiscal._upsert_nota_fiscal(db, 999, _NFE_DETALHE_MOCK, tipo_documento="nfce"))
        self.assertIn("nfce", self._insert_call(db)[1])

    def test_upsert_default_continua_nfe_sem_passar_tipo_documento(self):
        db = _FakeDBNotas(existing_id=None)
        self.run_async(self.fiscal._upsert_nota_fiscal(db, 998, _NFE_DETALHE_MOCK))
        self.assertIn("nfe", self._insert_call(db)[1])

    def test_update_grava_tipo_documento_e_mantem_bling_id_no_where(self):
        """No UPDATE o bling_id do WHERE tem que continuar sendo o ULTIMO
        argumento posicional — tipo_documento entra imediatamente ANTES dele."""
        db = _FakeDBNotas(existing_id=55)
        self.run_async(self.fiscal._upsert_nota_fiscal(db, 777, _NFE_DETALHE_MOCK, tipo_documento="nfse"))
        q, args = self._update_call(db)
        self.assertEqual(args[-1], 777)
        self.assertEqual(args[-2], "nfse")

    def test_contagem_de_placeholders_bate_com_argumentos(self):
        """Guarda contra o erro classico desta funcao: adicionar coluna e esquecer
        de adicionar o argumento (ou vice-versa) desalinha TODOS os campos fiscais
        seguintes sem erro de sintaxe — so' dado errado silencioso."""
        import re
        db_ins = _FakeDBNotas(existing_id=None)
        self.run_async(self.fiscal._upsert_nota_fiscal(db_ins, 999, _NFE_DETALHE_MOCK))
        q_ins, args_ins = self._insert_call(db_ins)
        self.assertEqual(max(int(n) for n in re.findall(r"\$(\d+)", q_ins)), len(args_ins))
        colunas = q_ins.split("(", 1)[1].split(")", 1)[0]
        # -1: sincronizado_em usa NOW(), nao placeholder
        self.assertEqual(len([c for c in colunas.split(",") if c.strip()]) - 1, len(args_ins))

        db_upd = _FakeDBNotas(existing_id=55)
        self.run_async(self.fiscal._upsert_nota_fiscal(db_upd, 777, _NFE_DETALHE_MOCK))
        q_upd, args_upd = self._update_call(db_upd)
        self.assertEqual(max(int(n) for n in re.findall(r"\$(\d+)", q_upd)), len(args_upd))

class TestSincronizarNfceNfseBling(unittest.TestCase):
    """NFC-e e NFS-e reaproveitam fiscal_notas_fiscais + _upsert_nota_fiscal,
    trocando so' o wrapper de API Bling e o tipo_documento gravado."""
    def setUp(self):
        import core.fiscal as fiscal
        self.fiscal = fiscal

    def _tipo_gravado(self, db):
        q, args = next(c for c in db.fetchvals if "INSERT INTO fiscal_notas_fiscais" in c[0])
        return args[-1]

    @patch("bling_erp.get_access_token", return_value="")
    def test_nfce_sem_token(self, mt):
        r = self.fiscal.sincronizar_nfce_bling()
        self.assertIn("error", r)

    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.listar_nfce", return_value={"data": []})
    def test_nfce_sem_notas(self, ml, mt):
        r = self.fiscal.sincronizar_nfce_bling()
        self.assertEqual(r["sync"], 0)

    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.listar_nfce", return_value={"data": [{"id": 111}]})
    @patch("bling_erp.get_nfce_detalhe", return_value={"data": _NFE_DETALHE_MOCK})
    def test_sincronizar_nfce_bling_grava_tipo_documento_nfce(self, mdet, ml, mt):
        db = _FakeDBNotas(existing_id=None)
        async def fake_get_db(): return db
        with patch.object(self.fiscal, "get_db", fake_get_db):
            r = self.fiscal.sincronizar_nfce_bling()
        self.assertEqual(r["sync"], 1)
        self.assertEqual(self._tipo_gravado(db), "nfce")

    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.listar_nfse", return_value={"data": [{"id": 222}]})
    @patch("bling_erp.get_nfse_detalhe", return_value={"data": _NFE_DETALHE_MOCK})
    def test_sincronizar_nfse_bling_grava_tipo_documento_nfse(self, mdet, ml, mt):
        db = _FakeDBNotas(existing_id=None)
        async def fake_get_db(): return db
        with patch.object(self.fiscal, "get_db", fake_get_db):
            r = self.fiscal.sincronizar_nfse_bling()
        self.assertEqual(r["sync"], 1)
        self.assertEqual(self._tipo_gravado(db), "nfse")

    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.listar_nfce", return_value={"data": [{"id": 111}]})
    @patch("bling_erp.get_nfce_detalhe", return_value={"error": "falhou"})
    def test_nfce_fallback_para_resumo_quando_detalhe_falha(self, mdet, ml, mt):
        db = _FakeDBNotas(existing_id=None)
        async def fake_get_db(): return db
        with patch.object(self.fiscal, "get_db", fake_get_db):
            r = self.fiscal.sincronizar_nfce_bling()
        self.assertEqual(r["sync"], 1)
        self.assertTrue(any("111" in e for e in r["erros"]))

    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.listar_nfce", return_value={"data": [{"id": i} for i in range(1, 61)]})
    @patch("bling_erp.get_nfce_detalhe", return_value={"data": _NFE_DETALHE_MOCK})
    def test_nfce_processa_em_lote_com_continuacao(self, mdet, ml, mt):
        """Mesmo cap de 50 por chamada do sync de NF-e (timeout de 100s do proxy)."""
        db = _FakeDBNotas(existing_id=None)
        async def fake_get_db(): return db
        with patch.object(self.fiscal, "get_db", fake_get_db):
            r1 = self.fiscal.sincronizar_nfce_bling()
        self.assertEqual(r1["sync"], 50)
        self.assertTrue(r1["mais_notas"])
        self.assertEqual(r1["proximo_pular"], 50)
        self.assertEqual(r1["total_notas"], 60)
        with patch.object(self.fiscal, "get_db", fake_get_db):
            r2 = self.fiscal.sincronizar_nfce_bling(pular=50)
        self.assertEqual(r2["sync"], 10)
        self.assertFalse(r2["mais_notas"])

    @patch("bling_erp.get_access_token", return_value="tok")
    @patch("bling_erp.listar_nfse", return_value={"data": [{"id": 222}]})
    def test_nfse_erro_fora_do_loop_nao_propaga(self, ml, mt):
        async def fake_get_db(): raise RuntimeError("conexao recusada")
        with patch.object(self.fiscal, "get_db", fake_get_db):
            r = self.fiscal.sincronizar_nfse_bling()
        self.assertIn("error", r)
        self.assertEqual(r["sync"], 0)

if __name__=="__main__":unittest.main(verbosity=2)
