import { Metadata } from "next";
import ProdutoClientPage from "./client";

export function generateStaticParams() {
  return [{ sku: "index" }];
}

type Props = { params: Promise<{ sku: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { sku } = await params;
  return { title: sku + " — Hermes" };
}

export default function Page({ params }: Props) {
  return <ProdutoClientPage />;
}
