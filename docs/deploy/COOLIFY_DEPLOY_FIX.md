# Como Corrigir o Deploy no Coolify

## ❌ Erro Atual

O Coolify está tentando usar Docker, mas não encontrava Dockerfile.

## ✅ Solução Implementada

Criei **Dockerfile** multi-stage para o dashboard React.

---

## 📋 Passo 1: Reconfigurar Serviço no Coolify

### Acesse o Serviço
1. Painel Coolify → Projects → athena
2. Clique no serviço que falhou
3. Clique em **"Update Service"** ou **"Settings"**

### Atualizar Configurações

**Service Type**: ✅ Docker (padrão)

**Image** (se necessário):
```
ghcr.io/coollabsio/coolify-helper:1.0.14
```

**Build Context**: `/`

**Dockerfile**: Deixe em branco (usará o Dockerfile raiz)

**Environment Variables** (se precisar):
```
NODE_ENV=production
PORT=5173
```

**Port**: `5173`

---

## 📋 Passo 2: Deploy

1. Clique em **"Redeploy"** ou **"Deploy"**
2. Aguarde o build:
   - **Stage 1**: npm install (aprox. 1-2 min)
   - **Stage 2**: npm run build (aprox. 1-2 min)
   - **Stage 3**: Iniciar serve

3. Se tudo verde ✅, deploy completo!

---

## 🌐 Passo 3: Acessar

Após deploy:
```
https://177.7.45.242:5173
```

Ou use o link fornecido no painel do Coolify.

---

## 🐛 Se Continuar Falhando

### Opção A: Dockerfile Específico para Dashboard

Crie Dockerfile específico na pasta dashboard:

```dockerfile
FROM node:18-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

FROM node:18-alpine
WORKDIR /app
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist

RUN npm install -g serve
EXPOSE 5173
CMD ["serve", "-s", "dist", "-l", "5173"]
```

No Coolify, configure:
```
Build Directory: /dashboard
Dockerfile: dashboard/Dockerfile
```

### Opção B: Build Command Simples

No Coolify, configure:

**Build Command**:
```
cd dashboard && npm install && npm run build
```

**Start Command**:
```
cd dashboard && npm install -g serve && serve -s dist -l 5173
```

### Opção C: Usar Nixpacks (Automático)

No Coolify, configure:

**Base Directory**: `/dashboard`

O Coolify detectará automaticamente o package.json e criará um Dockerfile.

---

## ✅ Checklist

- [ ] Reconfigurar serviço no Coolify
- [ ] Verificar Dockerfile detectado
- [ ] Configurar porta 5173
- [ ] Redeploy
- [ ] Verificar logs
- [ ] Acessar dashboard

---

## 🔍 Verificar Logs

No Coolify, clique em **"Logs"** e verifique:

✅ Sucesso esperado:
```
npm install ... done
vite build ... done
serve -s dist -l 5173
```

❌ Erros comuns:
- `npm install failed` → Deletar node_modules e redeploy
- `build failed` → Verificar vite.config.js
- `port in use` → Mudar para 5174

---

## 🎯 O que foi feito

1. ✅ Criado Dockerfile multi-stage
2. ✅ Removido scikit-learn do dashboard
3. ✅ Commitado e pushado para GitHub
4. ✅ Pronto para redeploy no Coolify

---

## 📞 Próximo Passo

Reconfigure o serviço no Coolify usando as instruções acima.

**Ou me avise se precisar de mais ajuda!**