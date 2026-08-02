"""_sync_contatos() (core/scheduler.py) — sincronizar_contatos_bling() so'
processa uma pagina por chamada. Sem paginar aqui, o job recorrente
(bling-contatos, a cada 30min) sempre re-sincronizava os mesmos 100
primeiros contatos do Bling e nunca alcancava o resto da base."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch

from core.scheduler import _sync_contatos


class TestSyncContatosPagina(unittest.TestCase):
    def test_percorre_todas_as_paginas_ate_a_ultima_incompleta(self):
        respostas = [
            {"sync": 100, "recebidos": 100},
            {"sync": 100, "recebidos": 100},
            {"sync": 37, "recebidos": 37},
        ]
        with patch("core.entidades.sincronizar_contatos_bling", side_effect=respostas) as mock_sync:
            _sync_contatos()
        self.assertEqual(mock_sync.call_count, 3)
        paginas_chamadas = [c.kwargs.get("pagina", c.args[0] if c.args else None) for c in mock_sync.call_args_list]
        self.assertEqual(paginas_chamadas, [1, 2, 3])

    def test_para_na_primeira_pagina_ja_incompleta(self):
        with patch("core.entidades.sincronizar_contatos_bling", return_value={"sync": 5, "recebidos": 5}) as mock_sync:
            _sync_contatos()
        mock_sync.assert_called_once()

    def test_erro_interrompe_sem_propagar_excecao(self):
        with patch("core.entidades.sincronizar_contatos_bling", return_value={"error": "Bling nao autenticado"}) as mock_sync:
            _sync_contatos()  # nao deve levantar
        mock_sync.assert_called_once()

    def test_excecao_inesperada_nao_propaga(self):
        with patch("core.entidades.sincronizar_contatos_bling", side_effect=RuntimeError("boom")):
            _sync_contatos()  # job roda em loop de background — nunca pode derrubar o scheduler


if __name__ == "__main__":
    unittest.main(verbosity=2)
