"use client";

function toISO(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function inicioDaSemana(d: Date): Date {
  const dia = d.getDay(); // 0=domingo
  const diff = d.getDate() - dia;
  return new Date(d.getFullYear(), d.getMonth(), diff);
}

const ATALHOS: { label: string; calcular: () => { inicio: string; fim: string } }[] = [
  {
    label: "Hoje",
    calcular: () => {
      const hoje = new Date();
      return { inicio: toISO(hoje), fim: toISO(hoje) };
    },
  },
  {
    label: "Esta semana",
    calcular: () => {
      const hoje = new Date();
      return { inicio: toISO(inicioDaSemana(hoje)), fim: toISO(hoje) };
    },
  },
  {
    label: "Este mês",
    calcular: () => {
      const hoje = new Date();
      return { inicio: toISO(new Date(hoje.getFullYear(), hoje.getMonth(), 1)), fim: toISO(hoje) };
    },
  },
  {
    label: "Últimos 30 dias",
    calcular: () => {
      const hoje = new Date();
      const inicio = new Date(hoje);
      inicio.setDate(inicio.getDate() - 30);
      return { inicio: toISO(inicio), fim: toISO(hoje) };
    },
  },
];

export default function DateRangePicker({
  dataInicio,
  dataFim,
  onChange,
}: {
  dataInicio: string;
  dataFim: string;
  onChange: (inicio: string, fim: string) => void;
}) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <input
        type="date"
        value={dataInicio}
        max={dataFim || undefined}
        onChange={(e) => onChange(e.target.value, dataFim)}
        className="text-xs rounded-lg px-2 py-1.5 bg-neutral-800 border border-neutral-700 text-neutral-300"
        aria-label="Data início"
      />
      <span className="text-xs" style={{ color: "var(--ink-700)" }}>até</span>
      <input
        type="date"
        value={dataFim}
        min={dataInicio || undefined}
        onChange={(e) => onChange(dataInicio, e.target.value)}
        className="text-xs rounded-lg px-2 py-1.5 bg-neutral-800 border border-neutral-700 text-neutral-300"
        aria-label="Data fim"
      />
      <div className="flex items-center gap-1 flex-wrap">
        {ATALHOS.map((atalho) => (
          <button
            key={atalho.label}
            type="button"
            onClick={() => {
              const { inicio, fim } = atalho.calcular();
              onChange(inicio, fim);
            }}
            className="text-[11px] px-2 py-1 rounded-full bg-neutral-800 border border-neutral-700 text-neutral-400 hover:text-neutral-200 hover:border-neutral-600 transition-colors"
          >
            {atalho.label}
          </button>
        ))}
      </div>
    </div>
  );
}
