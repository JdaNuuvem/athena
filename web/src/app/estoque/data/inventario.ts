import type { Inventario, ItemInventario } from "@/lib/types/domain";

const SKUS: Array<{ sku: string; produto: string; custo: number }> = [
  { sku: "CAM-001", produto: "Camiseta Basic", custo: 29.90 },
  { sku: "CAL-002", produto: "Calça Jeans", custo: 89.90 },
  { sku: "TEN-003", produto: "Tênis Runner", custo: 199.90 },
  { sku: "MOC-004", produto: "Mochila Escolar", custo: 79.90 },
  { sku: "BON-005", produto: "Boné Trucker", custo: 39.90 },
  { sku: "JAI-006", produto: "Jaqueta Corta-Vento", custo: 149.90 },
  { sku: "REG-007", produto: "Regata Esportiva", custo: 24.90 },
  { sku: "BER-008", produto: "Bermuda Sarja", custo: 69.90 },
  { sku: "MEI-009", produto: "Meia Cano Longo", custo: 19.90 },
  { sku: "CIN-010", produto: "Cinto Couro", custo: 49.90 },
  { sku: "BLA-011", produto: "Blazer Slim", custo: 179.90 },
  { sku: "VES-012", produto: "Vestido Floral", custo: 99.90 },
  { sku: "SAI-013", produto: "Saia Plissada", custo: 59.90 },
  { sku: "POL-014", produto: "Polo Clássica", custo: 69.90 },
  { sku: "SHO-015", produto: "Shorts Tactel", custo: 44.90 },
];

export const INVENTARIOS_MOCK: Inventario[] = [
  { id: 1, tipo: "ciclico", deposito: "CD Central", data_inicio: "2026-07-10", data_fim: "2026-07-10", status: "concluido", responsavel: "João Silva", itens_contados: 150, itens_divergentes: 3, acuracia_pct: 98.0 },
  { id: 2, tipo: "ciclico", deposito: "Loja Centro", data_inicio: "2026-07-12", status: "em_andamento", responsavel: "Maria Santos", itens_contados: 87, itens_divergentes: 5, acuracia_pct: 94.3 },
  { id: 3, tipo: "geral", deposito: "CD Central", data_inicio: "2026-06-01", data_fim: "2026-06-03", status: "concluido", responsavel: "Carlos Oliveira", itens_contados: 1247, itens_divergentes: 42, acuracia_pct: 96.6 },
  { id: 4, tipo: "parcial", deposito: "E-commerce", data_inicio: "2026-07-08", data_fim: "2026-07-09", status: "concluido", responsavel: "Ana Costa", itens_contados: 320, itens_divergentes: 8, acuracia_pct: 97.5 },
  { id: 5, tipo: "ciclico", deposito: "Loja Norte", data_inicio: "2026-07-14", status: "aberto", responsavel: "João Silva", itens_contados: 0, itens_divergentes: 0, acuracia_pct: 0 },
  { id: 6, tipo: "geral", deposito: "Outlet", data_inicio: "2026-05-15", data_fim: "2026-05-16", status: "concluido", responsavel: "Maria Santos", itens_contados: 680, itens_divergentes: 18, acuracia_pct: 97.4 },
];

export function gerarItensInventario(inventarioId: number): ItemInventario[] {
  return SKUS.slice(0, 10 + Math.floor(Math.random() * 5)).map((p, i) => {
    const saldoSistema = Math.floor(Math.random() * 100);
    const div = Math.random() > 0.85 ? Math.floor(Math.random() * 6) - 3 : 0;
    return {
      id: inventarioId * 100 + i,
      inventario_id: inventarioId,
      sku: p.sku,
      produto: p.produto,
      saldo_sistema: saldoSistema,
      saldo_contado: saldoSistema + div,
      divergencia: div,
      custo_unitario: p.custo,
      divergencia_valor: div * p.custo,
    };
  });
}
