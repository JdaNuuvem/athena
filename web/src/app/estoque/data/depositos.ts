import type { Deposito } from "@/lib/types/domain";

export const DEPOSITOS_MOCK: Deposito[] = [
  { id: 1, codigo: "CD-01", nome: "CD Central", tipo: "proprio", loja: "Matriz", endereco: { rua: "Av. Principal, 1000", predio: "A", corredor: "01-05", estante: "A1-D10" }, ativo: true },
  { id: 2, codigo: "LJ-01", nome: "Loja Centro", tipo: "proprio", loja: "Loja Centro", endereco: { rua: "Rua do Comércio, 200", corredor: "Térreo", estante: "E1-E8" }, ativo: true },
  { id: 3, codigo: "LJ-02", nome: "Loja Norte Shopping", tipo: "proprio", loja: "Loja Norte", endereco: { rua: "Av. Norte Sul, 500", predio: "Shopping", corredor: "2º Piso", estante: "F1-F6" }, ativo: true },
  { id: 4, codigo: "EC-01", nome: "E-commerce", tipo: "virtual", ativo: true },
  { id: 5, codigo: "MP-01", nome: "Marketplace", tipo: "virtual", ativo: true },
  { id: 6, codigo: "DS-01", nome: "Dropshipping Fornecedor A", tipo: "terceiro", ativo: true },
  { id: 7, codigo: "CD-02", nome: "Cross Docking", tipo: "proprio", endereco: { rua: "Rodovia BR 101, km 25", predio: "Galpão 3" }, ativo: false },
  { id: 8, codigo: "LJ-03", nome: "Outlet", tipo: "proprio", loja: "Outlet", endereco: { rua: "Estrada Velha, 80", corredor: "Piso 1", estante: "G1-G4" }, ativo: true },
];

export function totaisPorDeposito() {
  return DEPOSITOS_MOCK.filter(d => d.ativo).map(d => ({
    ...d,
    total_skus: Math.floor(Math.random() * 500) + 50,
    valor_estoque: Math.floor(Math.random() * 500000) + 50000,
    itens_baixo_estoque: Math.floor(Math.random() * 20),
  }));
}
