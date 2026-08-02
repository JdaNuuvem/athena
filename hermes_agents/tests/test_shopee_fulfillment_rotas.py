"""Testes de integracao — rotas de fulfillment Shopee->Bling em routes/shopee.py
(/api/shopee/pedidos/<order_sn>/fulfillment|vincular-bling|emitir-nota|
nota-pdf|despachar-confirmar)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

async def _mp(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

from flask import Flask
from routes.shopee import shopee_bp
import core.rbac as rbac

_TEST_TOKEN = "test-master-token-32-bytes-long!!"


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(shopee_bp)
    return app.test_client()


class TestFulfillmentStatusRota(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_sem_loja_id_retorna_400(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.get("/api/shopee/pedidos/SN-1/fulfillment", headers=headers)
        self.assertEqual(r.status_code, 400)

    def test_com_loja_id_chama_core(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.shopee_fulfillment.status_fulfillment",
                    return_value={"order_sn": "SN-1", "vinculado_bling": False}) as mock_status:
            r = self.client.get("/api/shopee/pedidos/SN-1/fulfillment?loja_id=7", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_status.assert_called_once_with("SN-1", 7)

    def test_erro_nao_encontrado_retorna_404(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.shopee_fulfillment.status_fulfillment",
                    return_value={"erro": "pedido nao encontrado — sincronize antes"}):
            r = self.client.get("/api/shopee/pedidos/SN-X/fulfillment?loja_id=7", headers=headers)
        self.assertEqual(r.status_code, 404)


class TestVincularBlingRota(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.shopee_fulfillment.vincular_pedido_bling") as mock_vincular:
            r = self.client.post("/api/shopee/pedidos/SN-1/vincular-bling", json={"loja_id": 7}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_vincular.assert_not_called()

    def test_sem_loja_id_retorna_400(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.post("/api/shopee/pedidos/SN-1/vincular-bling", json={}, headers=headers)
        self.assertEqual(r.status_code, 400)

    def test_vinculo_manual_repassa_id_pedido_bling(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.shopee_fulfillment.vincular_pedido_bling", return_value={"ok": True}) as mock_vincular:
            r = self.client.post("/api/shopee/pedidos/SN-1/vincular-bling",
                                  json={"loja_id": 7, "id_pedido_bling": 999}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_vincular.assert_called_once_with("SN-1", 7, id_pedido_bling=999)

    def test_erro_de_negocio_retorna_400(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.shopee_fulfillment.vincular_pedido_bling",
                    return_value={"erro": "pedido nao encontrado automaticamente no Bling"}):
            r = self.client.post("/api/shopee/pedidos/SN-1/vincular-bling", json={"loja_id": 7}, headers=headers)
        self.assertEqual(r.status_code, 400)


class TestEmitirNotaRota(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.shopee_fulfillment.emitir_nota_fiscal") as mock_emitir:
            r = self.client.post("/api/shopee/pedidos/SN-1/emitir-nota", json={"loja_id": 7}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_emitir.assert_not_called()

    def test_com_permissao_libera(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.shopee_fulfillment.emitir_nota_fiscal",
                    return_value={"ok": True, "bling_nota_fiscal_id": 20}) as mock_emitir:
            r = self.client.post("/api/shopee/pedidos/SN-1/emitir-nota", json={"loja_id": 7}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_emitir.assert_called_once_with("SN-1", 7)

    def test_erro_de_negocio_retorna_400(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.shopee_fulfillment.emitir_nota_fiscal",
                    return_value={"erro": "nota fiscal ja emitida para este pedido"}):
            r = self.client.post("/api/shopee/pedidos/SN-1/emitir-nota", json={"loja_id": 7}, headers=headers)
        self.assertEqual(r.status_code, 400)


class TestNotaPdfRota(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_com_pdf_disponivel_serve_bytes(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.shopee_fulfillment.baixar_nota_pdf", return_value=(b"%PDF-x", "application/pdf")):
            r = self.client.get("/api/shopee/pedidos/SN-1/nota-pdf?loja_id=7", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, b"%PDF-x")
        self.assertEqual(r.mimetype, "application/pdf")

    def test_sem_pdf_disponivel_retorna_404(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.shopee_fulfillment.baixar_nota_pdf", return_value=(None, None)):
            r = self.client.get("/api/shopee/pedidos/SN-1/nota-pdf?loja_id=7", headers=headers)
        self.assertEqual(r.status_code, 404)


class TestDespacharConfirmarRota(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]), \
             patch("core.shopee_fulfillment.marcar_despachado") as mock_marcar:
            r = self.client.post("/api/shopee/pedidos/SN-1/despachar-confirmar", json={"loja_id": 7}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_marcar.assert_not_called()

    def test_repassa_package_number(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.shopee_fulfillment.marcar_despachado", return_value={"ok": True}) as mock_marcar:
            r = self.client.post("/api/shopee/pedidos/SN-1/despachar-confirmar",
                                  json={"loja_id": 7, "package_number": "PKG-9"}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_marcar.assert_called_once_with("SN-1", 7, package_number="PKG-9")


if __name__ == "__main__":
    unittest.main(verbosity=2)
