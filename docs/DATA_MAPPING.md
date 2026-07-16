# Mapeamento de Dados — Produtos, Cadastros, Estoque

> Data: 2026-07-16 | Bling API v3 | 109 paginas frontend | 20 modulos

---

## 1. PRODUTOS — Fluxo de Dados

### 1.1 O que a Bling API retorna por produto (detail)

O sync `sincronizar_produtos()` mapeia **40+ campos** da Bling para `catalogo_produtos`:

| Campo Bling | Coluna DB | Usado no frontend? |
|-------------|-----------|--------------------|
| `codigo` | `sku` | Sim |
| `nome` / `descricao` | `descricao` | Sim |
| `id` | `id_bling` | Sim (sync two-way) |
| `situacao` | `situacao` | Sim |
| `tipo` | `bling_tipo` | **Nao** |
| `formato` | `formato` | **Nao** |
| `gtin` | `codigo_barras` | **Nao** |
| `gtinEmbalagem` | `gtin_embalagem` | **Nao** |
| `descricaoCurta` | `descricao_curta` | **Nao** |
| `descricaoComplementar` | `descricao_complementar` | **Nao** |
| `unidade` | `unidade_padrao` | **Nao** |
| `pesoBruto` / `pesoLiquido` | `peso_bruto` / `peso_liquido` | **Nao** |
| `volumes` / `itensPorCaixa` | `volumes` / `itens_por_caixa` | **Nao** |
| `marca` | `marca` | Sim (edit form) |
| `categoria.id` / `categoria.descricao` | `categoria_id` / `categoria` | Sim (badge) |
| `estoque.minimo` / `.maximo` | `estoque_minimo` / `estoque_maximo` | **Nao** |
| `tributacao.ncm` / `.cest` / `.origem` | `ncm` / `cest` / `origem_fiscal` | Sim (edit) |
| `fornecedor.precoCusto` | `preco_custo` | **Nao** |
| `preco` | — | Sim (listagem) |
| `imagemURL` / `midia.imagens` | `imagem_url` / `imagens` (jsonb) | Sim |
| `idProdutoPai` | `sku_pai` | Sim (hierarquia) |
| `variacoes[].variacao.nome` | `atributo` | Sim (variacoes tab) |

**🔴 GAP: 14 campos do Bling salvos no banco mas nunca exibidos no frontend.**

### 1.2 Campos que o frontend de produtos renderiza

| Campo | Origem | Exibido em |
|-------|--------|-----------|
| `sku` | `catalogo_produtos.sku` | Lista, detalhe |
| `nome` | `c.descricao` | Lista, detalhe |
| `valor` | `anuncios.preco` | Lista (R$) |
| `total_variacoes` | COUNT filhos | Badge "N var" |
| `categoria` | `c.categoria` | Badge |
| `imagem_url` | `c.imagem_url` | Foto do produto |
| `total_lojas` | COUNT anuncios | Label |
| `estoque_atual` | SUM `estoque_lojas` | StockBadge |
| `margem_pct` | `margens_diarias` | MargemBadge |
| `preco` | Bling API | Detalhe |
| `variacoes` | `catalogo_produtos` filhos | VariacoesTab |
| `atributo` | Bling variacoes | VariacoesTab (grid) |
| `descricao` | `c.descricao` | Edit form |
| `marca` | `c.marca` | Edit form |
| `ncm` | `c.ncm` | Edit form |
| `id_bling` | `c.id_bling` | Two-way sync indicator |

### 1.3 Bug encontrado

**`CadastroTab` envia `preco` para Bling mas nunca coleta o valor do campo.**
O form state inicial e a funcao `startEdit()` nao incluem `preco`. O push Bling envia `{ descricao, preco }` com `preco` sempre `undefined`.

---

## 2. CADASTROS — Campos Disponiveis

### 2.1 Tabelas e colunas

| Tabela | Colunas | Usadas no UI? |
|--------|---------|----------------|
| `cad_empresas` | razao_social, cnpj, ie, im, regime_tributario, porte, tipo, empresa_mae_id, endereco, telefone, email, status | **Todas** |
| `cad_clientes` | nome, tipo, documento, ie, im, limite_credito, score, status | Sim (CRUD panel) |
| `cad_fornecedores` | nome, tipo, documento, ie, im, limite_credito, score, status | Sim (CRUD panel) |
| `cad_transportadoras` | nome, cnpj, frota, regiao, status | Sim |
| `cad_vendedores` | nome, email, regiao, comissao_pct | Sim |
| `cad_usuarios` | nome, email, senha_hash, perfil, grupo_id, mfa_ativo, status | Sim |
| **Auxiliares:** | | |
| `cad_cliente_enderecos` | logradouro, numero, complemento, bairro, cidade, uf, cep | Sim |
| `cad_cliente_contatos` | tipo (email/telefone), valor, whatsapp | Sim |
| `cad_cliente_historico` | descricao, created_at | Sim |
| `cad_cliente_tags` | tag | Sim |
| `cad_fornecedor_enderecos` | mesmos campos | Sim |
| `cad_fornecedor_contatos` | mesmos campos | Sim |
| `cad_vendedor_metas` | mes, meta_valor, realizado | Sim |
| `cad_transp_frete` | origem, destino, valor, prazo | Sim |

### 2.2 Integracao Bling → Cadastros

**🔴 GAP: Bling `/contatos` nunca e sincronizado com `cad_clientes` ou `cad_fornecedores`.**

A API do Bling retorna por contato:
```
id, nome, codigo, situacao, numeroDocumento, telefone, celular, tipo (C/F)
```

Mapeamento possivel:
| Bling | Cadastros |
|-------|-----------|
| `nome` | `nome` |
| `numeroDocumento` | `documento` |
| `telefone` / `celular` | `contatos[].valor` |
| `tipo` | `tipo` (C=cliente PF, F=fornecedor) |
| `situacao` | `status` |
| `codigo` | nao mapeado (campo extra) |

**Acao pendente:** Criar `POST /api/cadastros/sync/bling` que popula `cad_clientes` (tipo C) e `cad_fornecedores` (tipo F) a partir dos contatos Bling.

---

## 3. ESTOQUE — Fontes de Dados

### 3.1 Duas fontes de verdade conflitantes

| Fonte | Onde e usada |
|-------|-------------|
| **Bling API** (`GET /estoques/saldos/{idDeposito}`) | Pagina `/estoque` — le estoque em tempo real do Bling |
| **Tabela local** `estoque_lojas` | `GET /api/estoque/lojas` + `PUT /api/estoque/lojas` |

⚠️ **O sync de produtos (`sincronizar_produtos`) grava em `catalogo_produtos` e `anuncios`, mas NAO atualiza `estoque_lojas`.** A pagina `/estoque` le do Bling direto, a pagina `/produtos` le de `estoque_lojas` local. **Duas visoes diferentes do mesmo estoque.**

### 3.2 Lojas / Depositos

| Fonte | Campos |
|-------|--------|
| **Bling API** (`GET /depositos`) | `id`, `descricao`, `situacao`, `padrao`, `desconsiderarSaldo` |
| **Tabela local** `lojas` | `id`, `nome` (=descricao), `bling_id`, `bling_descricao`, `ativa` (=situacao=='A') |
| **Usado no frontend** | `id`, `nome`, `bling_id` (via `useStore()`) |
| **Nao usado** | `padrao`, `desconsiderarSaldo` do Bling |

### 3.3 Saldo de estoque por deposito

Bling retorna para `GET /estoques/saldos/{idDeposito}`:
```json
{
  "data": [{
    "produto": { "id": 123 },
    "saldoFisicoTotal": 50,
    "saldoVirtualTotal": 30
  }]
}
```

Frontend espera: `idProduto` + `saldo` / `saldoFisico` / `saldoVirtual`.

⚠️ **Possivel mismatch de shape:** o campo e `produto.id` (aninhado), nao `idProduto` (flat). Pode causar leitura de saldo como 0.

### 3.4 Campos de estoque nao expostos

O sync de produtos grava no `catalogo_produtos`:
- `estoque_minimo` — existe na tabela, **nao usado no frontend** (sem alertas)
- `estoque_maximo` — existe, **nao usado**
- `estoque_crossdocking` — existe, **nao usado**
- `estoque_localizacao` — existe, **nao usado**
- `controlar_estoque` — existe, **nao usado**

---

## 4. Resumo de GAPS — O que precisa ser corrigido

### 🔴 Critico (quebra funcionalidade)

| # | Gap | Impacto |
|---|-----|---------|
| 1 | CadastroTab nao coleta `preco` no form — push Bling always undefined | Preco nunca atualiza no Bling |
| 2 | `estoque_lojas` local vs Bling API — duas fontes de verdade | Estoque inconsistente entre modulos |
| 3 | Bling saldo aninhado (`produto.id`) vs flat esperado (`idProduto`) | Saldo pode ler como 0 |

### 🟡 Alto (dados disponiveis nao usados)

| # | Gap | Acao |
|---|-----|------|
| 4 | 14 campos do Bling no `catalogo_produtos` nunca exibidos | Adicionar ao CadastroTab: peso, dimensoes, tributacao, estoque min/max |
| 5 | Bling `/contatos` nunca sincronizado com cadastros | Criar `POST /api/cadastros/sync/bling` |
| 6 | Fornecedor `preco_custo` do Bling salvo mas nao usado | Exibir no detalhe do produto |
| 7 | `estoque_minimo` / `estoque_maximo` salvos mas sem alertas | Adicionar alertas visuais no estoque |

### 🟢 Baixo (melhorias)

| # | Gap | Acao |
|---|-----|------|
| 8 | Deposito `padrao` e `desconsiderarSaldo` do Bling nao usados | Expor no seletor de loja |
| 9 | Marcas e categorias como strings — sem tabela propria | Criar tabelas normalizadas |
| 10 | `margem_min` query param no `/api/produtos` parseado mas nao aplicado | Corrigir SQL |
