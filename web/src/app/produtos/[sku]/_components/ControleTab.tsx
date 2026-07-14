"use client";

const depositosMock = [
  { deposito: "Matriz", estoqueAtual: 234, estoqueMin: 50, estoqueMax: 500, pontoReposicao: 100, loteEconomico: 200, leadTime: 7, fornecedor: "Plásticos Sul Ltda", status: "Ativo" },
  { deposito: "Filial Centro", estoqueAtual: 8, estoqueMin: 20, estoqueMax: 150, pontoReposicao: 40, loteEconomico: 100, leadTime: 5, fornecedor: "Plásticos Sul Ltda", status: "Crítico" },
  { deposito: "Filial Norte", estoqueAtual: 95, estoqueMin: 30, estoqueMax: 200, pontoReposicao: 60, loteEconomico: 80, leadTime: 10, fornecedor: "Distribuidora Norte", status: "Ativo" },
];

function Badge({ label, color }: { label: string; color: string }) {
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${color}`}>{label}</span>;
}

function ProgressBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div className="w-full bg-neutral-800 rounded-full h-2 overflow-hidden">
      <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function SugestaoReposicao({ atual, ponto, lote }: { atual: number; ponto: number; lote: number }) {
  if (atual >= ponto) return <span className="text-xs text-green-400">Estoque adequado</span>;
  const necessario = ponto - atual + lote;
  return <span className="text-xs text-amber-400">Comprar ~{necessario} un</span>;
}

export default function ControleTab() {
  return (
    <div className="space-y-6">
      {depositosMock.map((d) => {
        const barColor = d.estoqueAtual <= d.estoqueMin ? "bg-red-500" : d.estoqueAtual <= d.pontoReposicao ? "bg-amber-500" : "bg-green-500";
        return (
          <div key={d.deposito} className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-medium text-neutral-200">{d.deposito}</h3>
                <p className="text-xs text-neutral-500">Fornecedor: {d.fornecedor}</p>
              </div>
              <Badge label={d.status} color={d.status === "Ativo" ? "bg-green-900/50 text-green-400" : "bg-red-900/50 text-red-400"} />
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-neutral-500">Estoque Atual</span>
                <span className={`numeric font-medium ${d.estoqueAtual <= d.estoqueMin ? "text-red-400" : d.estoqueAtual <= d.pontoReposicao ? "text-amber-400" : "text-green-400"}`}>
                  {d.estoqueAtual} / {d.estoqueMax} un
                </span>
              </div>
              <ProgressBar value={d.estoqueAtual} max={d.estoqueMax} color={barColor} />
            </div>

            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
              <div className="bg-neutral-800/50 rounded-lg p-2.5">
                <p className="text-[10px] text-neutral-500 uppercase tracking-wider">Estoque Mínimo</p>
                <p className="text-sm text-red-400 numeric font-medium">{d.estoqueMin}</p>
              </div>
              <div className="bg-neutral-800/50 rounded-lg p-2.5">
                <p className="text-[10px] text-neutral-500 uppercase tracking-wider">Estoque Máximo</p>
                <p className="text-sm text-neutral-200 numeric font-medium">{d.estoqueMax}</p>
              </div>
              <div className="bg-neutral-800/50 rounded-lg p-2.5">
                <p className="text-[10px] text-neutral-500 uppercase tracking-wider">Ponto Reposição</p>
                <p className="text-sm text-neutral-200 numeric font-medium">{d.pontoReposicao}</p>
              </div>
              <div className="bg-neutral-800/50 rounded-lg p-2.5">
                <p className="text-[10px] text-neutral-500 uppercase tracking-wider">Lote Econômico</p>
                <p className="text-sm text-neutral-200 numeric font-medium">{d.loteEconomico}</p>
              </div>
              <div className="bg-neutral-800/50 rounded-lg p-2.5">
                <p className="text-[10px] text-neutral-500 uppercase tracking-wider">Lead Time</p>
                <p className="text-sm text-neutral-200 numeric font-medium">{d.leadTime} dias</p>
              </div>
              <div className="bg-neutral-800/50 rounded-lg p-2.5">
                <p className="text-[10px] text-neutral-500 uppercase tracking-wider">Sugestão</p>
                <SugestaoReposicao atual={d.estoqueAtual} ponto={d.pontoReposicao} lote={d.loteEconomico} />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
