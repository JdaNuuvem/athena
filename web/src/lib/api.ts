const API_BASE = "";

// Token invalido/expirado (ex: troca de ATHENA_JWT_SECRET invalida sessoes
// antigas) — limpa e manda pro login em vez de deixar a tela presa com 401
// silencioso em toda chamada.
export function handleUnauthorized() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("token");
  if (window.location.pathname !== "/login") {
    window.location.href = "/login";
  }
}

// Upload multipart nao pode passar por request() porque ele forca
// Content-Type: application/json — aqui o navegador precisa definir o
// boundary do multipart sozinho.
export async function lojasMidiaUpload(id: number, tipo: string, file: File): Promise<{ midia?: Record<string, unknown>; error?: string }> {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const formData = new FormData();
  formData.append("tipo", tipo);
  formData.append("arquivo", file);
  const res = await fetch(`${API_BASE}/api/lojas/manage/${id}/midia`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: formData,
    credentials: "include",
  });
  if (res.status === 401) handleUnauthorized();
  return res.json();
}

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
  if (res.status === 401) {
    handleUnauthorized();
  }
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
  ProdutoLimites,
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
import type { ConversaChat, MensagemChat, AnexoChat, ParticipanteChat } from "@/lib/types/chat";

export const api = {
  // Auth
  login: (email: string, password: string) =>
    request<{ token: string; refreshToken: string; expiresIn: number; user: { id: string; name: string; role: string }; permissions: string[] }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  // RBAC — papeis (cargos) e permissoes
  roles: () => request<{ roles: Array<{ id: number; nome: string; descricao: string | null; created_at: string; permissoes: string[] }> }>("/api/rbac/roles"),
  permissions: () => request<{ permissoes: Array<{ id: number; codigo: string; modulo: string; acao: string; descricao: string | null }> }>("/api/rbac/permissoes"),
  roleCreate: (nome: string, descricao: string, permissoes: string[]) =>
    request<{ id?: number; error?: string }>("/api/rbac/roles", { method: "POST", body: JSON.stringify({ nome, descricao, permissoes }) }),
  roleUpdate: (roleId: number, nome: string, descricao: string) =>
    request<{ id?: number; error?: string }>(`/api/rbac/roles/${roleId}`, { method: "PUT", body: JSON.stringify({ nome, descricao }) }),
  roleDelete: (roleId: number) => request<{ success?: boolean; error?: string }>(`/api/rbac/roles/${roleId}`, { method: "DELETE" }),
  rolesUpdatePermissions: (roleId: number, permissoes: string[]) =>
    request<{ id?: number; error?: string }>(`/api/rbac/roles/${roleId}`, { method: "PUT", body: JSON.stringify({ permissoes }) }),

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

  // Shopee (multiloja)
  shopeeSync: (lojaId?: number) =>
    request<{ total: number; erros: number; detalhes_erros?: string[] }>("/api/shopee/produtos/sincronizar", {
      method: "POST",
      body: JSON.stringify(lojaId ? { loja_id: lojaId } : {}),
    }),
  shopeeLojas: () =>
    request<{ lojas: Array<{ id: number; nome: string; shopee_shop_id: string; shopee_shop_name: string | null; shopee_token_expira_em: string | null; tem_token: boolean }> }>("/api/shopee/lojas"),
  shopeeConectarLoja: (lojaId: number) =>
    request<{ url: string }>(`/api/shopee/lojas/${lojaId}/conectar`, { method: "POST" }),
  shopeeAuthUrl: () => request<{ url: string }>("/api/shopee/auth-url"),
  shopeeAtualizarEstoqueProduto: (sku: string, lojaId: number, quantidade: number) =>
    request<{ error?: string }>(`/api/shopee/produtos/${sku}/estoque`, {
      method: "PUT",
      body: JSON.stringify({ loja_id: lojaId, quantidade }),
    }),
  shopeeEstoqueTodasLojas: (sku: string, quantidade: number) =>
    request<{ total: number; sucesso: number; erro?: string; resultados: Array<{ loja_id: number; loja_nome: string; resultado: Record<string, unknown> }> }>("/api/shopee/estoque/todas-lojas", {
      method: "POST",
      body: JSON.stringify({ sku, quantidade }),
    }),
  shopeeAtualizarPreco: (itemId: number, lojaId: number, price: number) =>
    request<{ error?: string }>(`/api/shopee/produtos/${itemId}/preco`, {
      method: "POST",
      body: JSON.stringify({ loja_id: lojaId, price }),
    }),
  shopeeRenovarToken: (lojaId: number) =>
    request<{ success?: boolean; expire_in?: number; error?: string }>(`/api/shopee/lojas/${lojaId}/renovar-token`, {
      method: "POST",
    }),
  shopeeVariacoes: (itemId: number, lojaId?: number) =>
    request<{ response?: { model?: Array<{ model_id: number; model_name: string; model_sku: string; price_info?: Array<{ current_price: number }>; stock_info_v2?: { summary_info?: { total_available_stock: number } } }>; tier_variation?: Array<{ name: string; option_list: Array<{ option: string }> }> }; error?: string }>(
      `/api/shopee/produtos/${itemId}/variacoes${lojaId ? `?loja_id=${lojaId}` : ""}`
    ),

  // Shopee — cadastro de produto (categorias, atributos, marcas, imagens)
  shopeeCategorias: (params?: { busca?: string; parentId?: number; apenasFolhas?: boolean }) => {
    const q = new URLSearchParams();
    if (params?.busca) q.set("busca", params.busca);
    if (params?.parentId != null) q.set("parent_id", String(params.parentId));
    if (params?.apenasFolhas) q.set("apenas_folhas", "true");
    return request<{ categorias: ShopeeCategoria[] | null }>(`/api/shopee/categorias?${q}`);
  },
  shopeeSincronizarCategorias: (lojaId?: number) =>
    request<{ total: number; erro?: string }>("/api/shopee/categorias/sincronizar", {
      method: "POST",
      body: JSON.stringify(lojaId ? { loja_id: lojaId } : {}),
    }),
  shopeeAtributos: (categoryId: number, lojaId?: number) =>
    request<{ atributos: ShopeeAtributo[]; erro?: string }>(`/api/shopee/categorias/${categoryId}/atributos${lojaId ? `?loja_id=${lojaId}` : ""}`),
  shopeeMarcas: (categoryId: number, lojaId?: number) =>
    request<{ marcas: ShopeeMarca[]; obrigatorio: boolean; erro?: string }>(`/api/shopee/categorias/${categoryId}/marcas${lojaId ? `?loja_id=${lojaId}` : ""}`),
  shopeeCanaisLogistica: (lojaId?: number) =>
    request<{ canais: Array<{ logistic_id: number; logistic_name: string; enabled: boolean }>; erro?: string }>(`/api/shopee/logistica/canais${lojaId ? `?loja_id=${lojaId}` : ""}`),
  shopeeUploadImagem: async (lojaId: number, source: File | string) => {
    const formData = new FormData();
    formData.append("loja_id", String(lojaId));
    if (typeof source === "string") formData.append("image_url", source);
    else formData.append("file", source);
    const res = await fetch("/api/shopee/upload-imagem", { method: "POST", body: formData });
    return res.json() as Promise<{ image_id?: string; image_url?: string; erro?: string }>;
  },
  shopeeCriarProduto: async (lojaId: number, dados: Record<string, unknown>) => {
    // ponytail: fetch cru (nao usa request()) porque o backend pode responder 400
    // com bloqueado_por_margem — precisamos ler o corpo do erro, nao so' lancar excecao.
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch("/api/shopee/produtos", {
      method: "POST", headers, credentials: "include",
      body: JSON.stringify({ ...dados, loja_id: lojaId }),
    });
    return res.json() as Promise<{
      response?: { item_id: number }; error?: string; message?: string;
      bloqueado_por_margem?: boolean;
      margem?: { margem_valor: number; margem_pct: number; custo: number; frete: number; comissao_valor: number };
    }>;
  },
  shopeeEditarProdutoShopee: (itemId: number, lojaId: number, dados: Record<string, unknown>) =>
    request<{ response?: unknown; error?: string }>(`/api/shopee/produtos/${itemId}`, {
      method: "PUT",
      body: JSON.stringify({ ...dados, loja_id: lojaId }),
    }),
  shopeeDeletarProdutoShopee: (itemId: number, lojaId: number) =>
    request<{ response?: unknown; error?: string }>(`/api/shopee/produtos/${itemId}?loja_id=${lojaId}`, { method: "DELETE" }),
  shopeeUnlistProduto: (itemId: number, lojaId: number, unlist: boolean) =>
    request<{ response?: unknown; error?: string }>(`/api/shopee/produtos/${itemId}/unlist`, {
      method: "POST",
      body: JSON.stringify({ loja_id: lojaId, unlist }),
    }),
  shopeeDetalheProduto: (itemId: number, lojaId?: number) =>
    request<{ item?: Record<string, unknown>; error?: string }>(`/api/shopee/produtos/${itemId}${lojaId ? `?loja_id=${lojaId}` : ""}`),
  shopeeDesconectarLoja: (lojaId: number) =>
    request<{ id?: number; nome?: string; error?: string }>(`/api/shopee/lojas/${lojaId}`, { method: "DELETE" }),
  shopeeSyncLog: () =>
    request<{ log: ShopeeSyncLogEntry[] }>("/api/shopee/sync-log"),
  shopeePedidos: (lojaId?: number, dias?: number, status?: string) => {
    const q = new URLSearchParams();
    if (lojaId) q.set("loja_id", String(lojaId));
    if (dias) q.set("dias", String(dias));
    if (status) q.set("status", status);
    return request<{ pedidos: ShopeePedido[]; error?: string }>(`/api/shopee/pedidos?${q}`);
  },
  shopeeDashboard: (dias?: number) =>
    request<{ lojas: ShopeeDashboardLoja[]; dias: number; error?: string }>(`/api/shopee/dashboard${dias ? `?dias=${dias}` : ""}`),

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
  produtosLimites: () => request<Record<string, ProdutoLimites>>("/api/produtos/limites"),
  criarProduto: (dados: Record<string, unknown>) =>
    request<{ success: boolean; produto?: Record<string, unknown>; error?: string }>("/api/produtos", {
      method: "POST",
      body: JSON.stringify(dados),
    }),

  listarMarcas: () => request<{ data: { id: number; nome: string }[] }>("/api/produtos/marcas"),
  criarMarca: (nome: string) =>
    request<{ id: number; nome: string; error?: string }>("/api/produtos/marcas", {
      method: "POST", body: JSON.stringify({ nome }),
    }),
  listarFabricantes: () => request<{ data: { id: number; nome: string }[] }>("/api/produtos/fabricantes"),
  criarFabricante: (nome: string) =>
    request<{ id: number; nome: string; error?: string }>("/api/produtos/fabricantes", {
      method: "POST", body: JSON.stringify({ nome }),
    }),
  listarCategoriasProduto: () => request<{ data: { id: number; nome: string; categoria_pai_id: number | null }[] }>("/api/produtos/categorias"),
  criarCategoriaProduto: (nome: string) =>
    request<{ id: number; nome: string; error?: string }>("/api/produtos/categorias", {
      method: "POST", body: JSON.stringify({ nome }),
    }),

  // Estoque — entrada via scanner de codigo de barras
  estoqueBuscarCodigo: (codigo: string) =>
    request<{ sku: string; descricao: string; codigo_barras: string | null; estoque_total: number; erro?: string }>(
      `/api/estoque/buscar-codigo?codigo=${encodeURIComponent(codigo)}`
    ),
  estoqueEntrada: (sku: string, loja: string, quantidade: number, motivo?: string) =>
    request<{ atual?: number; erro?: string }>("/api/estoque/entrada", {
      method: "POST",
      body: JSON.stringify({ sku, loja, quantidade, motivo: motivo || "" }),
    }),
  estoqueMotivos: () =>
    request<{ entrada: string[]; saida: string[]; transferencia: string[]; limite_aprovacao_unidades: number }>("/api/estoque/motivos"),

  // Estoque — saida com alcada de aprovacao
  estoqueSaida: (sku: string, loja: string, quantidade: number, motivo: string) =>
    request<{ ok?: boolean; atual?: number; pendente?: boolean; aprovacao_id?: number; erro?: string }>("/api/estoque/saida", {
      method: "POST",
      body: JSON.stringify({ sku, loja, quantidade, motivo }),
    }),
  estoqueListarAprovacoes: (status = "pendente", loja?: string) =>
    request<{ aprovacoes: EstoqueAprovacao[] }>(`/api/estoque/aprovacoes?status=${status}${loja ? `&loja=${encodeURIComponent(loja)}` : ""}`),
  estoqueAprovar: (id: number) =>
    request<{ ok?: boolean; atual?: number; erro?: string }>(`/api/estoque/aprovacoes/${id}/aprovar`, { method: "POST" }),
  estoqueRejeitar: (id: number, motivoRejeicao?: string) =>
    request<{ ok?: boolean; erro?: string }>(`/api/estoque/aprovacoes/${id}/rejeitar`, {
      method: "POST",
      body: JSON.stringify({ motivo_rejeicao: motivoRejeicao || "" }),
    }),

  // Estoque — transferencia entre lojas com confirmacao em duas pontas
  estoqueTransferir: (sku: string, origem: string, destino: string, quantidade: number, motivo: string) =>
    request<{ transferencia_id?: number; status?: string; pendente_aprovacao?: boolean; erro?: string }>("/api/estoque/transferir", {
      method: "POST",
      body: JSON.stringify({ sku, origem, destino, quantidade, motivo }),
    }),
  estoqueListarTransferencias: (status?: string, loja?: string) => {
    const q = new URLSearchParams();
    if (status) q.set("status", status);
    if (loja) q.set("loja", loja);
    return request<{ transferencias: EstoqueTransferencia[] }>(`/api/estoque/transferencias?${q}`);
  },
  estoqueTransferenciaAprovar: (id: number) =>
    request<{ ok?: boolean; erro?: string }>(`/api/estoque/transferencias/${id}/aprovar`, { method: "POST" }),
  estoqueTransferenciaRejeitar: (id: number, motivoRejeicao?: string) =>
    request<{ ok?: boolean; erro?: string }>(`/api/estoque/transferencias/${id}/rejeitar`, {
      method: "POST",
      body: JSON.stringify({ motivo_rejeicao: motivoRejeicao || "" }),
    }),
  estoqueTransferenciaConfirmar: (id: number, quantidadeRecebida: number) =>
    request<{ ok?: boolean; status?: string; discrepancia?: boolean; erro?: string }>(`/api/estoque/transferencias/${id}/confirmar`, {
      method: "POST",
      body: JSON.stringify({ quantidade_recebida: quantidadeRecebida }),
    }),

  // Estoque — contagem ciclica
  estoqueContagemSugestoes: (loja?: string) =>
    request<{ sugestoes: EstoqueContagemSugestao[] }>(`/api/estoque/contagem/sugestoes${loja ? `?loja=${encodeURIComponent(loja)}` : ""}`),
  estoqueContagemRegistrar: (sku: string, loja: string, quantidadeContada: number) =>
    request<{ diferenca?: number; ajuste_status?: string; erro?: string }>("/api/estoque/contagem/registrar", {
      method: "POST",
      body: JSON.stringify({ sku, loja, quantidade_contada: quantidadeContada }),
    }),
  estoqueContagemHistorico: (loja?: string) =>
    request<{ historico: EstoqueContagemHistorico[] }>(`/api/estoque/contagem/historico${loja ? `?loja=${encodeURIComponent(loja)}` : ""}`),

  // Estoque — relatorio de discrepancias
  estoqueRelatorioDiscrepancias: (dias = 30) =>
    request<{ por_loja: EstoqueDiscrepanciaLoja[]; por_operador: EstoqueDiscrepanciaOperador[] }>(`/api/estoque/relatorio-discrepancias?dias=${dias}`),

  // Lojas
  lojas: (periodo?: number) =>
    request<unknown[]>(`/api/lojas${periodo ? `?periodo=${periodo}` : ""}`),
  lojasManage: () => request<{ lojas: Array<{ id: number; nome: string; ativa: boolean }> }>("/api/lojas/manage"),
  lojasCriar: (nome: string, tipo?: "fisica" | "virtual") => request<{ loja: { id: number; nome: string; tipo?: string } }>("/api/lojas/manage", { method: "POST", body: JSON.stringify({ nome, tipo }) }),
  lojasAtualizar: (id: number, nome: string, shopee_markup_pct?: number, grupos_publicacao?: string, tipo?: "fisica" | "virtual") => request<{ success: boolean }>(`/api/lojas/manage/${id}`, { method: "PUT", body: JSON.stringify({ nome, shopee_markup_pct, grupos_publicacao, tipo }) }),
  lojasDeletar: (id: number) => request<{ success: boolean }>(`/api/lojas/manage/${id}`, { method: "DELETE" }),
  lojasSyncBling: () => request<{ sync: number; lojas: Array<{ acao: string; id: number; nome: string }> }>("/api/lojas/sync/bling", { method: "POST" }),
  lojasDepositoMap: () => request<{ map: Array<{ loja_id: number; nome: string; deposito_id: number }> }>("/api/lojas/deposito-map"),

  // Lojas — cadastro empresarial (Fase 2)
  lojasObter: (id: number) => request<{ loja: Record<string, unknown> }>(`/api/lojas/manage/${id}`),
  lojasAtualizarGeral: (id: number, campos: Record<string, unknown>) =>
    request<{ success?: boolean; error?: string }>(`/api/lojas/manage/${id}`, { method: "PUT", body: JSON.stringify(campos) }),
  lojasOperacionalAtualizar: (id: number, campos: Record<string, unknown>) =>
    request<{ success?: boolean; error?: string }>(`/api/lojas/manage/${id}/operacional`, { method: "PUT", body: JSON.stringify(campos) }),
  lojasComercialAtualizar: (id: number, campos: Record<string, unknown>) =>
    request<{ success?: boolean; error?: string }>(`/api/lojas/manage/${id}/comercial`, { method: "PUT", body: JSON.stringify(campos) }),
  lojasFiscalAtualizar: (id: number, campos: Record<string, unknown>) =>
    request<{ success?: boolean; error?: string }>(`/api/lojas/manage/${id}/fiscal`, { method: "PUT", body: JSON.stringify(campos) }),
  lojasFinanceiroAtualizar: (id: number, campos: Record<string, unknown>) =>
    request<{ success?: boolean; error?: string }>(`/api/lojas/manage/${id}/financeiro`, { method: "PUT", body: JSON.stringify(campos) }),
  lojasEstoqueConfigAtualizar: (id: number, campos: Record<string, unknown>) =>
    request<{ success?: boolean; error?: string }>(`/api/lojas/manage/${id}/estoque-config`, { method: "PUT", body: JSON.stringify(campos) }),
  lojasVirtualAtualizar: (id: number, campos: Record<string, unknown>) =>
    request<{ success?: boolean; error?: string }>(`/api/lojas/manage/${id}/virtual`, { method: "PUT", body: JSON.stringify(campos) }),
  lojasDeliveryAtualizar: (id: number, campos: Record<string, unknown>) =>
    request<{ success?: boolean; error?: string }>(`/api/lojas/manage/${id}/delivery`, { method: "PUT", body: JSON.stringify(campos) }),

  lojasResponsaveisListar: (id: number) =>
    request<{ responsaveis: Array<Record<string, unknown>> }>(`/api/lojas/manage/${id}/responsaveis`),
  lojasResponsavelVincular: (id: number, dados: Record<string, unknown>) =>
    request<{ responsavel?: Record<string, unknown>; error?: string }>(`/api/lojas/manage/${id}/responsaveis`, { method: "POST", body: JSON.stringify(dados) }),
  lojasResponsavelAtualizar: (id: number, vinculoId: number, dados: Record<string, unknown>) =>
    request<{ success?: boolean; error?: string }>(`/api/lojas/manage/${id}/responsaveis/${vinculoId}`, { method: "PUT", body: JSON.stringify(dados) }),
  lojasResponsavelRemover: (id: number, vinculoId: number) =>
    request<{ success?: boolean; error?: string }>(`/api/lojas/manage/${id}/responsaveis/${vinculoId}`, { method: "DELETE" }),

  lojasIntegracoesListar: (id: number) =>
    request<{ integracoes: Array<{ integracao: string; status: string; configurado: boolean }> }>(`/api/lojas/manage/${id}/integracoes`),
  lojasIntegracaoAtualizar: (id: number, chave: string, dados: { status: string; credenciais?: Record<string, unknown> }) =>
    request<{ integracao?: Record<string, unknown>; error?: string }>(`/api/lojas/manage/${id}/integracoes/${chave}`, { method: "PUT", body: JSON.stringify(dados) }),

  lojasMidiaListar: (id: number, tipo?: string) =>
    request<{ midia: Array<Record<string, unknown>> }>(`/api/lojas/manage/${id}/midia${tipo ? `?tipo=${tipo}` : ""}`),
  lojasMidiaRemover: (id: number, midiaId: number) =>
    request<{ success?: boolean; error?: string }>(`/api/lojas/manage/${id}/midia/${midiaId}`, { method: "DELETE" }),

  // KPI
  kpiOverview: (periodo?: number) =>
    request<Record<string, unknown>>(`/api/kpi/overview${periodo ? `?periodo=${periodo}` : ""}`),

  // Relatorios
  relatorioVendas: (dias: number, lojaId?: string) =>
    request<Record<string, unknown>>(`/api/relatorios/vendas?dias=${dias}${lojaId && lojaId !== "todas" ? `&loja_id=${lojaId}` : ""}`),
  relatorioEstoque: (lojaId?: string) =>
    request<Record<string, unknown>>(`/api/relatorios/estoque${lojaId && lojaId !== "todas" ? `?loja_id=${lojaId}` : ""}`),
  relatorioFluxoCaixa: (dias: number, lojaId?: string) =>
    request<Record<string, unknown>>(`/api/relatorios/fluxo-caixa?dias=${dias}${lojaId && lojaId !== "todas" ? `&loja_id=${lojaId}` : ""}`),
  relatorioClientes: (dias: number, lojaId?: string) =>
    request<Record<string, unknown>>(`/api/relatorios/clientes?dias=${dias}${lojaId && lojaId !== "todas" ? `&loja_id=${lojaId}` : ""}`),

  // Chat Interno
  chat: {
    listarConversas: () => request<{ data: ConversaChat[] }>("/api/chat/conversas"),
    criarConversaDm: (userId: number) =>
      request<ConversaChat>("/api/chat/conversas", {
        method: "POST", body: JSON.stringify({ tipo: "dm", user_id: userId }),
      }),
    criarConversaGrupo: (nome: string, descricao: string, participantes: number[], departamento?: string, lojaId?: number) =>
      request<ConversaChat>("/api/chat/conversas", {
        method: "POST",
        body: JSON.stringify({ tipo: "grupo", nome, descricao, participantes, departamento, loja_id: lojaId }),
      }),
    listarMensagens: (conversaId: number, antesDe?: string) =>
      request<{ data: MensagemChat[] }>(
        `/api/chat/conversas/${conversaId}/mensagens${antesDe ? `?antes_de=${encodeURIComponent(antesDe)}` : ""}`
      ),
    enviarMensagem: (conversaId: number, texto: string, anexoId?: number, threadPaiId?: number) =>
      request<MensagemChat>(`/api/chat/conversas/${conversaId}/mensagens`, {
        method: "POST", body: JSON.stringify({ texto, anexo_id: anexoId, thread_pai_id: threadPaiId }),
      }),
    editarMensagem: (mensagemId: number, texto: string) =>
      request<MensagemChat>(`/api/chat/mensagens/${mensagemId}`, {
        method: "PUT", body: JSON.stringify({ texto }),
      }),
    excluirMensagem: (mensagemId: number) =>
      request<MensagemChat>(`/api/chat/mensagens/${mensagemId}`, { method: "DELETE" }),
    marcarLido: (conversaId: number, ultimaMensagemId: number) =>
      request<{ success: boolean }>(`/api/chat/conversas/${conversaId}/lido`, {
        method: "POST", body: JSON.stringify({ ultima_mensagem_id: ultimaMensagemId }),
      }),
    buscar: (termo: string) => request<{ data: MensagemChat[] }>(`/api/chat/busca?q=${encodeURIComponent(termo)}`),
    canaisDepartamento: () => request<{ data: ConversaChat[] }>("/api/chat/canais-departamento"),
    listarParticipantes: (conversaId: number) =>
      request<{ data: ParticipanteChat[] }>(`/api/chat/conversas/${conversaId}/participantes`),
    uploadAnexo: async (arquivo: File): Promise<AnexoChat> => {
      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const formData = new FormData();
      formData.append("arquivo", arquivo);
      const res = await fetch("/api/chat/anexos", {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: "include",
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(err.error || `HTTP ${res.status}`);
      }
      return res.json();
    },
    urlDownloadAnexo: (anexoId: number) => `/api/chat/anexos/${anexoId}`,
  },

  // Hermes Chat (legado)
  hermesChat: (mensagem: string, user_id?: string, nome?: string) =>
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

  // Manutencao
  manutencaoDashboard: () => request<Record<string, unknown>>("/api/manutencao/kpi"),
  manutencaoAlertas: () => request<{ alertas: unknown[]; total: number }>("/api/manutencao/alertas"),
  manutencaoAgendar: (data: Record<string, unknown>) =>
    request<{ numero: string; success: boolean }>("/api/manutencao/agendar", { method: "POST", body: JSON.stringify(data) }),
  manutencaoIniciar: (id: number, tecnico: string) =>
    request<Record<string, unknown>>(`/api/manutencao/${id}/iniciar`, { method: "POST", body: JSON.stringify({ tecnico }) }),
  manutencaoConcluir: (id: number, data: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/api/manutencao/${id}/concluir`, { method: "POST", body: JSON.stringify(data) }),
  manutencaoMTBF: (tipo: string, id: string) =>
    request<Record<string, unknown>>(`/api/manutencao/mtbf/${tipo}/${id}`),

  // Qualidade
  qualidadeTaxaDefeitos: (periodo?: number) =>
    request<Record<string, unknown>>(`/api/qualidade/taxa_defeitos${periodo ? `?periodo=${periodo}` : ""}`),
  qualidadePareto: (periodo?: number) =>
    request<Record<string, unknown>>(`/api/qualidade/pareto${periodo ? `?periodo=${periodo}` : ""}`),
  qualidadeCAPAS: () => request<{ capas: unknown[]; total: number }>("/api/qualidade/capas"),
  qualidadeRegistrarInspecao: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>("/api/qualidade/inspecoes", { method: "POST", body: JSON.stringify(data) }),
  qualidadeCriarCAPA: (data: Record<string, unknown>) =>
    request<Record<string, unknown>>("/api/qualidade/capas", { method: "POST", body: JSON.stringify(data) }),

  // Moldes & CNC
  moldesHistorico: (id: number) => request<{ molde_id: number; historico: unknown[] }>(`/api/moldes/${id}/historico`),
  moldesStatus: (id: number) => request<Record<string, unknown>>(`/api/moldes/${id}/status`),
  cncCriarJob: (data: Record<string, unknown>) =>
    request<{ job_id: string; success: boolean }>("/api/cnc/jobs", { method: "POST", body: JSON.stringify(data) }),
  cncIniciarJob: (jobId: string, operador: string) =>
    request<Record<string, unknown>>(`/api/cnc/jobs/${jobId}/iniciar`, { method: "POST", body: JSON.stringify({ operador }) }),
  cncConcluirJob: (jobId: string, data: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/api/cnc/jobs/${jobId}/concluir`, { method: "POST", body: JSON.stringify(data) }),

  // Memory
  memoryStats: () => request<Record<string, unknown>>("/api/memory/stats"),
  memoryHistory: (agente?: string, categoria?: string) => {
    const q = new URLSearchParams();
    if (agente) q.set("agente", agente);
    if (categoria) q.set("categoria", categoria);
    return request<{ history: unknown[]; total: number }>(`/api/memory/history${q.toString() ? "?" + q : ""}`);
  },
  memoryRecall: (query: string, agente?: string) =>
    request<{ results: unknown[]; total: number }>("/api/memory/recall", { method: "POST", body: JSON.stringify({ query, agente }) }),

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

  // Auditoria
  auditoriaList: (filtros: { modulo?: string; email?: string; entidade?: string; acao?: string; data_inicio?: string; data_fim?: string; limit?: number }) => {
    const q = new URLSearchParams();
    Object.entries(filtros).forEach(([k, v]) => { if (v) q.set(k, String(v)); });
    return request<{ auditoria: Record<string, unknown>[] }>(`/api/auditoria${q.toString() ? "?" + q : ""}`);
  },
  auditoriaModulos: () => request<{ modulos: string[] }>("/api/auditoria/modulos"),

  // RBAC — usuarios (contas) e PIN / cracha (autorizacao gerencial fora do PDV)
  rbacListUsuarios: () => request<{ usuarios: { id: number; nome: string; email: string; role_id: number | null; ativo: boolean }[] }>("/api/rbac/usuarios"),
  rbacCreateUsuario: (nome: string, email: string, senha: string, role: string) =>
    request<{ id?: number; error?: string }>("/api/rbac/usuarios", { method: "POST", body: JSON.stringify({ nome, email, senha, role }) }),
  rbacUpdateUsuario: (id: number, dados: { nome?: string; role?: string; ativo?: boolean }) =>
    request<{ id?: number; error?: string }>(`/api/rbac/usuarios/${id}`, { method: "PUT", body: JSON.stringify(dados) }),
  rbacDefinirPin: (id: number, pin: string) => request<{ ok?: boolean; error?: string }>(`/api/rbac/usuarios/${id}/pin`, { method: "PUT", body: JSON.stringify({ pin }) }),
  rbacGerarCodigoBarras: (id: number) => request<{ ok?: boolean; codigo_barras?: string; error?: string }>(`/api/rbac/usuarios/${id}/codigo-barras`, { method: "POST" }),
  rbacAutorizar: (payload: { permissao: string; usuario_pin_id?: number | null; pin?: string; codigo_barras?: string }) =>
    request<{ ok?: boolean; id?: number; nome?: string; error?: string }>("/api/rbac/autorizar", { method: "POST", body: JSON.stringify(payload) }),
};

// Types — SSOT re-exports from lib/types/domain (removes duplicate definitions)
export type {
  Agent,
  KPIOverview,
  Product,
  ProdutoLimites,
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

export interface ShopeeCategoria {
  category_id: number;
  parent_category_id: number;
  nome: string;
  tem_filhos: boolean;
}

export interface ShopeeAtributo {
  attribute_id: number;
  original_attribute_name: string;
  is_mandatory: boolean;
  input_validation_type?: string;
  attribute_value_list?: Array<{ value_id: number; original_value_name: string }>;
}

export interface ShopeeMarca {
  brand_id: number;
  original_brand_name: string;
}

export interface ShopeeSyncLogEntry {
  id: number;
  tipo: string;
  status: string;
  itens_processados: number;
  erro: string | null;
  iniciado_em: string;
  concluido_em: string | null;
}

export interface ShopeePedido {
  order_sn: string;
  status: string;
  create_time: number;
  update_time: number;
  total_amount: number | string;
  buyer_username: string;
  recipient_nome: string;
  itens: Array<{ sku: string; nome: string; quantidade: number; preco: number | string }>;
}

export interface ShopeeDashboardLoja {
  loja_id: number;
  nome: string;
  shop_id: string;
  tem_token: boolean;
  receita: number;
  unidades_vendidas: number;
  skus_vendidos: number;
  anuncios_total: number;
  anuncios_ativos: number;
  produtos_estoque_baixo: number;
}

export interface EstoqueAprovacao {
  id: number;
  tipo: string;
  sku: string;
  produto_nome?: string;
  loja: string;
  quantidade: number;
  motivo: string;
  status: string;
  usuario_solicitante_id: number | null;
  usuario_solicitante_nome: string | null;
  usuario_aprovador_nome: string | null;
  motivo_rejeicao: string | null;
  criado_em: string;
  resolvido_em: string | null;
}

export interface EstoqueTransferencia {
  id: number;
  sku: string;
  produto_nome?: string;
  loja_origem: string;
  loja_destino: string;
  quantidade_solicitada: number;
  quantidade_recebida: number | null;
  motivo: string;
  status: string;
  usuario_solicitante_nome: string | null;
  usuario_aprovador_nome: string | null;
  usuario_confirmador_nome: string | null;
  criado_em: string;
}

export interface EstoqueContagemSugestao {
  sku: string;
  loja: string;
  quantidade: number;
  nome: string;
  preco_custo: number;
  valor_total: number;
  ultima_contagem: string | null;
}

export interface EstoqueContagemHistorico {
  id: number;
  sku: string;
  produto_nome?: string;
  loja: string;
  quantidade_sistema: number;
  quantidade_contada: number;
  diferenca: number;
  ajuste_status: string;
  usuario_nome: string | null;
  criado_em: string;
}

export interface EstoqueDiscrepanciaLoja {
  loja: string;
  saidas_aprovadas_qtd: number;
  saidas_aprovadas_eventos: number;
  transferencias_com_discrepancia: number;
  contagens_com_falta: number;
  unidades_falta_contagem: number;
}

export interface EstoqueDiscrepanciaOperador {
  operador: string;
  saidas_grandes_solicitadas: number;
  saidas_grandes_aprovadas_qtd: number;
  saidas_grandes_rejeitadas: number;
  contagens_com_falta: number;
  unidades_falta_contagem: number;
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

// ── Estoque por Loja ──

export interface EstoqueLojaRow {
  id: number;
  sku: string;
  nome: string;
  loja: string;
  quantidade: number;
  data_atualizacao: string;
  sync_status?: string;
}

export const estoqueLojas = (params: string) =>
  request<{ estoque: EstoqueLojaRow[]; total: number; pagina: number }>(`/api/estoque/lojas?${params}`);

export const estoqueAtualizar = (sku: string, loja: string, quantidade: number) =>
  request<{ ok?: boolean; erro?: string; bling_sync?: { ok?: boolean; error?: string } }>("/api/estoque/lojas", {
    method: "PUT",
    body: JSON.stringify({ sku, loja, quantidade, sync_bling: "1" }),
    headers: { "Content-Type": "application/json" },
  });

export interface RateioLoja {
  loja: string;
  quantidade: number;
  percentual: number;
}
export interface RateioResult {
  ok: boolean;
  sku: string;
  total: number;
  modo: string;
  lojas: RateioLoja[];
  percentuais: Record<string, number>;
  erro?: string;
}

export const estoqueRatear = (params: {
  sku: string;
  total: number;
  modo?: "igual" | "proporcional";
  lojas?: string[];
  periodo_dias?: number;
  percentuais?: Record<string, number>;
}) =>
  request<RateioResult>("/api/estoque/ratear", {
    method: "POST",
    body: JSON.stringify(params),
    headers: { "Content-Type": "application/json" },
  });

// ── Produtos por Loja ──

export interface ProdutoLojaRow {
  id: number;
  loja: string;
  sku: string;
  produto_mestre_sku: string | null;
  nome_mestre?: string;
  imagens?: unknown;
  // ponytail: colunas DECIMAL do Postgres chegam serializadas como string no
  // JSON (ex: "99.90"), nao como number — psycopg/Flask nao convertem. O
  // consumidor (estoque/lojas/page.tsx) precisa envolver em Number(...)
  // antes de formatar/comparar. Ver Important 3 da revisao final.
  estoque_atual: number | string;
  codigo_interno: string | null;
  codigo_barras_override: string | null;
  nome_override: string | null;
  status: string;
  preco_custo: number | string | null;
  preco_venda: number | string | null;
  promocao_ativa: boolean;
  promocao_preco: number | string | null;
  comissao_pct: number | string | null;
  fornecedor_id: number | null;
  deposito: string | null;
  localizacao_fisica: string | null;
  estoque_minimo: number | string | null;
  estoque_maximo: number | string | null;
  observacoes_internas: string | null;
}

export const listarProdutosLoja = (loja: string, params?: { busca?: string; pagina?: number; por_pagina?: number }) => {
  const q = new URLSearchParams({ loja });
  if (params?.busca) q.set("busca", params.busca);
  if (params?.pagina) q.set("pagina", String(params.pagina));
  if (params?.por_pagina) q.set("por_pagina", String(params.por_pagina));
  return request<{ produtos: ProdutoLojaRow[]; total: number; pagina: number }>(`/api/produtos-loja?${q}`);
};

export const obterProdutoLoja = (loja: string, sku: string) =>
  request<ProdutoLojaRow & { erro?: string }>(`/api/produtos-loja/${encodeURIComponent(loja)}/${encodeURIComponent(sku)}`);

export const criarProdutoLoja = (dados: Record<string, unknown>) =>
  request<{ ok?: boolean; erro?: string }>("/api/produtos-loja", { method: "POST", body: JSON.stringify(dados) });

export const atualizarProdutoLoja = (loja: string, sku: string, dados: Record<string, unknown>) =>
  request<{ ok?: boolean; erro?: string }>(`/api/produtos-loja/${encodeURIComponent(loja)}/${encodeURIComponent(sku)}`, {
    method: "PUT", body: JSON.stringify(dados),
  });

export const excluirProdutoLoja = (loja: string, sku: string) =>
  request<{ ok?: boolean; erro?: string }>(`/api/produtos-loja/${encodeURIComponent(loja)}/${encodeURIComponent(sku)}`, {
    method: "DELETE",
  });

export const replicarProdutoLoja = (loja_origem: string, sku: string, lojas_destino: string[]) =>
  request<{
    ok?: boolean;
    criados?: string[];
    ja_existentes?: string[];
    erro?: string;
    erros?: { loja: string; erro: string }[];
  }>("/api/produtos-loja/replicar", {
    method: "POST", body: JSON.stringify({ loja_origem, sku, lojas_destino }),
  });

export const sincronizarProdutoLojaDoMestre = (loja: string, sku: string, campos: string[]) =>
  request<{ ok?: boolean; erro?: string }>(`/api/produtos-loja/${encodeURIComponent(loja)}/${encodeURIComponent(sku)}/sincronizar-mestre`, {
    method: "POST", body: JSON.stringify({ campos }),
  });
