"""
Testes do fluxo Shopee (sandbox simulado) — nao ha credenciais reais configuradas
neste ambiente, entao simulamos as respostas da API da Shopee (baseadas no schema
documentado v2) e validamos assinatura HMAC, montagem de requests, parsing de
resposta, cache de categorias e as rotas Flask que o wizard "Publicar Shopee" usa.
"""
import sys, os, json, hmac, hashlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, MagicMock, AsyncMock
import unittest

# Mock DB pool global (mesmo padrao de test_bling_erp.py) para os imports no topo do modulo nao falharem
_fake_pool = AsyncMock()
_fake_conn = AsyncMock()
_fake_conn.fetch.return_value = []
_fake_conn.fetchrow.return_value = None
_fake_conn.fetchval.return_value = 0
_fake_conn.execute.return_value = "OK"
_fake_pool.acquire.return_value = _fake_conn

async def _mock_create_pool(*a, **kw):
    pool = AsyncMock()
    pool.acquire.return_value = _fake_conn
    return pool

_pool_patcher = patch("asyncpg.create_pool", side_effect=_mock_create_pool)
_pool_patcher.start()

# ponytail: quando este arquivo roda sozinho (sem o "priming" acidental que acontece
# quando a suite inteira e' coletada em certa ordem), set_config() tentaria uma conexao
# real ao Postgres. Aqui a gente nao quer testar persistencia de config, entao forcamos
# o modo memoria+arquivo (sem DB) de forma explicita, independente da ordem dos arquivos.
_db_table_patcher = patch("core.config._ensure_db_table", return_value=False)
_db_table_patcher.start()

import shopee
from core.config import set_config


def _configurar_loja_fake():
    """Simula uma loja Shopee ja conectada (config global legada — sem loja_id)."""
    set_config("shopee", "partner_id", "1237336")
    set_config("shopee", "api_key", "chave-secreta-sandbox")
    set_config("shopee", "shop_id", "227748635")
    set_config("shopee", "access_token", "token-sandbox-fake")


class TestAssinaturaHMAC(unittest.TestCase):
    """Confere que a assinatura bate com o algoritmo documentado da Shopee:
    HMAC-SHA256(partner_id + path + timestamp + access_token + shop_id, partner_key)."""

    def setUp(self):
        _configurar_loja_fake()

    def test_sign_gera_hash_esperado(self):
        # ponytail: validado ao vivo contra o sandbox real — o partner_key e' so' a CHAVE do
        # HMAC, nao entra na mensagem (bug real encontrado: "Wrong sign" ate' corrigir isso).
        sig = shopee._sign("/api/v2/product/get_category")
        cfg = shopee.get_shopee_config()
        esperado = hmac.new(
            cfg["api_key"].encode(),
            f"{cfg['partner_id']}/api/v2/product/get_category{sig['timestamp']}{cfg['access_token']}{cfg['shop_id']}".encode(),
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(sig["sign"], esperado)

    def test_configurado_true_com_credenciais(self):
        self.assertTrue(shopee.configurado())

    def test_configurado_false_sem_loja(self):
        # loja_id=999 nao existe -> obter_credenciais_shopee retorna {} -> nao configurado
        with patch("core.lojas.obter_credenciais_shopee", return_value={}):
            self.assertFalse(shopee.configurado(loja_id=999))


class TestRequestsMockados(unittest.TestCase):
    """Simula respostas do sandbox da Shopee (schema documentado) e valida o parsing."""

    def setUp(self):
        _configurar_loja_fake()

    @patch("shopee.requests.get")
    def test_get_category(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "response": {"category_list": [
                {"category_id": 100182, "parent_category_id": 0, "original_category_name": "Eletrônicos", "has_children": True},
                {"category_id": 100183, "parent_category_id": 100182, "original_category_name": "Celulares", "has_children": False},
            ]}
        }
        mock_get.return_value.raise_for_status = MagicMock()
        r = shopee.get_category()
        self.assertEqual(len(r["response"]["category_list"]), 2)
        # Confere que foi na URL certa com os params de assinatura
        called_url = mock_get.call_args[0][0]
        self.assertIn("product/get_category", called_url)
        params = mock_get.call_args[1]["params"]
        self.assertIn("sign", params)
        self.assertIn("shop_id", params)

    @patch("shopee.requests.get")
    def test_get_attribute_tree(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {
            "response": {"attribute_tree": [{
                "category_id": 100183,
                "attribute_list": [
                    {"attribute_id": 1, "original_attribute_name": "Marca", "is_mandatory": True,
                     "attribute_value_list": [{"value_id": 10, "original_value_name": "Genérico"}]},
                    {"attribute_id": 2, "original_attribute_name": "Voltagem", "is_mandatory": False},
                ],
            }]}
        }
        r = shopee.get_attribute_tree(100183)
        atributos = r["response"]["attribute_tree"][0]["attribute_list"]
        self.assertEqual(len(atributos), 2)
        self.assertTrue(atributos[0]["is_mandatory"])

    @patch("shopee.requests.get")
    def test_get_brand_list(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {
            "response": {"brand_list": [{"brand_id": 5, "original_brand_name": "Samsung"}], "is_mandatory": False}
        }
        r = shopee.get_brand_list(100183)
        self.assertEqual(r["response"]["brand_list"][0]["original_brand_name"], "Samsung")

    @patch("shopee.requests.post")
    def test_upload_image_envia_multipart(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = MagicMock()
        mock_post.return_value.json.return_value = {
            "response": {"image_info": {"image_id": "abc123", "image_url_list": [{"image_url": "https://cf.shopee.com.br/img/abc123"}]}}
        }
        r = shopee.upload_image(b"fakebytes", "foto.jpg")
        self.assertEqual(mock_post.call_args[1]["files"]["image"][0], "foto.jpg")
        image_info = r["response"]["image_info"]
        self.assertEqual(image_info["image_id"], "abc123")

    @patch("shopee.requests.post")
    def test_add_item_encaminha_payload(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.raise_for_status = MagicMock()
        mock_post.return_value.json.return_value = {"response": {"item_id": 999888}}
        payload = {
            "item_name": "Produto Teste", "item_sku": "SKU-001", "category_id": 100183,
            "original_price": 49.9, "weight": 0.3,
            "dimension": {"package_length": 10, "package_width": 10, "package_height": 5},
            "image": {"image_id_list": ["abc123"]},
            "brand": {"brand_id": 0, "original_brand_name": "No Brand"},
            "attribute_list": [{"attribute_id": 1, "attribute_value_list": [{"value_id": 10}]}],
            "logistic_info": [{"logistic_id": 1, "enabled": True}],
            "seller_stock": [{"stock": 25}],
        }
        r = shopee.add_item(payload)
        self.assertEqual(r["response"]["item_id"], 999888)
        body_enviado = mock_post.call_args[1]["json"]
        self.assertEqual(body_enviado["item_name"], "Produto Teste")
        self.assertEqual(body_enviado["category_id"], 100183)

    @patch("shopee.requests.get")
    def test_get_logistics_channel_list(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status = MagicMock()
        mock_get.return_value.json.return_value = {
            "response": {"logistics_channel_list": [{"logistic_id": 1, "logistic_name": "Standard Delivery", "enabled": True}]}
        }
        r = shopee.get_logistics_channel_list()
        self.assertTrue(r["response"]["logistics_channel_list"][0]["enabled"])


class TestCacheCategorias(unittest.TestCase):
    """Cache local de categorias (evita bater na API da Shopee toda vez que o usuario abre o seletor)."""

    def setUp(self):
        _configurar_loja_fake()

    @patch("shopee.get_db")
    @patch("shopee.get_category")
    def test_sincronizar_categorias_grava_no_banco(self, mock_get_category, mock_get_db):
        mock_get_category.return_value = {"response": {"category_list": [
            {"category_id": 1, "parent_category_id": 0, "original_category_name": "Casa", "has_children": False},
        ]}}
        fake_db = AsyncMock()
        mock_get_db.return_value = fake_db
        r = shopee.sincronizar_categorias()
        self.assertEqual(r["total"], 1)
        fake_db.execute.assert_called_once()
        args = fake_db.execute.call_args[0]
        self.assertIn("INSERT INTO shopee_categorias", args[0])
        self.assertEqual(args[1], 1)  # category_id

    @patch("shopee.get_db")
    def test_listar_categorias_cache_com_dados(self, mock_get_db):
        fake_db = AsyncMock()
        fake_db.fetchval.return_value = 2
        fake_db.fetch.return_value = [
            {"category_id": 1, "parent_category_id": 0, "nome": "Casa", "tem_filhos": False},
            {"category_id": 2, "parent_category_id": 0, "nome": "Eletrônicos", "tem_filhos": True},
        ]
        mock_get_db.return_value = fake_db
        resultado = shopee.listar_categorias_cache()
        self.assertEqual(len(resultado), 2)


class TestEstoqueMultiLoja(unittest.TestCase):
    @patch("shopee.sincronizar_estoque_shopee")
    @patch("core.lojas.listar_lojas_shopee")
    def test_sincronizar_estoque_todas_lojas(self, mock_listar, mock_sync):
        mock_listar.return_value = [
            {"id": 1, "nome": "Loja A"}, {"id": 2, "nome": "Loja B"},
        ]
        mock_sync.side_effect = [{"ok": True}, {"error": "token expirado"}]
        r = shopee.sincronizar_estoque_todas_lojas("SKU-001", 10)
        self.assertEqual(r["total"], 2)
        self.assertEqual(r["sucesso"], 1)

    @patch("core.lojas.listar_lojas_shopee", return_value=[])
    def test_sincronizar_estoque_todas_lojas_sem_lojas(self, mock_listar):
        r = shopee.sincronizar_estoque_todas_lojas("SKU-001", 10)
        self.assertEqual(r["total"], 0)
        self.assertIn("erro", r)


class TestRotasFlask(unittest.TestCase):
    """Testa as rotas que o wizard 'Publicar Shopee' chama, via Flask test_client."""

    @classmethod
    def setUpClass(cls):
        from athena_bridge import app
        app.config["TESTING"] = True
        cls.client = app.test_client()

    @patch("shopee.listar_categorias_cache")
    def test_rota_categorias(self, mock_listar):
        mock_listar.return_value = [{"category_id": 1, "parent_category_id": 0, "nome": "Casa", "tem_filhos": False}]
        resp = self.client.get("/api/shopee/categorias?busca=casa")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["categorias"][0]["nome"], "Casa")

    @patch("shopee.get_attribute_tree")
    def test_rota_atributos(self, mock_attr):
        # ponytail: formato real confirmado ao vivo no sandbox — response.list[0].attribute_tree
        # com campos "mandatory"/"name", nao "attribute_list"/"is_mandatory"/"original_attribute_name".
        mock_attr.return_value = {"response": {"list": [{"category_id": 100183, "attribute_tree": [
            {"attribute_id": 1, "name": "Cor", "mandatory": True, "attribute_value_list": [{"value_id": 9, "name": "Azul"}]},
        ]}]}}
        resp = self.client.get("/api/shopee/categorias/100183/atributos")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["atributos"][0]["original_attribute_name"], "Cor")
        self.assertTrue(body["atributos"][0]["is_mandatory"])
        self.assertEqual(body["atributos"][0]["attribute_value_list"][0]["original_value_name"], "Azul")

    @patch("shopee.get_brand_list")
    def test_rota_marcas(self, mock_brand):
        mock_brand.return_value = {"response": {"brand_list": [{"brand_id": 5, "original_brand_name": "Samsung"}], "is_mandatory": False}}
        resp = self.client.get("/api/shopee/categorias/100183/marcas")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.get_json()["obrigatorio"])

    @patch("shopee.upload_image")
    def test_rota_upload_imagem_por_url(self, mock_upload):
        mock_upload.return_value = {"response": {"image_info": {"image_id": "img1", "image_url_list": [{"image_url": "https://x/y.jpg"}]}}}
        with patch("requests.get") as mock_get:
            mock_get.return_value.content = b"fakejpegbytes"
            mock_get.return_value.raise_for_status = MagicMock()
            resp = self.client.post("/api/shopee/upload-imagem", data={"loja_id": "1", "image_url": "https://cdn.exemplo.com/produto.jpg"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["image_id"], "img1")

    def test_rota_upload_imagem_rejeita_url_invalida(self):
        resp = self.client.post("/api/shopee/upload-imagem", data={"loja_id": "1", "image_url": "file:///etc/passwd"})
        self.assertEqual(resp.status_code, 400)

    def test_rota_upload_imagem_rejeita_ip_privado_ssrf(self):
        # ponytail: protecao contra SSRF — nao pode usar o upload de imagem pra sondar rede interna
        for url in ["http://127.0.0.1/imagem.jpg", "http://169.254.169.254/latest/meta-data/", "http://10.0.0.5/x.jpg"]:
            resp = self.client.post("/api/shopee/upload-imagem", data={"loja_id": "1", "image_url": url})
            self.assertEqual(resp.status_code, 400, f"deveria bloquear {url}")

    @patch("requests.get", side_effect=Exception("connection refused to internal-db.corp.local:5432"))
    def test_rota_upload_imagem_nao_vaza_detalhe_de_erro(self, mock_get):
        resp = self.client.post("/api/shopee/upload-imagem", data={"loja_id": "1", "image_url": "https://www.google.com/x.jpg"})
        self.assertEqual(resp.status_code, 400)
        self.assertNotIn("internal-db.corp.local", resp.get_json().get("error", ""))

    @patch("shopee.add_item")
    def test_rota_criar_produto(self, mock_add):
        mock_add.return_value = {"response": {"item_id": 42}}
        resp = self.client.post("/api/shopee/produtos", json={
            "loja_id": 1, "item_name": "Produto X", "category_id": 100183, "original_price": 10.0,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["response"]["item_id"], 42)
        # loja_id nao deve vazar para dentro do payload da Shopee
        payload_enviado = mock_add.call_args[0][0]
        self.assertNotIn("loja_id", payload_enviado)

    def test_rota_criar_produto_sem_loja_id(self):
        resp = self.client.post("/api/shopee/produtos", json={"item_name": "X"})
        self.assertEqual(resp.status_code, 400)

    @patch("shopee.sincronizar_estoque_todas_lojas")
    def test_rota_estoque_todas_lojas(self, mock_sync):
        mock_sync.return_value = {"total": 2, "sucesso": 2, "resultados": []}
        resp = self.client.post("/api/shopee/estoque/todas-lojas", json={"sku": "SKU-001", "quantidade": 15})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["sucesso"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
