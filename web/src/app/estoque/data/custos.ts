import type { CurvaABCItem, IndicadorGiro, IndicadorRuptura, IndicadorCobertura } from "@/lib/types/domain";

interface SkuInfo { sku: string; produto: string; consumo: number; estoque_atual: number; demanda_diaria: number; estoque_min: number; estoque_max: number }

const SKUS: SkuInfo[] = [
  { sku: "CAM-001", produto: "Camiseta Basic", consumo: 485000, estoque_atual: 320, demanda_diaria: 18, estoque_min: 100, estoque_max: 500 },
  { sku: "CAL-002", produto: "Calça Jeans", consumo: 392000, estoque_atual: 145, demanda_diaria: 12, estoque_min: 80, estoque_max: 300 },
  { sku: "TEN-003", produto: "Tênis Runner", consumo: 588000, estoque_atual: 89, demanda_diaria: 15, estoque_min: 60, estoque_max: 250 },
  { sku: "MOC-004", produto: "Mochila Escolar", consumo: 124000, estoque_atual: 12, demanda_diaria: 4, estoque_min: 20, estoque_max: 100 },
  { sku: "BON-005", produto: "Boné Trucker", consumo: 86000, estoque_atual: 230, demanda_diaria: 7, estoque_min: 30, estoque_max: 150 },
  { sku: "JAI-006", produto: "Jaqueta Corta-Vento", consumo: 215000, estoque_atual: 38, demanda_diaria: 6, estoque_min: 25, estoque_max: 120 },
  { sku: "REG-007", produto: "Regata Esportiva", consumo: 198000, estoque_atual: 0, demanda_diaria: 10, estoque_min: 40, estoque_max: 200 },
  { sku: "BER-008", produto: "Bermuda Sarja", consumo: 156000, estoque_atual: 78, demanda_diaria: 5, estoque_min: 35, estoque_max: 180 },
  { sku: "MEI-009", produto: "Meia Cano Longo", consumo: 45000, estoque_atual: 560, demanda_diaria: 3, estoque_min: 30, estoque_max: 100 },
  { sku: "CIN-010", produto: "Cinto Couro", consumo: 72000, estoque_atual: 45, demanda_diaria: 2, estoque_min: 10, estoque_max: 60 },
  { sku: "BLA-011", produto: "Blazer Slim", consumo: 165000, estoque_atual: 6, demanda_diaria: 4, estoque_min: 15,estoque_max: 80 },
  { sku: "VES-012", produto: "Vestido Floral", consumo: 220000, estoque_atual: 95, demanda_diaria: 8, estoque_min: 30, estoque_max: 150 },
  { sku: "SAI-013", produto: "Saia Plissada", consumo: 93000, estoque_atual: 28, demanda_diaria: 4, estoque_min: 18, estoque_max: 90 },
  { sku: "POL-014", produto: "Polo Clássica", consumo: 310000, estoque_atual: 115, demanda_diaria: 10, estoque_min: 50, estoque_max: 250 },
  { sku: "SHO-015", produto: "Shorts Tactel", consumo: 88000, estoque_atual: 3, demanda_diaria: 4, estoque_min: 15, estoque_max: 80 },
];

const totalConsumo = SKUS.reduce((s, p) => s + p.consumo, 0);

function classificarABC(pctAcum: number): CurvaABCItem["classificacao"] {
  if (pctAcum <= 80) return "A";
  if (pctAcum <= 95) return "B";
  return "C";
}

export function gerarCurvaABC(): CurvaABCItem[] {
  const sorted = [...SKUS].sort((a, b) => b.consumo - a.consumo);
  let acum = 0;
  return sorted.map(p => {
    const pct = (p.consumo / totalConsumo) * 100;
    acum += pct;
    return {
      sku: p.sku, produto: p.produto,
      valor_consumo: p.consumo,
      pct_individual: Math.round(pct * 100) / 100,
      pct_acumulado: Math.round(acum * 100) / 100,
      classificacao: classificarABC(acum),
      giro: Math.round((p.demanda_diaria * 30 / (p.estoque_atual || 1)) * 10) / 10,
      estoque_atual: p.estoque_atual,
      cobertura_dias: Math.round(p.estoque_atual / (p.demanda_diaria || 1)),
    };
  });
}

export function gerarIndicadoresGiro(): IndicadorGiro[] {
  return SKUS.map(p => {
    const saidas = p.demanda_diaria * 30;
    const giro = Math.round((saidas / (p.estoque_atual || 1)) * 10) / 10;
    const tendencia: "up" | "down" | "stable" = giro > 3 ? "up" : giro < 1 ? "down" : "stable";
    return {
      sku: p.sku, produto: p.produto,
      saidas_30d: Math.round(saidas),
      estoque_medio: Math.round(p.estoque_atual),
      giro,
      tendencia,
    };
  });
}

export function gerarIndicadoresRuptura(): IndicadorRuptura[] {
  return SKUS
    .filter(p => p.estoque_atual < p.estoque_min)
    .map(p => ({
      sku: p.sku, produto: p.produto,
      dias_ruptura: Math.floor(Math.random() * 7) + 1,
      vendas_perdidas_estimadas: Math.floor(Math.random() * 30) + 5,
      impacto_receita: Math.floor(Math.random() * 5000) + 500,
      ultimo_abastecimento: new Date(Date.now() - Math.random() * 15 * 86400000).toISOString().split("T")[0],
    }));
}

export function gerarIndicadoresCobertura(): IndicadorCobertura[] {
  return SKUS.map(p => {
    const cob = Math.round(p.estoque_atual / (p.demanda_diaria || 1));
    const status: IndicadorCobertura["status"] =
      cob > 60 ? "excesso" : cob < 3 ? "critico" : cob < 7 ? "baixo" : "normal";
    return {
      sku: p.sku, produto: p.produto,
      estoque_atual: p.estoque_atual,
      demanda_diaria_media: p.demanda_diaria,
      cobertura_dias: cob,
      estoque_minimo: p.estoque_min,
      estoque_maximo: p.estoque_max,
      status,
    };
  });
}

export const ABC_COLORS: Record<string, string> = {
  A: "bg-indigo-900/30 text-indigo-400",
  B: "bg-amber-900/30 text-amber-400",
  C: "bg-neutral-700 text-neutral-400",
};
