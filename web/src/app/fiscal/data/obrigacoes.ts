import type { Obrigacao } from "../types";

export const OBRIGACOES_MOCK: Obrigacao[] = [
  {
    id: 1,
    nome: "SPED Fiscal",
    descricao: "Escrituração Fiscal Digital - ICMS/IPI",
    ultimaEntrega: "20/06/2026",
    proximoVencimento: "20/07/2026",
    periodicidade: "Mensal",
    status: "pendente",
  },
  {
    id: 2,
    nome: "SINTEGRA",
    descricao: "Sistema Integrado de Informações sobre Operações Interestaduais",
    ultimaEntrega: "15/06/2026",
    proximoVencimento: "15/07/2026",
    periodicidade: "Mensal",
    status: "andamento",
  },
  {
    id: 3,
    nome: "GNRE",
    descricao: "Guia Nacional de Recolhimento de Tributos Estaduais",
    ultimaEntrega: "10/06/2026",
    proximoVencimento: "10/07/2026",
    periodicidade: "Por operação",
    status: "entregue",
  },
];
