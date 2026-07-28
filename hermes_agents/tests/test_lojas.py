"""Testes unitarios de core/lojas.py — criacao/edicao/exclusao de lojas
fisicas e vinculacao de lojas online (Shopee), incluindo o regression guard
do bug de producao (coluna "ativa" ausente por CREATE TABLE IF NOT EXISTS
nao alterar tabela ja existente)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

_TEST_TOKEN = "test-master-token-32-bytes-long!!"


async def _mp(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m


# Protege a importacao de core.lojas: o modulo roda _ensure_bling_id() e
# _ensure_shopee_cols() (ALTER TABLE reais) no top-level, na primeira vez que
# for importado no processo. Sem esse patch, se este arquivo for o primeiro a
# importar core.lojas, essas chamadas tentam abrir uma conexao Postgres real.
patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

import core.lojas as lojas


class FakeDB:
    """Fake minimo cobrindo exatamente as queries usadas por core/lojas.py —
    nao e' um SQL engine generico."""

    def __init__(self):
        self.rows = {}  # id -> dict
        self._next_id = 1
        self.executed = []  # log de todas as queries passadas por execute()
        self.fetchrow_raises = None
        self.execute_raises = None

    def _norm(self, q):
        return " ".join(q.split())

    async def execute(self, query, *params):
        q = self._norm(query)
        self.executed.append(q)
        if self.execute_raises:
            raise self.execute_raises
        if "CREATE TABLE" in q or "ALTER TABLE" in q or "CREATE UNIQUE INDEX" in q or "CREATE INDEX" in q:
            return "OK"
        if q.startswith("UPDATE lojas SET nome = $1 WHERE id = $2"):
            id_loja = params[1]
            if id_loja not in self.rows:
                return "UPDATE 0"
            self.rows[id_loja]["nome"] = params[0]
            return "UPDATE 1"
        if q.startswith("UPDATE lojas SET shopee_markup_pct"):
            self.rows[params[1]]["shopee_markup_pct"] = params[0]
            return "UPDATE 1"
        if q.startswith("UPDATE lojas SET grupos_publicacao"):
            self.rows[params[1]]["grupos_publicacao"] = params[0]
            return "UPDATE 1"
        if q.startswith("UPDATE lojas SET tipo = $1 WHERE id = $2"):
            self.rows[params[1]]["tipo"] = params[0]
            return "UPDATE 1"
        if q.startswith("DELETE FROM lojas WHERE id = $1"):
            id_loja = params[0]
            if id_loja not in self.rows:
                return "DELETE 0"
            del self.rows[id_loja]
            return "DELETE 1"
        generico = self._update_generico(q, params)
        if generico is not None:
            return generico
        return "OK"

    def _update_generico(self, q, params):
        """Cobre o UPDATE dinamico gerado por core.lojas._update_campos()
        (usado por atualizar_geral e por todos os core/lojas_*.py que
        reaproveitam esse helper): "UPDATE lojas SET col1 = $1, col2 = $2
        WHERE id = $N"."""
        import re
        m = re.match(r"UPDATE lojas SET (.+) WHERE id = \$(\d+)$", q)
        if not m:
            return None
        id_loja = params[int(m.group(2)) - 1]
        if id_loja not in self.rows:
            return "UPDATE 0"
        for atrib in m.group(1).split(","):
            col, ph = [p.strip() for p in atrib.split("=")]
            idx = int(ph.lstrip("$")) - 1
            self.rows[id_loja][col] = params[idx]
        return "UPDATE 1"

    async def fetchval(self, query, *params):
        return 0

    async def fetchrow(self, query, *params):
        q = self._norm(query)
        if self.fetchrow_raises:
            raise self.fetchrow_raises
        if q.startswith("INSERT INTO lojas (nome, tipo)"):
            nome, tipo = params
            id_loja = self._next_id; self._next_id += 1
            row = {"id": id_loja, "nome": nome, "ativa": True, "tipo": tipo}
            self.rows[id_loja] = row
            return dict(row)
        if q.startswith("SELECT * FROM lojas WHERE id = $1"):
            row = self.rows.get(params[0])
            return dict(row) if row else None
        if q.startswith("UPDATE lojas SET shopee_shop_id = $1"):
            shop_id, shop_name, access_token, refresh_token, expira_em, id_loja = params
            if id_loja not in self.rows:
                return None
            row = self.rows[id_loja]
            row["shopee_shop_id"] = shop_id
            row["shopee_shop_name"] = shop_name or row.get("shopee_shop_name")
            row["shopee_access_token"] = access_token
            row["shopee_refresh_token"] = refresh_token
            return {"id": row["id"], "nome": row["nome"], "shopee_shop_id": row["shopee_shop_id"]}
        if q.startswith("INSERT INTO lojas (nome, shopee_shop_id"):
            nome, shop_id, shop_name, access_token, refresh_token, expira_em = params
            id_loja = self._next_id; self._next_id += 1
            row = {"id": id_loja, "nome": nome, "ativa": True, "tipo": "virtual",
                   "shopee_shop_id": shop_id, "shopee_shop_name": shop_name,
                   "shopee_access_token": access_token, "shopee_refresh_token": refresh_token}
            self.rows[id_loja] = row
            return {"id": id_loja, "nome": nome, "shopee_shop_id": shop_id}
        if q.startswith("UPDATE lojas SET shopee_shop_id = NULL"):
            id_loja = params[0]
            if id_loja not in self.rows:
                return None
            row = self.rows[id_loja]
            for campo in ("shopee_shop_id", "shopee_shop_name", "shopee_access_token", "shopee_refresh_token"):
                row[campo] = None
            return {"id": row["id"], "nome": row["nome"]}
        if q.startswith("SELECT shopee_shop_id, shopee_access_token, shopee_refresh_token"):
            id_loja = params[0]
            row = self.rows.get(id_loja)
            if not row:
                return None
            return {k: row.get(k) for k in ("shopee_shop_id", "shopee_access_token", "shopee_refresh_token")}
        return None

    async def fetch(self, query, *params):
        q = self._norm(query)
        if "SELECT id, nome, ativa, created_at, bling_id, tipo FROM lojas" in q:
            return [dict(r) for r in self.rows.values()]
        if "shopee_shop_id IS NOT NULL" in q and "tem_token" in q:
            return [{"id": r["id"], "nome": r["nome"], "shopee_shop_id": r.get("shopee_shop_id"),
                     "shopee_shop_name": r.get("shopee_shop_name"), "shopee_token_expira_em": None,
                     "tem_token": bool(r.get("shopee_access_token"))}
                    for r in self.rows.values() if r.get("shopee_shop_id")]
        return []


class TestLojasFisicas(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fake = FakeDB()

        async def _get_db(_fake=self.fake):
            return _fake
        self._p = patch("core.lojas.get_db", side_effect=_get_db)
        self._p.start()
        lojas._table_ok = True  # pula _ensure_table() real (CREATE TABLE)

    def tearDown(self):
        self._p.stop()
        lojas._table_ok = False

    async def test_criar_loja_fisica_default(self):
        r = lojas.criar("Loja Centro")
        self.assertNotIn("error", r)
        self.assertEqual(r["nome"], "Loja Centro")
        self.assertEqual(r["tipo"], "fisica")
        self.assertTrue(r["ativa"])

    async def test_criar_loja_tipo_invalido_cai_para_fisica(self):
        r = lojas.criar("Loja X", tipo="qualquer-coisa")
        self.assertEqual(r["tipo"], "fisica")

    async def test_criar_loja_tipo_hibrida_e_marketplace_aceitos(self):
        """Fase 2 do frontend expoe 4 tipos (fisica/virtual/hibrida/
        marketplace) — o backend precisa aceitar todos, nao so' os 2 originais."""
        self.assertEqual(lojas.criar("Loja Hibrida", tipo="hibrida")["tipo"], "hibrida")
        self.assertEqual(lojas.criar("Loja Marketplace", tipo="marketplace")["tipo"], "marketplace")

    async def test_listar_retorna_lojas_criadas(self):
        lojas.criar("Loja A")
        lojas.criar("Loja B")
        result = lojas.listar()
        nomes = {r["nome"] for r in result}
        self.assertEqual(nomes, {"Loja A", "Loja B"})

    async def test_atualizar_nome_sucesso(self):
        criada = lojas.criar("Loja Antiga")
        ok = lojas.atualizar(criada["id"], "Loja Nova")
        self.assertTrue(ok)
        self.assertEqual(self.fake.rows[criada["id"]]["nome"], "Loja Nova")

    async def test_atualizar_loja_inexistente_retorna_false(self):
        ok = lojas.atualizar(9999, "Nome Qualquer")
        self.assertFalse(ok)

    async def test_atualizar_tipo_para_virtual(self):
        criada = lojas.criar("Loja Fisica")
        ok = lojas.atualizar(criada["id"], "Loja Fisica", tipo="virtual")
        self.assertTrue(ok)
        self.assertEqual(self.fake.rows[criada["id"]]["tipo"], "virtual")

    async def test_deletar_loja_sucesso(self):
        criada = lojas.criar("Loja Descartavel")
        ok = lojas.deletar(criada["id"])
        self.assertTrue(ok)
        self.assertNotIn(criada["id"], self.fake.rows)

    async def test_deletar_loja_inexistente_retorna_false(self):
        ok = lojas.deletar(9999)
        self.assertFalse(ok)

    async def test_criar_loja_com_erro_db_retorna_error_e_loga(self):
        """Regressao do bug de producao: qualquer excecao no INSERT deve virar
        {"error": str(e)} pro caller (nunca 500 generico opaco) e ser
        persistida via syslog em vez de silenciosamente descartada."""
        self.fake.fetchrow_raises = Exception('column "ativa" does not exist')
        with patch("core.seguranca.syslog") as mock_syslog:
            r = lojas.criar("Loja Charme")
        self.assertEqual(r, {"error": 'column "ativa" does not exist'})
        mock_syslog.assert_called_once()
        args, kwargs = mock_syslog.call_args
        self.assertEqual(args[0], "ERROR")
        self.assertEqual(args[1], "lojas")
        self.assertIn("ativa", args[2])


class TestLojasCadastroGeral(unittest.IsolatedAsyncioTestCase):
    """Identificacao/endereco/contatos (cadastro empresarial completo) e
    sincronizacao de status <-> ativa (aditiva, nao quebra WHERE ativa=TRUE
    ja espalhado em estoque/pdv/vendas)."""

    def setUp(self):
        self.fake = FakeDB()

        async def _get_db(_fake=self.fake):
            return _fake
        self._p = patch("core.lojas.get_db", side_effect=_get_db)
        self._p.start()
        lojas._table_ok = True

    def tearDown(self):
        self._p.stop()
        lojas._table_ok = False

    async def test_atualizar_geral_identificacao_e_endereco(self):
        criada = lojas.criar("Loja Centro")
        ok = lojas.atualizar_geral(criada["id"], {
            "nome_fantasia": "Charme Nilopolis", "cnpj_cpf": "12345678000199",
            "cep": "26520-000", "cidade": "Nilopolis", "estado": "RJ",
            "instagram": "@charme.nilopolis",
        })
        self.assertTrue(ok)
        row = self.fake.rows[criada["id"]]
        self.assertEqual(row["nome_fantasia"], "Charme Nilopolis")
        self.assertEqual(row["cidade"], "Nilopolis")
        self.assertEqual(row["instagram"], "@charme.nilopolis")

    async def test_atualizar_geral_ignora_campos_fora_do_whitelist(self):
        criada = lojas.criar("Loja X")
        ok = lojas.atualizar_geral(criada["id"], {"nome_fantasia": "X Fantasia", "senha_admin": "hackeado"})
        self.assertTrue(ok)
        self.assertNotIn("senha_admin", self.fake.rows[criada["id"]])

    async def test_status_bloqueada_sincroniza_ativa_false(self):
        criada = lojas.criar("Loja Y")
        lojas.atualizar_geral(criada["id"], {"status": "bloqueada"})
        row = self.fake.rows[criada["id"]]
        self.assertEqual(row["status"], "bloqueada")
        self.assertFalse(row["ativa"])

    async def test_status_ativa_sincroniza_ativa_true(self):
        criada = lojas.criar("Loja Z")
        lojas.atualizar_geral(criada["id"], {"status": "ativa"})
        self.assertTrue(self.fake.rows[criada["id"]]["ativa"])

    async def test_status_invalido_cai_para_ativa(self):
        criada = lojas.criar("Loja W")
        lojas.atualizar_geral(criada["id"], {"status": "sei-la"})
        row = self.fake.rows[criada["id"]]
        self.assertEqual(row["status"], "ativa")
        self.assertTrue(row["ativa"])

    async def test_obter_loja_completa(self):
        criada = lojas.criar("Loja Completa")
        lojas.atualizar_geral(criada["id"], {"razao_social": "Loja Completa LTDA"})
        obtida = lojas.obter(criada["id"])
        self.assertEqual(obtida["razao_social"], "Loja Completa LTDA")

    async def test_obter_loja_inexistente_retorna_none(self):
        self.assertIsNone(lojas.obter(9999))


class TestLojasOnlineShopee(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fake = FakeDB()

        async def _get_db(_fake=self.fake):
            return _fake
        self._p = patch("core.lojas.get_db", side_effect=_get_db)
        self._p.start()
        lojas._table_ok = True

    def tearDown(self):
        self._p.stop()
        lojas._table_ok = False

    async def test_criar_loja_shopee_sucesso(self):
        r = lojas.criar_loja_shopee("SHOP123", "token-abc", refresh_token="refresh-abc", shop_name="Minha Loja Shopee")
        self.assertNotIn("error", r)
        self.assertEqual(r["shopee_shop_id"], "SHOP123")
        self.assertEqual(self.fake.rows[r["id"]]["shopee_access_token"], "token-abc")

    async def test_criar_loja_shopee_sem_nome_usa_fallback(self):
        r = lojas.criar_loja_shopee("SHOP999", "token-xyz")
        self.assertEqual(r["nome"], "Shopee SHOP999")

    async def test_vincular_shopee_a_loja_existente(self):
        fisica = lojas.criar("Loja Fisica p/ vincular")
        r = lojas.vincular_shopee(fisica["id"], "SHOP1", "tok1", refresh_token="ref1", shop_name="Loja Vinculada")
        self.assertNotIn("error", r)
        self.assertEqual(r["shopee_shop_id"], "SHOP1")
        self.assertEqual(self.fake.rows[fisica["id"]]["shopee_shop_id"], "SHOP1")

    async def test_vincular_shopee_loja_inexistente_retorna_error(self):
        r = lojas.vincular_shopee(9999, "SHOP1", "tok1")
        self.assertIn("error", r)

    async def test_desconectar_shopee_limpa_credenciais(self):
        loja = lojas.criar_loja_shopee("SHOP2", "tok2", refresh_token="ref2")
        r = lojas.desconectar_shopee(loja["id"])
        self.assertNotIn("error", r)
        row = self.fake.rows[loja["id"]]
        self.assertIsNone(row["shopee_shop_id"])
        self.assertIsNone(row["shopee_access_token"])

    async def test_desconectar_shopee_loja_inexistente_retorna_error(self):
        r = lojas.desconectar_shopee(9999)
        self.assertIn("error", r)

    async def test_listar_lojas_shopee_so_traz_vinculadas(self):
        lojas.criar("Loja Sem Shopee")
        lojas.criar_loja_shopee("SHOP3", "tok3")
        result = lojas.listar_lojas_shopee()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["shopee_shop_id"], "SHOP3")
        self.assertTrue(result[0]["tem_token"])

    async def test_obter_credenciais_shopee(self):
        loja = lojas.criar_loja_shopee("SHOP4", "tok4", refresh_token="ref4")
        creds = lojas.obter_credenciais_shopee(loja["id"])
        self.assertEqual(creds["shopee_shop_id"], "SHOP4")
        self.assertEqual(creds["shopee_access_token"], "tok4")
        self.assertEqual(creds["shopee_refresh_token"], "ref4")

    async def test_obter_credenciais_shopee_loja_inexistente_retorna_dict_vazio(self):
        creds = lojas.obter_credenciais_shopee(9999)
        self.assertEqual(creds, {})


class TestEnsureTableRegressaoColunaAtiva(unittest.IsolatedAsyncioTestCase):
    """Guarda a correcao do bug de producao: _ensure_table() precisa emitir um
    ALTER TABLE defensivo para a coluna "ativa", nao so' para "tipo" — porque
    CREATE TABLE IF NOT EXISTS nao adiciona colunas a uma tabela ja existente
    e a tabela em producao foi criada antes dessa coluna existir."""

    async def test_ensure_table_executa_alter_para_ativa_e_tipo(self):
        fake = FakeDB()

        async def _get_db(_fake=fake):
            return _fake
        with patch("core.lojas.get_db", side_effect=_get_db):
            lojas._table_ok = False
            lojas._ensure_table()
        alters = [q for q in fake.executed if "ALTER TABLE lojas" in q]
        self.assertTrue(any("ativa" in q for q in alters),
                         "regressao: falta o ALTER TABLE ADD COLUMN IF NOT EXISTS ativa")
        self.assertTrue(any("tipo" in q for q in alters))
        lojas._table_ok = False


if __name__ == "__main__":
    unittest.main(verbosity=2)
