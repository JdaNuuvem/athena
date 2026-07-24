import { Metadata } from "next";
import AgentClientPage from "./client";

type Props = { params: Promise<{ id: string }> };

// ponytail: producao serve um export estatico — rotas dinamicas precisam de
// pelo menos um param conhecido em build-time. O id real e' lido em runtime
// no client (useParams); o Flask serve este mesmo HTML para qualquer
// /agents/<id-real> via fallback (ver serve_frontend).
export async function generateStaticParams() {
  return [{ id: "placeholder" }];
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  return { title: `Agente ${id} — Hermes` };
}

export default function Page({ params }: Props) {
  return <AgentClientPage />;
}
