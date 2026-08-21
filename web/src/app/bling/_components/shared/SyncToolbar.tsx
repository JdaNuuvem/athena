interface SyncToolbarProps {
  onSync: () => void;
  sincronizando?: boolean;
  label?: string;
  total?: number;
  unidade?: string;
  children?: React.ReactNode;
}

export default function SyncToolbar({
  onSync,
  sincronizando = false,
  label = "Sincronizar",
  total,
  unidade = "registros",
  children,
}: SyncToolbarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        onClick={onSync}
        disabled={sincronizando}
        className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 text-white text-xs rounded-lg hover:bg-indigo-500 transition-colors disabled:opacity-50"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
          <path d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
        </svg>
        {sincronizando ? "Sincronizando..." : label}
      </button>
      {children}
      {typeof total === "number" && (
        <span className="text-xs text-neutral-500 ml-auto">
          {total} {unidade}
        </span>
      )}
    </div>
  );
}
