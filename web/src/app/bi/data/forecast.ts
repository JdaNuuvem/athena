import type { ForecastDataPoint } from "../types";

export function gerarForecast(diasHistoricos = 60, diasProjecao = 30): ForecastDataPoint[] {
  const pontos: ForecastDataPoint[] = [];
  const base = 8500;
  const tendencia = 35;
  const sazonalidadeAmp = 1200;
  const periodo = 7;

  // Historical
  for (let i = 0; i < diasHistoricos; i++) {
    const day = diasHistoricos - i;
    const t = i;
    const sazonal = Math.sin((t / periodo) * Math.PI * 2) * sazonalidadeAmp;
    const noise = (Math.random() - 0.5) * 800;
    const valor = base + t * tendencia + sazonal + noise;
    pontos.unshift({
      periodo: `D-${day}`,
      historico: Math.round(Math.max(0, valor)),
    });
  }

  // Projection
  for (let i = 0; i < diasProjecao; i++) {
    const t = diasHistoricos + i;
    const sazonal = Math.sin((t / periodo) * Math.PI * 2) * sazonalidadeAmp;
    const valor = base + t * tendencia + sazonal;
    const width = 600 + i * 25;
    pontos.push({
      periodo: `D+${i + 1}`,
      historico: i === 0 ? Math.round(base + (diasHistoricos - 1) * tendencia + Math.sin((diasHistoricos - 1) / periodo * Math.PI * 2) * sazonalidadeAmp) : 0,
      previsao: i === 0 ? undefined : Math.round(valor),
      limiteInferior: i === 0 ? undefined : Math.round(valor - width),
      limiteSuperior: i === 0 ? undefined : Math.round(valor + width),
    });
  }

  return pontos;
}

export const FORECAST_RESUMO = {
  receitaProjetada: 312450.00,
  crescimentoEsperado: 8.7,
  confianca: 92,
  cenarios: {
    otimista: 348200.00,
    esperado: 312450.00,
    pessimista: 274800.00,
  },
  fatores: [
    { nome: "Sazonalidade", impacto: "positivo", valor: "+4.2%" },
    { nome: "Tendência de Mercado", impacto: "positivo", valor: "+3.5%" },
    { nome: "Inflação", impacto: "negativo", valor: "-1.3%" },
    { nome: "Concorrência", impacto: "neutro", valor: "0%" },
  ],
};
