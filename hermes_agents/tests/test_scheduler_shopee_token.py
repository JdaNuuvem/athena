"""
Job de renovacao automatica de token Shopee (core/scheduler.py::_renovar_tokens_shopee).

Contexto: o access_token da Shopee sempre expira em poucas horas (~4h, definido pela
propria Shopee via 'expire_in' — nao e' algo que o Athena configure), mesmo que o
vendedor tenha autorizado o app por 365 dias no painel da Shopee (isso e' a duracao
da AUTORIZACAO/refresh_token, um conceito diferente). Sem renovacao automatica,
qualquer chamada a' API Shopee passa a falhar a cada ~4h ate' alguem clicar
manualmente em "renovar token". Este job renova proativamente antes de expirar.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timedelta
from unittest.mock import patch
import unittest

from core.scheduler import _renovar_tokens_shopee


class TestRenovarTokensShopee(unittest.TestCase):

    @patch("shopee.refresh_shopee_token")
    @patch("core.lojas.listar_lojas_shopee")
    def test_renova_token_prestes_a_expirar(self, mock_listar, mock_refresh):
        mock_listar.return_value = [{
            "id": 7, "nome": "Loja Shopee BR", "tem_token": True,
            "shopee_token_expira_em": datetime.now() + timedelta(minutes=5),
        }]
        mock_refresh.return_value = {"success": True, "expire_in": 14400}
        _renovar_tokens_shopee()
        mock_refresh.assert_called_once_with(loja_id=7)

    @patch("shopee.refresh_shopee_token")
    @patch("core.lojas.listar_lojas_shopee")
    def test_ja_expirado_tambem_renova(self, mock_listar, mock_refresh):
        mock_listar.return_value = [{
            "id": 3, "nome": "Loja Expirada", "tem_token": True,
            "shopee_token_expira_em": datetime.now() - timedelta(hours=1),
        }]
        mock_refresh.return_value = {"success": True}
        _renovar_tokens_shopee()
        mock_refresh.assert_called_once_with(loja_id=3)

    @patch("shopee.refresh_shopee_token")
    @patch("core.lojas.listar_lojas_shopee")
    def test_token_ainda_valido_nao_renova(self, mock_listar, mock_refresh):
        mock_listar.return_value = [{
            "id": 9, "nome": "Loja OK", "tem_token": True,
            "shopee_token_expira_em": datetime.now() + timedelta(hours=3),
        }]
        _renovar_tokens_shopee()
        mock_refresh.assert_not_called()

    @patch("shopee.refresh_shopee_token")
    @patch("core.lojas.listar_lojas_shopee")
    def test_loja_sem_token_nao_renova(self, mock_listar, mock_refresh):
        mock_listar.return_value = [{
            "id": 11, "nome": "Loja Desconectada", "tem_token": False,
            "shopee_token_expira_em": None,
        }]
        _renovar_tokens_shopee()
        mock_refresh.assert_not_called()

    @patch("shopee.refresh_shopee_token")
    @patch("core.lojas.listar_lojas_shopee")
    def test_falha_na_renovacao_nao_propaga_excecao(self, mock_listar, mock_refresh):
        mock_listar.return_value = [{
            "id": 5, "nome": "Loja Refresh Invalido", "tem_token": True,
            "shopee_token_expira_em": datetime.now() - timedelta(minutes=1),
        }]
        mock_refresh.return_value = {"error": "refresh_token invalido ou expirado"}
        try:
            _renovar_tokens_shopee()
        except Exception as e:
            self.fail(f"_renovar_tokens_shopee nao deveria propagar excecao: {e}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
