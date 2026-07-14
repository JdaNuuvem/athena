import type { VendaDiaria, VendaSemanal, VendaMensal, CategoriaVenda } from "../types";

export function gerarVendasDiarias(): VendaDiaria[] {
  return Array.from({ length: 30 }, (_, i) => {
    const base = 8000 + Math.sin(i / 5) * 2500;
    const variacao = (Math.random() - 0.5) * 2000;
    const custoRatio = 0.45 + Math.random() * 0.15;
    return {
      dia: String(i + 1).padStart(2, "0"),
      valor: Math.round(base + variacao),
      custo: Math.round((base + variacao) * custoRatio),
      margem: Math.round((1 - custoRatio) * 100),
    };
  });
}

export function gerarVendasSemanais(): VendaSemanal[] {
  const base = 65000;
  return Array.from({ length: 12 }, (_, i) => {
    const variacao = (Math.random() - 0.4) * 15000;
    const valor = Math.round(base + variacao);
    return {
      semana: `S${String(i + 1).padStart(2, "0")}`,
      valor,
      ticketMedio: Math.round(180 + Math.random() * 60),
      pedidos: Math.round(valor / (180 + Math.random() * 50)),
    };
  });
}

export function gerarVendasMensais(): VendaMensal[] {
  const meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
  const base = 280000;
  return meses.map((mes, i) => {
    const sazonalidade = 1 + Math.sin((i / 12) * Math.PI * 2) * 0.15;
    const tendencia = 1 + i * 0.02;
    const valor = Math.round(base * sazonalidade * tendencia * (0.9 + Math.random() * 0.2));
    return {
      mes,
      valor,
      custo: Math.round(valor * (0.5 + Math.random() * 0.15)),
      margem: Math.round(100 - (50 + Math.random() * 15)),
      variacaoPercent: Math.round((Math.random() - 0.2) * 20),
    };
  });
}

export function gerarCategorias(): CategoriaVenda[] {
  return [
    {
      categoria: "Utilidades Domésticas",
      valor: 87500,
      percentual: 31,
      produtos: [
        { nome: "Organizador MC-001", sku: "ORG-001", valor: 45300, qtd: 320, margem: 38.5 },
        { nome: "Kit Presente Luxo", sku: "KIT-012", valor: 29100, qtd: 145, margem: 28.3 },
        { nome: "Jogo de Copos Crystal", sku: "JGC-003", valor: 22400, qtd: 210, margem: 18.7 },
        { nome: "Porta Temperos Duplo", sku: "PTD-007", valor: 18700, qtd: 415, margem: 14.2 },
      ],
    },
    {
      categoria: "Bebidas e Térmicos",
      valor: 72300,
      percentual: 25,
      produtos: [
        { nome: "Garrafa Térmica Pro", sku: "GTP-001", valor: 38200, qtd: 280, margem: 42.1 },
        { nome: "Copo Térmico 500ml", sku: "CT5-002", valor: 21400, qtd: 350, margem: 35.4 },
        { nome: "Cooler Compacto", sku: "COL-005", valor: 12700, qtd: 180, margem: 22.8 },
      ],
    },
    {
      categoria: "Eletrônicos",
      valor: 54100,
      percentual: 19,
      produtos: [
        { nome: "Mini Projetor LED", sku: "MPL-001", valor: 28100, qtd: 95, margem: 15.3 },
        { nome: "Carregador Rápido", sku: "CRF-003", valor: 16800, qtd: 520, margem: 28.7 },
        { nome: "Fone Bluetooth", sku: "FBT-002", valor: 9200, qtd: 340, margem: 31.2 },
      ],
    },
    {
      categoria: "Decoração",
      valor: 42300,
      percentual: 15,
      produtos: [
        { nome: "Vaso Decorativo", sku: "VAS-001", valor: 15300, qtd: 210, margem: 45.0 },
        { nome: "Quadro Abstrato", sku: "QAB-003", valor: 11200, qtd: 140, margem: 52.1 },
        { nome: "Cortina Blackout", sku: "CBL-002", valor: 15800, qtd: 180, margem: 33.5 },
      ],
    },
    {
      categoria: "Pet",
      valor: 28900,
      percentual: 10,
      produtos: [
        { nome: "Cama Pet Premium", sku: "CPP-001", valor: 12400, qtd: 150, margem: 40.2 },
        { nome: "Comedouro Automático", sku: "CAT-002", valor: 9800, qtd: 95, margem: 35.8 },
        { nome: "Arranhador Torre", sku: "ATR-001", valor: 6700, qtd: 110, margem: 38.1 },
      ],
    },
  ];
}
