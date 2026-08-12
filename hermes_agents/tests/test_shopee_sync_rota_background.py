"""Testes de regressao — POST /api/shopee/produtos/sincronizar precisa
responder na hora (dispara em background) em vez de rodar sync_produtos +
sync_pedidos sincrono dentro do request, que estourava o timeout de proxy
(HTTP 524) em catalogos grandes."""
import sys, os, unittest, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

async def _mp(*a, **kw):
    return AsyncMock()

patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

from flask import Flask
import routes.integrations as integrations


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(integrations.integrations_bp)
    return app.test_client()


class TestShopeeSyncRotaBackground(unittest.TestCase):
    def setUp(self):
        self.client = _app()
        with integrations._sync_lock:
            integrations._sync_em_andamento.clear()

    def test_responde_processando_sem_esperar_o_worker(self):
        """A rota nao pode bloquear ate' sync_produtos/sync_pedidos
        terminarem - isso e' exatamente o que causava o 524. Trava um evento
        dentro do worker pra provar que a resposta HTTP chega ANTES dele
        liberar."""
        liberar_worker = threading.Event()
        worker_comecou = threading.Event()

        def _worker_travado(loja_id):
            worker_comecou.set()
            liberar_worker.wait(timeout=5)

        with patch.object(integrations, "_shopee_sync_worker", side_effect=_worker_travado):
            r = self.client.post("/api/shopee/produtos/sincronizar", json={"loja_id": 3})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.get_json(), {"status": "processando", "loja_id": 3})
            self.assertTrue(worker_comecou.wait(timeout=2), "worker deveria ter comecado a rodar")
        liberar_worker.set()

    def test_sem_body_nao_da_400(self):
        """Mesma classe de bug do /conectar: Content-Type json + corpo vazio
        nao pode abortar a rota com 400 automatico do Werkzeug."""
        with patch.object(integrations, "_shopee_sync_worker"):
            r = self.client.post("/api/shopee/produtos/sincronizar", data="", content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["loja_id"], None)

    def test_segunda_chamada_pra_mesma_loja_nao_dispara_outro_worker(self):
        """Enquanto uma sync da loja 3 esta rodando, uma segunda chamada pra
        loja 3 nao pode empilhar outro worker - so' reporta 'ja_processando'."""
        with integrations._sync_lock:
            integrations._sync_em_andamento.add(3)
        with patch.object(integrations, "_shopee_sync_worker") as mock_worker:
            r = self.client.post("/api/shopee/produtos/sincronizar", json={"loja_id": 3})
        self.assertEqual(r.get_json(), {"status": "ja_processando", "loja_id": 3})
        mock_worker.assert_not_called()

    def test_lojas_diferentes_disparam_workers_independentes(self):
        with integrations._sync_lock:
            integrations._sync_em_andamento.add(3)
        with patch.object(integrations, "_shopee_sync_worker") as mock_worker:
            r = self.client.post("/api/shopee/produtos/sincronizar", json={"loja_id": 4})
        self.assertEqual(r.get_json(), {"status": "processando", "loja_id": 4})
        mock_worker.assert_called_once()

    def test_worker_libera_a_chave_mesmo_com_erro(self):
        """finally do worker precisa liberar _sync_em_andamento mesmo se
        sync_produtos/sync_pedidos levantar - senao a loja fica travada em
        'ja_processando' pra sempre apos uma falha."""
        with patch("shopee_sync.sync_produtos", side_effect=Exception("boom")):
            integrations._shopee_sync_worker(7)
        with integrations._sync_lock:
            self.assertNotIn(7, integrations._sync_em_andamento)


if __name__ == "__main__":
    unittest.main(verbosity=2)
