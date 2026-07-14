import { getPrisma, disconnectPrisma } from '../src/shared/infrastructure/persistence/prisma-client'

const prisma = getPrisma()

const PERMISSIONS = [
  // Dashboard
  { code: 'dashboard:view', module: 'dashboard', action: 'view', description: 'Visualizar dashboard' },

  // Products
  { code: 'products:view', module: 'products', action: 'view', description: 'Visualizar produtos' },
  { code: 'products:create', module: 'products', action: 'create', description: 'Criar produtos' },
  { code: 'products:edit', module: 'products', action: 'edit', description: 'Editar produtos' },
  { code: 'products:delete', module: 'products', action: 'delete', description: 'Excluir produtos' },
  { code: 'products:export', module: 'products', action: 'export', description: 'Exportar produtos' },

  // Orders
  { code: 'orders:view', module: 'orders', action: 'view', description: 'Visualizar pedidos' },
  { code: 'orders:create', module: 'orders', action: 'create', description: 'Criar pedidos' },
  { code: 'orders:edit', module: 'orders', action: 'edit', description: 'Editar pedidos' },
  { code: 'orders:delete', module: 'orders', action: 'delete', description: 'Excluir pedidos' },
  { code: 'orders:approve', module: 'orders', action: 'approve', description: 'Aprovar pedidos' },
  { code: 'orders:export', module: 'orders', action: 'export', description: 'Exportar pedidos' },

  // Inventory
  { code: 'inventory:view', module: 'inventory', action: 'view', description: 'Visualizar estoque' },
  { code: 'inventory:create', module: 'inventory', action: 'create', description: 'Criar itens de estoque' },
  { code: 'inventory:edit', module: 'inventory', action: 'edit', description: 'Editar estoque' },
  { code: 'inventory:delete', module: 'inventory', action: 'delete', description: 'Excluir itens de estoque' },
  { code: 'inventory:export', module: 'inventory', action: 'export', description: 'Exportar estoque' },

  // Customers
  { code: 'customers:view', module: 'customers', action: 'view', description: 'Visualizar clientes' },
  { code: 'customers:create', module: 'customers', action: 'create', description: 'Criar clientes' },
  { code: 'customers:edit', module: 'customers', action: 'edit', description: 'Editar clientes' },
  { code: 'customers:delete', module: 'customers', action: 'delete', description: 'Excluir clientes' },
  { code: 'customers:export', module: 'customers', action: 'export', description: 'Exportar clientes' },

  // Financial
  { code: 'financial:view', module: 'financial', action: 'view', description: 'Visualizar financeiro' },
  { code: 'financial:create', module: 'financial', action: 'create', description: 'Criar registros financeiros' },
  { code: 'financial:edit', module: 'financial', action: 'edit', description: 'Editar financeiro' },
  { code: 'financial:delete', module: 'financial', action: 'delete', description: 'Excluir registros financeiros' },
  { code: 'financial:approve', module: 'financial', action: 'approve', description: 'Aprovar transações' },
  { code: 'financial:export', module: 'financial', action: 'export', description: 'Exportar financeiro' },

  // Fiscal
  { code: 'fiscal:view', module: 'fiscal', action: 'view', description: 'Visualizar fiscal' },
  { code: 'fiscal:create', module: 'fiscal', action: 'create', description: 'Criar documentos fiscais' },
  { code: 'fiscal:edit', module: 'fiscal', action: 'edit', description: 'Editar fiscal' },
  { code: 'fiscal:delete', module: 'fiscal', action: 'delete', description: 'Excluir documentos fiscais' },
  { code: 'fiscal:export', module: 'fiscal', action: 'export', description: 'Exportar fiscal' },

  // CRM
  { code: 'crm:view', module: 'crm', action: 'view', description: 'Visualizar CRM' },
  { code: 'crm:create', module: 'crm', action: 'create', description: 'Criar registros CRM' },
  { code: 'crm:edit', module: 'crm', action: 'edit', description: 'Editar CRM' },
  { code: 'crm:delete', module: 'crm', action: 'delete', description: 'Excluir registros CRM' },

  // Services / Atendimento
  { code: 'services:view', module: 'services', action: 'view', description: 'Visualizar atendimentos' },
  { code: 'services:create', module: 'services', action: 'create', description: 'Criar atendimentos' },
  { code: 'services:edit', module: 'services', action: 'edit', description: 'Editar atendimentos' },
  { code: 'services:delete', module: 'services', action: 'delete', description: 'Excluir atendimentos' },

  // HR
  { code: 'hr:view', module: 'hr', action: 'view', description: 'Visualizar RH' },
  { code: 'hr:create', module: 'hr', action: 'create', description: 'Criar registros RH' },
  { code: 'hr:edit', module: 'hr', action: 'edit', description: 'Editar RH' },
  { code: 'hr:delete', module: 'hr', action: 'delete', description: 'Excluir registros RH' },

  // Purchasing / Compras
  { code: 'purchasing:view', module: 'purchasing', action: 'view', description: 'Visualizar compras' },
  { code: 'purchasing:create', module: 'purchasing', action: 'create', description: 'Criar compras' },
  { code: 'purchasing:edit', module: 'purchasing', action: 'edit', description: 'Editar compras' },
  { code: 'purchasing:delete', module: 'purchasing', action: 'delete', description: 'Excluir compras' },
  { code: 'purchasing:approve', module: 'purchasing', action: 'approve', description: 'Aprovar compras' },

  // Manufacturing / Produção
  { code: 'manufacturing:view', module: 'manufacturing', action: 'view', description: 'Visualizar produção' },
  { code: 'manufacturing:create', module: 'manufacturing', action: 'create', description: 'Criar ordens de produção' },
  { code: 'manufacturing:edit', module: 'manufacturing', action: 'edit', description: 'Editar produção' },
  { code: 'manufacturing:delete', module: 'manufacturing', action: 'delete', description: 'Excluir ordens de produção' },

  // Documents
  { code: 'documents:view', module: 'documents', action: 'view', description: 'Visualizar documentos' },
  { code: 'documents:create', module: 'documents', action: 'create', description: 'Criar documentos' },
  { code: 'documents:edit', module: 'documents', action: 'edit', description: 'Editar documentos' },
  { code: 'documents:delete', module: 'documents', action: 'delete', description: 'Excluir documentos' },

  // Automations
  { code: 'automations:view', module: 'automations', action: 'view', description: 'Visualizar automações' },
  { code: 'automations:create', module: 'automations', action: 'create', description: 'Criar automações' },
  { code: 'automations:edit', module: 'automations', action: 'edit', description: 'Editar automações' },
  { code: 'automations:delete', module: 'automations', action: 'delete', description: 'Excluir automações' },

  // Workflows
  { code: 'workflows:view', module: 'workflows', action: 'view', description: 'Visualizar workflows' },
  { code: 'workflows:create', module: 'workflows', action: 'create', description: 'Criar workflows' },
  { code: 'workflows:edit', module: 'workflows', action: 'edit', description: 'Editar workflows' },
  { code: 'workflows:delete', module: 'workflows', action: 'delete', description: 'Excluir workflows' },
  { code: 'workflows:trigger', module: 'workflows', action: 'trigger', description: 'Executar workflows' },

  // Integrations
  { code: 'integrations:view', module: 'integrations', action: 'view', description: 'Visualizar integrações' },
  { code: 'integrations:create', module: 'integrations', action: 'create', description: 'Criar integrações' },
  { code: 'integrations:edit', module: 'integrations', action: 'edit', description: 'Editar integrações' },
  { code: 'integrations:delete', module: 'integrations', action: 'delete', description: 'Excluir integrações' },
  { code: 'integrations:manage', module: 'integrations', action: 'manage', description: 'Gerenciar integrações' },

  // Reports
  { code: 'reports:view', module: 'reports', action: 'view', description: 'Visualizar relatórios' },
  { code: 'reports:create', module: 'reports', action: 'create', description: 'Criar relatórios' },
  { code: 'reports:edit', module: 'reports', action: 'edit', description: 'Editar relatórios' },
  { code: 'reports:delete', module: 'reports', action: 'delete', description: 'Excluir relatórios' },
  { code: 'reports:export', module: 'reports', action: 'export', description: 'Exportar relatórios' },

  // Agents
  { code: 'agents:view', module: 'agents', action: 'view', description: 'Visualizar agentes' },
  { code: 'agents:manage', module: 'agents', action: 'manage', description: 'Gerenciar agentes' },

  // Settings
  { code: 'settings:view', module: 'settings', action: 'view', description: 'Visualizar configurações' },
  { code: 'settings:manage', module: 'settings', action: 'manage', description: 'Gerenciar configurações' },

  // Users
  { code: 'users:view', module: 'users', action: 'view', description: 'Visualizar usuários' },
  { code: 'users:create', module: 'users', action: 'create', description: 'Criar usuários' },
  { code: 'users:edit', module: 'users', action: 'edit', description: 'Editar usuários' },
  { code: 'users:delete', module: 'users', action: 'delete', description: 'Excluir usuários' },
  { code: 'users:manage', module: 'users', action: 'manage', description: 'Gerenciar usuários' },

  // Roles
  { code: 'roles:view', module: 'roles', action: 'view', description: 'Visualizar cargos' },
  { code: 'roles:create', module: 'roles', action: 'create', description: 'Criar cargos' },
  { code: 'roles:edit', module: 'roles', action: 'edit', description: 'Editar cargos' },
  { code: 'roles:delete', module: 'roles', action: 'delete', description: 'Excluir cargos' },
  { code: 'roles:manage', module: 'roles', action: 'manage', description: 'Gerenciar cargos' },

  // PDV
  { code: 'pdv:view', module: 'pdv', action: 'view', description: 'Visualizar PDV' },
  { code: 'pdv:manage', module: 'pdv', action: 'manage', description: 'Operar PDV' },

  // BI
  { code: 'bi:view', module: 'bi', action: 'view', description: 'Visualizar BI' },
  { code: 'bi:create', module: 'bi', action: 'create', description: 'Criar análises BI' },
  { code: 'bi:edit', module: 'bi', action: 'edit', description: 'Editar BI' },
  { code: 'bi:delete', module: 'bi', action: 'delete', description: 'Excluir análises BI' },

  // Cadastros
  { code: 'registrations:view', module: 'registrations', action: 'view', description: 'Visualizar cadastros' },
  { code: 'registrations:create', module: 'registrations', action: 'create', description: 'Criar cadastros' },
  { code: 'registrations:edit', module: 'registrations', action: 'edit', description: 'Editar cadastros' },
  { code: 'registrations:delete', module: 'registrations', action: 'delete', description: 'Excluir cadastros' },
]

const VIEW_ONLY = PERMISSIONS.filter(p => p.action === 'view')
const OPERATOR_EXTRA = PERMISSIONS.filter(p => ['create', 'edit', 'export'].includes(p.action))
const ALL = PERMISSIONS

async function main() {
  console.log('🔐 Seeding RBAC...\n')

  // === Roles ===
  const roles = [
    { id: 'ROLE-ADMIN', name: 'admin', description: 'Acesso total ao sistema', isSystem: true },
    { id: 'ROLE-OPERATOR', name: 'operator', description: 'Acesso operacional (CRUD sem exclusão)', isSystem: true },
    { id: 'ROLE-VIEWER', name: 'viewer', description: 'Acesso somente leitura', isSystem: true },
  ]
  for (const r of roles) {
    await prisma.role.upsert({ where: { name: r.name }, create: r, update: {} })
  }
  console.log(`  ${roles.length} roles`)

  // === Permissions ===
  let created = 0
  for (const p of PERMISSIONS) {
    await prisma.permission.upsert({
      where: { code: p.code },
      create: { id: `PERM-${p.code.replace(/:/g, '-')}`, ...p },
      update: {},
    })
    created++
  }
  console.log(`  ${created} permissions`)

  // === Role-Permission assignments ===
  const allPermissions = await prisma.permission.findMany()

  // Admin: ALL permissions
  const adminRole = await prisma.role.findUnique({ where: { name: 'admin' } })
  if (adminRole) {
    await prisma.rolePermission.deleteMany({ where: { roleId: adminRole.id } })
    await prisma.rolePermission.createMany({
      data: allPermissions.map(p => ({ roleId: adminRole.id, permissionId: p.id })),
    })
  }

  // Operator: view + create + edit + export (no delete, no approve, no manage for sensitive modules)
  const operatorRole = await prisma.role.findUnique({ where: { name: 'operator' } })
  if (operatorRole) {
    await prisma.rolePermission.deleteMany({ where: { roleId: operatorRole.id } })
    const operatorPerms = allPermissions.filter(p => {
      const action = p.code.split(':')[1]
      return ['view', 'create', 'edit', 'export', 'trigger'].includes(action)
    })
    await prisma.rolePermission.createMany({
      data: operatorPerms.map(p => ({ roleId: operatorRole.id, permissionId: p.id })),
    })
  }

  // Viewer: view only
  const viewerRole = await prisma.role.findUnique({ where: { name: 'viewer' } })
  if (viewerRole) {
    await prisma.rolePermission.deleteMany({ where: { roleId: viewerRole.id } })
    const viewerPerms = allPermissions.filter(p => p.code.endsWith(':view'))
    await prisma.rolePermission.createMany({
      data: viewerPerms.map(p => ({ roleId: viewerRole.id, permissionId: p.id })),
    })
  }

  console.log(`  role-permission assignments done`)

  // === Users ===
  await prisma.userRole.deleteMany()
  await prisma.user.deleteMany()

  const { hashPassword } = await import('../src/shared/infrastructure/auth/users')

  const users = [
    { id: 'USER-001', email: 'admin@athena.io', passwordHash: hashPassword('athena-admin-2026'), name: 'Administrador', active: true },
    { id: 'USER-002', email: 'operator@athena.io', passwordHash: hashPassword('athena-op-2026'), name: 'Operador', active: true },
    { id: 'USER-003', email: 'viewer@athena.io', passwordHash: hashPassword('athena-view-2026'), name: 'Visualizador', active: true },
  ]
  for (const u of users) {
    await prisma.user.create({ data: u })
  }

  // Assign roles to users
  await prisma.userRole.createMany({
    data: [
      { userId: 'USER-001', roleId: adminRole!.id },
      { userId: 'USER-002', roleId: operatorRole!.id },
      { userId: 'USER-003', roleId: viewerRole!.id },
    ],
  })
  console.log(`  ${users.length} users with roles`)

  console.log('\n✅ RBAC seed completo.\n')
}

main()
  .catch(console.error)
  .finally(async () => { await disconnectPrisma() })
