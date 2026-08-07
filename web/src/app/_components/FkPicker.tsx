"use client";

import { useState, useEffect, useRef } from "react";
import { api } from "@/lib/api";

interface FkPickerProps {
  tabela: string;
  labelField?: string;
  value: string;
  onChange: (id: string) => void;
  placeholder?: string;
}

// Autocomplete pra campos de chave estrangeira (ex.: cliente_id em
// cad_cliente_enderecos) — antes eram inputs numericos crus, exigindo que o
// usuario soubesse o ID de cor. Aqui ele busca por nome e o ID vai junto
// por baixo dos panos.
export default function FkPicker({ tabela, labelField = "nome", value, onChange, placeholder }: FkPickerProps) {
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<Record<string, unknown>[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [resolvedLabel, setResolvedLabel] = useState<string | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancel = false;
    if (!value) { setResolvedLabel(null); return; }
    api.cadGet(tabela, Number(value))
      .then(r => {
        if (cancel) return;
        const label = r && !("error" in r) ? String(r[labelField] ?? `#${value}`) : `#${value}`;
        setResolvedLabel(label);
      })
      .catch(() => { if (!cancel) setResolvedLabel(`#${value}`); });
    return () => { cancel = true; };
  }, [tabela, value, labelField]);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    const t = setTimeout(async () => {
      try {
        const r = await api.cadListPaginado(tabela, 1, 8, query || undefined);
        setOptions((r.data || []) as Record<string, unknown>[]);
      } catch { setOptions([]); }
      finally { setLoading(false); }
    }, 300);
    return () => clearTimeout(t);
  }, [tabela, query, open]);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  return (
    <div ref={boxRef} className="relative">
      <input
        type="text"
        value={open ? query : (resolvedLabel ?? (value ? `#${value}` : ""))}
        onFocus={() => { setOpen(true); setQuery(""); }}
        onChange={e => setQuery(e.target.value)}
        placeholder={placeholder ?? "Buscar por nome..."}
        className="w-full rounded-lg border border-neutral-600 bg-neutral-700 px-3 py-2 text-xs text-neutral-200 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500/50"
      />
      {open && (
        <div className="absolute z-10 mt-1 max-h-52 w-full overflow-y-auto rounded-lg border border-neutral-600 bg-neutral-800 shadow-xl">
          {loading ? (
            <div className="px-3 py-2 text-[11px] text-neutral-500">Buscando...</div>
          ) : options.length === 0 ? (
            <div className="px-3 py-2 text-[11px] text-neutral-500">Nenhum resultado</div>
          ) : options.map(o => (
            <button
              key={String(o.id)}
              type="button"
              onMouseDown={e => e.preventDefault()}
              onClick={() => { onChange(String(o.id)); setResolvedLabel(String(o[labelField] ?? `#${o.id}`)); setOpen(false); }}
              className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-xs text-neutral-200 hover:bg-indigo-600/20"
            >
              <span className="truncate">{String(o[labelField] ?? `#${o.id}`)}</span>
              <span className="shrink-0 text-neutral-500">#{String(o.id)}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
