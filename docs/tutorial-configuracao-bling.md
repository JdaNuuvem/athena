# Tutorial: Como configurar a API do Bling ERP

Este tutorial foi feito para pessoas sem experiência técnica configurarem a integração com a API do Bling passo a passo.

## 📋 O que você vai precisar

Antes de começar, tenha em mãos:
- Uma conta ativa no Bling ERP
- Plano Lite ou superior (gratuito para pequenas empresas)
- Seu CNPJ (para emissão de notas fiscais)
- Acesso ao painel do Athena (já configurado)

## 🔑 Passo 1: Criar conta no Bling ERP

### 1.1 Acesse o Bling
1. Vá até: https://www.bling.com.br/
2. Clique em "Criar conta grátis"
3. Escolha o plano adequado:
   - **Lite**: Gratuito para pequenas empresas (ideal para começar)
   - **Pro**: R$99/mês (funcionalidades avançadas)
   - **Enterprise**: Contato comercial

### 1.2 Configure sua empresa
1. Preencha os dados da empresa:
   - CNPJ/CPF
   - Razão Social
   - Nome Fantasia
   - Inscrição Estadual
   - Endereço completo
   - Dados de contato
2. Configure os dados fiscais:
   - Regime tributário (Simples Nacional, Lucro Presumido, etc.)
   - Atividade econômica (CNAE)
   - CFOP padrão
3. Valide o cadastro via e-mail

### 1.3 Configure o plano gratuito (se aplicável)
1. Após o cadastro, você terá 15 dias de teste gratuito
2. Ao final do período, você será redirecionado para escolher o plano
3. O plano Lite é gratuito para empresas com até:
   - 50 pedidos por mês
   - 100 produtos
   - 50 clientes

## 🔑 Passo 2: Obter API Key do Bling

### 2.1 Acesse as configurações de integração
1. Faça login no Bling
2. Clique no menu lateral: **Configurações** (ícone de engrenagem)
3. Selecione **Integrações** no menu esquerdo
4. Clique em **API**

### 2.2 Gere sua API Key
1. Na seção "API Key", clique em **Gerar nova API Key**
2. **IMPORTANTE**: A API Key só será exibida uma vez!
3. Copie a chave gerada imediatamente
4. Guarde em local seguro (recomendado: gerenciador de senhas)

**A API Key tem este formato:**
```
abc123def456ghi789jkl012mno345pq6
```

### 2.3 Configure permissões da API
1. Na mesma página, você verá as permissões disponíveis
2. Certifique-se de que as seguintes permissões estejam ativas:
   - ✅ Produtos (GET, POST, PUT)
   - ✅ Pedidos (GET, POST)
   - ✅ Notas Fiscais (GET, POST)
   - ✅ Contas a Receber (GET, POST)
   - ✅ Estoque (GET, POST)

### 2.4 Entenda os tipos de API
O Bling oferece dois tipos de integração:

**API V2 (Recomendada):**
- Mais moderna e completa
- Baseada em REST
- Melhor documentação
- Suporte total

**API V1 (Legado):**
- Mantida para compatibilidade
- Menos recursos
- Será descontinuada

**Use sempre a API V2!**

## 🔑 Passo 3: Configurar o ambiente

### 3.1 Determine o ambiente
O Bling não tem ambiente de sandbox separado como outros sistemas, mas você pode:
- **Testar no plano Lite grátis** antes de assinar o Pro
- **Usar dados de teste** durante o desenvolvimento
- **Criar produtos fictícios** para testar

### 3.2 Configurar Webhooks (opcional)
Para atualizações em tempo real:
1. Em Configurações → Integrações → Webhooks
2. Adicione a URL do seu servidor:
   ```
   https://seu-dominio.com/api/bling/webhooks
   ```
3. Selecione os eventos desejados:
   - Novo pedido
   - Pedido alterado
   - Nota fiscal emitida
   - Conta a receber paga
4. Clique em "Salvar"

## ⚙️ Passo 4: Configurar no Athena

### 4.1 Acessar o painel de integração
1. Faça login no Athena
2. Clique em **Integrações** no menu lateral
3. Selecione **Bling ERP**

### 4.2 Preencher os campos
Preencha com as informações que você copiou:

```
API Key: [cole sua API Key gerada]
Modo Sandbox: desmarcar (Bling não tem sandbox oficial)
Sincronização Automática: ativar
Intervalo de Sincronização: 30 minutos
```

### 4.3 Configurar opções de sincronização
Marque as funcionalidades desejadas:
- ✅ **Sincronizar Produtos** — Atualizar catálogo
- ✅ **Sincronizar Pedidos** — Importar novos pedidos
- ✅ **Sincronizar Notas Fiscais** — NF-e/NFC-e emitidas
- ✅ **Sincronizar Contas a Receber** — Controle financeiro
- ✅ **Sincronizar Estoque** — Atualização em tempo real

### 4.4 Testar a conexão
1. Clique no botão **"Testar Conexão"**
2. Se aparecer "✓ Conexão bem-sucedida!", está tudo certo!
3. O sistema mostrará quantos produtos foram encontrados

### 4.5 Primeira sincronização
1. Clique em cada aba (Produtos, Pedidos, Notas Fiscais, Contas a Receber)
2. Clique em **"Sincronizar Agora"** em cada aba
3. Aguarde o processo (primeira sincronização pode levar alguns minutos)
4. Verifique se os dados apareceram nas tabelas

## 📊 Passo 5: Configurar o mapeamento de dados

### 5.1 Mapeamento de produtos
Configure a correspondência de campos:
- **Código Bling** → SKU do Athena
- **Descrição** → Nome do produto
- **Preço** → Preço de venda
- **Estoque Atual** → Quantidade disponível
- **GTIN/EAN** → Código de barras

### 5.2 Mapeamento de pedidos
Configure como os pedidos serão processados:
- **Status do pedido** → Mapeamento de status
- **Cliente** → Integração com CRM
- **Itens** → Atualização de estoque automática
- **Pagamento** → Integração financeira

### 5.3 Mapeamento fiscal
Configure as notas fiscais:
- **Série padrão** (ex: 1, 2)
- **CFOP padrão** (ex: 5102 para vendas)
- **Natureza da operação**
- **Regime tributário**

## 🔄 Passo 6: Testar o fluxo completo

### 6.1 Criar um produto teste
1. No Bling, crie um novo produto simples
2. Preencha os campos básicos:
   - Código: TESTE-001
   - Descrição: Produto Teste
   - Preço: 99.90
   - Estoque: 10
3. Salve o produto

### 6.2 Sincronizar produtos
1. No Athena, clique em **"Sincronizar Agora"** na aba Produtos
2. Verifique se o produto TESTE-001 aparece na tabela
3. Confirme os dados (preço, estoque, descrição)

### 6.3 Criar um pedido teste
1. No Bling, crie um novo pedido manual
2. Adicione o produto TESTE-001
3. Defina como "Atendido"
4. Salve o pedido

### 6.4 Sincronizar pedidos
1. No Athena, clique em **"Sincronizar Agora"** na aba Pedidos
2. Verifique se o pedido aparece na tabela
3. Confirme os dados (cliente, itens, valor total)

## 🔧 Passo 7: Configurar sincronização automática

### 7.1 Ativar auto-sync
1. Configure o intervalo (recomendado: 30 minutos)
2. Ative a sincronização automática
3. O sistema fará:
   - Pull de novos produtos a cada 30 minutos
   - Pull de novos pedidos a cada 30 minutos
   - Pull de notas fiscais emitidas
   - Pull de contas a receber

### 7.2 Monitorar a sincronização
1. Acompanhe os logs no console
2. Verifique a data da última sincronização
3. Monitore erros (se houver)
4. Ajuste o intervalo se necessário

## 🔑 Passo 8: Configurar emissão de notas fiscais

### 8.1 Configurar dados fiscais
1. No Bling, configure seus certificados digitais:
   - Certificado A1 (em arquivo)
   - Certificado A3 (em token)
2. Configure a SEFAZ:
   - Ambiente de homologação (para testes)
   - Ambiente de produção (para emissão real)

### 8.2 Testar emissão
1. Crie um pedido teste
2. Clique em "Gerar Nota Fiscal"
3. Verifique se a nota foi gerada corretamente
4. Acesse o DANFE para conferir

### 8.3 Sincronizar notas
1. No Athena, clique em **"Sincronizar Agora"** na aba Notas Fiscais
2. Verifique se a nota aparece na tabela
3. Confirme os dados (chave de acesso, valor, cliente)

## 💰 Passo 9: Configurar contas a receber

### 9.1 Configurar formas de pagamento
1. No Bling, configure as formas de pagamento:
   - Boleto bancário
   - Cartão de crédito
   - PIX
   - Transferência bancária
2. Defina os prazos padrão

### 9.2 Sincronizar recebíveis
1. Após a venda, as contas a receber são geradas automaticamente
2. No Athena, sincronize as contas a receber
3. Verifique os vencimentos e valores

## 🔧 Dicas de Solução de Problemas

### Problema: "Conexão falhou"
**Solução:**
1. Verifique se a API Key está correta
2. Confirme que seu plano Bling permite API
3. Verifique se as permissões estão ativas
4. Tente gerar uma nova API Key

### Problema: "Produtos não aparecem"
**Solução:**
1. Clique em "Sincronizar Agora" na aba Produtos
2. Verifique se você tem produtos ativos no Bling
3. Confirme se a situação é "A" (ativo)
4. Verifique os logs de erro

### Problema: "Pedidos não aparecem"
**Solução:**
1. Verifique se há pedidos recentes no Bling
2. Confirme se a data do pedido está no período de sincronização
3. Verifique o status do pedido (deve ser "Atendido")
4. Ajuste o filtro de data se necessário

### Problema: "Erro de rate limit"
**Solução:**
1. Aumente o intervalo de sincronização
2. Reduza a quantidade de dados por requisição
3. O sistema respeita automaticamente os limites da API
4. Se persistir, contate o suporte Bling

### Problema: "Nota fiscal não emitida"
**Solução:**
1. Verifique se o certificado digital está válido
2. Confirme se a SEFAZ está disponível
3. Verifique se todos os dados fiscais estão preenchidos
4. Consulte o status na SEFAZ

### Problema: "Erro de autenticação"
**Solução:**
1. Verifique se a API Key expirou
2. Tente gerar uma nova API Key
3. Confirme se o plano Bling está ativo
4. Verifique as permissões da API

## 📞 Suporte

### Suporte Bling:
- **Documentação API:** https://developer.bling.com.br/
- **Central de Ajuda:** https://ajuda.bling.com.br
- **Email:** suporte@bling.com.br
- **Telefone:** (51) 3209-8888

### Suporte Athena:
- **Documentação Interna:** /docs/
- **Equipe de Desenvolvimento:** [contato]

## 🎉 Parabéns!

Você configurou com sucesso a integração com o Bling ERP. Seus produtos, pedidos, notas fiscais e contas a receber agora estarão sincronizados automaticamente no Athena.

## 📚 Próximos Passos

1. **Configurar webhooks** para atualizações em tempo real
2. **Mapear campos personalizados** para sua necessidade
3. **Configurar emissão automática** de notas fiscais
4. **Integrar com outros sistemas** (Shopee, Mercado Livre, etc.)
5. **Automatizar processos** de venda e faturamento

---

**Lembre-se:**
- Mantenha sua API Key segura, nunca compartilhe
- Monitore regularmente os logs de erro
- Teste sempre no plano Lite antes de assinar o Pro
- Ajuste o intervalo de sincronização conforme sua necessidade
- Use o ambiente de homologação para testes fiscais