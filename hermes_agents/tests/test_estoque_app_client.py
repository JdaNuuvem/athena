"""Testes do client HTTP pro app de bipagem/atualizacao de estoque."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, MagicMock

import core.estoque_app_client as client


def _resp(json_body):
    m = MagicMock()
    m.json.return_value = json_body
    m.raise_for_status = MagicMock()
    return m


class TestFetchProdutosExistentes(unittest.TestCase):
    def test_sem_api_key_levanta_erro_sem_bater_na_rede(self):
        with patch("core.estoque_app_client._api_key", return_value=""), \
             patch("core.estoque_app_client.requests.get") as mock_get:
            with self.assertRaises(client.EstoqueAppError):
                client.fetch_produtos_existentes()
        mock_get.assert_not_called()

    def test_manda_header_x_api_key(self):
        with patch("core.estoque_app_client._api_key", return_value="minha-chave"), \
             patch("core.estoque_app_client.requests.get",
                   return_value=_resp({"ok": True, "produtos": []})) as mock_get:
            client.fetch_produtos_existentes()
        headers = mock_get.call_args.kwargs["headers"]
        self.assertEqual(headers["X-API-Key"], "minha-chave")

    def test_sem_filial_id_nao_manda_o_param(self):
        with patch("core.estoque_app_client._api_key", return_value="k"), \
             patch("core.estoque_app_client.requests.get",
                   return_value=_resp({"ok": True, "produtos": []})) as mock_get:
            client.fetch_produtos_existentes()
        self.assertEqual(mock_get.call_args.kwargs["params"], {})

    def test_com_filial_id_manda_o_param(self):
        with patch("core.estoque_app_client._api_key", return_value="k"), \
             patch("core.estoque_app_client.requests.get",
                   return_value=_resp({"ok": True, "produtos": []})) as mock_get:
            client.fetch_produtos_existentes(filial_id=63)
        self.assertEqual(mock_get.call_args.kwargs["params"], {"filialId": 63})

    def test_retorna_lista_de_produtos(self):
        with patch("core.estoque_app_client._api_key", return_value="k"), \
             patch("core.estoque_app_client.requests.get",
                   return_value=_resp({"ok": True, "produtos": [{"codproduto": "A"}]})):
            resultado = client.fetch_produtos_existentes()
        self.assertEqual(resultado, [{"codproduto": "A"}])

    def test_ok_false_levanta_estoqueapperror(self):
        with patch("core.estoque_app_client._api_key", return_value="k"), \
             patch("core.estoque_app_client.requests.get",
                   return_value=_resp({"ok": False, "error": "chave invalida"})):
            with self.assertRaises(client.EstoqueAppError):
                client.fetch_produtos_existentes()

    def test_falha_de_rede_levanta_estoqueapperror(self):
        with patch("core.estoque_app_client._api_key", return_value="k"), \
             patch("core.estoque_app_client.requests.get", side_effect=Exception("timeout")):
            with self.assertRaises(client.EstoqueAppError):
                client.fetch_produtos_existentes()


class TestApiKey(unittest.TestCase):
    def test_prioriza_env_var(self):
        with patch.dict(os.environ, {"ESTOQUE_APP_API_KEY": "da-env"}):
            self.assertEqual(client._api_key(), "da-env")

    def test_cai_pro_config_quando_sem_env_var(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch("core.config.get_config", return_value="do-banco"):
            self.assertEqual(client._api_key(), "do-banco")


if __name__ == "__main__":
    unittest.main(verbosity=2)
