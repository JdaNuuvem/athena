# Plano: Recriar Componentes de Tab do Módulo Cadastros

## Objetivo
Recriar os 6 componentes de tab do módulo Cadastros com navegação horizontal + sidebar vertical para sub-items, integrados com API Flask já existente.

## Estrutura do Backend (cadastros.py)
- **Empresas**: cad_empresas, cad_multiempresa
- **Usuários**: cad_usuarios, cad_permissoes, cad_grupos, cad_historico_acessos
- **Clientes**: cad_clientes, cad_cliente_enderecos, cad_cliente_contatos, cad_cliente_historico, cad_cliente_tags
- **Fornecedores**: cad_fornecedores, cad_fornecedor_enderecos, cad_fornecedor_contatos, cad_fornecedor_historico, cad_fornecedor_tags
- **Transportadoras**: cad_transportadoras, cad_transp_frete, cad_transp_contatos
- **Vendedores**: cad_vendedores, cad_vendedor_metas

## Ações

### 1. Atualizar `web/src/app/cadastros/page.tsx`
- Implementar 6 tabs horizontais: Empresas, Usuários, Clientes, Fornecedores, Transportadoras, Vendedores
- Importar 6 componentes de tab
- Seguir padrão estilo RH (quando pronto) ou padrão Tailwind minimal

### 2. Criar `web/src/app/cadastros/_components/EmpresasTab.tsx`
- Sub-items: Lista, Multiempresa
- Usar SidebarLayout para navegação vertical
- CRUD básico (nome, cnpj, ie, im, regime_tributario, porte, tipo, endereco, telefone, email, status)
- Multiempresa: tabela de vínculos entre empresas (empresa_id, tipo_vinculo)

### 3. Criar `web/src/app/cadastros/_components/UsuariosTab.tsx`
- Sub-items: Lista, Permissões, Grupos, Histórico Acessos
- SidebarLayout + CRUD (nome, email, perfil, grupo_id, mfa_ativo, status)
- Permissões: tabela por perfil + módulo (api.cadPermissoes)
- Grupos: gestão de grupos e perfil padrão
- Histórico: log de acessos (usuario_id, acao, ip)

### 4. Criar `web/src/app/cadastros/_components/ClientesTab.tsx`
- Sub-items: Lista, Endereços, Contatos, Histórico, Tags
- SidebarLayout + CRUD (nome, tipo PF/PJ, documento, ie, im, limite_credito, score, status)
- Endereços, Contatos, Histórico, Tags: tabelas relacionais por cliente_id

### 5. Criar `web/src/app/cadastros/_components/FornecedoresTab.tsx`
- Sub-items: Lista, Endereços, Contatos, Histórico, Tags
- SidebarLayout + CRUD (nome, tipo, documento, ie, im, limite_credito, score, status)
- Similar estrutura de Clientes, com resumo de compras (api.cadFornecedorResumo)

### 6. Criar `web/src/app/cadastros/_components/TransportadorasTab.tsx`
- Sub-items: Lista, Frete, Contatos
- SidebarLayout + CRUD (nome, cnpj, frota, regiao, status)
- Frete: tabela de rotas (origem, destino, valor, prazo)
- Contatos: gestão de contatos por transportadora

### 7. Criar `web/src/app/cadastros/_components/VendedoresTab.tsx`
- Sub-items: Lista, Metas
- SidebarLayout + CRUD (nome, email, regiao, comissao_pct)
- Metas: gestão de metas mensais por vendedor (api.cadVendedorMetas)
- Comissão: resumo de comissões (api.cadVendedorComissao)

## API Cliente (já existe em web/src/lib/api.ts)
```typescript
api.cadList(tabela)
api.cadGet(tabela, id)
api.cadCreate(tabela, data)
api.cadUpdate(tabela, id, data)
api.cadDelete(tabela, id)
api.cadPermissoes()
api.cadVendedorComissao()
api.cadVendedorMetas(mes?)
api.cadFornecedorResumo()
```

## Estilo
- Tailwind CSS, tema dark (neutral-800/700/600/500/400/200/100)
- Indigo para destaque (indigo-600/20, indigo-300)
- Transições suaves
- Estados de loading/erro
- Confirmação de exclusão

## Validação
- `tsc --noEmit` (TypeScript compile check)
- Teste manual de CRUD em cada tab
- Navegação entre tabs e sub-items