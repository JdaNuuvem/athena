"""Testes de core.cadastros.listar_clientes_filtrado — endpoint dedicado de
Contatos (paginacao real + filtros + dados de remarketing), sem tocar em
list_paginado/_list_pagina/_count, que continuam servindo as outras 5
tabelas de Cadastros."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

async def _mock_pool(*args, **kwargs):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mock_pool)
patcher.start()

import core.cadastros as cadastros


class _FakeDB:
    def __init__(self, total=0, rows=None):
        self.total = total
        self.rows = rows if rows is not None else []
        self.fetchval_calls = []
        self.fetch_calls = []

    async def fetchval(self, query, *params):
        self.fetchval_calls.append((query, params))
        return self.total

    async def fetch(self, query, *params):
        self.fetch_calls.append((query, params))
        return self.rows


def _cliente(id=1, nome="Cliente A", ultima_compra=None, total_gasto=0, qtd_pedidos=0, tags=None, whatsapp=False):
    return {
        "id": id, "nome": nome, "tipo": "PF", "documento": "123", "email": "a@x.com",
        "telefone": "111", "status": "ativo", "whatsapp": whatsapp, "data_nascimento": None,
        "ultima_compra": ultima_compra, "total_gasto": total_gasto, "qtd_pedidos": qtd_pedidos,
        "tags": tags or [],
    }


class TestListarClientesFiltradoPaginacao(unittest.TestCase):
    def test_retorna_metadados_de_paginacao(self):
        fake = _FakeDB(total=45, rows=[_cliente()])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            resultado = cadastros.listar_clientes_filtrado(pagina=2, por_pagina=20)
        self.assertEqual(resultado["total"], 45)
        self.assertEqual(resultado["pagina"], 2)
        self.assertEqual(resultado["por_pagina"], 20)
        self.assertEqual(resultado["total_paginas"], 3)

    def test_pagina_fora_do_intervalo_devolve_lista_vazia(self):
        fake = _FakeDB(total=5, rows=[])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            resultado = cadastros.listar_clientes_filtrado(pagina=99, por_pagina=20)
        self.assertEqual(resultado["data"], [])
        self.assertEqual(resultado["total"], 5)
        self.assertEqual(resultado["total_paginas"], 1)

    def test_pagina_invalida_nao_quebra(self):
        fake = _FakeDB(total=0, rows=[])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            resultado = cadastros.listar_clientes_filtrado(pagina=0, por_pagina=-5)
        self.assertEqual(resultado["pagina"], 1)
        self.assertEqual(resultado["por_pagina"], 1)


class TestListarClientesFiltradoFiltros(unittest.TestCase):
    def test_filtro_status_isolado(self):
        fake = _FakeDB(total=1, rows=[_cliente()])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            cadastros.listar_clientes_filtrado(status="ativo")
        query, params = fake.fetch_calls[-1]
        self.assertIn("c.status =", query)
        self.assertIn("ativo", params)

    def test_filtro_tag_isolado(self):
        fake = _FakeDB(total=1, rows=[_cliente()])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            cadastros.listar_clientes_filtrado(tag="VIP")
        query, params = fake.fetch_calls[-1]
        self.assertIn("EXISTS", query)
        self.assertIn("VIP", params)

    def test_filtro_whatsapp_isolado(self):
        fake = _FakeDB(total=1, rows=[_cliente(whatsapp=True)])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            cadastros.listar_clientes_filtrado(whatsapp=True)
        query, params = fake.fetch_calls[-1]
        self.assertIn("c.whatsapp =", query)
        self.assertIn(True, params)

    def test_filtro_sem_comprar_dias_inclui_quem_nunca_comprou(self):
        fake = _FakeDB(total=1, rows=[_cliente()])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            cadastros.listar_clientes_filtrado(sem_comprar_dias=30)
        query, params = fake.fetch_calls[-1]
        self.assertIn("compras.ultima_compra IS NULL", query)
        self.assertIn(30, params)

    def test_combinacao_de_filtros(self):
        fake = _FakeDB(total=1, rows=[_cliente()])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            cadastros.listar_clientes_filtrado(status="ativo", tag="VIP", whatsapp=True, sem_comprar_dias=60)
        query, params = fake.fetch_calls[-1]
        self.assertIn("c.status =", query)
        self.assertIn("EXISTS", query)
        self.assertIn("c.whatsapp =", query)
        self.assertIn("compras.ultima_compra IS NULL", query)
        self.assertEqual(len(params), 4)


class TestListarClientesFiltradoOrdenacao(unittest.TestCase):
    def test_sort_whitelist_aceita_colunas_derivadas(self):
        fake = _FakeDB(total=0, rows=[])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            cadastros.listar_clientes_filtrado(sort="ultima_compra", order="asc")
        query, _ = fake.fetch_calls[-1]
        self.assertIn("ORDER BY compras.ultima_compra ASC", query)

    def test_sort_total_gasto(self):
        fake = _FakeDB(total=0, rows=[])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            cadastros.listar_clientes_filtrado(sort="total_gasto", order="desc")
        query, _ = fake.fetch_calls[-1]
        self.assertIn("ORDER BY compras.total_gasto DESC", query)

    def test_sort_fora_da_whitelist_cai_no_default(self):
        fake = _FakeDB(total=0, rows=[])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            cadastros.listar_clientes_filtrado(sort="documento; DROP TABLE cad_clientes;--")
        query, _ = fake.fetch_calls[-1]
        self.assertIn("ORDER BY c.id", query)
        self.assertNotIn("DROP TABLE", query)

    def test_order_fora_da_whitelist_cai_no_default_desc(self):
        fake = _FakeDB(total=0, rows=[])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            cadastros.listar_clientes_filtrado(order="qualquer-coisa")
        query, _ = fake.fetch_calls[-1]
        self.assertIn("ORDER BY c.id DESC", query)


class TestListarClientesFiltradoRespostaEBusca(unittest.TestCase):
    def test_resposta_inclui_campos_de_remarketing(self):
        fake = _FakeDB(total=1, rows=[_cliente(ultima_compra="2026-07-01", total_gasto=500, qtd_pedidos=3, tags=["VIP"])])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            resultado = cadastros.listar_clientes_filtrado()
        item = resultado["data"][0]
        self.assertEqual(item["ultima_compra"], "2026-07-01")
        self.assertEqual(item["total_gasto"], 500)
        self.assertEqual(item["tags"], ["VIP"])

    def test_busca_livre_usa_mesmos_campos_de_clientes(self):
        fake = _FakeDB(total=0, rows=[])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            cadastros.listar_clientes_filtrado(busca="joao")
        query, params = fake.fetch_calls[-1]
        self.assertIn("c.nome ILIKE", query)
        self.assertIn("c.documento ILIKE", query)
        self.assertIn("c.email ILIKE", query)
        self.assertIn("c.telefone ILIKE", query)
        self.assertIn("%joao%", params)


class TestTagsDisponiveis(unittest.TestCase):
    def test_retorna_lista_de_tags(self):
        async def _fetch(query, *params):
            return [{"tag": "VIP"}, {"tag": "Atacado"}]
        fake_db = AsyncMock()
        fake_db.fetch = _fetch
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake_db)):
            resultado = cadastros.tags_disponiveis()
        self.assertEqual(resultado, ["VIP", "Atacado"])

    def test_erro_de_banco_devolve_lista_vazia(self):
        async def _fetch_falha(query, *params):
            raise RuntimeError("db down")
        fake_db = AsyncMock()
        fake_db.fetch = _fetch_falha
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake_db)):
            resultado = cadastros.tags_disponiveis()
        self.assertEqual(resultado, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
