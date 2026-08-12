"""Testes do client HTTP pro app de bipagem/atualizacao de estoque."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, MagicMock

import core.estoque_app_client as client


def _resp(json_body, status_ok=True):
    m = MagicMock()
    m.json.return_value = json_body
    m.raise_for_status = MagicMock() if status_ok else MagicMock(side_effect=Exception("HTTP 500"))
    return m


class TestFetchCache(unittest.TestCase):
    def test_fetch_produtos_retorna_data(self):
        with patch("core.estoque_app_client.requests.get",
                    return_value=_resp({"ok": True, "data": [{"id": 1}]})) as mock_get:
            resultado = client.fetch_produtos()
        self.assertEqual(resultado, [{"id": 1}])
        url_chamada = mock_get.call_args[0][0]
        self.assertTrue(url_chamada.endswith("/api/cache/produtos"))

    def test_fetch_estoques_retorna_data(self):
        with patch("core.estoque_app_client.requests.get",
                    return_value=_resp({"ok": True, "data": [{"filial": 1}]})):
            resultado = client.fetch_estoques()
        self.assertEqual(resultado, [{"filial": 1}])

    def test_fetch_filiais_retorna_data(self):
        with patch("core.estoque_app_client.requests.get",
                    return_value=_resp({"ok": True, "data": [{"id": 1}]})):
            resultado = client.fetch_filiais()
        self.assertEqual(resultado, [{"id": 1}])

    def test_ok_false_levanta_estoqueapperror(self):
        with patch("core.estoque_app_client.requests.get",
                    return_value=_resp({"ok": False, "error": "cache vazio"})):
            with self.assertRaises(client.EstoqueAppError):
                client.fetch_produtos()

    def test_falha_de_rede_levanta_estoqueapperror(self):
        with patch("core.estoque_app_client.requests.get", side_effect=Exception("timeout")):
            with self.assertRaises(client.EstoqueAppError):
                client.fetch_produtos()

    def test_status_devolve_json_bruto(self):
        with patch("core.estoque_app_client.requests.get",
                    return_value=_resp({"ok": True, "ready": True, "counts": {"produtos": 19292}})):
            resultado = client.status()
        self.assertTrue(resultado["ready"])
        self.assertEqual(resultado["counts"]["produtos"], 19292)


if __name__ == "__main__":
    unittest.main(verbosity=2)
