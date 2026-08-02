import TicketDetalheClient from "./client";

// producao serve export estatico (output: 'export') — rotas dinamicas
// precisam de pelo menos um param conhecido em build-time. O id real e'
// lido em runtime no client (usePathname), mesmo padrao de /lojas/[id].
export async function generateStaticParams() {
  return [{ id: "placeholder" }];
}

export default function TicketDetalhePage() {
  return <TicketDetalheClient />;
}
