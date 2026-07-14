import type { MovimentacaoEstoque } from "@/lib/types/domain";

const RESPONSAVEIS = ["João Silva", "Maria Santos", "Carlos Oliveira", "Ana Costa"];
const DEPOSITOS = ["CD Central", "Loja Centro", "Loja Norte", "E-commerce"];
const SKUS = [
  { sku: "CAM-001", nome: "Camiseta Basic" },
  { sku: "CAL-002", nome: "Calça Jeans" },
  { sku: "TEN-003", nome: "Tênis Runner" },
  { sku: "MOC-004", nome: "Mochila Escolar" },
  { sku: "BON-005", nome: "Boné Trucker" },
  { sku: "JAI-006", nome: "Jaqueta Corta-Vento" },
  { sku: "REG-007", nome: "Regata Esportiva" },
  { sku: "BER-008", nome: "Bermuda Sarja" },
  { sku: "MEI-009", nome: "Meia Cano Longo" },
  { sku: "CIN-010", nome: "Cinto Couro" },
];

function pick<T>(arr: T[]): T { return arr[Math.floor(Math.random() * arr.length)]; }

function recentDate(daysBack: number): string {
  const d = new Date();
  d.setDate(d.getDate() - Math.floor(Math.random() * daysBack));
  return d.toISOString().split("T")[0];
}

export function gerarMovimentacoes(count = 80): MovimentacaoEstoque[] {
  const tipos: MovimentacaoEstoque["tipo"][] = [
    "entrada", "saida", "transferencia", "ajuste", "perda",
    "inventario", "producao", "consumo", "devolucao", "troca",
    "reserva", "separacao", "expedicao",
  ];

  return Array.from({ length: count }, (_, i) => {
    const tipo = pick(tipos);
    const prod = pick(SKUS);
    const qtd = tipo === "entrada" ? Math.floor(Math.random() * 200) + 10 :
                tipo === "perda" ? -(Math.floor(Math.random() * 5) + 1) :
                tipo === "saida" || tipo === "consumo" ? -(Math.floor(Math.random() * 20) + 1) :
                Math.floor(Math.random() * 50) + 1;
    const custo = parseFloat((Math.random() * 150 + 10).toFixed(2));

    return {
      id: i + 1,
      tipo,
      sku: prod.sku,
      produto: prod.nome,
      quantidade: qtd,
      deposito_origem: tipo === "transferencia" || tipo === "saida" ? pick(DEPOSITOS) : undefined,
      deposito_destino: tipo === "transferencia" || tipo === "entrada" ? pick(DEPOSITOS) : undefined,
      documento: Math.random() > 0.4 ? `NF-${String(1000 + i).padStart(4, "0")}` : undefined,
      motivo: Math.random() > 0.5 ? pick(["Reposição", "Venda", "Devolução cliente", "Ajuste inventário", "Quebra", "Produção interna"]) : undefined,
      responsavel: pick(RESPONSAVEIS),
      data: recentDate(60),
      custo_unitario: tipo !== "transferencia" ? custo : undefined,
      custo_total: tipo !== "transferencia" ? Math.abs(qtd) * custo : undefined,
    };
  });
}
