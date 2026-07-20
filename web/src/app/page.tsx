import { redirect } from "next/navigation";

// A Shopee redireciona para o dominio raiz apos a autorizacao (?code=...&shop_id=...)
// quando o Redirect URL cadastrado no Console e' so o dominio, sem o path do callback.
// Encaminha esses parametros para a rota real de troca de token em vez de derruba-los
// no redirect padrao para /dashboard.
export default async function Home({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  if (params.code) {
    const qs = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (typeof value === "string") qs.set(key, value);
    }
    redirect(`/api/shopee/callback?${qs.toString()}`);
  }
  redirect("/dashboard");
}
