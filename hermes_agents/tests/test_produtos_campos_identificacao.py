"""POST/PUT /api/produtos aceitam os novos campos de identificacao da Fase 1
do PIM Core, exigem permissao granular (produtos.criar/produtos.editar) em
vez de so' 'esta logado', e a auditoria passa a registrar o usuario real."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

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

# editar_produto() usa _db_sync() -> psycopg2.connect() (sincrono, fora do
# pool asyncpg mockado acima) — precisa de mock proprio, senao tenta abrir
# conexao real e cai em 500. Sem autospec (diferente de test_all_endpoints.py):
# se este arquivo rodar depois de test_all_endpoints.py na mesma sessao de
# pytest, psycopg2.connect ja' foi trocado por um MagicMock (o patcher de la'
# nunca da' stop) e autospec=True quebra tentando espelhar um Mock.
_psycopg_patcher = patch("psycopg2.connect")
_psycopg_patcher.start()

# athena_bridge.API_TOKEN e' lido de os.environ["ATHENA_TOKEN"] uma unica vez,
# no import do modulo (nao a cada request) — por isso precisa estar setado
# ANTES do import abaixo, e nao so' via patch.dict no setUp de cada teste
# (mesmo padrao ja usado em test_all_endpoints.py). Sem isso, o bypass de
# token master fica sempre stale/vazio e toda request com _TEST_TOKEN cai
# em 401 no before_request antes de chegar no RBAC granular.
os.environ.setdefault("ATHENA_TOKEN", _TEST_TOKEN)

import athena_bridge
import core.rbac as rbac


def _app():
    athena_bridge.app.config["TESTING"] = True
    return athena_bridge.app.test_client()


class TestCriarProdutoComNovosCampos(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env.start()
        self.client = _app()

    def tearDown(self):
        self._env.stop()

    def test_criar_sem_permissao_produtos_criar_nega(self):
        token = rbac.gerar_token_sessao(1, "op@x.com", "Estoquista")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["produtos.ver"]), \
             patch("core.catalogo.criar") as mock_criar:
            r = self.client.post("/api/produtos", json={"sku": "X1", "descricao": "Produto X"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_criar.assert_not_called()

    def test_criar_com_novos_campos_passa_pro_catalogo(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        payload = {
            "sku": "X1", "descricao": "Produto X",
            "classificacao": "variavel", "nome_reduzido": "Prod X",
            "nome_impressao": "PRODUTO X", "codigo_interno": "INT-001",
            "codigo_erp": "ERP-001", "ex_tipi": "01", "modelo": "M1",
            "linha": "Linha A", "colecao": "Verao 2026",
            "marca_id": 5, "fabricante_id": 7, "categoria_id_norm": 2,
        }
        with patch("core.catalogo.criar", return_value={"id": 1, **payload}) as mock_criar, \
             patch("core.seguranca.auditar_alteracao") as mock_audit:
            r = self.client.post("/api/produtos", json=payload, headers=headers)
        self.assertEqual(r.status_code, 201)
        campos_enviados = mock_criar.call_args.args[0]
        for campo in ("classificacao", "nome_reduzido", "nome_impressao", "codigo_interno",
                      "codigo_erp", "ex_tipi", "modelo", "linha", "colecao",
                      "marca_id", "fabricante_id", "categoria_id_norm"):
            self.assertIn(campo, campos_enviados, f"campo {campo} nao foi repassado pro catalogo")
        mock_audit.assert_called_once()
        self.assertEqual(mock_audit.call_args.args[0], "criar")
        self.assertEqual(mock_audit.call_args.args[1], "produtos")


class TestEditarProdutoComNovosCampos(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env.start()
        self.client = _app()

    def tearDown(self):
        self._env.stop()

    def test_editar_sem_permissao_produtos_editar_nega(self):
        token = rbac.gerar_token_sessao(1, "op@x.com", "Estoquista")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["produtos.ver"]):
            r = self.client.put("/api/produtos/X1", json={"classificacao": "kit"}, headers=headers)
        self.assertEqual(r.status_code, 403)

    def test_editar_classificacao_e_auditado_com_dados_antes_depois(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.seguranca.auditar_alteracao") as mock_audit:
            r = self.client.put("/api/produtos/X1", json={"classificacao": "kit", "marca_id": 5}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_audit.assert_called_once()
        self.assertEqual(mock_audit.call_args.args[0], "editar")
        dados_depois = mock_audit.call_args.kwargs.get("dados_depois")
        self.assertEqual(dados_depois.get("classificacao"), "kit")


if __name__ == "__main__":
    unittest.main(verbosity=2)
