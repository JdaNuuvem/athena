import type { Column } from "@/lib/types/ui";

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyExtractor: (item: T) => string | number;
  emptyMessage?: string;
  countLabel?: string;
}

export default function DataTable<T>({
  columns,
  data,
  keyExtractor,
  emptyMessage = "Nenhum registro",
  countLabel,
}: DataTableProps<T>) {
  if (data.length === 0) {
    return (
      <div className="bg-neutral-800 border border-neutral-700 rounded-lg p-8 text-center">
        <p className="text-neutral-400 text-sm">{emptyMessage}</p>
      </div>
    );
  }

  const alignClass = (a?: string) => a === "center" ? "text-center" : a === "right" ? "text-right" : "text-left";

  return (
    <div className="space-y-1">
      {countLabel && <div className="text-xs text-neutral-500">{countLabel}</div>}
      <div className="bg-neutral-800 border border-neutral-700 rounded-lg overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-neutral-700 text-neutral-400 bg-neutral-850">
              {columns.map(col => (
                <th key={col.key} className={`p-3 ${alignClass(col.align)}`}>
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr
                key={keyExtractor(row)}
                className={`border-b border-neutral-700/50 ${i % 2 === 0 ? "bg-neutral-800" : "bg-neutral-800/50"}`}
              >
                {columns.map(col => {
                  const value = (row as Record<string, unknown>)[col.key];
                  return (
                    <td key={col.key} className={`p-3 ${alignClass(col.align)}`}>
                      {col.render ? col.render(value, row, i) : String(value ?? "—")}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
