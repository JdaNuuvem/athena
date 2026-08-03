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
