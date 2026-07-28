"""Testes de core/rbac_lojas.py — RBAC por loja (Fase 4, modo suave):
usuario sem vinculo ativo em loja_responsaveis nao tem nenhuma restricao
(comportamento identico ao de antes desta fase); usuario com vinculo(s)
ativo(s) so' deve ver as lojas vinculadas."""
import sys, os, datetime, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock


async def _mp(*a, **kw):
    return AsyncMock()


patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import core.rbac_lojas as rbac_lojas

HOJE = datetime.date.today()
ONTEM = HOJE - datetime.timedelta(days=1)
AMANHA = HOJE + datetime.timedelta(days=1)


class FakeDB:
    def __init__(self, vinculos: list = None):
        # cada vinculo: {"usuario_id":, "loja_id":, "data_fim": date|None}
        self.vinculos = vinculos or []

    async def fetch(self, query, *params):
        q = " ".join(query.split())
        if q.startswith("SELECT DISTINCT loja_id FROM loja_responsaveis"):
            (usuario_id,) = params
            ids = sorted({
                v["loja_id"] for v in self.vinculos
                if v["usuario_id"] == usuario_id and (v["data_fim"] is None or v["data_fim"] >= HOJE)
            })
            return [{"loja_id": i} for i in ids]
        return []


class TestLojasPermitidas(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fake = FakeDB()

        async def _get_db(_fake=self.fake):
            return _fake
        self._p = patch("core.rbac_lojas.get_db", side_effect=_get_db)
        self._p.start()

    def tearDown(self):
        self._p.stop()

    async def test_usuario_sem_user_id_retorna_none(self):
        """Token master (usuario_atual_da_request retorna user_id=None) —
        sem restricao, igual hoje."""
        self.assertIsNone(rbac_lojas.lojas_permitidas(None))

    async def test_usuario_sem_vinculo_retorna_none(self):
        self.fake.vinculos = []
        self.assertIsNone(rbac_lojas.lojas_permitidas(7))

    async def test_usuario_com_vinculo_ativo_retorna_lista(self):
        self.fake.vinculos = [{"usuario_id": 7, "loja_id": 3, "data_fim": None}]
        self.assertEqual(rbac_lojas.lojas_permitidas(7), [3])

    async def test_usuario_com_vinculo_ativo_com_data_fim_futura(self):
        self.fake.vinculos = [{"usuario_id": 7, "loja_id": 3, "data_fim": AMANHA}]
        self.assertEqual(rbac_lojas.lojas_permitidas(7), [3])

    async def test_usuario_com_vinculo_encerrado_nao_conta(self):
        """data_fim no passado — vinculo encerrado, nao restringe (equivale
        a nao ter vinculo nenhum: sem restricao)."""
        self.fake.vinculos = [{"usuario_id": 7, "loja_id": 3, "data_fim": ONTEM}]
        self.assertIsNone(rbac_lojas.lojas_permitidas(7))

    async def test_usuario_com_multiplas_lojas(self):
        self.fake.vinculos = [
            {"usuario_id": 7, "loja_id": 3, "data_fim": None},
            {"usuario_id": 7, "loja_id": 5, "data_fim": None},
        ]
        self.assertEqual(rbac_lojas.lojas_permitidas(7), [3, 5])

    async def test_vinculo_de_outro_usuario_nao_interfere(self):
        self.fake.vinculos = [{"usuario_id": 99, "loja_id": 3, "data_fim": None}]
        self.assertIsNone(rbac_lojas.lojas_permitidas(7))


if __name__ == "__main__":
    unittest.main(verbosity=2)
