"""Hardening de /api/produtos (listar/detalhe/editar) e /api/documentos
(upload de imagem do produto): RBAC ausente em GET, conexao sincrona
(psycopg2) vazando em caso de excecao, valor sem validacao de tipo indo cru
pro UPDATE, e mime type de upload confiado sem whitelist (XSS armazenado
via GET /api/documentos/<id> servido inline)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock, MagicMock

_TEST_TOKEN = "test-master-token-32-bytes-long!!"

async def _mp(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=1), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

_psycopg_patcher = patch("psycopg2.connect")
_psycopg_patcher.start()

os.environ.setdefault("ATHENA_TOKEN", _TEST_TOKEN)

import athena_bridge
import core.rbac as rbac


def _app():
    athena_bridge.app.config["TESTING"] = True
    return athena_bridge.app.test_client()


class _FakeCursor:
    """Cursor psycopg2 minimo — COUNT sempre 0, fetchall sempre vazio,
    registra as queries executadas pra inspecao (ex.: valor do LIMIT)."""
    def __init__(self):
        self.queries = []
        self.description = []

    def execute(self, sql, params=None):
        self.queries.append((sql, params))

    def fetchone(self):
        return [0]

    def fetchall(self):
        return []

    def close(self):
        pass


class _FakeConn:
    def __init__(self, cursor=None):
        self._cursor = cursor or _FakeCursor()
        self.closed = False

    def cursor(self, cursor_factory=None):
        return self._cursor

    def rollback(self):
        pass

    def close(self):
        self.closed = True


class TestProdutosListarDetalheRBAC(unittest.TestCase):
    """GET /api/produtos e GET /api/produtos/<sku> so' checavam autenticacao
    generica — qualquer usuario logado, com qualquer papel, via custo,
    fornecedor e margem do catalogo inteiro."""

    def setUp(self):
        self._env = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env.start()
        self.client = _app()

    def tearDown(self):
        self._env.stop()

    def test_listar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(1, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]):
            r = self.client.get("/api/produtos", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_detalhe_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(1, "op@x.com", "Sem Papel")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=[]):
            r = self.client.get("/api/produtos/X1", headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_listar_com_permissao_libera(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        fake_conn = _FakeConn()
        with patch("athena_bridge._db_sync", return_value=fake_conn):
            r = self.client.get("/api/produtos", headers=headers)
        self.assertEqual(r.status_code, 200)


class TestProdutosPorPaginaCap(unittest.TestCase):
    """por_pagina sem limite superior deixava um cliente pedir uma varredura
    completa da tabela (catalogo pode ter dezenas de milhares de SKUs)."""

    def setUp(self):
        self._env = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env.start()
        self.client = _app()

    def tearDown(self):
        self._env.stop()

    def test_por_pagina_acima_do_max_e_clampado(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        fake_conn = _FakeConn()
        with patch("athena_bridge._db_sync", return_value=fake_conn):
            r = self.client.get("/api/produtos?por_pagina=999999", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["por_pagina"], athena_bridge.PRODUTOS_POR_PAGINA_MAX)

    def test_por_pagina_zero_ou_negativo_vira_pelo_menos_1(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        fake_conn = _FakeConn()
        with patch("athena_bridge._db_sync", return_value=fake_conn):
            r = self.client.get("/api/produtos?por_pagina=-5", headers=headers)
        self.assertEqual(r.get_json()["por_pagina"], 1)


class TestProdutosConexaoNaoVaza(unittest.TestCase):
    """_db_sync()/_conn_sync() sem try/finally deixava a conexao psycopg2
    aberta toda vez que uma excecao estourava no meio da query — o driver
    so' fechava via GC, ate o max_connections do Postgres estourar."""

    def setUp(self):
        self._env = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env.start()
        self.client = _app()

    def tearDown(self):
        self._env.stop()

    def test_excecao_no_meio_da_query_ainda_fecha_conexao(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        cursor = _FakeCursor()
        cursor.execute = MagicMock(side_effect=RuntimeError("SQL explodiu"))
        fake_conn = _FakeConn(cursor)
        with patch("athena_bridge._db_sync", return_value=fake_conn):
            r = self.client.get("/api/produtos", headers=headers)
        self.assertEqual(r.status_code, 200)  # listar_produtos captura e devolve {"erro":...}
        self.assertTrue(fake_conn.closed, "conexao deveria ter sido fechada mesmo com excecao")


class TestEditarProdutoValidacaoDeTipo(unittest.TestCase):
    """editar_produto aceitava qualquer valor cru pro UPDATE — um
    preco_custo="abc" so' estourava la' na frente como excecao generica do
    driver do Postgres."""

    def setUp(self):
        self._env = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env.start()
        self.client = _app()

    def tearDown(self):
        self._env.stop()

    def test_preco_custo_nao_numerico_rejeita_400(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.put("/api/produtos/X1", json={"preco_custo": "abc"}, headers=headers)
        self.assertEqual(r.status_code, 400)
        self.assertIn("preco_custo", r.get_json()["error"])

    def test_marca_id_nao_numerico_rejeita_400(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        r = self.client.put("/api/produtos/X1", json={"marca_id": "abc"}, headers=headers)
        self.assertEqual(r.status_code, 400)

    def test_imagem_url_esta_na_whitelist_de_campos(self):
        # upload de imagem so' funciona se o backend aceitar o campo
        # imagem_url no PUT generico — antes nao estava na lista de colunas.
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        fake_conn = _FakeConn()
        with patch("athena_bridge._db_sync", return_value=fake_conn), \
             patch("core.seguranca.auditar_alteracao"):
            r = self.client.put("/api/produtos/X1", json={"imagem_url": "/api/documentos/42"}, headers=headers)
        self.assertEqual(r.status_code, 200)
        sql_executada = " ".join(q[0] for q in fake_conn._cursor.queries)
        self.assertIn("imagem_url", sql_executada)


class TestDocumentosUploadMimeWhitelist(unittest.TestCase):
    """mime_type vem cru do Content-Type que o cliente manda — sem
    whitelist, um upload de .html/.svg com Content-Type manipulado, servido
    depois inline, executava no contexto de origem do app (XSS armazenado)."""

    def test_upload_recusa_mime_fora_da_whitelist(self):
        from core.documentos import upload
        resultado = upload(b"<script>alert(1)</script>", "malicioso.html",
                            entidade_tipo="produto", mime_type="text/html")
        self.assertIn("error", resultado)

    def test_upload_aceita_imagem(self):
        from core.documentos import upload
        with patch("core.documentos.run_async", return_value={"id": 1, "nome_original": "foto.png"}):
            resultado = upload(b"fake-png-bytes", "foto.png",
                                entidade_tipo="produto", mime_type="image/png")
        self.assertNotIn("error", resultado)

    def test_upload_aceita_video_para_midia_de_loja(self):
        # core/lojas_midia.py usa este upload() com tipo "video"
        from core.documentos import upload
        with patch("core.documentos.run_async", return_value={"id": 2}):
            resultado = upload(b"fake-mp4-bytes", "loja.mp4",
                                entidade_tipo="loja", mime_type="video/mp4")
        self.assertNotIn("error", resultado)

    def test_download_forca_anexo_para_mime_nao_seguro(self):
        from core.documentos import MIME_TYPES_INLINE_SEGUROS
        self.assertNotIn("text/html", MIME_TYPES_INLINE_SEGUROS)
        self.assertNotIn("image/svg+xml", MIME_TYPES_INLINE_SEGUROS)
        self.assertIn("image/png", MIME_TYPES_INLINE_SEGUROS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
