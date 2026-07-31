"""Testes de core/produtos_loja.py — CRUD isolado com FakeDB."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch


class FakeDBProdutosLoja:
    def __init__(self):
        self.linhas = {}  # (loja, sku) -> dict
        self._next_id = 1
        self.auditorias = []

    async def execute(self, query, *params):
        return "OK"

    async def fetchval(self, query, *params):
        q = " ".join(query.split())
        if "SELECT id FROM produtos_loja WHERE loja" in q:
            loja, sku = params
            row = self.linhas.get((loja, sku))
            return row["id"] if row else None
        if "SELECT COUNT(*) FROM produtos_loja" in q:
            # Mirror core.produtos_loja.listar_por_loja(): a query de COUNT(*)
            # usa o mesmo sql_where da query principal, entao quando ha busca
            # ela tambem filtra o COUNT (nao so' a pagina de resultados).
            loja = params[0]
            busca = params[1] if len(params) > 1 else None
            rows = [r for (l, _), r in self.linhas.items() if l == loja]
            if busca and busca.strip("%"):
                termo = busca.strip("%").lower()
                rows = [r for r in rows if termo in r.get("sku", "").lower()]
            return len(rows)
        return None

    async def fetchrow(self, query, *params):
        q = " ".join(query.split())
        if q.startswith("INSERT INTO produtos_loja"):
            loja, sku, mestre = params[0], params[1], params[2]
            row = {"id": self._next_id, "loja": loja, "sku": sku, "produto_mestre_sku": mestre}
            self.linhas[(loja, sku)] = row
            self._next_id += 1
            return row
        if q.startswith("SELECT * FROM produtos_loja WHERE loja"):
            loja, sku = params
            return self.linhas.get((loja, sku))
        if q.startswith("UPDATE produtos_loja SET"):
            loja, sku = params[0], params[1]
            row = self.linhas.get((loja, sku))
            if not row:
                return None
            # Apply all editable field updates from params[2:]
            campo_nomes = ["preco_custo", "preco_venda", "promocao_ativa", "promocao_preco",
                          "promocao_inicio", "promocao_fim", "comissao_pct", "fornecedor_id",
                          "deposito", "localizacao_fisica", "estoque_minimo", "estoque_maximo",
                          "observacoes_internas", "produto_mestre_sku", "codigo_interno",
                          "codigo_barras_override", "nome_override", "status"]
            for i, val in enumerate(params[2:]):
                if i < len(campo_nomes):
                    row[campo_nomes[i]] = val
            return row
        if q.startswith("DELETE FROM produtos_loja"):
            loja, sku = params
            row = self.linhas.pop((loja, sku), None)
            return row
        return None

    async def fetch(self, query, *params):
        # Extract pagination and search params
        # params structure: [loja, (optional)busca_pattern, (optional)loja_estoque_resolvida, ..., por_pagina, offset]
        # Nao da' pra inferir a presenca de busca por contagem de params (Task 8
        # do vinculo fisica x virtual acrescentou um bind param extra pro JOIN
        # com estoque_lojas, deslocando a contagem independente de haver busca
        # ou nao) — em vez disso, identifica pelo formato: busca sempre vem
        # como "%termo%" (a producao envolve com % nos dois lados), enquanto
        # loja/loja_estoque_resolvida sao nomes literais de loja, sem %.
        loja = params[0]
        busca = next(
            (p for p in params[1:-2] if isinstance(p, str) and p.startswith("%") and p.endswith("%")),
            None)

        # Extract pagination params (last two elements)
        por_pagina = params[-2]
        offset = params[-1]

        # Filter by loja
        rows = [dict(r) for (l, _), r in self.linhas.items() if l == loja]

        # Filter by search if present
        if busca and busca.strip("%"):
            search_term = busca.strip("%").lower()
            rows = [r for r in rows if search_term in r.get("sku", "").lower()]

        # Apply offset and limit for pagination
        paginated = rows[offset:offset + por_pagina]

        # Add join-derived fields
        for row in paginated:
            row["estoque_atual"] = 0  # Default stock from estoque_lojas join
            row["nome_mestre"] = None  # From catalogo_produtos join
            row["imagens"] = None  # From catalogo_produtos join

        return paginated


class TestProdutosLoja(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.fake = FakeDBProdutosLoja()
        async def _get_db(_fake=self.fake):
            return _fake
        self.patch_db = patch("core.produtos_loja.get_db", side_effect=_get_db)
        self.patch_db.start()
        self.patch_audit = patch("core.produtos_loja.auditar_alteracao", return_value=None)
        self.patch_audit.start()
        self.patch_audit_del = patch("core.produtos_loja.auditar_exclusao", return_value=None)
        self.patch_audit_del.start()
        import core.produtos_loja as m
        m._ok = True

    def tearDown(self):
        self.patch_db.stop()
        self.patch_audit.stop()
        self.patch_audit_del.stop()

    async def test_criar_produto_loja(self):
        from core.produtos_loja import criar
        r = criar("Loja A", "SKU1", produto_mestre_sku="SKU1")
        self.assertTrue(r.get("ok"))
        self.assertEqual(r["sku"], "SKU1")

    async def test_criar_duplicado_erro(self):
        from core.produtos_loja import criar
        criar("Loja A", "SKU1")
        r = criar("Loja A", "SKU1")
        self.assertIn("erro", r)

    async def test_criar_sem_loja_ou_sku_erro(self):
        from core.produtos_loja import criar
        self.assertIn("erro", criar("", "SKU1"))
        self.assertIn("erro", criar("Loja A", ""))

    async def test_obter_existente(self):
        from core.produtos_loja import criar, obter
        criar("Loja A", "SKU1")
        r = obter("Loja A", "SKU1")
        self.assertIsNotNone(r)
        self.assertEqual(r["sku"], "SKU1")

    async def test_obter_inexistente_retorna_none(self):
        from core.produtos_loja import obter
        self.assertIsNone(obter("Loja A", "SKU_NAO_EXISTE"))

    async def test_excluir_existente(self):
        from core.produtos_loja import criar, excluir, obter
        criar("Loja A", "SKU1")
        r = excluir("Loja A", "SKU1")
        self.assertTrue(r.get("ok"))
        self.assertIsNone(obter("Loja A", "SKU1"))

    async def test_excluir_inexistente_erro(self):
        from core.produtos_loja import excluir
        self.assertIn("erro", excluir("Loja A", "SKU_NAO_EXISTE"))

    async def test_atualizar_sem_campos_editaveis_erro(self):
        from core.produtos_loja import criar, atualizar
        criar("Loja A", "SKU1")
        r = atualizar("Loja A", "SKU1", campo_invalido="x")
        self.assertIn("erro", r)

    async def test_listar_por_loja(self):
        from core.produtos_loja import criar, listar_por_loja
        criar("Loja A", "SKU1", produto_mestre_sku="SKU1")
        criar("Loja A", "SKU2", produto_mestre_sku="SKU2")
        criar("Loja B", "SKU1", produto_mestre_sku="SKU1")
        r = listar_por_loja("Loja A")
        self.assertEqual(r["total"], 2)
        self.assertEqual(len(r["produtos"]), 2)
        self.assertEqual(r["pagina"], 1)
        skus = [p["sku"] for p in r["produtos"]]
        self.assertIn("SKU1", skus)
        self.assertIn("SKU2", skus)

    async def test_atualizar_sucesso(self):
        from core.produtos_loja import criar, atualizar
        criar("Loja A", "SKU1", preco_custo=50.00)
        r = atualizar("Loja A", "SKU1", preco_custo=99.90, preco_venda=150.00)
        self.assertTrue(r.get("ok"))
        self.assertEqual(r["preco_custo"], 99.90)
        self.assertEqual(r["preco_venda"], 150.00)
        self.assertEqual(r["sku"], "SKU1")

    async def test_listar_por_loja_pagination_page1(self):
        from core.produtos_loja import criar, listar_por_loja
        criar("Loja A", "SKU1")
        criar("Loja A", "SKU2")
        criar("Loja A", "SKU3")
        r = listar_por_loja("Loja A", pagina=1, por_pagina=2)
        self.assertEqual(r["total"], 3)
        self.assertEqual(len(r["produtos"]), 2)
        self.assertEqual(r["pagina"], 1)

    async def test_listar_por_loja_pagination_page2(self):
        # ponytail: nao afirma qual SKU especifico cai na pagina 2 — a ordem
        # real vem de "ORDER BY pl.updated_at DESC, pl.id DESC" (ver Important
        # 5 da revisao final), que o FakeDB nao simula (ele so' preserva a
        # ordem de insercao do dict). Afirmar um SKU fixo aqui so' acertaria
        # por coincidencia da ordem de insercao do teste, nao porque reflete
        # o comportamento real do ORDER BY contra um Postgres de verdade.
        # Em vez disso, verificamos a invariante que de fato importa: as duas
        # paginas juntas cobrem todos os SKUs, sem duplicatas.
        from core.produtos_loja import criar, listar_por_loja
        criar("Loja A", "SKU1")
        criar("Loja A", "SKU2")
        criar("Loja A", "SKU3")
        pagina1 = listar_por_loja("Loja A", pagina=1, por_pagina=2)
        pagina2 = listar_por_loja("Loja A", pagina=2, por_pagina=2)
        self.assertEqual(pagina2["total"], 3)
        self.assertEqual(len(pagina2["produtos"]), 1)
        self.assertEqual(pagina2["pagina"], 2)
        skus_pagina1 = {p["sku"] for p in pagina1["produtos"]}
        skus_pagina2 = {p["sku"] for p in pagina2["produtos"]}
        self.assertEqual(len(skus_pagina1), 2)
        self.assertEqual(len(skus_pagina2), 1)
        self.assertEqual(skus_pagina1 | skus_pagina2, {"SKU1", "SKU2", "SKU3"})
        self.assertEqual(skus_pagina1 & skus_pagina2, set())

    async def test_listar_por_loja_busca_search(self):
        from core.produtos_loja import criar, listar_por_loja
        criar("Loja A", "SKU1")
        criar("Loja A", "SKU2")
        criar("Loja A", "ABC123")
        r = listar_por_loja("Loja A", busca="SKU")
        self.assertEqual(r["total"], 2)
        self.assertEqual(len(r["produtos"]), 2)
        skus = [p["sku"] for p in r["produtos"]]
        self.assertIn("SKU1", skus)
        self.assertIn("SKU2", skus)
        self.assertNotIn("ABC123", skus)

    async def test_listar_por_loja_has_join_fields(self):
        from core.produtos_loja import criar, listar_por_loja
        criar("Loja A", "SKU1")
        r = listar_por_loja("Loja A")
        self.assertEqual(len(r["produtos"]), 1)
        row = r["produtos"][0]
        self.assertIn("estoque_atual", row)
        self.assertIn("nome_mestre", row)
        self.assertIn("imagens", row)

    async def test_replicar_para_lojas_nao_copia_operacional(self):
        from core.produtos_loja import criar, replicar_para_lojas, obter
        criar("Loja A", "SKU1", produto_mestre_sku="SKU1")
        r = replicar_para_lojas("Loja A", "SKU1", ["Loja B", "Loja C"])
        self.assertTrue(r.get("ok"))
        self.assertEqual(set(r["criados"]), {"Loja B", "Loja C"})
        destino = obter("Loja B", "SKU1")
        self.assertIsNone(destino.get("preco_custo"))
        self.assertIsNone(destino.get("preco_venda"))
        self.assertIsNone(destino.get("fornecedor_id"))

    async def test_replicar_pula_loja_ja_existente(self):
        from core.produtos_loja import criar, replicar_para_lojas
        criar("Loja A", "SKU1", produto_mestre_sku="SKU1")
        criar("Loja B", "SKU1", produto_mestre_sku="SKU1")
        r = replicar_para_lojas("Loja A", "SKU1", ["Loja B", "Loja C"])
        self.assertEqual(r["ja_existentes"], ["Loja B"])
        self.assertEqual(r["criados"], ["Loja C"])

    async def test_replicar_origem_nao_existe_retorna_erro(self):
        from core.produtos_loja import replicar_para_lojas
        r = replicar_para_lojas("Loja Inexistente", "SKU_NAO_EXISTE", ["Loja B"])
        self.assertIn("erro", r)
        self.assertNotIn("ok", r)

    async def test_replicar_lista_vazia_retorna_listas_vazias(self):
        from core.produtos_loja import criar, replicar_para_lojas
        criar("Loja A", "SKU1", produto_mestre_sku="SKU1")
        r = replicar_para_lojas("Loja A", "SKU1", [])
        self.assertTrue(r.get("ok"))
        self.assertEqual(r["criados"], [])
        self.assertEqual(r["ja_existentes"], [])
        self.assertEqual(r["erros"], [])

    async def test_replicar_captura_erro_de_criar(self):
        from core.produtos_loja import criar, replicar_para_lojas
        # Create origin product
        criar("Loja A", "SKU1", produto_mestre_sku="SKU1")

        # Patch criar to fail for "Loja B" but succeed for others
        import core.produtos_loja as m
        original_criar = m.criar
        def criar_mock_fail_for_b(loja, sku, **kwargs):
            if loja == "Loja B":
                return {"erro": "erro simulado na loja B"}
            return original_criar(loja, sku, **kwargs)

        with patch("core.produtos_loja.criar", side_effect=criar_mock_fail_for_b):
            r = replicar_para_lojas("Loja A", "SKU1", ["Loja B", "Loja C", "Loja D"])

        self.assertTrue(r.get("ok"))
        self.assertEqual(r["criados"], ["Loja C", "Loja D"])
        self.assertEqual(r["ja_existentes"], [])
        self.assertEqual(len(r["erros"]), 1)
        self.assertEqual(r["erros"][0]["loja"], "Loja B")
        self.assertIn("erro simulado na loja B", r["erros"][0]["erro"])

    async def test_sincronizar_do_mestre_limpa_override(self):
        from core.produtos_loja import criar, atualizar, sincronizar_do_mestre
        criar("Loja A", "SKU1", produto_mestre_sku="SKU1")
        atualizar("Loja A", "SKU1", nome_override="Nome customizado da loja")
        r = sincronizar_do_mestre("Loja A", "SKU1", ["nome_override"])
        self.assertTrue(r.get("ok"))

    async def test_sincronizar_campo_invalido_erro(self):
        from core.produtos_loja import criar, sincronizar_do_mestre
        criar("Loja A", "SKU1", produto_mestre_sku="SKU1")
        r = sincronizar_do_mestre("Loja A", "SKU1", ["preco_custo"])
        self.assertIn("erro", r)


class TestResolverNomeLoja(unittest.IsolatedAsyncioTestCase):
    """Testa a traducao id-numerico -> nome de loja no limite HTTP
    (routes/produtos_loja.py:_resolver_nome_loja) — Critical 1 da revisao
    final. produtos_loja.loja precisa guardar o NOME da loja (mesma
    convencao de estoque_lojas/pdv/entidades.py), mas o frontend manda o id
    numerico da loja selecionada no seletor global; sem essa traducao o
    LEFT JOIN com estoque_lojas em listar_por_loja() nunca bate.

    ponytail: nao reusa FakeDBProdutosLoja (ela simula a tabela produtos_loja,
    nao a tabela lojas usada por esse lookup) — um fake minimo dedicado a
    "SELECT nome FROM lojas WHERE id = $1" e' mais simples e mais fiel do que
    forcar a fake existente a cobrir uma query completamente diferente."""

    class FakeDBLojas:
        def __init__(self, id_para_nome):
            self.id_para_nome = id_para_nome

        async def fetchval(self, query, *params):
            if "SELECT nome FROM lojas WHERE id" in " ".join(query.split()):
                return self.id_para_nome.get(params[0])
            return None

    def setUp(self):
        self.fake = self.FakeDBLojas({7: "Loja Centro"})
        async def _get_db(_fake=self.fake):
            return _fake
        self.patch_db = patch("routes.produtos_loja.get_db", side_effect=_get_db)
        self.patch_db.start()

    def tearDown(self):
        self.patch_db.stop()

    async def test_id_numerico_e_traduzido_para_nome(self):
        from routes.produtos_loja import _resolver_nome_loja
        self.assertEqual(_resolver_nome_loja("7"), "Loja Centro")

    async def test_nome_ja_passa_direto(self):
        from routes.produtos_loja import _resolver_nome_loja
        self.assertEqual(_resolver_nome_loja("Loja Centro"), "Loja Centro")

    async def test_id_inexistente_faz_fallback_para_string_original(self):
        from routes.produtos_loja import _resolver_nome_loja
        self.assertEqual(_resolver_nome_loja("999"), "999")

    async def test_string_vazia_passa_direto(self):
        from routes.produtos_loja import _resolver_nome_loja
        self.assertEqual(_resolver_nome_loja(""), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
