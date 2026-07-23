export interface SearchResult { id: number; codigo: string; nome: string; preco: number; estoque_atual?: number; situacao: string; }
export interface CartItem { codigo: string; descricao: string; quantidade: number; valor_unitario: number; desconto: number; }
export interface Operador { id: number; nome: string; role: string; desconto_maximo_percent: number; }
export const FORMAS = ["dinheiro", "pix", "cartao_credito", "cartao_debito", "vale", "voucher", "crediario"];
