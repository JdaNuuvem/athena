// Dados reais via API
export async function getForecastData() {
  try {
    const r = await fetch("/api/relatorios/previsao?dias=60");
    const d = await r.json();
    return { media_diaria: d.media_diaria || 0, previsao_30d: d.previsao_30d || 0 };
  } catch { return { media_diaria: 0, previsao_30d: 0 }; }
}

export function gerarForecast() {
  return Array.from({ length: 30 }, (_, i) => ({ periodo: String(i + 1).padStart(2, "0") + "/07" }));
}

export const FORECAST_RESUMO = {
  receitaProjetada: 0, crescimentoEsperado: 0, confianca: 0,
  cenarios: { otimista: 0, esperado: 0, pessimista: 0 }, fatores: [],
} as any;
