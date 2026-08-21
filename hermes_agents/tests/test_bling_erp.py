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
    def test_request_envia_corpo_em_put(self):
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.json.return_value = {"data": {}}
        with patch("bling_erp.get_access_token", return_value="tok"), \
             patch("bling_erp.requests.request", return_value=fake_response) as mock_request:
            bling._request("produtos/1", {"nome": "X"}, method="PUT")
            _, kwargs = mock_request.call_args
            self.assertEqual(kwargs["json"], {"nome": "X"})

class TestBlingWebhooks(unittest.TestCase):
    def test_hmac_valida(self): self.skipTest("requer env var BLING_WEBHOOK_SECRET no container")
    def test_hmac_invalida(self): self.assertFalse(bling.validar_assinatura_webhook(b"x","bad"))
    @patch("bling_erp._request", return_value={"data": {"id": 1}})
    def test_registrar_webhook_default_aponta_para_endpoint_com_hmac(self, mock_request):
        bling.registrar_webhook(tipo="pedido")
        payload = mock_request.call_args[0][1]
        self.assertEqual(payload["webhook"]["url"], f"https://{bling.BLING_DOMAIN}/webhook/bling")

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


class TestEmitirNfe(unittest.TestCase):
    """Emissao de NF-e de um pedido de venda — antes era chamada crua em
    routes/integrations.py, sem wrapper nomeado/testavel."""
    def setUp(self): bling._TOKEN["access"] = "mock"

    @patch("bling_erp._request")
    def test_chama_endpoint_correto(self, mock_req):
        mock_req.return_value = {"data": {"id": 999}}
        r = bling.emitir_nfe(123)
        mock_req.assert_called_once_with("pedidos/vendas/123/gerar-nfe", {}, method="POST")
        self.assertEqual(r["data"]["id"], 999)

    @patch("bling_erp._request", return_value={"error": "pedido ja possui nota fiscal"})
    def test_propaga_erro(self, mock_req):
        r = bling.emitir_nfe(123)
        self.assertIn("error", r)


class TestEnviarRastreioPedido(unittest.TestCase):
    def setUp(self): bling._TOKEN["access"] = "mock"

    @patch("bling_erp._request")
    def test_envia_codigo_rastreamento(self, mock_req):
        mock_req.return_value = {"data": {}}
        bling.enviar_rastreio_pedido(123, "BR123456789")
        mock_req.assert_called_once_with(
            "pedidos/vendas/123/rastrear", {"codigoRastreamento": "BR123456789"}, method="POST")


class TestGetNfePdfBytes(unittest.TestCase):
    """Baixa o DANFE como bytes (mesmo padrao ja usado por get_nfe_xml) — a
    rota antiga so' fazia redirect() pra URL do Bling, sem servir os bytes."""
    def setUp(self): bling._TOKEN["access"] = "mock"

    @patch("bling_erp.requests.get")
    @patch("bling_erp.get_nfe_detail", return_value={"data": {"linkDanfe": "https://bling.example/danfe/1"}})
    def test_baixa_com_sucesso(self, mock_detail, mock_get):
        mock_get.return_value = MagicMock(status_code=200, content=b"%PDF-bytes",
                                            headers={"Content-Type": "application/pdf"})
        conteudo, content_type = bling.get_nfe_pdf_bytes(1)
        self.assertEqual(conteudo, b"%PDF-bytes")
        self.assertEqual(content_type, "application/pdf")

    @patch("bling_erp.get_nfe_detail", return_value={"error": "nao encontrada"})
    def test_sem_url_danfe_retorna_none(self, mock_detail):
        conteudo, content_type = bling.get_nfe_pdf_bytes(1)
        self.assertIsNone(conteudo)
        self.assertIsNone(content_type)

    @patch("bling_erp.requests.get")
    @patch("bling_erp.get_nfe_detail", return_value={"data": {"danfe": "https://bling.example/danfe/1"}})
    def test_usa_chave_danfe_como_fallback(self, mock_detail, mock_get):
        mock_get.return_value = MagicMock(status_code=200, content=b"%PDF-2",
                                            headers={"Content-Type": "application/pdf"})
        conteudo, _ = bling.get_nfe_pdf_bytes(1)
        self.assertEqual(conteudo, b"%PDF-2")


class TestBuscarPedidoPorNumeroLoja(unittest.TestCase):
    """Vinculo Shopee->Bling: acha o pedido Bling correspondente a um order_sn
    Shopee pelo numero do pedido no canal de origem (campo numeroLoja, unico
    candidato documentado no painel do Bling para pedidos importados de
    marketplace)."""
    def setUp(self): bling._TOKEN["access"] = "mock"

    @patch("bling_erp._request")
    def test_encontra_por_numero_loja(self, mock_req):
        mock_req.return_value = {"data": [
            {"id": 1, "numeroLoja": "OUTRO"},
            {"id": 2, "numeroLoja": "2412345ABCDEF"},
        ]}
        r = bling.buscar_pedido_por_numero_loja("2412345ABCDEF")
        self.assertEqual(r["id"], 2)

    @patch("bling_erp._request", return_value={"data": []})
    def test_nao_encontrado_retorna_none(self, mock_req):
        r = bling.buscar_pedido_por_numero_loja("SEM-MATCH")
        self.assertIsNone(r)

    @patch("bling_erp._request")
    def test_pagina_ate_encontrar_ou_esgotar(self, mock_req):
        pagina_1 = {"data": [{"id": i, "numeroLoja": f"X{i}"} for i in range(100)]}
        pagina_2 = {"data": [{"id": 200, "numeroLoja": "ACHOU"}]}
        pagina_3 = {"data": []}
        mock_req.side_effect = [pagina_1, pagina_2, pagina_3]
        r = bling.buscar_pedido_por_numero_loja("ACHOU")
        self.assertEqual(r["id"], 200)
        self.assertEqual(mock_req.call_count, 2)


class TestListarLojas(unittest.TestCase):
    """Listagem de lojas/canais de venda do Bling."""
    def setUp(self): bling._TOKEN["access"] = "mock"

    @patch("bling_erp._request")
    def test_listar_lojas_chama_endpoint_correto(self, mock_request):
        mock_request.return_value = {"data": []}
        bling.listar_lojas(pagina=2, limite=50)
        mock_request.assert_called_once_with("lojas", {"pagina": 2, "limite": 50})

    @patch("bling_erp._request", return_value={"data": [{"id": 1, "nome": "Loja 1"}]})
    def test_listar_lojas_retorna_resposta(self, mock_request):
        r = bling.listar_lojas()
        self.assertIn("data", r)
        self.assertEqual(r["data"][0]["id"], 1)


class TestListarContasContabeis(unittest.TestCase):
    """Listagem de contas contábeis (plano de contas) do Bling."""
    def setUp(self): bling._TOKEN["access"] = "mock"

    @patch("bling_erp._request")
    def test_listar_contas_contabeis_chama_endpoint_correto(self, mock_request):
        mock_request.return_value = {"data": []}
        bling.listar_contas_contabeis(pagina=1, limite=100)
        mock_request.assert_called_once_with("contas/contabeis", {"pagina": 1, "limite": 100})

    @patch("bling_erp._request", return_value={"data": [{"id": 1, "nome": "1.1.01 - Caixa"}]})
    def test_listar_contas_contabeis_retorna_resposta(self, mock_request):
        r = bling.listar_contas_contabeis()
        self.assertIn("data", r)
        self.assertEqual(r["data"][0]["nome"], "1.1.01 - Caixa")


class TestSincronizarCanaisBling(unittest.TestCase):
    """Sync de canais de venda do Bling (tabela bling_canais)."""
    def setUp(self): bling._TOKEN["access"] = "mock"

    def test_sincronizar_canais_bling_cria_tabela_e_faz_upsert(self):
        fake_db = AsyncMock()
        fake_db.fetchval.return_value = None  # nenhum canal existente ainda
        with patch("bling_erp.get_access_token", return_value="tok"), \
             patch("bling_erp.get_db", new=AsyncMock(return_value=fake_db)), \
             patch("bling_erp.listar_lojas", return_value={"data": [
                 {"id": 111, "descricao": "Loja Virtual", "situacao": "A"},
             ]}):
            resultado = bling.sincronizar_canais_bling()
        self.assertEqual(resultado["sync"], 1)
        # confirma que criou a tabela e fez INSERT (nao UPDATE, ja que fetchval retornou None)
        sqls_executados = [c.args[0] for c in fake_db.execute.call_args_list]
        self.assertTrue(any("CREATE TABLE IF NOT EXISTS bling_canais" in s for s in sqls_executados))
        self.assertTrue(any("INSERT INTO bling_canais" in s for s in sqls_executados))


class TestSituacoes(unittest.TestCase):
    """CRUD de Situacoes (status customizados de pedido/NF)."""
    def setUp(self): bling._TOKEN["access"] = "mock"

    @patch("bling_erp._request", return_value={"data": []})
    def test_listar_situacoes_chama_endpoint_correto(self, mock_request):
        bling.listar_situacoes(pagina=1, limite=100)
        mock_request.assert_called_once_with("situacoes", {"pagina": 1, "limite": 100})

    @patch("bling_erp._request", return_value={"data": {"id": 1}})
    def test_criar_situacao_chama_endpoint_correto(self, mock_request):
        bling.criar_situacao({"nome": "Aguardando Pagamento", "cor": "FFA500"})
        mock_request.assert_called_once_with("situacoes", {"nome": "Aguardando Pagamento", "cor": "FFA500"}, method="POST")

    @patch("bling_erp._request", return_value={"data": {}})
    def test_atualizar_situacao_chama_endpoint_correto(self, mock_request):
        bling.atualizar_situacao(42, {"nome": "Pago"})
        mock_request.assert_called_once_with("situacoes/42", {"nome": "Pago"}, method="PUT")

    @patch("bling_erp._request", return_value={})
    def test_deletar_situacao_chama_endpoint_correto(self, mock_request):
        bling.deletar_situacao(42)
        mock_request.assert_called_once_with("situacoes/42", method="DELETE")

    def test_sincronizar_situacoes_bling_cria_tabela_e_faz_upsert(self):
        fake_db = AsyncMock()
        fake_db.fetchval.return_value = None
        with patch("bling_erp.get_access_token", return_value="tok"), \
             patch("bling_erp.get_db", new=AsyncMock(return_value=fake_db)), \
             patch("bling_erp.listar_situacoes", return_value={"data": [
                 {"id": 777, "nome": "Aguardando Pagamento", "cor": "FFA500", "modulo": "pedidos"},
             ]}):
            resultado = bling.sincronizar_situacoes_bling()
        self.assertEqual(resultado["sync"], 1)
        sqls_executados = [c.args[0] for c in fake_db.execute.call_args_list]
        self.assertTrue(any("CREATE TABLE IF NOT EXISTS bling_situacoes" in s for s in sqls_executados))
        self.assertTrue(any("INSERT INTO bling_situacoes" in s for s in sqls_executados))


class TestPedidosCompra(unittest.TestCase):
    """Wrappers de API Bling para pedidos de compra."""
    def setUp(self): bling._TOKEN["access"] = "mock"

    @patch("bling_erp._request", return_value={"data": []})
    def test_listar_pedidos_compra_chama_endpoint_correto(self, mock_request):
        bling.listar_pedidos_compra(pagina=2, limite=50)
        mock_request.assert_called_once_with("pedidos/compras", {"pagina": 2, "limite": 50})

    @patch("bling_erp._request", return_value={"data": {}})
    def test_get_pedido_compra_detalhe_chama_endpoint_correto(self, mock_request):
        bling.get_pedido_compra_detalhe(123)
        mock_request.assert_called_once_with("pedidos/compras/123")

    @patch("bling_erp._request", return_value={"data": {}})
    def test_marcar_pedido_compra_recebido_chama_endpoint_correto(self, mock_request):
        bling.marcar_pedido_compra_recebido(123)
        mock_request.assert_called_once_with("pedidos/compras/123/receber", {}, method="POST")


class TestNfceNfse(unittest.TestCase):
    """Wrappers de API Bling para NFC-e (consumidor) e NFS-e (servico)."""
    def setUp(self): bling._TOKEN["access"] = "mock"

    @patch("bling_erp._request", return_value={"data": []})
    def test_listar_nfce_chama_endpoint_correto(self, mock_request):
        bling.listar_nfce(pagina=1, limite=100)
        mock_request.assert_called_once_with("nfce", {"pagina": 1, "limite": 100})

    @patch("bling_erp._request", return_value={"data": {}})
    def test_get_nfce_detalhe_chama_endpoint_correto(self, mock_request):
        bling.get_nfce_detalhe(321)
        mock_request.assert_called_once_with("nfce/321")

    @patch("bling_erp._request", return_value={"data": []})
    def test_listar_nfse_chama_endpoint_correto(self, mock_request):
        bling.listar_nfse(pagina=1, limite=100)
        mock_request.assert_called_once_with("nfse", {"pagina": 1, "limite": 100})

    @patch("bling_erp._request", return_value={"data": {}})
    def test_get_nfse_detalhe_chama_endpoint_correto(self, mock_request):
        bling.get_nfse_detalhe(654)
        mock_request.assert_called_once_with("nfse/654")

class TestAmbienteBling(unittest.TestCase):
    """Toggle producao/homologacao: default seguro, base URL nunca hardcoded,
    tokens segregados por ambiente."""

    def setUp(self):
        os.environ.pop("BLING_AMBIENTE", None)
        os.environ.pop("BLING_BASE_URL_HOMOLOGACAO", None)

    def test_ambiente_default_e_producao(self):
        with patch("bling_erp.get_config", return_value=""):
            self.assertEqual(bling.get_ambiente(), "producao")

    def test_ambiente_invalido_cai_para_producao(self):
        with patch("bling_erp.get_config", return_value="qualquer-coisa"):
            self.assertEqual(bling.get_ambiente(), "producao")

    def test_ambiente_le_da_config(self):
        with patch("bling_erp.get_config", return_value="homologacao"):
            self.assertEqual(bling.get_ambiente(), "homologacao")

    def test_ambiente_le_do_env_com_prioridade(self):
        os.environ["BLING_AMBIENTE"] = "homologacao"
        try:
            with patch("bling_erp.get_config", return_value="producao"):
                self.assertEqual(bling.get_ambiente(), "homologacao")
        finally:
            os.environ.pop("BLING_AMBIENTE", None)

    def test_set_ambiente_persiste_e_limpa_cache_de_token(self):
        bling._TOKEN["access"] = "token-de-producao"
        bling._TOKEN["refresh"] = "refresh-de-producao"
        with patch("bling_erp.set_config") as mock_set:
            r = bling.set_ambiente("homologacao")
        self.assertEqual(r["ambiente"], "homologacao")
        mock_set.assert_called_once_with("bling", "ambiente", "homologacao")
        # cache do ambiente anterior nao pode vazar pro novo ambiente
        self.assertEqual(bling._TOKEN["access"], "")
        self.assertEqual(bling._TOKEN["refresh"], "")

    def test_set_ambiente_invalido_nao_persiste(self):
        with patch("bling_erp.set_config") as mock_set:
            r = bling.set_ambiente("xpto")
        self.assertIn("error", r)
        mock_set.assert_not_called()

    def test_base_url_em_producao_e_a_constante(self):
        with patch("bling_erp.get_ambiente", return_value="producao"):
            self.assertEqual(bling._base_url(), bling.BASE_URL)

    def test_base_url_em_homologacao_sem_host_configurado_cai_em_producao(self):
        """Bling v3 nao publica host de sandbox. Sem config, homologacao isola
        os DADOS mas continua falando com a API real — nunca aponta pra host
        inventado."""
        with patch("bling_erp.get_ambiente", return_value="homologacao"),              patch("bling_erp.get_config", return_value=""):
            self.assertEqual(bling._base_url(), bling.BASE_URL)

    def test_base_url_em_homologacao_usa_host_configurado_sem_barra_final(self):
        with patch("bling_erp.get_ambiente", return_value="homologacao"),              patch("bling_erp.get_config", return_value="https://sandbox.bling.test/Api/v3/"):
            self.assertEqual(bling._base_url(), "https://sandbox.bling.test/Api/v3")

    def test_chave_de_token_e_sufixada_em_homologacao(self):
        """Autenticar em homologacao nao pode sobrescrever o token de producao."""
        with patch("bling_erp.get_ambiente", return_value="homologacao"),              patch("bling_erp.set_config") as mock_set:
            bling.set_access_token("tok-homologacao")
        mock_set.assert_called_once_with("bling", "access_token_homologacao", "tok-homologacao")

    def test_chave_de_token_em_producao_continua_sem_sufixo(self):
        with patch("bling_erp.get_ambiente", return_value="producao"),              patch("bling_erp.set_config") as mock_set:
            bling.set_refresh_token("refresh-producao")
        mock_set.assert_called_once_with("bling", "refresh_token", "refresh-producao")

    def test_status_expoe_ambiente_e_base_url(self):
        with patch("bling_erp.get_ambiente", return_value="homologacao"):
            s = bling.status()
        self.assertEqual(s["ambiente"], "homologacao")
        self.assertIn("base_url", s)

if __name__=="__main__": unittest.main(verbosity=2)

patcher.stop()
