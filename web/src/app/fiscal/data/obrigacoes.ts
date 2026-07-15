// Dados via Bling API
export async function getobrigacoesFiscais() {
  try {
    const r = await fetch("/api/bling/financeiro/notas-fiscais?limite=50");
    const d = await r.json();
    return d.data || [];
  } catch { return []; }
}
export const obrigacoesMockData: any[] = [];
