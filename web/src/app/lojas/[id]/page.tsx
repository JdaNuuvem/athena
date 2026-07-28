import LojaClientPage from "./client";

// producao serve um export estatico (output: 'export') — rotas dinamicas
// precisam de pelo menos um param conhecido em build-time. O id real e'
// lido em runtime no client (useParams); o Flask serve este mesmo HTML pra
// qualquer /lojas/<id-real> via fallback (ver serve_frontend), mesmo padrao
// de web/src/app/produtos/[sku]/page.tsx.
export async function generateStaticParams() {
  return [{ id: "placeholder" }];
}

export default function LojaPage() {
  return <LojaClientPage />;
}
