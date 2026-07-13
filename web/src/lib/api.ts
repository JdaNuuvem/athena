const API_BASE = "";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  // Auth
  login: (username: string, password: string) =>
    request<{ token: string; role: string; name: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  me: () => request<{ name: string; role: string; permissoes: string[] }>("/api/me"),

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
  listarProdutos: (params?: { busca?: string; loja?: string; pagina?: number }) => {
    const q = new URLSearchParams();
    if (params?.busca) q.set("busca", params.busca);
    if (params?.loja) q.set("loja", params.loja);
    if (params?.pagina) q.set("pagina", String(params.pagina));
    return request<{ produtos: unknown[]; total: number; pagina: number }>(`/api/produtos?${q}`);
  },

  detalheProduto: (sku: string) => request<Record<string, unknown>>(`/api/produtos/${sku}`),

  // Lojas
  lojas: (periodo?: number) =>
    request<unknown[]>(`/api/lojas${periodo ? `?periodo=${periodo}` : ""}`),

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
};

// Types
export interface Agent {
  id: string;
  name: string;
  role: string;
  status: string;
  context: string;
  taskCount: number;
}

export interface KPIOverview {
  receita_total: number;
  total_pedidos: number;
  total_produtos: number;
  total_anuncios: number;
  ticket_medio: number;
  receita_por_canal: Record<string, number>;
  top_skus: Array<{
    sku: string;
    nome: string;
    qtd: number;
    receita: number;
    margem: number;
  }>;
}

export interface Product {
  sku: string;
  nome: string;
  margem_pct: number;
  receita_30d: number;
  vendidos_30d: number;
  estoque_lojas: Array<{ loja: string; preco: number; status: string }>;
  total_lojas: number;
}

export interface Integration {
  id: string;
  name: string;
  category: string;
  status: string;
}

// Bling types
export interface BlingProduct {
  id: number;
  codigo: string;
  descricao: string;
  preco: number;
  estoque_atual: number;
  estoque_minimo: number;
  situacao: string;
}

export interface BlingOrder {
  id: number;
  numero: string;
  data: string;
  total_venda: number;
  situacao: string;
  contato_nome: string;
  imported_at: string;
}

export interface BlingInvoice {
  id: number;
  numero: string;
  serie: string;
  data_emissao: string;
  valor_nota: number;
  situacao: string;
  cliente_nome: string;
  imported_at: string;
}

export interface BlingReceivable {
  id: number;
  descricao: string;
  valor: number;
  data_vencimento: string;
  situacao: string;
}

export interface BlingConfig {
  api_key: string;
  sandbox: boolean;
  auto_sync: boolean;
  sync_interval_minutes: number;
  sync_products: boolean;
  sync_orders: boolean;
  sync_invoices: boolean;
  sync_receivables: boolean;
  sync_stock: boolean;
  auth_url: string;
  autenticado: boolean;
}

// ── Novos tipos Bling (Task 5) ──

export interface BlingStatus {
  client_id_setado: boolean;
  autenticado: boolean;
  auth_url: string;
}

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

export interface BlingDeposito {
  id: number;
  descricao: string;
  situacao: string;
  [key: string]: unknown;
}

export interface BlingEstoqueSaldo {
  idProduto: number;
  codigo: string;
  saldo: number;
  [key: string]: unknown;
}

export interface BlingResumoVendas {
  total_receita: number;
  total_pedidos: number;
  dias_analisados: number;
  top_skus: Array<{ sku: string; quantidade: number; receita: number }>;
  vendas_diarias: Array<[string, number]>;
}

export interface BlingWebhook {
  id: number;
  url: string;
  evento: string;
  situacao: string;
  [key: string]: unknown;
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
  return res.json();
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
