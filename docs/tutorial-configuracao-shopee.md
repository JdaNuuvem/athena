# Tutorial: Como configurar a API da Shopee para leigos

Este tutorial foi feito para pessoas sem experiência técnica configurarem a integração com a API da Shopee passo a passo.

## 📋 O que você vai precisar

Antes de começar, tenha em mãos:
- Uma conta ativa de vendedor na Shopee
- Seu CNPJ ou CPF (se for MEI)
- Um e-mail válido para cadastro
- Acesso ao painel do Athena (já configurado)

## 🔑 Passo 1: Criar conta de Desenvolvedor Shopee

### 1.1 Acesse o portal de desenvolvedores
1. Vá até: https://open.shopee.com.br/
2. Clique em "Entrar" no canto superior direito
3. Faça login com sua conta de vendedor Shopee

### 1.2 Preencha os dados da empresa
1. Após login, clique em "Criar Aplicativo"
2. Preencha os campos:
   - **Nome do App**: Athena OS Integration
   - **Descrição**: Sistema de gestão de estoque e pedidos
   - **Categoria**: E-commerce / Gestão de Inventário
   - **Website**: https://seu-dominio.com (ou localhost em desenvolvimento)
   - **URL de Redirecionamento**: https://seu-dominio.com/shopee/callback

### 1.3 Aguarde aprovação
A Shopee pode levar de 1 a 3 dias úteis para aprovar seu aplicativo.

## 🎯 Passo 2: Obter credenciais da API

### 2.1 Após aprovação
1. Acesse novamente: https://open.shopee.com.br/
2. Vá em "Meus Aplicativos"
3. Selecione seu aplicativo criado

### 2.2 Copie as credenciais essenciais
Você precisará das seguintes informações (guarde bem!):

```
✅ Partner ID: [número que aparece no painel]
✅ Partner Key: [chave secreta longa - SÓ VOCÊ TEM ACESSO]
✅ Shop ID: [ID da sua loja - geralmente no seu perfil Shopee]
```

### Como encontrar cada credencial:

**Partner ID:**
- Aparece na página principal do seu aplicativo
- É um número geralmente entre 100.000 e 999.999

**Partner Key:**
- Está na aba "Configurações" ou "API Keys"
- Clique em "Mostrar" ou "Gerar nova chave"
- ⚠️ **MUITO IMPORTANTE**: Nunca compartilhe esta chave!
- Guarde em local seguro, você só verá uma vez

**Shop ID:**
- Acesse seu Seller Center da Shopee
- Vá em "Meus Produtos" → "Todos os Produtos"
- O Shop ID está na URL do navegador, geralmente algo como:
  `https://seller.shopee.com.br/portal/product/[SHOP_ID]/list`

## 🔐 Passo 3: Gerar Token de Acesso

### 3.1 Primeiro acesso (Autorização OAuth)
1. No painel do Athena, vá em **Configurações** → **Integrações** → **Shopee**
2. Clique em "Conectar com Shopee"
3. Você será redirecionado para a página de login da Shopee
4. Faça login e autorize o acesso
5. Será redirecionado de volta ao Athena com o token gerado

### 3.2 Refresh automático do token
- O token expira a cada 4 horas
- O Athena renova automaticamente usando refresh tokens
- Não precisa fazer nada manualmente

## ⚙️ Passo 4: Configurar no Athena

### 4.1 Acessar o painel de configuração
1. Faça login no Athena
2. Clique em **Configurações** no menu lateral
3. Selecione **Integrações** → **Shopee**

### 4.2 Preencher os campos
Preencha com as informações que você copiou:

```
Partner ID: [cole seu Partner ID]
Partner Key: [cole seu Partner Key]
Shop ID: [cole seu Shop ID]
Region: br (Brasil)
Sandbox: desativado (para produção)
```

### 4.3 Testar a conexão
1. Clique no botão **"Testar Conexão"**
2. Se aparecer "✓ Conexão bem-sucedida", está tudo certo!
3. Se aparecer erro, verifique:
   - Se todas as credenciais estão corretas
   - Se seu aplicativo foi aprovado pela Shopee
   - Se você selecionou a região correta (br)

### 4.4 Primeira sincronização
1. Clique em **"Sincronizar Agora"**
2. Aguarde o processo (pode levar alguns minutos na primeira vez)
3. Verifique se seus produtos apareceram na lista

## 🛡️ Passo 5: Modo Sandbox (Testes)

Antes de usar em produção, recomendamos testar no modo Sandbox:

### 5.1 Ativar Sandbox
1. Nas configurações da Shopee no Athena
2. Marque a opção **"Modo Sandbox"**
3. Isso usará um ambiente de teste que não afeta seus dados reais

### 5.2 Testar todas as funcionalidades
- Sincronização de produtos
- Atualização de estoque
- Importação de pedidos

### 5.3 Desativar Sandbox
Após testar tudo, desmarque "Modo Sandbox" para usar dados reais.

## 📊 Passo 6: Monitorar a integração

### 6.1 Dashboard de Shopee
No painel Athena, você verá:
- Produtos sincronizados
- Estoque atualizado
- Última sincronização
- Erros, se houver

### 6.2 Logs de erro
Se aparecerem erros:
- **error_sign**: Verifique se Partner Key está correta
- **error_auth**: Token expirado, o sistema renovará automaticamente
- **error_rate_limit**: Muitas requisições, aguarde 60 segundos
- **error_param**: Parâmetros inválidos, contate suporte

## 🔧 Dicas de Solução de Problemas

### Problema: "Conexão falhou"
**Solução:**
1. Verifique se Partner ID e Partner Key estão corretos
2. Confirme que seu aplicativo foi aprovado
3. Tente gerar novo Partner Key nas configurações da Shopee

### Problema: "Token expirado"
**Solução:**
1. O sistema deve renovar automaticamente
2. Se persistir, clique em "Reconectar" nas configurações
3. Refaça o processo de autorização OAuth

### Problema: "Produtos não aparecem"
**Solução:**
1. Clique em "Sincronizar Agora"
2. Verifique se você tem produtos ativos na Shopee
3. Confirme que o Shop ID está correto

### Problema: "Erro de rate limit"
**Solução:**
1. Aguarde 60 segundos
2. O sistema respeita automaticamente os limites da API
3. Se ocorrer frequentemente, entre em contato com a Shopee para aumentar limites

## 📞 Suporte

Se você precisar de ajuda:
- Documentação oficial: https://open.shopee.com.br/documents
- Suporte Shopee: https://help.shopee.com.br
- Suporte Athena: (contato do seu fornecedor)

## 🎉 Parabéns!

Você configurou com sucesso a integração com a Shopee. Seus produtos agora estarão sincronizados automaticamente e os pedidos serão importados para o Athena.

---

**Lembre-se:**
- Mantenha suas credenciais seguras
- Nunca compartilhe o Partner Key
- Monitore regularmente os logs de erro
- Teste sempre no modo Sandbox primeiro