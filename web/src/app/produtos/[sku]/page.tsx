import ProdutoClientPage from "./client";

// ponytail: producao serve um export estatico (output: 'export') — rotas
// dinamicas precisam de pelo menos um param conhecido em build-time. O SKU
// real e' lido em runtime no client (useParams), entao o valor aqui e' so'
// um placeholder para satisfazer o build; o Flask serve este mesmo HTML para
// qualquer /produtos/<sku-real> via fallback (ver serve_frontend).
export async function generateStaticParams() {
  return [{ sku: "placeholder" }];
}

export default function ProdutoPage() {
  return <ProdutoClientPage />;
}
