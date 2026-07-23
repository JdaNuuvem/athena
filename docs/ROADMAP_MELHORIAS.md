# 🗺️ Plano de Melhorias — Athena

Um resumo simples de tudo que vamos construir, pra que serve e quanto trabalho dá.

---

## 🔴 Fase 1 — Proteção (não perder dinheiro)

### 1. Alerta de margem negativa
**Complexidade:** 🔵 Fácil (2-3 horas)  
**O que vai ser feito:**  
Antes de publicar qualquer produto na Shopee, o sistema vai calcular se o preço final cobre todos os custos (comissão da Shopee + frete + custo do produto). Se não cobrir, o sistema **bloqueia** e mostra uma mensagem explicando o motivo.  
  ```
  ❌ "Sabonete X" não pode ser publicado na Loja C
     Preço: R$ 12,00  
     - Comissão (18%): R$ 2,16  
     - Frete médio: R$ 5,00  
     - Custo do produto: R$ 8,00  
     Resultado: **PREJUÍZO de R$ 3,16**  
     Sugestão: preço mínimo de R$ 18,00  
  ```
**Resultado:** Zero produtos vendidos com prejuízo por descuido.

### 2. Sincronização automática de estoque
**Complexidade:** 🟡 Médio (4-6 horas)  
**O que vai ser feito:**  
Hoje, quando você ajusta o estoque no Athena, precisa sincronizar manualmente com cada loja Shopee. Vamos automatizar: qualquer alteração de estoque no Athena é enviada automaticamente para **todas as lojas Shopee** conectadas.  
**Resultado:** Acabou o "esqueci de atualizar o estoque na Loja B e vendi o que não tinha".

---

## 🟡 Fase 2 — Enxergar os números

### 3. DRE por loja (lucro real)
**Complexidade:** 🟡 Médio (4-6 horas)  
**O que vai ser feito:**  
Uma tela nova que mostra, para cada loja Shopee:  
- Quanto ela vendeu (receita)  
- Quanto a Shopee cobrou de comissão e frete  
- Quanto custaram os produtos  
- Quanto sobrou de **lucro real**  

```
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ Loja A      │ │ Loja B      │ │ Loja C      │
│ Vendeu: 50k │ │ Vendeu: 35k │ │ Vendeu: 12k │
│ Custos: 28k │ │ Custos: 22k │ │ Custos: 9k  │
│ Lucro: 22k  │ │ Lucro: 13k  │ │ Lucro: 3k   │ ← ⚠ Essa loja está ganhando pouco!
│ Margem: 44% │ │ Margem: 37% │ │ Margem: 25% │
└─────────────┘ └─────────────┘ └─────────────┘
```
**Resultado:** Saber exatamente qual loja está dando mais lucro e qual precisa de ajuste.

---

## 🟠 Fase 3 — Precificar automaticamente

### 4. Markup por loja
**Complexidade:** 🟡 Médio (6-8 horas)  
**O que vai ser feito:**  
Cada loja pode ter um **markup diferente** (percentual de lucro sobre o custo). Você configura uma vez:
- Loja A: markup 2.5x (vende 2,5x o valor de custo)  
- Loja B: markup 2.0x  

Quando o sistema replicar os produtos, cada loja recebe o preço correto automaticamente.  
**Resultado:** Cada loja com preço adequado ao seu custo operacional, sem você precisar calcular um por um.

### 5. Réguas de desconto automático
**Complexidade:** 🟡 Médio (4-6 horas)  
**O que vai ser feito:**  
O sistema aplica descontos automaticamente baseado em regras que você define:
- "Loja nova: 10% de desconto nos primeiros 30 dias"  
- "Produto parado há mais de 30 dias: baixar 10%"  
- "Estoque alto (mais de 90 dias parado): baixar 15%"  
- "Black Friday: aplicar desconto programado"  
**Resultado:** Produto encalhado não fica parado pra sempre. Loja nova começa competitiva.

---

## 🔵 Fase 4 — Replicar produtos inteligentemente

### 6. Replicar produtos entre lojas
**Complexidade:** 🔴 Difícil (6-8 horas)  
**O que vai ser feito:**  
Você já tem uma loja Shopee com produtos vendendo. Quando conectar uma loja nova, vai ter um botão: **"Copiar produtos da Loja A"**. O sistema:
1. Puxa todos os produtos da loja origem (nomes, preços, fotos, descrições)  
2. Reenvia as fotos para a loja nova  
3. Publica tudo automaticamente  

**Resultado:** Abrir loja nova = 1 clique + esperar. Em vez de cadastrar produto por produto.

### 7. Catálogo diferenciado por loja
**Complexidade:** 🟢 Fácil (3-4 horas)  
**O que vai ser feito:**  
Nem todo produto precisa ir para toda loja. Você vai poder criar **grupos de produtos**:
- "Premium" → vai só para a Loja A  
- "Econômico" → vai para a Loja B  
- "Todos" → vai para todas  

Na hora de replicar, você escolhe quais grupos levar.  
**Resultado:** Cada loja com seu próprio estilo e público, sem virar uma bagunça de produtos que não combinam.

### 8. Rotação de estoque entre lojas
**Complexidade:** 🟡 Médio (3-4 horas)  
**O que vai ser feito:**  
Se um produto está encalhado na Loja A mas vendendo bem na Loja B, o Athena sugere: "Transferir 50 unidades da Loja A para a Loja B".  
**Resultado:** Menos dinheiro parado em estoque que não gira.

---

## 🟣 Fase 5 — Otimizar margem

### 9. Reprecificação por concorrência
**Complexidade:** 🔴 Difícil (8-12 horas)  
**O que vai ser feito:**  
Ao publicar um produto, o sistema consulta o preço médio dos concorrentes na Shopee. Se seu preço estiver muito acima, ele avisa.
**Resultado:** Seus produtos não morrem na estreia porque o preço estava fora da realidade.

### 10. Sugestão de kits / combo
**Complexidade:** 🟡 Médio (4-6 horas)  
**O que vai ser feito:**  
O sistema analisa: "quem comprou X também comprou Y". Na hora de publicar, ele sugere criar um **kit** com os dois produtos por um preço promocional.
**Resultado:** Cliente compra mais de uma vez = ticket médio maior.

---

## 📊 Tabela resumo

| # | Funcionalidade | Pra que serve | Esforço |
|---|---------------|---------------|---------|
| 1 | Alerta de margem negativa | Não vender com prejuízo | 2-3h |
| 2 | Estoque automático | Sincronizar tudo sem esquecer | 4-6h |
| 3 | DRE por loja | Saber o lucro real de cada loja | 4-6h |
| 4 | Markup por loja | Cada loja com preço certo | 6-8h |
| 5 | Desconto automático | Queimar estoque sem pensar | 4-6h |
| 6 | Replicar produtos | Abrir loja nova em 1 clique | 6-8h |
| 7 | Catálogo por loja | Cada loja com seu mix | 3-4h |
| 8 | Rotação de estoque | Aproveitar estoque parado | 3-4h |
| 9 | Reprecificação concorrência | Não errar preço de estreia | 8-12h |
| 10 | Sugestão de kits | Aumentar ticket médio | 4-6h |
| | **Total** | | **44-63h** |

---

## Como vamos fazer (ordem)

```
Mês 1 → Fases 1 + 2 (Proteção + Enxergar)
  Não perder dinheiro + ver números reais

Mês 2 → Fase 3 (Precificar)
  Automatizar markup e descontos

Mês 3 → Fase 4 (Replicar)
  Abrir lojas novas em 1 clique

Mês 4 → Fase 5 (Otimizar)
  Concorrência + kits
```

---

## Perguntas frequentes

**Preciso trocar de plano?** Não. Todas as melhorias estão incluídas.

**Vou perder dados existentes?** Não. Nada é apagado.

**Preciso instalar algo?** Não. Tudo roda no sistema atual.

**Funciona para lojas que já existem?** Sim. As melhorias afetam lojas novas e existentes.
