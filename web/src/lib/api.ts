const API_BASE = "";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const method = options?.method || "GET";
  if (method !== "GET" && method !== "HEAD") headers["Content-Type"] = "application/json";

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

import type {
  Agent,
  KPIOverview,
  Product,
  BlingProduct,
  BlingOrder,
  BlingInvoice,
  BlingReceivable,
  BlingConfig,
  BlingStatus,
  BlingDeposito,
  BlingEstoqueSaldo,
  BlingResumoVendas,
  BlingWebhook,
  Integration,
} from "@/lib/types/domain";

export const api = {
  // Auth
  login: (email: string, password: string) =>
    request<{ token: string; refreshToken: string; expiresIn: number; user: { id: string; name: string; role: string }; permissions: string[] }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  me: () => request<{ id: string; name: string; role: string; roles: string[]; permissions: string[] }>("/api/auth/me"),

  // RBAC
  roles: () => request<{ roles: Array<{ id: string; name: string; description: string | null; active: boolean; isSystem: boolean; permissionCodes: string[]; createdAt: string }> }>("/api/roles"),
  permissions: () => request<{ permissions: Array<{ id: string; code: string; module: string; action: string; description: string | null }> }>("/api/permissions"),
  rolesUpdatePermissions: (roleId: string, permissionIds: string[]) =>
    request<{ roleId: string; permissionCodes: string[] }>(`/api/roles/${roleId}/permissions`, {
      method: "PUT",
      body: JSON.stringify({ permissionIds }),
    }),

  // Health
  health: () => request<{ status: string; agents: Record<string, number>; infrastructure: Record<string, { connected: boolean }> }>("/api/health"),

  agentsList: () => request<{ agents: Agent[] }>("/api/agents"),

  // AG-04 - Planejador
  planoDiario: (data?: string) =>
    request<{ plano: unknown[]; capacidade_utilizada: number; total_pedidos: number }>("/api/agent/ag_04_planejador/plano_diario", {
      method: "POST",
      body: JSON.stringify({ data }),
    }),

  adicionarPedido: (pedido: { sku: string; quantidade: number; prazo: string; prioridade?: number; cliente_id?: string }) =>
    request<Record<string, unknown>>("/api/agent/ag_04_planejador/adicionar_pedido", {
      method: "POST",
      body: JSON.stringify(pedido),
    }),

  // AG-05 - Industrial
  relatorioIndustrial: () => request<Record<string, unknown>>("/api/agent/ag_05_industrial/relatorio"),

  oee: (machineId: string) => request<Record<string, unknown>>(`/api/agent/ag_05_industrial/oee/${machineId}`),

  // AG-06 - Telegram
  processarMensagem: (user_id: string, mensagem: string, nome?: string) =>
    request<Record<string, unknown>>("/api/agent/ag_06_telegram/processar", {
      method: "POST",
      body: JSON.stringify({ user_id, mensagem, nome }),
    }),

  // AG-07 - Laboratório
  analisarProduto: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>("/api/agent/ag_07_laboratorio/analisar", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Config
  getConfig: () => request<Record<string, Record<string, string>>>("/api/config"),

  setConfig: (sistema: string, data: Record<string, string>) =>
    request<{ success: boolean }>(`/api/config/${sistema}`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  configStatus: () =>
    request<{ telegram: boolean; bling: boolean; shopee: boolean }>("/api/config/status"),

  // Integrations
  integrations: () =>
    request<Array<{ id: string; name: string; category: string; status: string }>>("/api/integrations"),

  // Industrial Dashboard
  moldesDashboard: () =>
    request<{ moldes_criticos: unknown[]; jobs_cnc_ativos: unknown[]; eventos_recentes: unknown[] }>("/api/moldes/dashboard"),

  qualidadeDefeitos: (periodo = 30) =>
    request<{ lotes_inspecionados: number; taxa_reprovacao_pct: number; por_sku: unknown[] }>(`/api/qualidade/taxa_defeitos?periodo=${periodo}`),

  manutencaoPendentes: () =>
    request<{ total: number; alertas_ativos: number; kpis: Record<string, number> }>("/api/manutencao/pendentes"),

  telegramStats: () =>
    request<{ total_clientes: number; total_pedidos: number; faturamento_total: number; ticket_medio_geral: number }>("/api/agent/ag_06_telegram/stats"),

  // Bling
  blingStatus: () => request<{ autenticado: boolean; client_id_setado: boolean; auth_url: string }>("/api/bling/status"),
  blingSync: () => request<{ produtos: { sincronizados: number; erro?: string }; pedidos: { sincronizados: number; erro?: string } }>("/api/bling/sync", { method: "POST" }),
  blingSyncProducts: () => request<{ count: number; errors: string[] }>("/api/bling/sync/products", { method: "POST" }),
  blingSyncOrders: () => request<{ count: number; errors: string[] }>("/api/bling/sync/orders", { method: "POST" }),
  blingSyncInvoices: () => request<{ count: number; errors: string[] }>("/api/bling/sync/invoices", { method: "POST" }),
  blingSyncReceivables: () => request<{ count: number; errors: string[] }>("/api/bling/sync/receivables", { method: "POST" }),
  blingProducts: () => request<BlingProduct[]>("/api/bling/products"),
  blingOrders: () => request<BlingOrder[]>("/api/bling/orders"),
  blingInvoices: () => request<BlingInvoice[]>("/api/bling/invoices"),
  blingReceivables: () => request<BlingReceivable[]>("/api/bling/receivables"),
  blingConfig: () => request<BlingConfig>("/api/bling/config"),
  blingSetConfig: (data: Record<string, unknown>) => request<{ success: boolean }>("/api/bling/config", { method: "PUT", body: JSON.stringify(data) }),
  blingTest: () => request<{ success: boolean; message: string }>("/api/bling/test", { method: "POST" }),
  blingAuthUrl: () => request<{ auth_url: string; autenticado: boolean }>("/api/bling/auth"),
  blingRegisterWebhook: (tipo?: string, url?: string) =>
    request<Record<string, unknown>>("/api/bling/webhook/registrar", {
      method: "POST",
      body: JSON.stringify({ tipo: tipo || "pedido", url }),
    }),

  // Shopee
  shopeeSync: () => request<{ total: number; itens: unknown[] }>("/api/shopee/produtos/sincronizar", { method: "POST" }),

  // Hermes
  hermesAgents: () => request<unknown[]>("/api/hermes/agents"),
  hermesOpportunities: () => request<unknown[]>("/api/hermes/opportunities"),
  hermesAlerts: () => request<unknown[]>("/api/hermes/alerts"),
  hermesExecutions: () => request<unknown[]>("/api/hermes/executions"),
  hermesExecute: (agent_id: string, action: string, params?: Record<string, unknown>) =>
    request<{ success: boolean; data?: unknown }>("/api/hermes/execute", {
      method: "POST",
      body: JSON.stringify({ agent_id, action, params }),
    }),

  // Produtos
  listarProdutos: (params?: { busca?: string; loja?: string; pagina?: number; variacoes?: boolean }) => {
    const q = new URLSearchParams();
    if (params?.busca) q.set("busca", params.busca);
    if (params?.loja) q.set("loja", params.loja);
    if (params?.pagina) q.set("pagina", String(params.pagina));
    if (params?.variacoes) q.set("variacoes", "1");
    return request<{ produtos: unknown[]; total: number; pagina: number }>(`/api/produtos?${q}`);
  },

  detalheProduto: (sku: string) => request<Record<string, unknown>>(`/api/produtos/${sku}`),

  // Lojas
  lojas: (periodo?: number) =>
    request<unknown[]>(`/api/lojas${periodo ? `?periodo=${periodo}` : ""}`),
  lojasManage: () => request<{ lojas: Array<{ id: number; nome: string; ativa: boolean }> }>("/api/lojas/manage"),
  lojasCriar: (nome: string) => request<{ loja: { id: number; nome: string } }>("/api/lojas/manage", { method: "POST", body: JSON.stringify({ nome }) }),
  lojasAtualizar: (id: number, nome: string) => request<{ success: boolean }>(`/api/lojas/manage/${id}`, { method: "PUT", body: JSON.stringify({ nome }) }),
  lojasDeletar: (id: number) => request<{ success: boolean }>(`/api/lojas/manage/${id}`, { method: "DELETE" }),

  // KPI
  kpiOverview: (periodo?: number) =>
    request<Record<string, unknown>>(`/api/kpi/overview${periodo ? `?periodo=${periodo}` : ""}`),

  // Chat
  chat: (mensagem: string, user_id?: string, nome?: string) =>
    request<{ resposta: string; agente: string; intencao: string }>("/api/hermes/chat", {
      method: "POST",
      body: JSON.stringify({ mensagem, user_id: user_id || "anon", nome: nome || "Visitante" }),
    }),

  // Shopee Ads
  shopeeAdsCampaigns: () => request<unknown[]>("/api/shopee-ads/campaigns"),

  // ML
  mlStatus: () => request<{ modelo_treinado: boolean }>("/api/ml/status"),
  mlTreinar: () => request<Record<string, unknown>>("/api/ml/treinar", { method: "POST" }),

  // RH
  rhList: (tabela: string) => request<{ data: unknown[] }>(`/api/rh/${tabela}`),
  rhGet: (tabela: string, id: number) => request<Record<string, unknown>>(`/api/rh/${tabela}/${id}`),
  rhCreate: (tabela: string, data: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/api/rh/${tabela}`, { method: "POST", body: JSON.stringify(data) }),
  rhUpdate: (tabela: string, id: number, data: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/api/rh/${tabela}/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  rhDelete: (tabela: string, id: number) =>
    request<{ success: boolean }>(`/api/rh/${tabela}/${id}`, { method: "DELETE" }),
  rhPontoPorData: (data: string) => request<{ data: unknown[] }>(`/api/rh/ponto/data/${data}`),
  rhFolhaResumo: (mes: string) => request<Record<string, number>>(`/api/rh/folha/resumo/${mes}`),
  rhBeneficiosResumo: () =>
    request<{ total_empresa: number; total_funcionario: number; beneficios: unknown[] }>("/api/rh/beneficios/resumo"),

  // Cadastros
  cadList: (tabela: string) => request<{ data: unknown[] }>(`/api/cadastros/${tabela}`),
  cadGet: (tabela: string, id: number) => request<Record<string, unknown>>(`/api/cadastros/${tabela}/${id}`),
  cadCreate: (tabela: string, data: Record<string, unknown>) => request<Record<string, unknown>>(`/api/cadastros/${tabela}`, { method: "POST", body: JSON.stringify(data) }),
  cadUpdate: (tabela: string, id: number, data: Record<string, unknown>) => request<Record<string, unknown>>(`/api/cadastros/${tabela}/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  cadDelete: (tabela: string, id: number) => request<{ success: boolean }>(`/api/cadastros/${tabela}/${id}`, { method: "DELETE" }),
  cadPermissoes: () => request<{ data: unknown[] }>("/api/cadastros/permissoes/perfil"),
  cadVendedorComissao: () => request<{ vendedores: unknown[]; total_comissoes: number }>("/api/cadastros/vendedores/comissao"),
  cadVendedorMetas: (mes?: string) => request<{ data: unknown[] }>(`/api/cadastros/vendedores/metas${mes ? "/" + mes : ""}`),
  cadFornecedorResumo: () => request<{ data: unknown[] }>("/api/cadastros/fornecedores/resumo"),

  // Financeiro
  finList: (tabela: string) => request<{ data: unknown[] }>(`/api/financeiro/${tabela}`),
  finGet: (tabela: string, id: number) => request<Record<string, unknown>>(`/api/financeiro/${tabela}/${id}`),
  finCreate: (tabela: string, data: Record<string, unknown>) => request<Record<string, unknown>>(`/api/financeiro/${tabela}`, { method: "POST", body: JSON.stringify(data) }),
  finUpdate: (tabela: string, id: number, data: Record<string, unknown>) => request<Record<string, unknown>>(`/api/financeiro/${tabela}/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  finDelete: (tabela: string, id: number) => request<{ success: boolean }>(`/api/financeiro/${tabela}/${id}`, { method: "DELETE" }),
  finFluxoResumo: (dias?: number) => request<{ resumo: Record<string, number>; diario: unknown[] }>(`/api/financeiro/fluxo_caixa/resumo${dias ? "?dias=" + dias : ""}`),
  finDREResumo: (mes?: string) => request<{ receitas: number; despesas: number; resultado: number; lucro: boolean; items: unknown[] }>(`/api/financeiro/dre/resumo${mes ? "/" + mes : ""}`),
};

// Types — SSOT re-exports from lib/types/domain (removes duplicate definitions)
export type {
  Agent,
  KPIOverview,
  Product,
  BlingProduct,
  BlingOrder,
  BlingInvoice,
  BlingReceivable,
  BlingConfig,
  BlingStatus,
  BlingDeposito,
  BlingEstoqueSaldo,
  BlingResumoVendas,
  BlingWebhook,
  Integration,
} from "@/lib/types/domain";

export interface BlingProduto {
  id: number;
  codigo: string;
  descricao: string;
  preco: number;
  situacao: string;
  [key: string]: unknown;
}

export interface BlingProdutosResponse {
  data: BlingProduto[];
  error?: string;
}

// ── Bling API Methods (standalone, usam fetch direto) ──

export async function getBlingStatus(): Promise<BlingStatus> {
  const res = await fetch("/api/bling/status");
  return res.json();
}

export async function getBlingAuthUrl(): Promise<{ url: string }> {
  const res = await fetch("/api/bling/auth");
  return res.json();
}

export async function listarBlingProdutos(
  pagina = 1,
  limite = 100
): Promise<BlingProdutosResponse> {
  const res = await fetch(`/api/bling/produtos?pagina=${pagina}&limite=${limite}`);
  if (!res.ok) return { data: [], error: `HTTP ${res.status}` };
  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("application/json")) return { data: [], error: "resposta nao-JSON" };
  return res.json();
}

export async function criarBlingProduto(
  dados: Record<string, unknown>
): Promise<{ data?: BlingProduto; error?: string }> {
  const res = await fetch("/api/bling/produtos", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(dados),
  });
  return res.json();
}

export async function atualizarBlingProduto(
  id: number,
  dados: Record<string, unknown>
): Promise<{ data?: BlingProduto; error?: string }> {
  const res = await fetch(`/api/bling/produtos/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(dados),
  });
  return res.json();
}

export async function deletarBlingProduto(
  id: number
): Promise<{ success?: boolean; error?: string }> {
  const res = await fetch(`/api/bling/produtos/${id}`, { method: "DELETE" });
  return res.json();
}

export async function atualizarSituacaoProdutos(
  ids: number[],
  situacao: string
): Promise<{ success?: boolean; error?: string }> {
  const res = await fetch("/api/bling/produtos/situacoes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids, situacao }),
  });
  return res.json();
}

export async function sincronizarBlingProdutos(): Promise<{
  sincronizados?: number;
  erro?: string;
}> {
  const res = await fetch("/api/bling/produtos/sincronizar", { method: "POST" });
  return res.json();
}

export async function listarBlingDepositos(
  pagina = 1,
  limite = 100
): Promise<{ data: BlingDeposito[] }> {
  const res = await fetch(`/api/bling/depositos?pagina=${pagina}&limite=${limite}`);
  if (!res.ok) return { data: [] };
  return res.json().catch(() => ({ data: [] }));
}

export async function obterSaldoDeposito(
  idDeposito: number,
  idsProdutos?: number[]
): Promise<{ data: BlingEstoqueSaldo[] }> {
  const params = new URLSearchParams();
  idsProdutos?.forEach((id) => params.append("idsProdutos[]", String(id)));
  const query = params.toString();
  const res = await fetch(`/api/bling/estoque/${idDeposito}${query ? "?" + query : ""}`);
  return res.json();
}

export async function atualizarEstoqueDeposito(dados: {
  idDeposito: number;
  idProduto: number;
  operacao: string;
  quantidade: number;
  preco?: number;
}): Promise<{ success?: boolean; error?: string }> {
  const res = await fetch("/api/bling/estoque", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(dados),
  });
  return res.json();
}

export async function listarBlingPedidos(
  pagina = 1,
  limite = 100
): Promise<{ data: unknown[]; error?: string }> {
  const res = await fetch(`/api/bling/vendas?pagina=${pagina}&limite=${limite}`);
  return res.json();
}

export async function sincronizarBlingPedidos(): Promise<{
  sincronizados?: number;
  erro?: string;
}> {
  const res = await fetch("/api/bling/vendas/sincronizar", { method: "POST" });
  return res.json();
}

export async function resumoVendasBling(
  dias = 30
): Promise<BlingResumoVendas> {
  const res = await fetch(`/api/bling/vendas/resumo?dias=${dias}`);
  return res.json();
}

export async function listarContasReceber(
  pagina = 1,
  limite = 100
): Promise<{ data: unknown[]; error?: string }> {
  const res = await fetch(`/api/bling/financeiro/contas-receber?pagina=${pagina}&limite=${limite}`);
  return res.json();
}

export async function listarNotasFiscais(
  pagina = 1,
  limite = 100
): Promise<{ data: unknown[]; error?: string }> {
  const res = await fetch(`/api/bling/financeiro/notas-fiscais?pagina=${pagina}&limite=${limite}`);
  return res.json();
}

export async function listarBlingWebhooks(
  pagina = 1,
  limite = 100
): Promise<{ data: BlingWebhook[] }> {
  const res = await fetch(`/api/bling/webhooks?pagina=${pagina}&limite=${limite}`);
  return res.json();
}

export async function criarBlingWebhook(
  evento: string,
  url: string
): Promise<{ data?: BlingWebhook; error?: string }> {
  const res = await fetch("/api/bling/webhooks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ evento, url }),
  });
  return res.json();
}

export async function deletarBlingWebhook(
  id: number
): Promise<{ success?: boolean; error?: string }> {
  const res = await fetch(`/api/bling/webhooks/${id}`, { method: "DELETE" });
  return res.json();
}

export async function listarBlingEventos(): Promise<{ total: number; eventos: string[] }> {
  const res = await fetch("/webhook/bling/eventos");
  return res.json();
}

export async function listarBlingNotificacoes(
  pagina = 1,
  limite = 100
): Promise<{ data: unknown[] }> {
  const res = await fetch(`/api/bling/notificacoes?pagina=${pagina}&limite=${limite}`);
  return res.json();
}

export async function confirmarLeituraNotificacao(
  id: number
): Promise<{ success?: boolean; error?: string }> {
  const res = await fetch(`/api/bling/notificacoes/${id}`, {
    method: "PATCH",
  });
  return res.json();
}


export async function listarBlingContatos(pagina = 1, limite = 100, tipo = ""): Promise<{ data: unknown[] }> {
  const params = new URLSearchParams({ pagina: String(pagina), limite: String(limite) });
  if (tipo) params.set("tipo", tipo);
  const res = await fetch("/api/bling/contatos?" + params);
  return res.json();
}

export async function listarBlingCategorias(pagina = 1, limite = 100): Promise<{ data: unknown[] }> {
  const res = await fetch("/api/bling/categorias?pagina=" + pagina + "&limite=" + limite);
  return res.json();
}

export async function getBlingPedidoDetalhe(id: number): Promise<{ data: unknown }> {
  const res = await fetch("/api/bling/vendas/" + id);
  return res.json();
}

export async function listarBlingContasPagar(pagina = 1, limite = 100): Promise<{ data: unknown[] }> {
  const res = await fetch("/api/bling/financeiro/contas-pagar?pagina=" + pagina + "&limite=" + limite);
  return res.json();
}

// ── NFe Download ──

export function baixarNFeXML(idNota: number): void {
  window.open(`/api/bling/financeiro/notas-fiscais/${idNota}/xml`, "_blank");
}

export function abrirNFeDANFE(idNota: number): void {
  window.open(`/api/bling/financeiro/notas-fiscais/${idNota}/danfe`, "_blank");
}

// ── Fiscal ──

export async function fiscalDashboard(): Promise<import("@/lib/types/domain").FiscalDashboard> {
  const res = await fetch("/api/fiscal/dashboard");
  return res.json();
}

export async function fiscalList(tabela: string): Promise<{ data: unknown[] }> {
  const res = await fetch(`/api/fiscal/${tabela}`);
  return res.json();
}

export async function fiscalGet(tabela: string, id: number): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/fiscal/${tabela}/${id}`);
  return res.json();
}

export async function fiscalCreate(tabela: string, data: Record<string, unknown>): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/fiscal/${tabela}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function fiscalUpdate(tabela: string, id: number, data: Record<string, unknown>): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/fiscal/${tabela}/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function fiscalDelete(tabela: string, id: number): Promise<{ success: boolean }> {
  const res = await fetch(`/api/fiscal/${tabela}/${id}`, { method: "DELETE" });
  return res.json();
}

export async function fiscalCalcularTributos(notaId: number): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/fiscal/tributos/calcular/${notaId}`);
  return res.json();
}

export async function fiscalObrigacoesProximas(dias?: number): Promise<{ data: unknown[] }> {
  const res = await fetch(`/api/fiscal/obrigacoes/proximas${dias ? "?dias=" + dias : ""}`);
  return res.json();
}

export async function fiscalObrigacoesAtrasadas(): Promise<{ data: unknown[] }> {
  const res = await fetch("/api/fiscal/obrigacoes/atrasadas");
  return res.json();
}

export async function fiscalBaixarObrigacao(id: number): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/fiscal/obrigacoes/${id}/baixar`, { method: "POST" });
  return res.json();
}

export async function fiscalSyncNotasFiscais(pagina?: number, limite?: number): Promise<{ sync: number; error?: string }> {
  const res = await fetch("/api/fiscal/sync/notas-fiscais", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pagina: pagina || 1, limite: limite || 100 }),
  });
  return res.json();
}

export async function fiscalSyncContasReceber(pagina?: number, limite?: number): Promise<{ sync: number; error?: string }> {
  const res = await fetch("/api/fiscal/sync/contas-receber", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pagina: pagina || 1, limite: limite || 100 }),
  });
  return res.json();
}

export async function fiscalSyncContasPagar(pagina?: number, limite?: number): Promise<{ sync: number; error?: string }> {
  const res = await fetch("/api/fiscal/sync/contas-pagar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pagina: pagina || 1, limite: limite || 100 }),
  });
  return res.json();
}

export async function fiscalSyncTudo(): Promise<{ notas_fiscais: number; contas_receber: number; contas_pagar: number }> {
  const res = await fetch("/api/fiscal/sync/tudo", { method: "POST" });
  return res.json();
}

export async function fiscalNFItens(notaId: number): Promise<{ data: unknown[] }> {
  const res = await fetch(`/api/fiscal/notas-fiscais/${notaId}/itens`);
  return res.json();
}

export async function fiscalNFImpostos(notaId: number): Promise<{ data: unknown[] }> {
  const res = await fetch(`/api/fiscal/notas-fiscais/${notaId}/impostos`);
  return res.json();
}

// ── Vendas ──

export async function vendasDashboard(dias?: number): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/vendas/dashboard${dias ? "?dias=" + dias : ""}`);
  return res.json();
}

export async function vendasList(tabela: string, params?: Record<string, string>): Promise<{ data: unknown[] }> {
  const q = new URLSearchParams(params || {});
  const res = await fetch(`/api/vendas/${tabela}${q.toString() ? "?" + q : ""}`);
  return res.json();
}

export async function vendasGet(tabela: string, id: number): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/vendas/${tabela}/${id}`);
  return res.json();
}

export async function vendasCreate(tabela: string, data: Record<string, unknown>): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/vendas/${tabela}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function vendasUpdate(tabela: string, id: number, data: Record<string, unknown>): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/vendas/${tabela}/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function vendasDelete(tabela: string, id: number): Promise<{ success: boolean }> {
  const res = await fetch(`/api/vendas/${tabela}/${id}`, { method: "DELETE" });
  return res.json();
}

export async function vendasCriarPedido(dados: Record<string, unknown>): Promise<Record<string, unknown>> {
  const res = await fetch("/api/vendas/pedido", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(dados),
  });
  return res.json();
}

export async function vendasDetalhePedido(id: number): Promise<{ pedido: Record<string, unknown>; itens: unknown[]; pagamentos: unknown[]; historico: unknown[] }> {
  const res = await fetch(`/api/vendas/pedido/${id}`);
  return res.json();
}

export async function vendasAtualizarStatus(id: number, status: string, usuario?: string): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/vendas/pedido/${id}/status`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, usuario }),
  });
  return res.json();
}

export async function vendasSyncBling(pagina?: number, limite?: number): Promise<{ sync: number; error?: string }> {
  const res = await fetch("/api/vendas/sync/bling", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pagina: pagina || 1, limite: limite || 100 }),
  });
  return res.json();
}

// ── Integracoes / SSOT ──

export async function catalogoListar(): Promise<{ data: unknown[] }> {
  const res = await fetch("/api/catalogo");
  return res.json();
}
export async function catalogoBuscarSku(sku: string): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/catalogo/sku/${sku}`);
  return res.json();
}
export async function integrVincularClientes(): Promise<{ vinculados: number }> {
  const res = await fetch("/api/integracoes/vincular-clientes", { method: "POST" });
  return res.json();
}
export async function integrMigrarFornecedores(): Promise<{ migrados: number }> {
  const res = await fetch("/api/integracoes/migrar-fornecedores", { method: "POST" });
  return res.json();
}
export async function integrMigrarContas(): Promise<Record<string, number>> {
  const res = await fetch("/api/integracoes/migrar-contas", { method: "POST" });
  return res.json();
}
export async function integrMigrarTudo(): Promise<Record<string, unknown>> {
  const res = await fetch("/api/integracoes/migrar-tudo", { method: "POST" });
  return res.json();
}
export async function evtFaturarVenda(id: number): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/eventos/venda/${id}/faturar`, { method: "POST" });
  return res.json();
}
export async function evtReceberCompra(id: number): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/eventos/compra/${id}/receber`, { method: "POST" });
  return res.json();
}
export async function evtFinalizarProducao(id: number): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/eventos/producao/${id}/finalizar`, { method: "POST" });
  return res.json();
}
export async function evtFecharCaixaPDV(id: number, saldoFinal?: number): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/eventos/pdv/${id}/fechar-caixa`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ saldo_final: saldoFinal || 0 }),
  });
  return res.json();
}
export async function evtConverterLead(id: number): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/eventos/crm/lead/${id}/converter`, { method: "POST" });
  return res.json();
}
export async function evtNegociacaoGanha(id: number): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/eventos/crm/negociacao/${id}/ganha`, { method: "POST" });
  return res.json();
}
export async function evtProcessarFila(limit?: number): Promise<{ processados: number }> {
  const res = await fetch(`/api/eventos/processar${limit ? "?limit=" + limit : ""}`, { method: "POST" });
  return res.json();
}
export async function fiscalAlertasObrigacoes(): Promise<Record<string, unknown>> {
  const res = await fetch("/api/fiscal/obrigacoes/alertas");
  return res.json();
}
