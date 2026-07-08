# 🚀 Deploy Completo - Guia Passo a Passo

## 🔐 Credenciais Coolify

- **IP**: 177.7.45.242
- **Email**: jp.webcreative@gmail.com
- **Senha**: Zoikom276151@
- **Painel**: https://177.7.45.242:8000

---

## 📋 Checklist de Deploy

### ✅ Passo 1: Login no Coolify

1. Acesse: https://177.7.45.242:8000
2. Email: jp.webcreative@gmail.com
3. Senha: Zoikom276151@
4. Clique em **"Login"**

---

### ✅ Passo 2: Configurar Serviço Hermes API

1. **Acessar**: Projects → athena → Clique no serviço Hermes API
2. **Clique**: "Redeploy" ou "Deploy"
3. **Aguarde**: 2-3 minutos
4. **Status**: Deve ficar verde ✅

**URL após deploy**: https://177.7.45.242:8000/api

---

### ✅ Passo 3: Configurar Serviço Dashboard

#### 3.1 Criar Serviço

1. **Projects** → **"+ Create Service"**
2. **Tipo**: Git
3. **URL**: https://github.com/JdaNuuvem/athena.git
4. **Branch**: master
5. **Build Directory**: /
6. **Dockerfile**: Deixe em branco (usará Dockerfile raiz)
7. **Port**: 5173
8. **Clique**: "Create Service"

#### 3.2 Deploy

1. Clique em **"Deploy"**
2. Aguarde 2-3 minutos
3. Status deve ficar verde ✅

**URL após deploy**: https://177.7.45.242:5173

---

### ✅ Passo 4: Testar Autenticação Athena

#### 4.1 Fazer Login

No terminal ou Postman:

```bash
curl -X POST https://177.7.45.242:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"api_key": "athena-token-123456789"}'
```

**Resposta esperada**:
```json
{
  "token": "athena-token-123456789",
  "role": "admin",
  "name": "Athena Admin"
}
```

#### 4.2 Testar Health Check

```bash
curl https://177.7.45.242:8000/api/health
```

**Resposta esperada**:
```json
{
  "status": "healthy",
  "agents": {...},
  "infrastructure": {...},
  "uptime": 86400,
  "version": "1.0.0",
  "memory": {...}
}
```

#### 4.3 Testar Lista de Agents

```bash
curl https://177.7.45.242:8000/api/agents
```

**Resposta esperada**: Lista com 13 agentes

---

### ✅ Passo 5: Acessar Athena Frontend

1. Acesse: http://a181zp5xj2ety5z82mopyqzi.177.7.45.242.sslip.io
2. Você deve ver o login
3. **API Key**: athena-token-123456789
4. Clique em **"Login"**

**Dashboard deve carregar sem erros!**

---

### ✅ Passo 6: Acessar Hermes Dashboard

1. Acesse: https://177.7.45.242:5173
2. Dashboard deve carregar
3. Preencher configurações:
   - **Telegram Token**: Token do @BotFather
   - **Bling API Key**: Key do Bling
   - **Shopee**: Partner ID, Shop ID, API Key
4. Clicar em **"Salvar"**

---

### ✅ Passo 7: Testar Integrações

#### 7.1 Testar API Hermes

```bash
curl https://177.7.45.242:8000/api/config/status
```

#### 7.2 Testar Telegram

```bash
curl https://177.7.45.242:8000/api/test/telegram
```

#### 7.3 Testar Bling

```bash
curl https://177.7.45.242:8000/api/test/bling
```

#### 7.4 Testar Shopee

```bash
curl https://177.7.45.242:8000/api/test/shopee
```

---

## 🌐 URLs Finais

| Serviço | URL | Status |
|---------|-----|--------|
| **Coolify Panel** | https://177.7.45.242:8000 | ✅ |
| **Hermes API** | https://177.7.45.242:8000/api | ✅ |
| **Hermes Dashboard** | https://177.7.45.242:5173 | ✅ |
| **Athena Frontend** | http://a181zp5xj2ety5z82mopyqzi.177.7.45.242.sslip.io | ✅ |
| **GitHub** | https://github.com/JdaNuuvem/athena | ✅ |

---

## 🎯 Credenciais de Teste

### Athena OS Login
- **API Key**: athena-token-123456789
- **Token**: athena-token-123456789
- **Role**: admin

### Hermes Configurações
- **Telegram**: Token do @BotFather
- **Bling**: API Key do Bling
- **Shopee**: Partner ID, Shop ID, API Key

---

## 🐛 Troubleshooting

### Dashboard não carrega (5173)

**Problema**: Serviço não rodando

**Solução**:
1. Coolify → Services → Dashboard
2. Clique em "Logs"
3. Verifique erros
4. Clique em "Redeploy"

### Athena 401 Unauthorized

**Problema**: Token não configurado

**Solução**:
1. Acesse Athena frontend
2. Use API key: athena-token-123456789
3. Login

### API não responde (8000)

**Problema**: Serviço Hermes parado

**Solução**:
1. Coolify → Services → Hermes API
2. Clique em "Redeploy"
3. Aguarde 2-3 minutos

### Porta em uso

**Problema**: Porta 5173 ocupada

**Solução**:
1. Mude para 5174
2. Update Service → Port: 5174
3. Redeploy

---

## ✅ Resumo do que foi feito

1. ✅ Adicionada autenticação Athena OS
2. ✅ Criados endpoints `/api/auth/login`, `/api/health`, `/api/agents`
3. ✅ Commitado e pushado: `7f1832d`
4. ✅ Dockerfile configurado para dashboard
5. ✅ Pronto para deploy no Coolify

---

## 🚀 Próximo Passo

1. **Login no Coolify**: https://177.7.45.242:8000
2. **Redeploy serviço Hermes**
3. **Criar/Redeploy serviço Dashboard**
4. **Acessar Athena frontend** → Testar login
5. **Acessar Hermes dashboard** → Configurar APIs

**Ou me avise se precisar de ajuda!**