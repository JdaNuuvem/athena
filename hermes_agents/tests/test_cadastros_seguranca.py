"""Testes de integracao — CRUD generico de cadastros (empresas, usuarios,
clientes, fornecedores, transportadoras, vendedores) antes nao checava
nenhuma permissao, e /api/cadastros/usuarios vazava senha_hash pelo GET."""
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

patcher = patch("asyncpg.create_pool", side_effect=_mp)
patcher.start()

from flask import Flask
from routes.cadastros import cadastros_bp
import core.cadastros as cadastros
import core.rbac as rbac


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(cadastros_bp)
    return app.test_client()


class TestCadastrosCRUDExigePermissao(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_criar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["pdv.operar"]), \
             patch("core.cadastros.create") as mock_create:
            r = self.client.post("/api/cadastros/usuarios", json={"nome": "X", "perfil": "admin"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_create.assert_not_called()

    def test_criar_com_permissao_libera(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["cadastros.criar"]), \
             patch("core.cadastros.create", return_value={"id": 1}) as mock_create:
            r = self.client.post("/api/cadastros/clientes", json={"nome": "Cliente X"}, headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_create.assert_called_once()

    def test_editar_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["cadastros.criar"]), \
             patch("core.cadastros.update") as mock_update:
            r = self.client.put("/api/cadastros/usuarios/1", json={"perfil": "admin"}, headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_update.assert_not_called()

    def test_excluir_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["cadastros.criar", "cadastros.editar"]), \
             patch("core.cadastros.delete") as mock_delete:
            r = self.client.delete("/api/cadastros/usuarios/1", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_delete.assert_not_called()

    def test_excluir_com_permissao_libera_e_audita(self):
        headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
        with patch("core.cadastros.get", return_value={"id": 1, "nome": "X"}), \
             patch("core.cadastros.delete", return_value={"success": True}) as mock_delete, \
             patch("core.seguranca.auditar_exclusao") as mock_audit:
            r = self.client.delete("/api/cadastros/usuarios/1", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_delete.assert_called_once()
        mock_audit.assert_called_once_with("cadastros", "usuarios", 1, {"id": 1, "nome": "X"})

    def test_listar_sem_permissao_nega(self):
        # Antes desse teste existir, GET /api/cadastros/<tabela> nao checava
        # nenhuma permissao — qualquer usuario autenticado (mesmo sem acesso
        # ao modulo Cadastros) conseguia listar clientes/fornecedores/usuarios.
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["pdv.operar"]), \
             patch("core.cadastros.list") as mock_list:
            r = self.client.get("/api/cadastros/clientes", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_list.assert_not_called()

    def test_listar_com_permissao_libera(self):
        token = rbac.gerar_token_sessao(9, "gerente@x.com", "Gerente")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["cadastros.ver"]), \
             patch("core.cadastros.list", return_value=[{"id": 1, "nome": "Cliente X"}]) as mock_list:
            r = self.client.get("/api/cadastros/clientes", headers=headers)
        self.assertEqual(r.status_code, 200)
        mock_list.assert_called_once()

    def test_obter_um_sem_permissao_nega(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador Loja")
        headers = {"Authorization": f"Bearer {token}"}
        with patch("core.rbac.get_permissoes_por_usuario", return_value=["pdv.operar"]), \
             patch("core.cadastros.get") as mock_get:
            r = self.client.get("/api/cadastros/clientes/1", headers=headers)
        self.assertEqual(r.status_code, 403)
        mock_get.assert_not_called()


class TestCadastrosUsuariosNaoVazaSenha(unittest.TestCase):
    """core.cadastros.get/list nunca devem devolver senha_hash da tabela
    usuarios, mesmo que a query subjacente use SELECT *."""

    def test_list_remove_senha_hash(self):
        with patch("core.cadastros._list", return_value=[
            {"id": 1, "nome": "A", "senha_hash": "segredo1"},
            {"id": 2, "nome": "B", "senha_hash": "segredo2"},
        ]):
            resultado = cadastros.list("usuarios")
        self.assertTrue(all("senha_hash" not in r for r in resultado))
        self.assertEqual([r["nome"] for r in resultado], ["A", "B"])

    def test_get_remove_senha_hash(self):
        with patch("core.cadastros._get", return_value={"id": 1, "nome": "A", "senha_hash": "segredo"}):
            resultado = cadastros.get("usuarios", 1)
        self.assertNotIn("senha_hash", resultado)
        self.assertEqual(resultado["nome"], "A")

    def test_outras_tabelas_nao_sao_afetadas(self):
        with patch("core.cadastros._get", return_value={"id": 1, "nome": "Cliente", "documento": "123"}):
            resultado = cadastros.get("clientes", 1)
        self.assertEqual(resultado, {"id": 1, "nome": "Cliente", "documento": "123"})

    def test_rota_get_usuarios_nao_expoe_senha_hash(self):
        env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        env_patch.start()
        try:
            client = _app()
            headers = {"Authorization": f"Bearer {_TEST_TOKEN}"}
            with patch("core.cadastros._list", return_value=[{"id": 1, "nome": "A", "senha_hash": "segredo"}]):
                r = client.get("/api/cadastros/usuarios", headers=headers)
            data = r.get_json()
            self.assertNotIn("senha_hash", data["data"][0])
        finally:
            env_patch.stop()


class TestCadastrosListaPaginada(unittest.TestCase):
    """list_paginado() — antes /api/cadastros/<tabela> so' tinha LIMIT 100
    fixo, sem offset/total/busca no servidor."""

    def test_retorna_metadados_de_paginacao(self):
        with patch("core.cadastros._list_pagina", return_value=[{"id": 1, "nome": "A"}]), \
             patch("core.cadastros._count", return_value=45):
            resultado = cadastros.list_paginado("clientes", pagina=2, por_pagina=20)
        self.assertEqual(resultado["total"], 45)
        self.assertEqual(resultado["pagina"], 2)
        self.assertEqual(resultado["por_pagina"], 20)
        self.assertEqual(resultado["total_paginas"], 3)  # ceil(45/20)
        self.assertEqual(resultado["data"], [{"id": 1, "nome": "A"}])

    def test_calcula_offset_pela_pagina(self):
        with patch("core.cadastros._list_pagina", return_value=[]) as mock_list, \
             patch("core.cadastros._count", return_value=0):
            cadastros.list_paginado("clientes", pagina=3, por_pagina=10)
        self.assertEqual(mock_list.call_args.kwargs["offset"], 20)
        self.assertEqual(mock_list.call_args.kwargs["limit"], 10)

    def test_repassa_busca_e_campos_buscaveis_da_tabela(self):
        with patch("core.cadastros._list_pagina", return_value=[]) as mock_list, \
             patch("core.cadastros._count", return_value=0):
            cadastros.list_paginado("clientes", pagina=1, busca="joao")
        self.assertEqual(mock_list.call_args.kwargs["busca"], "joao")
        self.assertIn("nome", mock_list.call_args.kwargs["campos_busca"])

    def test_remove_senha_hash_de_usuarios_tambem_paginado(self):
        with patch("core.cadastros._list_pagina", return_value=[{"id": 1, "nome": "A", "senha_hash": "x"}]), \
             patch("core.cadastros._count", return_value=1):
            resultado = cadastros.list_paginado("usuarios", pagina=1)
        self.assertNotIn("senha_hash", resultado["data"][0])

    def test_pagina_e_por_pagina_invalidos_nao_quebram(self):
        with patch("core.cadastros._list_pagina", return_value=[]) as mock_list, \
             patch("core.cadastros._count", return_value=0):
            resultado = cadastros.list_paginado("clientes", pagina=0, por_pagina=-5)
        self.assertEqual(resultado["pagina"], 1)
        self.assertEqual(mock_list.call_args.kwargs["offset"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
