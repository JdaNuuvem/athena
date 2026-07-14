import type { NotaFiscal } from "../types";

export function gerarNotasMock(quantidade = 25): NotaFiscal[] {
  const tipos = ["NF-e", "NFC-e", "NFS-e", "CT-e", "MDF-e"];
  return Array.from({ length: quantidade }, (_, i) => {
    const tipo = tipos[i % 5];
    const dia = 28 - (i % 28);
    return {
      id: 1000 + i,
      numero:
        tipo === "NF-e" ? `55${String(100000 + i)}` :
        tipo === "NFC-e" ? `65${String(200000 + i)}` :
        tipo === "CT-e" ? `57${String(300000 + i)}` :
        tipo === "MDF-e" ? `58${String(400000 + i)}` :
        `NFS-e-${i + 1}`,
      dataEmissao: `2026-07-${String(dia).padStart(2, "0")}`,
      dataOperacao: `2026-07-${String(dia).padStart(2, "0")}`,
      contato: { nome: `Cliente ${i + 1}`, numeroDocumento: `${String(10000000000 + i * 13)}` },
      situacao: i % 7 === 0 ? 2 : i % 11 === 0 ? 3 : 1,
      tipo: tipo.startsWith("NF") ? 0 : 1,
      chaveAcesso: `3520${String(100000000000000 + i * 7)}5500100${String(i).padStart(8, "0")}`,
      loja: { id: 1 },
      naturezaOperacao: { id: 1 },
      valorNota: parseFloat((150 + Math.random() * 5000).toFixed(2)),
      total: parseFloat((150 + Math.random() * 5000).toFixed(2)),
    };
  });
}
