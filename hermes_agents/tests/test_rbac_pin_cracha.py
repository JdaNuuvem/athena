"""Testes de integracao — PIN/cracha para usuarios do RBAC principal (fora
do PDV), usado para autorizar acoes sensiveis (ex: alcada do financeiro) sem
precisar trocar de sessao. Mesmo padrao ja validado no PDV."""
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

import core.rbac as rbac


class TestDefinirPin(unittest.TestCase):
    def test_pin_invalido_letras_rejeitado(self):
        r = rbac.definir_pin(1, "abcd")
        self.assertIn("error", r)

    def test_pin_curto_rejeitado(self):
        r = rbac.definir_pin(1, "123")
        self.assertIn("error", r)

    def test_pin_valido_aceito(self):
        with patch("core.rbac.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetchrow.return_value = {"id": 1}
            mock_get_db.return_value = db
            r = rbac.definir_pin(1, "1234")
        self.assertTrue(r.get("ok"))


class TestVerificarPinUsuario(unittest.TestCase):
    def test_pin_correto_com_permissao_autoriza(self):
        salt, h = rbac._hash_secreto("1234")
        with patch("core.rbac.get_db") as mock_get_db, \
             patch("core.rbac.get_permissoes_por_usuario", return_value=["financeiro.aprovar"]):
            db = AsyncMock()
            db.fetchrow.return_value = {"id": 9, "nome": "Gerente Fulano", "pin_hash": f"{salt}:{h}"}
            mock_get_db.return_value = db
            r = rbac.verificar_pin_usuario(9, "1234", "financeiro.aprovar")
        self.assertTrue(r.get("ok"))
        self.assertEqual(r["nome"], "Gerente Fulano")

    def test_pin_incorreto_nega(self):
        salt, h = rbac._hash_secreto("1234")
        with patch("core.rbac.get_db") as mock_get_db, \
             patch("core.rbac._pin_bloqueado", return_value=False), \
             patch("core.rbac._registrar_tentativa_pin"):
            db = AsyncMock()
            db.fetchrow.return_value = {"id": 9, "nome": "Gerente Fulano", "pin_hash": f"{salt}:{h}"}
            mock_get_db.return_value = db
            r = rbac.verificar_pin_usuario(9, "0000", "financeiro.aprovar")
        self.assertIn("error", r)

    def test_usuario_inexistente_devolve_erro_generico_igual_ao_pin_errado(self):
        """Nao pode diferenciar 'usuario nao existe' de 'PIN errado' — vira
        oraculo de enumeracao de usuario para quem tenta ids ao acaso."""
        with patch("core.rbac.get_db") as mock_get_db, \
             patch("core.rbac._pin_bloqueado", return_value=False), \
             patch("core.rbac._registrar_tentativa_pin"):
            db = AsyncMock()
            db.fetchrow.return_value = None
            mock_get_db.return_value = db
            r_inexistente = rbac.verificar_pin_usuario(999, "1234")
        salt, h = rbac._hash_secreto("1234")
        with patch("core.rbac.get_db") as mock_get_db, \
             patch("core.rbac._pin_bloqueado", return_value=False), \
             patch("core.rbac._registrar_tentativa_pin"):
            db = AsyncMock()
            db.fetchrow.return_value = {"id": 9, "nome": "X", "pin_hash": f"{salt}:{h}"}
            mock_get_db.return_value = db
            r_pin_errado = rbac.verificar_pin_usuario(9, "0000")
        self.assertEqual(r_inexistente["error"], r_pin_errado["error"])

    def test_usuario_bloqueado_nega_mesmo_com_pin_correto(self):
        salt, h = rbac._hash_secreto("1234")
        with patch("core.rbac.get_db") as mock_get_db, \
             patch("core.rbac._pin_bloqueado", return_value=True):
            db = AsyncMock()
            db.fetchrow.return_value = {"id": 9, "nome": "X", "pin_hash": f"{salt}:{h}"}
            mock_get_db.return_value = db
            r = rbac.verificar_pin_usuario(9, "1234")
        self.assertIn("error", r)

    def test_tentativas_erradas_repetidas_bloqueiam_usuario(self):
        """Sem esse limite, /api/rbac/autorizar seria um oraculo de forca
        bruta contra o PIN (so' 10 mil combinacoes possiveis em 4 digitos)."""
        with patch("core.rbac.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetchrow.return_value = {"tentativas": rbac._PIN_MAX_TENTATIVAS - 1}
            mock_get_db.return_value = db
            rbac._registrar_tentativa_pin(9, sucesso=False)
        args = db.execute.call_args[0]
        self.assertIn("INTERVAL", args[0])

    def test_pin_correto_sem_permissao_nega(self):
        salt, h = rbac._hash_secreto("1234")
        with patch("core.rbac.get_db") as mock_get_db, \
             patch("core.rbac.get_permissoes_por_usuario", return_value=["pdv.operar"]):
            db = AsyncMock()
            db.fetchrow.return_value = {"id": 9, "nome": "Operador Comum", "pin_hash": f"{salt}:{h}"}
            mock_get_db.return_value = db
            r = rbac.verificar_pin_usuario(9, "1234", "financeiro.aprovar")
        self.assertIn("error", r)


class TestVerificarCodigoBarrasUsuario(unittest.TestCase):
    def test_codigo_identifica_automaticamente_quem_tem_a_permissao(self):
        salt, h = rbac._hash_secreto("ABCD1234")
        with patch("core.rbac.get_db") as mock_get_db, \
             patch("core.rbac.get_permissoes_por_usuario", return_value=["financeiro.aprovar"]):
            db = AsyncMock()
            db.fetch.return_value = [{"id": 9, "nome": "Gerente Fulano", "codigo_barras_hash": f"{salt}:{h}"}]
            mock_get_db.return_value = db
            r = rbac.verificar_codigo_barras_usuario("ABCD1234", "financeiro.aprovar")
        self.assertTrue(r.get("ok"))
        self.assertEqual(r["id"], 9)

    def test_codigo_nao_reconhecido_nega(self):
        with patch("core.rbac.get_db") as mock_get_db:
            db = AsyncMock()
            db.fetch.return_value = []
            mock_get_db.return_value = db
            r = rbac.verificar_codigo_barras_usuario("XXXX", "financeiro.aprovar")
        self.assertIn("error", r)


class TestAutorizarComPermissao(unittest.TestCase):
    def test_sem_pin_e_sem_codigo_retorna_erro(self):
        r = rbac.autorizar_com_permissao("financeiro.aprovar")
        self.assertIn("error", r)

    def test_codigo_de_barras_tem_prioridade_sobre_pin(self):
        with patch("core.rbac.verificar_codigo_barras_usuario", return_value={"ok": True, "id": 5, "nome": "X"}) as mock_cb, \
             patch("core.rbac.verificar_pin_usuario") as mock_pin:
            r = rbac.autorizar_com_permissao("financeiro.aprovar", usuario_pin_id=9, pin="1234", codigo_barras="ABC")
        mock_cb.assert_called_once()
        mock_pin.assert_not_called()
        self.assertTrue(r.get("ok"))


class TestListUsuariosNaoVazaSegredos(unittest.TestCase):
    """GET /api/rbac/usuarios devolvia password_hash de todo mundo sem
    nenhuma checagem de permissao — mesma classe de bug ja corrigida em
    cadastros/usuarios. list_usuarios() nunca deve devolver password_hash,
    pin_hash nem codigo_barras_hash."""

    def test_list_usuarios_remove_campos_sensiveis(self):
        with patch("core.rbac._list", return_value=[
            {"id": 1, "nome": "Admin", "email": "a@x.com", "password_hash": "s:h", "pin_hash": "s:h", "codigo_barras_hash": "s:h"},
        ]):
            resultado = rbac.list_usuarios()
        self.assertNotIn("password_hash", resultado[0])
        self.assertNotIn("pin_hash", resultado[0])
        self.assertNotIn("codigo_barras_hash", resultado[0])
        self.assertEqual(resultado[0]["nome"], "Admin")

    def test_rota_get_usuarios_exige_permissao(self):
        from flask import Flask
        from routes.rbac import rbac_bp
        env_patch = patch.dict(os.environ, {"ATHENA_TOKEN": _TEST_TOKEN})
        env_patch.start()
        try:
            app = Flask(__name__)
            app.config["TESTING"] = True
            app.register_blueprint(rbac_bp)
            client = app.test_client()
            token = rbac.gerar_token_sessao(7, "op@x.com", "Sem Papel")
            headers = {"Authorization": f"Bearer {token}"}
            with patch("core.rbac.get_permissoes_por_usuario", return_value=[]):
                r = client.get("/api/rbac/usuarios", headers=headers)
            self.assertEqual(r.status_code, 403)
        finally:
            env_patch.stop()


if __name__ == "__main__":
    unittest.main(verbosity=2)
