# Rocket.Chat — Infra + SSO (Fase 1+2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provisionar o Rocket.Chat + MongoDB no Coolify e fazer o Hermes atuar como Identity Provider OAuth2 para ele, para que um usuário logado no Hermes entre no Rocket.Chat sem logar de novo.

**Architecture:** Container Rocket.Chat + MongoDB (replica-set single-node) versionado como `docker-compose.yml` em `deploy/rocketchat/`. Novo blueprint Flask `hermes_agents/routes/oauth_provider.py` com 3 rotas (`/oauth/authorize`, `/oauth/token`, `/oauth/userinfo`) apoiado em `hermes_agents/core/oauth_provider.py`, que gera/valida `code` e `access_token` como JWTs curtos assinados com `pyjwt` — mesmo padrão de `core/rbac.py`, sem framework OAuth novo. O Rocket.Chat descobre o provider sozinho no boot via variáveis de ambiente `Accounts_OAuth_Custom_Hermes*` (mecanismo nativo dele).

**Tech Stack:** Flask (blueprint), `pyjwt` (já em `hermes_agents/requirements.txt`), `asyncpg` (consulta a `rbac_usuarios`), Docker Compose (Rocket.Chat `registry.rocket.chat/rocketchat/rocket.chat:8.6.1` + `mongodb/mongodb-community-server:8.2-ubi8`).

## Global Constraints

- Sem dependências Python novas — reaproveitar `pyjwt` já instalado (não usar Authlib nem outro framework OAuth).
- Segredos (`ATHENA_JWT_SECRET`, client_id/secret do OAuth) sempre via variável de ambiente, nunca hardcoded no código ou no `docker-compose.yml` versionado (usar `${VAR}` do shell).
- Seguir o padrão de testes já usado no projeto: `unittest.TestCase`, mock de `asyncpg.create_pool` antes de importar os módulos, `Flask.test_client()`. Rodar com `python -m pytest hermes_agents/tests/test_X.py -v` a partir da raiz do repo.
- Nomes de identificadores, mensagens e comentários em português, seguindo o resto do código de `hermes_agents/`.
- Escopo é só Fase 1+2 (infra + SSO). Não implementar embed no `/chat`, migração de histórico ou integração com tickets — isso é de fases futuras (ver spec).

---

### Task 1: Docker Compose do Rocket.Chat + MongoDB com Custom OAuth

**Files:**
- Create: `deploy/rocketchat/docker-compose.yml`
- Create: `deploy/rocketchat/.env.example`
- Create: `deploy/rocketchat/README.md`

**Interfaces:**
- Produces: variáveis de ambiente `ROCKETCHAT_ROOT_URL`, `ROCKETCHAT_OAUTH_CLIENT_ID`, `ROCKETCHAT_OAUTH_CLIENT_SECRET`, `HERMES_PUBLIC_URL` — consumidas manualmente ao subir o serviço no Coolify. Task 4 usa os mesmos nomes de `ROCKETCHAT_OAUTH_CLIENT_ID`/`ROCKETCHAT_OAUTH_CLIENT_SECRET`/`HERMES_PUBLIC_URL` do lado do Flask.

- [ ] **Step 1: Criar o `docker-compose.yml`**

```yaml
# deploy/rocketchat/docker-compose.yml
services:
  rocketchat:
    image: registry.rocket.chat/rocketchat/rocket.chat:8.6.1
    container_name: rocketchat
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      ROOT_URL: "${ROCKETCHAT_ROOT_URL}"
      PORT: "3000"
      DEPLOY_METHOD: "docker"
      MONGO_URL: "mongodb://mongodb:27017/rocketchat?replicaSet=rs0"
      MONGO_OPLOG_URL: "mongodb://mongodb:27017/local?replicaSet=rs0"
      # Custom OAuth "Hermes" — o Rocket.Chat le essas variaveis no boot e
      # registra o provider sozinho (initCustomOAuthServices.ts), sem
      # precisar de nenhuma chamada a Admin API.
      Accounts_OAuth_Custom_Hermes: "true"
      Accounts_OAuth_Custom_Hermes_id: "${ROCKETCHAT_OAUTH_CLIENT_ID}"
      Accounts_OAuth_Custom_Hermes_secret: "${ROCKETCHAT_OAUTH_CLIENT_SECRET}"
      Accounts_OAuth_Custom_Hermes_url: "${HERMES_PUBLIC_URL}"
      Accounts_OAuth_Custom_Hermes_token_path: "/oauth/token"
      Accounts_OAuth_Custom_Hermes_identity_path: "/oauth/userinfo"
      Accounts_OAuth_Custom_Hermes_authorize_path: "/oauth/authorize"
      Accounts_OAuth_Custom_Hermes_scope: "openid"
      Accounts_OAuth_Custom_Hermes_login_style: "redirect"
      Accounts_OAuth_Custom_Hermes_key_field: "username"
      Accounts_OAuth_Custom_Hermes_username_field: "username"
      Accounts_OAuth_Custom_Hermes_email_field: "email"
      Accounts_OAuth_Custom_Hermes_name_field: "name"
      Accounts_OAuth_Custom_Hermes_merge_users: "true"
      Accounts_OAuth_Custom_Hermes_show_button: "true"
    volumes:
      - rocketchat_uploads:/app/uploads
    depends_on:
      mongodb:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/api/v1/info"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 120s

  mongodb:
    image: mongodb/mongodb-community-server:8.2-ubi8
    container_name: rocketchat_mongodb
    restart: unless-stopped
    command: ["--replSet", "rs0", "--oplogSize", "128"]
    volumes:
      - rocketchat_mongodb:/data/db
    healthcheck:
      test: >
        mongosh --quiet --eval "
          try {
            var status = rs.status();
            if (status.ok === 1) quit(0);
            else quit(1);
          } catch(e) {
            rs.initiate({ _id: 'rs0', members: [{ _id: 0, host: 'mongodb:27017' }] });
            quit(1);
          }
        "
      interval: 10s
      timeout: 10s
      retries: 30
      start_period: 30s

volumes:
  rocketchat_uploads:
  rocketchat_mongodb:
```

- [ ] **Step 2: Criar `.env.example` documentando as variáveis exigidas**

```bash
# deploy/rocketchat/.env.example
# URL publica do Rocket.Chat (dominio configurado no Coolify)
ROCKETCHAT_ROOT_URL=https://chat.athena.zoikom.site

# URL publica do backend Flask do Hermes (onde ficam /oauth/authorize, /oauth/token, /oauth/userinfo)
HERMES_PUBLIC_URL=https://athena.zoikom.site

# Client OAuth2 representando este Rocket.Chat perante o Hermes.
# Gerar uma vez com: python -c "import secrets; print(secrets.token_urlsafe(32))"
ROCKETCHAT_OAUTH_CLIENT_ID=
ROCKETCHAT_OAUTH_CLIENT_SECRET=
```

- [ ] **Step 3: Criar `README.md` com o passo a passo de deploy**

```markdown
# Deploy do Rocket.Chat no Coolify

## 1. Gerar credenciais do client OAuth

python -c "import secrets; print(secrets.token_urlsafe(32))"   # client id
python -c "import secrets; print(secrets.token_urlsafe(32))"   # client secret

## 2. Criar o recurso no Coolify

1. No Coolify, criar um novo recurso do tipo "Docker Compose".
2. Colar o conteudo de `docker-compose.yml` deste diretorio.
3. Configurar as variaveis de ambiente do recurso com os valores de `.env.example`
   (ROCKETCHAT_ROOT_URL, HERMES_PUBLIC_URL, ROCKETCHAT_OAUTH_CLIENT_ID, ROCKETCHAT_OAUTH_CLIENT_SECRET).
4. Configurar o dominio do recurso (subdominio proposto: chat.athena.zoikom.site),
   apontando para a porta 3000 do servico `rocketchat`.

## 3. Configurar o mesmo client no lado do Hermes

No ambiente do backend Flask (mesmo Coolify, servico do Hermes), definir:

- `ROCKETCHAT_OAUTH_CLIENT_ID` — mesmo valor gerado no passo 1
- `ROCKETCHAT_OAUTH_CLIENT_SECRET` — mesmo valor gerado no passo 1
- `ROCKETCHAT_OAUTH_REDIRECT_URI` — `https://chat.athena.zoikom.site/_oauth/hermes`
  (Rocket.Chat gera esse callback automaticamente como `<ROOT_URL>/_oauth/<nome-do-provider-em-minusculo>`)
- `HERMES_PUBLIC_URL` — mesmo valor de `.env.example`

## 4. Smoke test

1. Subir o recurso e aguardar o healthcheck do `rocketchat` ficar verde (pode levar ~2min no primeiro boot).
2. Acessar a URL publica do Rocket.Chat — deve aparecer a tela de setup wizard inicial (criar conta admin).
3. Completar o wizard criando um usuario admin local (independente do SSO — necessario para a conta root existir).
4. Na tela de login, deve aparecer um botao "Hermes" (ou o nome configurado) alem do login local — confirma que
   o Custom OAuth foi lido a partir das variaveis de ambiente.
5. O teste do fluxo de login via SSO de ponta a ponta depende da Task 3 (rotas `/oauth/*`) estarem no ar —
   ver Task 5 deste plano.
```

- [ ] **Step 4: Commit**

```bash
git add deploy/rocketchat/docker-compose.yml deploy/rocketchat/.env.example deploy/rocketchat/README.md
git commit -m "chore: docker-compose do Rocket.Chat + MongoDB com Custom OAuth Hermes"
```

---

### Task 2: `core/oauth_provider.py` — geração/validação de `code` e `access_token`

**Files:**
- Create: `hermes_agents/core/oauth_provider.py`
- Test: `hermes_agents/tests/test_oauth_provider_core.py`

**Interfaces:**
- Consumes: `core.rbac._jwt_secret() -> str`, `core.rbac.JWT_ALGORITHM: str` (já existem em `hermes_agents/core/rbac.py:20-29,17`).
- Produces (usado pela Task 3):
  - `gerar_authorization_code(user_id: int, client_id: str, redirect_uri: str) -> str`
  - `validar_authorization_code(code: str, client_id: str, redirect_uri: str) -> int | None`
  - `gerar_access_token(user_id: int) -> str`
  - `validar_access_token(token: str) -> int | None`

- [ ] **Step 1: Escrever os testes que falham**

```python
# hermes_agents/tests/test_oauth_provider_core.py
"""Testes do core do OAuth provider — geracao/validacao de authorization
code e access token como JWTs curtos, sem estado em memoria/banco."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ATHENA_JWT_SECRET", "test-secret-32-bytes-long-enough!!")

from core.oauth_provider import (
    gerar_authorization_code, validar_authorization_code,
    gerar_access_token, validar_access_token,
)

_CLIENT_ID = "rocketchat"
_REDIRECT_URI = "https://chat.exemplo.com/_oauth/hermes"


class TestAuthorizationCode(unittest.TestCase):
    def test_code_valido_retorna_user_id(self):
        code = gerar_authorization_code(42, _CLIENT_ID, _REDIRECT_URI)
        self.assertEqual(validar_authorization_code(code, _CLIENT_ID, _REDIRECT_URI), 42)

    def test_code_com_client_id_errado_rejeita(self):
        code = gerar_authorization_code(42, _CLIENT_ID, _REDIRECT_URI)
        self.assertIsNone(validar_authorization_code(code, "outro-client", _REDIRECT_URI))

    def test_code_com_redirect_uri_errado_rejeita(self):
        code = gerar_authorization_code(42, _CLIENT_ID, _REDIRECT_URI)
        self.assertIsNone(validar_authorization_code(code, _CLIENT_ID, "https://outro.com/cb"))

    def test_code_vazio_rejeita(self):
        self.assertIsNone(validar_authorization_code("", _CLIENT_ID, _REDIRECT_URI))

    def test_code_expirado_rejeita(self):
        import core.oauth_provider as op
        original = op.CODE_EXPIRACAO_SEGUNDOS
        op.CODE_EXPIRACAO_SEGUNDOS = -1
        try:
            code = gerar_authorization_code(42, _CLIENT_ID, _REDIRECT_URI)
        finally:
            op.CODE_EXPIRACAO_SEGUNDOS = original
        self.assertIsNone(validar_authorization_code(code, _CLIENT_ID, _REDIRECT_URI))

    def test_access_token_nao_e_aceito_como_code(self):
        token = gerar_access_token(42)
        self.assertIsNone(validar_authorization_code(token, _CLIENT_ID, _REDIRECT_URI))


class TestAccessToken(unittest.TestCase):
    def test_token_valido_retorna_user_id(self):
        token = gerar_access_token(42)
        self.assertEqual(validar_access_token(token), 42)

    def test_token_invalido_rejeita(self):
        self.assertIsNone(validar_access_token("token-invalido"))

    def test_token_vazio_rejeita(self):
        self.assertIsNone(validar_access_token(""))

    def test_authorization_code_nao_e_aceito_como_access_token(self):
        code = gerar_authorization_code(42, _CLIENT_ID, _REDIRECT_URI)
        self.assertIsNone(validar_access_token(code))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar os testes e confirmar que falham por `ModuleNotFoundError`**

Run: `python -m pytest hermes_agents/tests/test_oauth_provider_core.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.oauth_provider'`

- [ ] **Step 3: Implementar `core/oauth_provider.py`**

```python
# hermes_agents/core/oauth_provider.py
"""OAuth2 provider — o Hermes atua como Identity Provider para clientes
externos (Rocket.Chat). Mesmo padrao de core/rbac.py: JWT assinado com
pyjwt, sem framework OAuth novo.

`code` e `access_token` sao os dois JWTs curtos do fluxo Authorization
Code — cada um carrega um claim `typ` (`oauth_code` / `oauth_access`) para
que um nao possa ser usado no lugar do outro mesmo sendo ambos JWTs
assinados com o mesmo secret."""
from datetime import datetime, timedelta, timezone
import jwt as _jwt
from core.rbac import _jwt_secret, JWT_ALGORITHM

AGENT = "OAuth Provider"

CODE_EXPIRACAO_SEGUNDOS = 60
ACCESS_TOKEN_EXPIRACAO_SEGUNDOS = 3600


def gerar_authorization_code(user_id: int, client_id: str, redirect_uri: str) -> str:
    payload = {
        "typ": "oauth_code",
        "user_id": user_id,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=CODE_EXPIRACAO_SEGUNDOS),
        "iat": datetime.now(timezone.utc),
    }
    return _jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def validar_authorization_code(code: str, client_id: str, redirect_uri: str) -> "int | None":
    if not code:
        return None
    try:
        payload = _jwt.decode(code, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except Exception:
        return None
    if payload.get("typ") != "oauth_code":
        return None
    if payload.get("client_id") != client_id or payload.get("redirect_uri") != redirect_uri:
        return None
    return payload.get("user_id")


def gerar_access_token(user_id: int) -> str:
    payload = {
        "typ": "oauth_access",
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=ACCESS_TOKEN_EXPIRACAO_SEGUNDOS),
        "iat": datetime.now(timezone.utc),
    }
    return _jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def validar_access_token(token: str) -> "int | None":
    if not token:
        return None
    try:
        payload = _jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except Exception:
        return None
    if payload.get("typ") != "oauth_access":
        return None
    return payload.get("user_id")
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `python -m pytest hermes_agents/tests/test_oauth_provider_core.py -v`
Expected: PASS — 9 passed

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/core/oauth_provider.py hermes_agents/tests/test_oauth_provider_core.py
git commit -m "feat: core do OAuth provider - code e access token como JWT curto"
```

---

### Task 3: Blueprint Flask `/oauth/authorize`, `/oauth/token`, `/oauth/userinfo`

**Files:**
- Create: `hermes_agents/routes/oauth_provider.py`
- Test: `hermes_agents/tests/test_oauth_provider_rotas.py`

**Interfaces:**
- Consumes:
  - `core.oauth_provider.gerar_authorization_code/validar_authorization_code/gerar_access_token/validar_access_token` (Task 2)
  - `core.rbac.verificar_token_sessao(token: str) -> dict | None` (já existe, `hermes_agents/core/rbac.py:40-47`)
  - `core.get_db() -> asyncpg.Pool` e `core.run_async(coro) -> Any` (já existem, `hermes_agents/core/__init__.py:102,123`)
- Produces: `oauth_provider_bp` (Flask `Blueprint`, `url_prefix="/oauth"`) — consumido pela Task 4 em `athena_bridge.py`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# hermes_agents/tests/test_oauth_provider_rotas.py
"""Testes de integracao das rotas /oauth/* — mesmo padrao de
test_atendimento_seguranca.py: mocka asyncpg.create_pool antes de
importar os modulos, Flask test_client, tokens gerados via core.rbac."""
import sys, os, unittest
from unittest.mock import patch, AsyncMock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TEST_SECRET = "test-secret-32-bytes-long-enough!!"
os.environ.setdefault("ATHENA_JWT_SECRET", _TEST_SECRET)

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
from routes.oauth_provider import oauth_provider_bp
import core.rbac as rbac

_CLIENT_ID = "client-de-teste"
_CLIENT_SECRET = "segredo-de-teste"
_REDIRECT_URI = "https://chat.exemplo.com/_oauth/hermes"

_ENV_OAUTH = {
    "ROCKETCHAT_OAUTH_CLIENT_ID": _CLIENT_ID,
    "ROCKETCHAT_OAUTH_CLIENT_SECRET": _CLIENT_SECRET,
    "ROCKETCHAT_OAUTH_REDIRECT_URI": _REDIRECT_URI,
    "HERMES_LOGIN_URL": "https://athena.exemplo.com/login",
}


def _app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(oauth_provider_bp)
    return app.test_client()


class TestAuthorize(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, _ENV_OAUTH)
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_sem_sessao_redireciona_para_login_do_hermes(self):
        r = self.client.get(
            "/oauth/authorize",
            query_string={"response_type": "code", "client_id": _CLIENT_ID, "redirect_uri": _REDIRECT_URI},
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers["Location"], "https://athena.exemplo.com/login")

    def test_com_sessao_valida_redireciona_com_code(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador")
        r = self.client.get(
            "/oauth/authorize",
            query_string={"response_type": "code", "client_id": _CLIENT_ID, "redirect_uri": _REDIRECT_URI, "state": "xyz"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(r.status_code, 302)
        location = r.headers["Location"]
        self.assertTrue(location.startswith(_REDIRECT_URI))
        self.assertIn("code=", location)
        self.assertIn("state=xyz", location)

    def test_client_id_errado_rejeita(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador")
        r = self.client.get(
            "/oauth/authorize",
            query_string={"response_type": "code", "client_id": "outro", "redirect_uri": _REDIRECT_URI},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(r.status_code, 400)

    def test_redirect_uri_errado_rejeita(self):
        token = rbac.gerar_token_sessao(7, "op@x.com", "Operador")
        r = self.client.get(
            "/oauth/authorize",
            query_string={"response_type": "code", "client_id": _CLIENT_ID, "redirect_uri": "https://outro.com/cb"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(r.status_code, 400)

    def test_response_type_invalido_rejeita(self):
        r = self.client.get(
            "/oauth/authorize",
            query_string={"response_type": "token", "client_id": _CLIENT_ID, "redirect_uri": _REDIRECT_URI},
        )
        self.assertEqual(r.status_code, 400)


class TestToken(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, _ENV_OAUTH)
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def _obter_code(self, user_id=7):
        from core.oauth_provider import gerar_authorization_code
        return gerar_authorization_code(user_id, _CLIENT_ID, _REDIRECT_URI)

    def test_troca_code_valido_por_access_token(self):
        code = self._obter_code()
        r = self.client.post("/oauth/token", data={
            "client_id": _CLIENT_ID, "client_secret": _CLIENT_SECRET,
            "code": code, "redirect_uri": _REDIRECT_URI,
        })
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertIn("access_token", body)
        self.assertEqual(body["token_type"], "Bearer")

    def test_client_secret_errado_rejeita(self):
        code = self._obter_code()
        r = self.client.post("/oauth/token", data={
            "client_id": _CLIENT_ID, "client_secret": "errado",
            "code": code, "redirect_uri": _REDIRECT_URI,
        })
        self.assertEqual(r.status_code, 401)

    def test_code_invalido_rejeita(self):
        r = self.client.post("/oauth/token", data={
            "client_id": _CLIENT_ID, "client_secret": _CLIENT_SECRET,
            "code": "code-invalido", "redirect_uri": _REDIRECT_URI,
        })
        self.assertEqual(r.status_code, 400)


class TestUserinfo(unittest.TestCase):
    def setUp(self):
        self._env_patch = patch.dict(os.environ, _ENV_OAUTH)
        self._env_patch.start()
        self.client = _app()

    def tearDown(self):
        self._env_patch.stop()

    def test_token_valido_retorna_dados_do_usuario(self):
        from core.oauth_provider import gerar_access_token
        token = gerar_access_token(7)
        usuario = {"id": 7, "nome": "Fulano da Silva", "email": "fulano@x.com"}
        with patch("routes.oauth_provider._buscar_usuario", AsyncMock(return_value=usuario)):
            r = self.client.get("/oauth/userinfo", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertEqual(body["id"], 7)
        self.assertEqual(body["email"], "fulano@x.com")
        self.assertEqual(body["username"], "fulano")
        self.assertEqual(body["name"], "Fulano da Silva")

    def test_token_invalido_rejeita(self):
        r = self.client.get("/oauth/userinfo", headers={"Authorization": "Bearer invalido"})
        self.assertEqual(r.status_code, 401)

    def test_usuario_inativo_ou_removido_rejeita(self):
        from core.oauth_provider import gerar_access_token
        token = gerar_access_token(999)
        with patch("routes.oauth_provider._buscar_usuario", AsyncMock(return_value=None)):
            r = self.client.get("/oauth/userinfo", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(r.status_code, 401)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar os testes e confirmar que falham por `ModuleNotFoundError`**

Run: `python -m pytest hermes_agents/tests/test_oauth_provider_rotas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'routes.oauth_provider'`

- [ ] **Step 3: Implementar `routes/oauth_provider.py`**

```python
# hermes_agents/routes/oauth_provider.py
"""Rotas do OAuth2 provider (Authorization Code flow) que fazem o Hermes
atuar como Identity Provider para clientes externos — hoje so' o
Rocket.Chat. Ver hermes_agents/core/oauth_provider.py para a geracao/
validacao de code e access_token."""
import os
from urllib.parse import quote
from flask import Blueprint, request, jsonify, redirect
from core import get_db, run_async
from core.rbac import verificar_token_sessao
from core.oauth_provider import (
    gerar_authorization_code, validar_authorization_code,
    gerar_access_token, validar_access_token,
)

oauth_provider_bp = Blueprint("oauth_provider", __name__, url_prefix="/oauth")


def _client_id() -> str:
    return os.environ.get("ROCKETCHAT_OAUTH_CLIENT_ID", "")


def _client_secret() -> str:
    return os.environ.get("ROCKETCHAT_OAUTH_CLIENT_SECRET", "")


def _redirect_uri_esperado() -> str:
    return os.environ.get("ROCKETCHAT_OAUTH_REDIRECT_URI", "")


def _hermes_login_url() -> str:
    return os.environ.get("HERMES_LOGIN_URL", "/login")


def _token_da_request() -> str:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[len("Bearer "):]
    return request.cookies.get("auth_token", "")


@oauth_provider_bp.route("/authorize", methods=["GET"])
def authorize():
    if request.args.get("response_type") != "code":
        return jsonify({"error": "unsupported_response_type"}), 400

    client_id = request.args.get("client_id", "")
    redirect_uri = request.args.get("redirect_uri", "")
    if not _client_id() or client_id != _client_id():
        return jsonify({"error": "invalid_client"}), 400
    if not _redirect_uri_esperado() or redirect_uri != _redirect_uri_esperado():
        return jsonify({"error": "invalid_redirect_uri"}), 400

    payload = verificar_token_sessao(_token_da_request())
    if not payload or not payload.get("user_id"):
        return redirect(_hermes_login_url())

    code = gerar_authorization_code(payload["user_id"], client_id, redirect_uri)
    state = request.args.get("state", "")
    separador = "&" if "?" in redirect_uri else "?"
    destino = f"{redirect_uri}{separador}code={quote(code)}"
    if state:
        destino += f"&state={quote(state)}"
    return redirect(destino)


@oauth_provider_bp.route("/token", methods=["POST"])
def token():
    client_id = request.form.get("client_id", "")
    client_secret = request.form.get("client_secret", "")
    code = request.form.get("code", "")
    redirect_uri = request.form.get("redirect_uri", "")

    if not _client_id() or not _client_secret() or client_id != _client_id() or client_secret != _client_secret():
        return jsonify({"error": "invalid_client"}), 401

    user_id = validar_authorization_code(code, client_id, redirect_uri)
    if not user_id:
        return jsonify({"error": "invalid_grant"}), 400

    access_token = gerar_access_token(user_id)
    return jsonify({"access_token": access_token, "token_type": "Bearer", "expires_in": 3600})


async def _buscar_usuario(user_id: int):
    db = await get_db()
    row = await db.fetchrow(
        "SELECT id, nome, email FROM rbac_usuarios WHERE id = $1 AND ativo = TRUE", user_id
    )
    return dict(row) if row else None


@oauth_provider_bp.route("/userinfo", methods=["GET"])
def userinfo():
    user_id = validar_access_token(_token_da_request())
    if not user_id:
        return jsonify({"error": "invalid_token"}), 401

    usuario = run_async(_buscar_usuario(user_id))
    if not usuario:
        return jsonify({"error": "invalid_token"}), 401

    email = usuario.get("email", "")
    username = email.split("@")[0] if email else f"usuario{usuario['id']}"
    return jsonify({
        "id": usuario["id"],
        "username": username,
        "email": email,
        "name": usuario.get("nome") or username,
    })
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `python -m pytest hermes_agents/tests/test_oauth_provider_rotas.py -v`
Expected: PASS — 11 passed

- [ ] **Step 5: Commit**

```bash
git add hermes_agents/routes/oauth_provider.py hermes_agents/tests/test_oauth_provider_rotas.py
git commit -m "feat: rotas /oauth/authorize, /oauth/token, /oauth/userinfo"
```

---

### Task 4: Registrar o blueprint no app principal

**Files:**
- Modify: `hermes_agents/athena_bridge.py:284` (logo após `app.register_blueprint(chat_bp)`)

**Interfaces:**
- Consumes: `oauth_provider_bp` de `routes.oauth_provider` (Task 3).

- [ ] **Step 1: Adicionar o import e o registro do blueprint**

Editar `hermes_agents/athena_bridge.py`: localizar a linha `app.register_blueprint(chat_bp)` (linha 284) e adicionar logo abaixo:

```python
app.register_blueprint(oauth_provider_bp)
```

E localizar a linha `from routes.chat import chat_bp` (linha 248) para adicionar logo abaixo:

```python
from routes.oauth_provider import oauth_provider_bp
```

- [ ] **Step 2: Rodar a suíte completa de testes para garantir que nada quebrou**

Run: `python -m pytest hermes_agents/tests/ -v -k "oauth or atendimento or chat"`
Expected: PASS — todos os testes de oauth, atendimento e chat continuam passando

- [ ] **Step 3: Commit**

```bash
git add hermes_agents/athena_bridge.py
git commit -m "feat: registra blueprint oauth_provider no app principal"
```

---

### Task 5: Smoke test manual ponta a ponta

**Files:** nenhum arquivo — checklist de validação manual, não há o que automatizar sem o Rocket.Chat real rodando.

**Interfaces:**
- Consumes: Task 1 (Rocket.Chat no ar), Task 4 (rotas `/oauth/*` no ar em produção/staging).

- [ ] **Step 1: Configurar as variáveis de ambiente reais**

No ambiente do backend Flask (Coolify), definir `ROCKETCHAT_OAUTH_CLIENT_ID`, `ROCKETCHAT_OAUTH_CLIENT_SECRET` (mesmos valores usados no `docker-compose.yml` do Rocket.Chat), `ROCKETCHAT_OAUTH_REDIRECT_URI` (`https://<dominio-rocketchat>/_oauth/hermes`), `HERMES_PUBLIC_URL`, `HERMES_LOGIN_URL`.

- [ ] **Step 2: Validar o fluxo completo**

1. Fazer login normal no Hermes (obter `auth_token`).
2. Acessar a URL pública do Rocket.Chat, clicar no botão "Hermes" na tela de login.
3. Confirmar que é redirecionado para `/oauth/authorize` do Hermes e, como já está autenticado, é imediatamente redirecionado de volta para o Rocket.Chat com `code=...` na URL.
4. Confirmar que o Rocket.Chat completa o login sozinho (troca o `code` por `access_token` internamente) e mostra a tela principal do chat já autenticado.
5. Conferir no admin do Rocket.Chat (`Administração > Usuários`) que a conta foi criada com o `username`/`email`/`name` corretos vindos do `/oauth/userinfo`.
6. Deslogar do Hermes (invalidar o `auth_token`), acessar o Rocket.Chat em uma aba anônima e confirmar que `/oauth/authorize` redireciona para a tela de login do Hermes em vez de criar uma sessão.

- [ ] **Step 3: Documentar o resultado**

Anotar no `deploy/rocketchat/README.md` (seção "Smoke test") a data em que o fluxo foi validado com sucesso e qualquer ajuste de configuração que tenha sido necessário além do previsto neste plano.

---

## Self-Review

**Spec coverage:**
- Infra Rocket.Chat + MongoDB → Task 1.
- `/oauth/authorize`, `/oauth/token`, `/oauth/userinfo` → Tasks 2-3.
- Configuração do Custom OAuth sem tela manual → Task 1 (env vars nativas).
- Fluxo de dados completo (login automático) → Task 5 (smoke test).
- Erros (sessão expirada, client mal configurado) → cobertos nos testes da Task 3 (`test_sem_sessao_redireciona_para_login_do_hermes`, `test_client_secret_errado_rejeita`, `test_code_invalido_rejeita`).
- Itens "fora de escopo" do spec (embed, migração, integração com tickets, mapeamento de roles) → não têm task aqui, corretamente, pois pertencem a fases futuras.

**Placeholder scan:** nenhum "TBD"/"TODO"/"implementar depois" — todos os steps têm código completo.

**Type consistency:** `gerar_authorization_code`/`validar_authorization_code`/`gerar_access_token`/`validar_access_token` usados na Task 3 com a mesma assinatura definida na Task 2. `_buscar_usuario` (Task 3) é a mesma função mockada nos testes (`routes.oauth_provider._buscar_usuario`). `oauth_provider_bp` é o mesmo nome de `Blueprint` produzido na Task 3 e consumido na Task 4.
