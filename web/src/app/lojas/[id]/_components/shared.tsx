"use client";

export function InputGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="text-[10px] text-neutral-500 uppercase tracking-wider">{label}</label>
      {children}
    </div>
  );
}

export function Section({ title, children, onSave, saving, msg }: {
  title: string;
  children: React.ReactNode;
  onSave?: () => void;
  saving?: boolean;
  msg?: string;
}) {
  return (
    <fieldset className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 space-y-4">
      <div className="flex items-center justify-between px-1">
        <legend className="text-sm font-medium text-neutral-300">{title}</legend>
        {onSave && (
          <div className="flex items-center gap-2">
            {msg && <span className="text-xs text-emerald-400">{msg}</span>}
            <button
              onClick={onSave}
              disabled={saving}
              className="px-3 py-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs rounded-lg"
            >
              {saving ? "Salvando..." : "Salvar"}
            </button>
          </div>
        )}
      </div>
      {children}
    </fieldset>
  );
}

export function TextField({ label, value, onChange, placeholder, type = "text" }: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <InputGroup label={label}>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500"
      />
    </InputGroup>
  );
}

export function TextAreaField({ label, value, onChange, rows = 3 }: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  rows?: number;
}) {
  return (
    <InputGroup label={label}>
      <textarea
        rows={rows}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500"
      />
    </InputGroup>
  );
}

export function SelectField({ label, value, onChange, options }: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <InputGroup label={label}>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </InputGroup>
  );
}

export function CheckboxField({ label, checked, onChange }: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-xs text-neutral-300 cursor-pointer">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="rounded border-neutral-700 bg-neutral-800"
      />
      {label}
    </label>
  );
}

export function strVal(loja: Record<string, unknown> | null, campo: string): string {
  const v = loja?.[campo];
  if (v === null || v === undefined) return "";
  return String(v);
}
