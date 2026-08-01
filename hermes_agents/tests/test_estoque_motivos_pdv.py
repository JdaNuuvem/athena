"""Motivo venda_pdv em MOTIVOS_SAIDA/_MAPA_MOVIMENTO_SAIDA."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestMotivoVendaPdv(unittest.TestCase):
    def test_venda_pdv_em_motivos_saida(self):
        from core.estoque import MOTIVOS_SAIDA
        self.assertIn("venda_pdv", MOTIVOS_SAIDA)

    def test_venda_pdv_mapeia_para_tipo_movimento_venda(self):
        from core.estoque import _MAPA_MOVIMENTO_SAIDA
        self.assertEqual(_MAPA_MOVIMENTO_SAIDA.get("venda_pdv"), "venda")


if __name__ == "__main__":
    unittest.main()
