import { Metadata } from "next";
import AgentClientPage from "./client";

type Props = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  return { title: `Agente ${id} — Hermes` };
}

export default function Page({ params }: Props) {
  return <AgentClientPage />;
}
