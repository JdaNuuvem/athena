"""Testes de core/lojas_integracoes.py — slots de config das 15 integracoes
ainda nao implementadas + espelho de status de Bling/Shopee (que ja tem
mecanismo proprio e funcional em core/lojas.py)."""
import sys, os, json, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock


async def _mp(*a, **kw):
    return AsyncMock()


patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import core.lojas_integracoes as integ


class FakeDB:
    def __init__(self):
        self.integracoes = {}  # (loja_id, chave) -> dict
        self.lojas = {1: {"bling_id": None, "shopee_shop_id": None}}

    def _norm(self, q):
        return " ".join(q.split())

    async def execute(self, query, *params):
        q = self._norm(query)
        if "CREATE TABLE" in q:
            return "OK"
        if q.startswith("INSERT INTO loja_integracoes"):
            loja_id, chave = params
            key = (loja_id, chave)
            if key not in self.integracoes:
                self.integracoes[key] = {"integracao": chave, "status": "nao_implementada", "credenciais": {}}
            return "OK"
        return "OK"

    async def fetch(self, query, *params):
        q = self._norm(query)
        if q.startswith("SELECT integracao, status, credenciais FROM loja_integracoes"):
            loja_id = params[0]
            return [dict(v) for (lid, _), v in self.integracoes.items() if lid == loja_id]
        return []

    async def fetchrow(self, query, *params):
        q = self._norm(query)
        if q.startswith("SELECT bling_id, shopee_shop_id FROM lojas"):
            loja_id = params[0]
            return self.lojas.get(loja_id, {"bling_id": None, "shopee_shop_id": None})
        if q.startswith("UPDATE loja_integracoes SET status"):
            status, credenciais_json, loja_id, chave = params
            key = (loja_id, chave)
            if key not in self.integracoes:
                return None
            self.integracoes[key]["status"] = status
            self.integracoes[key]["credenciais"] = json.loads(credenciais_json)
            return {"integracao": chave, "status": status}
        return None


class TestLojasIntegracoes(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fake = FakeDB()

        async def _get_db(_fake=self.fake):
            return _fake
        self._p = patch("core.lojas_integracoes.get_db", side_effect=_get_db)
        self._p.start()
        integ._table_ok = True

    def tearDown(self):
        self._p.stop()
        integ._table_ok = False

    async def test_seed_cria_15_integracoes_nao_implementadas(self):
        integ._seed(1)
        self.assertEqual(len(self.fake.integracoes), 15)
        self.assertTrue(all(v["status"] == "nao_implementada" for v in self.fake.integracoes.values()))

    async def test_listar_inclui_bling_e_shopee_no_topo_nao_configurados(self):
        result = integ.listar(1)
        self.assertEqual(len(result), 17)  # 15 configuraveis + bling + shopee
        self.assertEqual(result[0]["integracao"], "bling")
        self.assertEqual(result[0]["status"], "nao_configurada")
        self.assertEqual(result[1]["integracao"], "shopee")

    async def test_listar_reflete_bling_ativo(self):
        self.fake.lojas[1]["bling_id"] = 999
        result = integ.listar(1)
        bling = next(i for i in result if i["integracao"] == "bling")
        self.assertEqual(bling["status"], "ativa")

    async def test_atualizar_status_integracao_configuravel(self):
        r = integ.atualizar_status(1, "mercado_livre", "ativa", credenciais={"client_id": "abc"})
        self.assertNotIn("error", r)
        self.assertEqual(r["status"], "ativa")
        self.assertEqual(self.fake.integracoes[(1, "mercado_livre")]["credenciais"], {"client_id": "abc"})

    async def test_atualizar_status_bling_rejeitado(self):
        """Bling/Shopee tem fluxo proprio — nao devem ser editaveis por aqui."""
        r = integ.atualizar_status(1, "bling", "ativa")
        self.assertIn("error", r)

    async def test_atualizar_status_invalido_rejeitado(self):
        r = integ.atualizar_status(1, "mercado_livre", "voando")
        self.assertIn("error", r)


if __name__ == "__main__":
    unittest.main(verbosity=2)
