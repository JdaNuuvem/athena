#!/usr/bin/env python3
"""
Testes de integração para Fase 0 + Fase 1 - Fundação de Acesso e Núcleo Multiloja.
"""
import sys
from core import log


def test_auth_jwt_login_and_me():
    """Testa que o login emite um JWT por usuário e /api/me devolve o papel real."""
    log("TEST", "Testando login JWT e /api/me...")
    from athena_bridge import app
    import jwt
    client = app.test_client()

    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    assert resp.status_code == 200, f"Login deve retornar 200: {resp.get_json()}"
    body = resp.get_json()
    assert body["role"] == "admin", f"Role deve ser admin: {body}"
    token = body["token"]
    log("TEST", f"✅ Login emitiu token para role={body['role']}")

    # Verify token is a JWT (not a static API_TOKEN)
    try:
        from routes.auth import JWT_SECRET
        decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        assert decoded["role"] == "admin", "Token role deve ser admin"
        log("TEST", f"✅ Token é um JWT válido com role: {decoded['role']}")
    except jwt.InvalidSignatureError:
        raise AssertionError("Token não é um JWT válido (signature inválida)")
    except Exception as e:
        raise AssertionError(f"Token não é um JWT válido: {e}")

    resp_me = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert resp_me.status_code == 200, f"/api/me deve retornar 200: {resp_me.get_json()}"
    me = resp_me.get_json()
    assert me["role"] == "admin", f"/api/me deve refletir role do token: {me}"
    assert "ver_lojas" in me["permissoes"], f"Admin deve ter ver_lojas: {me}"
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
