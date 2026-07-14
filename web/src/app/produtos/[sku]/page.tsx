import { Metadata } from "next";
import ProdutoClientPage from "./client";

export function generateStaticParams() {
  return [{ sku: "index" }];
}

export const metadata: Metadata = { title: "Produto — Hermes" };

export default function Page() {
  return <ProdutoClientPage />;
}
