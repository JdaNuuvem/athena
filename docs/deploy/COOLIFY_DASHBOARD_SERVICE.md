# Como Criar Serviço Dashboard no Coolify

## 📍 Passo 1: Acessar Painel do Coolify

1. Acesse: https://177.7.45.242:8000
2. Faça login com suas credenciais
3. Vá para **Projects** → Clique no projeto "athena"

## 📦 Passo 2: Criar Novo Serviço

1. No projeto, clique no botão **"+ Create Service"**
2. Selecione **"Git"** como fonte
3. Preencha:

### Detalhes do Repositório
```
Git Repository URL: https://github.com/JdaNuuvem/athena.git
Branch: master
```

### Configuração de Build
```
Build Directory: / (raiz do repo)
Build Command: cd dashboard && npm install
```

### Configuração de Runtime
```
Start Command: cd dashboard && npm run dev -- --host 0.0.0.0
Environment: Production
```

### Porta
```
Port: 5173
```

### Configuração de Domínio
```
Domain: (deixe em branco para usar o padrão)
```

## 🚀 Passo 3: Deploy

1. Clique em **"Deploy"**
2. Aguarde o build (aprox. 2-3 min)
3. Se estiver tudo verde ✅, o serviço está pronto

## 🌐 Passo 4: Acessar

Após deploy:
```
https://177.7.45.242:5173
```

Ou verifique o link no painel do Coolify.

---

## ⚠️ Se Der Erro de Porta

Se a porta 5173 estiver em uso, mude para 5174:

### Build Command
```
cd dashboard && npm install
```

### Start Command
```
cd dashboard && npm run dev -- --host 0.0.0.0 --port 5174
```

### Porta
```
Port: 5174
```

---

## 🔄 Passo 5: Atualizar Dashboard (se necessário)

No dashboard atual, atualize a URL da API:

```javascript
const API_BASE = 'https://177.7.45.242:8000/api'
```

---

## ✅ Checklist

- [ ] Acessar painel Coolify
- [ ] Criar novo serviço Git
- [ ] Configurar URL do repo
- [ ] Configurar build command
- [ ] Configurar start command
- [ ] Configurar porta
- [ ] Deployar
- [ ] Testar acesso

---

## 🎯 Resumo Visual

**Painel Coolify** → **+ Create Service** → **Git**
  ↓
**Repo URL**: https://github.com/JdaNuuvem/athena.git
  ↓
**Build**: `cd dashboard && npm install`
  ↓
**Start**: `cd dashboard && npm run dev -- --host 0.0.0.0`
  ↓
**Port**: 5173
  ↓
**Deploy** ✅
  ↓
**Acessar**: https://177.7.45.242:5173