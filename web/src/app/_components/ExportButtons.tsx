"use client";

import Icon from "./Icon";
import { exportarCSV, exportarXLSX, exportarPDF } from "@/lib/export";

interface ExportButtonsProps {
  columns: string[];
  rows: (string | number)[][];
  filename: string;
  title?: string;
}

export default function ExportButtons({ columns, rows, filename, title }: ExportButtonsProps) {
  if (rows.length === 0) return null;
  return (
    <div className="flex items-center gap-1.5">
      <button onClick={() => exportarCSV(columns, rows, filename)} title="Exportar CSV" className="flex items-center gap-1.5 rounded-lg border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs font-medium text-neutral-300 transition-colors hover:bg-neutral-700">
        <Icon name="download" size={13} /> CSV
      </button>
      <button onClick={() => exportarXLSX(columns, rows, filename)} title="Exportar XLSX" className="flex items-center gap-1.5 rounded-lg border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs font-medium text-neutral-300 transition-colors hover:bg-neutral-700">
        <Icon name="download" size={13} /> XLSX
      </button>
      <button onClick={() => exportarPDF(columns, rows, filename, title)} title="Exportar PDF" className="flex items-center gap-1.5 rounded-lg border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-xs font-medium text-neutral-300 transition-colors hover:bg-neutral-700">
        <Icon name="download" size={13} /> PDF
      </button>
    </div>
  );
}
