import type { VendaDiaria } from "../types/index";

// Dados reais via API
export async function getVendasData() {
  try {
    const r = await fetch("/api/relatorios/vendas?dias=60");
    const d = await r.json();
    return {
      diarias: (d.diarias || []).map((x: any) => ({ data: (x.dia || "").slice(0, 10), valor: x.valor || 0, quantidade: x.qtd || 0 })),
      total: d.total || 0, quantidade: d.quantidade || 0,
    };
  } catch { return { diarias: [], total: 0, quantidade: 0 }; }
}

export function gerarVendasDiarias(): VendaDiaria[] {
  return Array.from({ length: 30 }, (_, i) => ({ dia: String(i + 1).padStart(2, "0") + "/07", valor: 0, custo: 0, margem: 0 }));
}

export function gerarCategorias() { return []; }
