import { Metadata } from "next";
import AgentClientPage from "./client";

export function generateStaticParams() {
  return [{ id: "index" }];
}

export const metadata: Metadata = { title: "Agente — Hermes" };

export default function Page() {
  return <AgentClientPage />;
}
