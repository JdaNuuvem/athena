"use client";

import { useState } from "react";

export type DateFilterValue = { data_inicio?: string; data_fim?: string; dias?: number };

interface DateFilterProps {
  value: DateFilterValue;
  onChange: (v: DateFilterValue) => void;
  dateField?: string;
}

export default function DateFilter({ value, onChange, dateField }: DateFilterProps) {
  const [mode, setMode] = useState<"preset" | "custom">("preset");

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={() => setMode(m => m === "preset" ? "custom" : "preset")}
        className="text-[10px] text-neutral-500 hover:text-neutral-300 px-1"
        title={mode === "preset" ? "Intervalo personalizado" : "Período rápido"}
      >
        {mode === "preset" ? "📅" : "⚡"}
      </button>
      {mode === "preset" ? (
        <select
          value={value.dias ?? 30}
          onChange={e => onChange({ dias: Number(e.target.value) })}
          className="bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200"
        >
          {[7, 15, 30, 60, 90].map(d => <option key={d} value={d}>Últimos {d} dias</option>)}
        </select>
      ) : (
        <div className="flex items-center gap-1.5">
          <input
            type="date"
            value={value.data_inicio ?? ""}
            onChange={e => onChange({ ...value, data_inicio: e.target.value, dias: undefined })}
            className="bg-neutral-800 border border-neutral-700 rounded px-1.5 py-1 text-xs text-neutral-200 w-[130px] [color-scheme:dark]"
          />
          <span className="text-xs text-neutral-500">até</span>
          <input
            type="date"
            value={value.data_fim ?? ""}
            onChange={e => onChange({ ...value, data_fim: e.target.value, dias: undefined })}
            className="bg-neutral-800 border border-neutral-700 rounded px-1.5 py-1 text-xs text-neutral-200 w-[130px] [color-scheme:dark]"
          />
          {(value.data_inicio || value.data_fim) && (
            <button
              onClick={() => onChange({})}
              className="text-[10px] text-red-400 hover:text-red-300 px-1"
              title="Limpar datas"
            >✕</button>
          )}
        </div>
      )}
    </div>
  );
}
