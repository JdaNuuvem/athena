#!/usr/bin/env python3
"""
Testes de integração para Fase 0 + Fase 1 - Fundação de Acesso e Núcleo Multiloja.

ponytail: este teste importava routes.auth (USUARIOS/JWT_SECRET) — um
blueprint inteiro (login + /api/me proprios, com seu esquema de permissoes
"ver_lojas"/"ver_estoque" etc) que nunca foi registrado em athena_bridge.py
e por isso nunca rodou de verdade; o /api/auth/login e /api/me reais sao os
definidos diretamente em athena_bridge.py, com o esquema de permissoes do
RBAC (core/rbac.py, codigos "modulo.acao"). routes/auth.py foi removido por
ser codigo morto; este teste foi reescrito para validar o login/permissoes
que realmente rodam em producao.
"""
TEST_PASSWORD = "senha-teste-123"

import os
from core import log


def test_auth_jwt_login_and_me():
    """Testa que o login master (ATHENA_ADMIN_EMAIL/ATHENA_ADMIN_PW) emite um
    JWT valido e que /api/me devolve o papel e as permissoes reais."""
    log("TEST", "Testando login JWT e /api/me...")
    os.environ["ATHENA_ADMIN_EMAIL"] = "admin@teste.local"
    os.environ["ATHENA_ADMIN_PW"] = TEST_PASSWORD
    from athena_bridge import app
    from core.rbac import verificar_token_sessao
    import jwt

    client = app.test_client()

    resp = client.post("/api/auth/login", json={"email": "admin@teste.local", "password": TEST_PASSWORD})
    assert resp.status_code == 200, f"Login deve retornar 200: {resp.get_json()}"
    body = resp.get_json()
    assert body["role"] == "admin", f"Role deve ser admin: {body}"
    token = body["token"]
    log("TEST", f"✅ Login emitiu token para role={body['role']}")

    # Verify token is a real signed JWT (nao um token estatico)
    payload = verificar_token_sessao(token)
    assert payload is not None, "Token deve ser um JWT valido e assinado"
    assert payload["role"] == "admin", "Token role deve ser admin"
    log("TEST", f"✅ Token é um JWT válido com role: {payload['role']}")

    try:
        jwt.decode(token + "adulterado", "chave-errada", algorithms=["HS256"])
        raise AssertionError("Token adulterado nao deveria decodificar")
    except jwt.PyJWTError:
        pass

    resp_me = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert resp_me.status_code == 200, f"/api/me deve retornar 200: {resp_me.get_json()}"
    me = resp_me.get_json()
    assert me["role"] == "admin", f"/api/me deve refletir role do token: {me}"
    assert me["permissoes"] == ["*"], f"Login master deve ter todas as permissoes: {me}"
    log("TEST", f"✅ /api/me devolveu permissoes: {me['permissoes']}")

    resp_no_token = client.get("/api/me")
    assert resp_no_token.status_code == 401, "Sem token deve retornar 401"
    log("TEST", "✅ /api/me sem token retorna 401")

    return True


def run_all_tests():
    """Executa todos os testes."""
    log("TEST", "=" * 50)
    log("TEST", "Iniciando testes Fase 0 + Fase 1")
    log("TEST", "=" * 50)

    tests = [
        ("Auth JWT + /api/me", test_auth_jwt_login_and_me),
    ]

    resultados = []
    for nome, test_func in tests:
        try:
            sucesso = test_func()
            resultados.append((nome, "PASSOU" if sucesso else "FALHOU"))
        except Exception as e:
            log("TEST", f"❌ {nome} falhou: {e}")
            resultados.append((nome, f"ERRO: {str(e)}"))

    log("TEST", "=" * 50)
    log("TEST", "Resultados:")
    for nome, resultado in resultados:
        log("TEST", f"  {nome}: {resultado}")
    log("TEST", "=" * 50)

    return all(r[1] == "PASSOU" for r in resultados)


if __name__ == "__main__":
    sucesso = run_all_tests()
    sys.exit(0 if sucesso else 1)
