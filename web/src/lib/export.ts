// Exportação genérica CSV/XLSX/PDF a partir de colunas+linhas já formatadas
// (strings prontas pra exibição — quem chama já aplicou fmtBRL/fmtDataBR).
// CSV usa Blob puro (mesmo padrão já usado em CrudPanel.tsx, sem lib). XLSX
// usa exceljs (não xlsx/sheetjs — esse tem prototype pollution + ReDoS sem
// correção disponível no pacote npm). PDF usa jspdf + jspdf-autotable.

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function exportarCSV(columns: string[], rows: (string | number)[][], filename: string) {
  const escapar = (v: unknown) => {
    const s = String(v ?? "");
    return /[",;\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const linhas = [columns.map(escapar).join(";"), ...rows.map(row => row.map(escapar).join(";"))];
  const csv = "﻿" + linhas.join("\r\n");
  downloadBlob(new Blob([csv], { type: "text/csv;charset=utf-8;" }), `${filename}.csv`);
}

export async function exportarXLSX(columns: string[], rows: (string | number)[][], filename: string) {
  const ExcelJS = (await import("exceljs")).default;
  const wb = new ExcelJS.Workbook();
  const ws = wb.addWorksheet("Dados");
  const headerRow = ws.addRow(columns);
  headerRow.font = { bold: true };
  rows.forEach(r => ws.addRow(r));
  ws.columns.forEach(col => { col.width = 18; });
  const buffer = await wb.xlsx.writeBuffer();
  downloadBlob(
    new Blob([buffer], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }),
    `${filename}.xlsx`);
}

export async function exportarPDF(columns: string[], rows: (string | number)[][], filename: string, title?: string) {
  const { default: jsPDF } = await import("jspdf");
  const autoTable = (await import("jspdf-autotable")).default;
  const doc = new jsPDF({ orientation: columns.length > 6 ? "landscape" : "portrait" });
  if (title) {
    doc.setFontSize(13);
    doc.text(title, 14, 15);
  }
  autoTable(doc, {
    head: [columns],
    body: rows,
    startY: title ? 20 : 10,
    styles: { fontSize: 8 },
    headStyles: { fillColor: [79, 70, 229] },
  });
  doc.save(`${filename}.pdf`);
}
