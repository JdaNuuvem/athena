# Deploy Completo - Hermes + Dashboard

## 🚀 Deploy no Servidor Coolify (177.7.45.242)

### Serviços a Deployar
1. **API REST** (Flask) - Porta 5000 → https://177.7.45.242:8000/api
2. **Dashboard React** (Vite) - Porta 5173 → https://177.7.45.242:5173
3. **Telegram Bot** (python-telegram-bot) - Porta 8443

### Passo 1: Preparar Repositório
```bash
# Commitar alterações
git add .
git commit -m "feat: Dashboard configurado para rede"
git push origin master
```

### Passo 2: Deploy da API no Coolify
Acessar terminal do Coolify:
```
http://177.7.45.242:8000/project/ms4tg7zfr6chjyg4nnku9u1o/environment/rx4y3uxy042an81bjjsi5sbr/service/w9hn3qezdgivens9g1o7r3of/terminal
```

Comandos:
```bash
# Instalar dependências
pip install flask flask-cors python-telegram-bot requests scikit-learn pandas psycopg2-binary aiohttp

# Iniciar API
cd /workspace
python hermes_agents/athena_bridge.py
```

### Passo 3: Deploy do Dashboard no Coolify
No Coolify, criar um novo serviço:
1. **Git Repository**: https://github.com/JdaNuuvem/athena
2. **Branch**: master
3. **Build Command**: `npm install`
4. **Start Command**: `npm run dev -- --host 0.0.0.0`
5. **Port**: 5173

### Passo 4: Iniciar Telegram Bot
No terminal do serviço Hermes:
```bash
# Bot Telegram (opcional - via API)
python hermes_agents/start_telegram_bot.py
```

### Passo 5: Testar
```bash
# API
curl https://177.7.45.242:8000/api/config/status

# Dashboard
# Abrir navegador em https://177.7.45.242:5173
```

---

## 🌐 Acessos

### Frontend
- **Dashboard**: https://177.7.45.242:5173
- **Configurações**: /api/config
- **Status**: /api/config/status

### API
- **Base**: https://177.7.45.242:8000/api
- **Documentação**: /docs
- **Testes**: /api/test/*

### Webhooks
- **Bling**: /webhook/bling/pedido
- **Shopee**: /webhook/shopee/pedido

---

## ⚠️ Problema Atual

O dashboard está rodando **localmente** (192.168.1.27:5173), mas o usuário acessa via **Coolify** (177.7.45.242:5173).

### Solução 1: Deploy no Coolify (Recomendado)
1. Criar serviço separado para o dashboard
2. Configurar build/start commands
3. Configurar porta 5173

### Solução 2: Proxy Reverso
Configurar o servidor Coolify para redirecionar `:5173` para a máquina local

### Solução 3: Build de Produção
```bash
cd dashboard
npm run build
# Gerar: dist/
# Upload para servidor Coolify
```

---

## 📝 Checklist de Deploy

- [ ] Commitar código no GitHub
- [ ] Criar serviço Hermes API no Coolify
- [ ] Criar serviço Dashboard no Coolify
- [ ] Configurar portas (5000, 5173, 8443)
- [ ] Testar API endpoints
- [ ] Testar dashboard
- [ ] Configurar webhooks no Bling
- [ ] Configurar webhooks na Shopee
- [ ] Iniciar Telegram Bot
- [ ] Treinar modelo ML

---

## 🔧 Troubleshooting

### Dashboard não carrega
```bash
# Verificar se o serviço está rodando
pm2 list

# Verificar logs
pm2 logs dashboard

# Reiniciar
pm2 restart dashboard
```

### API não responde
```bash
# Verificar se Flask está rodando
curl http://localhost:5000/api/config/status

# Verificar logs
pm2 logs api
```

### Telegram Bot offline
```bash
# Verificar token
curl https://api.telegram.org/bot<TOKEN>/getMe

# Reiniciar bot
pm2 restart telegram-bot
```

---

## 📚 Documentação Adicional

- `DEPLOY_INSTRUCTIONS.md` - Deploy Hermes Agent Swarm
- `INTEGRACAO_BLING_V3.md` - Integração Bling ERP
- `FUNCIONALIDADES_COMPLETAS.md` - Todas as funcionalidades