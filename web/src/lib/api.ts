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
  blingStatus: () => request<Record<string, unknown>>("/api/bling/status"),
  blingSync: () => request<Record<string, unknown>>("/api/bling/sync", { method: "POST" }),
  blingProducts: () => request<unknown[]>("/api/bling/products"),
  blingOrders: () => request<unknown[]>("/api/bling/orders"),

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
