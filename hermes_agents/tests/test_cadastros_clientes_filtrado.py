"""Testes de core.cadastros.listar_clientes_filtrado — endpoint dedicado de
Contatos (paginacao real + filtros + dados de remarketing), sem tocar em
list_paginado/_list_pagina/_count, que continuam servindo as outras 5
tabelas de Cadastros."""
import sys, os, unittest, datetime
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

    def test_order_by_tem_desempate_estavel_por_id(self):
        # Clientes sem compra empatam em total_gasto=0/ultima_compra=NULL —
        # sem desempate por c.id, a ordem entre linhas empatadas pode variar
        # de uma pagina pra outra da mesma consulta.
        fake = _FakeDB(total=0, rows=[])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            cadastros.listar_clientes_filtrado(sort="total_gasto", order="desc")
        query, _ = fake.fetch_calls[-1]
        self.assertIn("ORDER BY compras.total_gasto DESC NULLS LAST, c.id DESC", query)


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


class TestListarClientesFiltradoCountLateral(unittest.TestCase):
    """COUNT(*) so' precisa do LATERAL de compras quando algum filtro
    referencia compras.* na WHERE (hoje, so' sem_comprar_dias) — nos demais
    casos ele forcava uma agregacao por cliente contra vendas_pedidos sem
    necessidade em toda paginacao/filtro."""

    def test_count_sem_sem_comprar_dias_nao_inclui_lateral(self):
        fake = _FakeDB(total=0, rows=[])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            cadastros.listar_clientes_filtrado(status="ativo", tag="VIP", whatsapp=True)
        count_query, _ = fake.fetchval_calls[-1]
        self.assertNotIn("LATERAL", count_query)

    def test_count_com_sem_comprar_dias_inclui_lateral(self):
        fake = _FakeDB(total=0, rows=[])
        with patch("core.cadastros.get_db", AsyncMock(return_value=fake)):
            cadastros.listar_clientes_filtrado(sem_comprar_dias=30)
        count_query, _ = fake.fetchval_calls[-1]
        self.assertIn("LATERAL", count_query)


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


class TestCoercaoDataNascimentoClientes(unittest.TestCase):
    """asyncpg nao converte string ISO pra DATE automaticamente — exige
    datetime.date de verdade, senao estoura erro em runtime. A tela de
    Contatos manda data_nascimento como string "YYYY-MM-DD" (<input
    type="date">) tanto ao criar quanto ao editar (o modal sempre reenvia o
    campo). Mesmo problema ja resolvido em core.crm._coerce_datas; aqui
    escopado so' pra clientes.data_nascimento."""

    def test_create_converte_data_nascimento_string_para_date(self):
        with patch("core.cadastros._create", return_value={"id": 1}) as mock_create:
            cadastros.create("clientes", {"nome": "Cliente X", "data_nascimento": "1990-05-12"})
        dados_enviados = mock_create.call_args.args[1]
        self.assertIsInstance(dados_enviados["data_nascimento"], datetime.date)
        self.assertEqual(dados_enviados["data_nascimento"], datetime.date(1990, 5, 12))

    def test_update_converte_data_nascimento_string_para_date(self):
        # Regressao central do achado: editar um contato que ja tem
        # data_nascimento preenchida reenvia o campo mesmo sem o usuario
        # mexer nele — precisa continuar virando datetime.date, senao toda
        # edicao de um contato com data de nascimento quebra.
        with patch("core.cadastros._update", return_value={"id": 1}) as mock_update:
            cadastros.update("clientes", 1, {"nome": "Cliente X", "data_nascimento": "1990-05-12"})
        dados_enviados = mock_update.call_args.args[2]
        self.assertIsInstance(dados_enviados["data_nascimento"], datetime.date)
        self.assertEqual(dados_enviados["data_nascimento"], datetime.date(1990, 5, 12))

    def test_update_data_nascimento_vazia_vira_none(self):
        with patch("core.cadastros._update", return_value={"id": 1}) as mock_update:
            cadastros.update("clientes", 1, {"data_nascimento": ""})
        dados_enviados = mock_update.call_args.args[2]
        self.assertIsNone(dados_enviados["data_nascimento"])

    def test_outra_tabela_nao_e_afetada_pela_coercao(self):
        with patch("core.cadastros._create", return_value={"id": 1}) as mock_create:
            cadastros.create("fornecedores", {"nome": "Fornecedor X", "data_nascimento": "1990-05-12"})
        dados_enviados = mock_create.call_args.args[1]
        self.assertEqual(dados_enviados["data_nascimento"], "1990-05-12")


if __name__ == "__main__":
    unittest.main(verbosity=2)
